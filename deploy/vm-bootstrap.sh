#!/usr/bin/env bash
# KPI Operations — VM host bootstrap (PR-4).
# Prepares a fresh Ubuntu host for the docker-compose.prod.yml stack:
#   phase 1  sanity checks (read-only; fatal on low disk / case-insensitive FS)
#   phase 2  docker install (guarded no-op when docker + compose exist)
#   phase 3  docker group membership (re-login required to take effect)
#   phase 4  ufw firewall — deny-incoming + allows 22 443 80 7070 5443 3389,
#            enable LAST and only after the 22/tcp rule is verified (anti-lockout)
#   phase 5  data root (preflight + init-data-root; --chown deferred to deploy)
#   phase 6  app checkout + .env scaffold (secrets generated, never echoed)
#
# EVERY privileged command is printed and individually confirmed (y/N);
# declining a gate SKIPS that action and continues.
#
# Usage:
#   vm-bootstrap.sh [--root DIR] [--app-dir DIR] [--ip ADDR]
#   vm-bootstrap.sh --print-config           # resolved config, no actions
#   vm-bootstrap.sh --scaffold-env-only DIR  # only write DIR/.env (test seam)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT=/opt/kpi-operations
APP_DIR=""
HOST_IP=192.168.2.234
REPO_URL=https://github.com/ccmanuelf/kpi-operations.git
PRINT_CONFIG=0
SCAFFOLD_ONLY=""

while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:?missing value for $1}"; shift 2 ;;
    --app-dir) APP_DIR="${2:?missing value for $1}"; shift 2 ;;
    --ip) HOST_IP="${2:?missing value for $1}"; shift 2 ;;
    --print-config) PRINT_CONFIG=1; shift ;;
    --scaffold-env-only) SCAFFOLD_ONLY="${2:?missing value for $1}"; shift 2 ;;
    -h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
  esac
done
[ -z "$APP_DIR" ] && APP_DIR="$ROOT/app"

if [ "$PRINT_CONFIG" -eq 1 ]; then
  echo "ROOT=$ROOT"; echo "APP_DIR=$APP_DIR"; echo "IP=$HOST_IP"
  exit 0
fi

confirm() { # confirm <description> — y/N gate; default No; decline returns 1
  printf '\n>> %s\n' "$1"
  read -r -p "   proceed? [y/N] " reply
  case "$reply" in
    y|Y|yes|YES) return 0 ;;
    *) echo "   skipped."; return 1 ;;
  esac
}

run_priv() { # print + confirm + sudo-execute; a declined gate SKIPS (returns 0)
  printf '\n>> sudo %s\n' "$*"
  read -r -p "   proceed? [y/N] " reply
  case "$reply" in
    y|Y|yes|YES) sudo "$@" ;;
    *) echo "   skipped." ;;
  esac
}

# Safe secret generators: DB passwords are URL-interpolated into DATABASE_URL
# and read by compose, so they must avoid @ : / % # ? and $ — plain
# alphanumerics only. SECRET_KEY is not URL-embedded; token_urlsafe is fine.
gen_db_secret() {
  python3 -c "import secrets,string;print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))"
}
gen_secret_key() {
  python3 -c "import secrets;print(secrets.token_urlsafe(64))"
}

scaffold_env() { # scaffold_env <dir with .env.prod.example> — writes <dir>/.env
  local dir="$1" env_file secret_key db_pw root_pw
  env_file="$dir/.env"
  if [ -f "$env_file" ]; then
    echo "   $env_file already exists — keeping it (idempotent re-run)."
    return 0
  fi
  if [ ! -f "$dir/.env.prod.example" ]; then
    echo "ERROR: $dir/.env.prod.example not found — is the app checked out?" >&2
    return 1
  fi
  secret_key="$(gen_secret_key)"
  db_pw="$(gen_db_secret)"
  root_pw="$(gen_db_secret)"
  ( umask 077
    sed -e "s|^SECRET_KEY=.*|SECRET_KEY=${secret_key}|" \
        -e "s|^DB_PASSWORD=.*|DB_PASSWORD=${db_pw}|" \
        -e "s|^DB_ROOT_PASSWORD=.*|DB_ROOT_PASSWORD=${root_pw}|" \
        -e "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://${HOST_IP}|" \
        "$dir/.env.prod.example" > "$env_file"
    printf 'TZ=America/Monterrey\n' >> "$env_file"
    # docker-compose.prod.yml falls back to /opt/kpi-operations if unset;
    # writing it unconditionally keeps a non-default --root coherent with
    # the data root prepared in phases 1/5.
    printf 'KPI_DATA_ROOT=%s\n' "$ROOT" >> "$env_file"
  )
  chmod 600 "$env_file"
  echo "   wrote $env_file (mode 600; secrets generated, intentionally not shown)."
}

if [ -n "$SCAFFOLD_ONLY" ]; then
  scaffold_env "$SCAFFOLD_ONLY"
  exit $?
fi

echo "== KPI VM bootstrap: ROOT=$ROOT APP_DIR=$APP_DIR IP=$HOST_IP"

# --- phase 1: sanity (read-only, no sudo) -------------------------------------
echo "-- phase 1: sanity"
. /etc/os-release 2>/dev/null || true
echo "   OS: ${PRETTY_NAME:-unknown}"
if command -v docker >/dev/null 2>&1; then
  docker --version | sed 's/^/   /' || true
else
  echo "   docker: MISSING (phase 2 will install)"
fi
if docker compose version >/dev/null 2>&1; then
  docker compose version | sed 's/^/   /' || true
else
  echo "   docker compose plugin: MISSING (phase 2 will install)"
fi
base="$(dirname "$ROOT")"; [ -d "$base" ] || base=/
free_kb=$(df -Pk "$base" | awk 'NR==2 {print $4}')
free_gb=$((free_kb / 1024 / 1024))
echo "   free disk at $base: ${free_gb}G"
if [ "$free_gb" -lt 20 ]; then
  echo "ERROR: need >= 20 GB free at $base (have ${free_gb}G)." >&2
  exit 1
fi
# Case-sensitivity probe on a throwaway dir (assumed same filesystem as ROOT;
# the real ROOT is probed again with sudo in phase 5). Fatal here by design:
# a case-insensitive datadir corrupts MariaDB (errno 1033 — PR-3 lesson).
pf_tmp="$(mktemp -d "$base/kpi-preflight.XXXXXX" 2>/dev/null || mktemp -d)"
bash "$SCRIPT_DIR/preflight.sh" "$pf_tmp"
rm -rf "$pf_tmp"
echo "   preflight (case-sensitivity): OK"

# --- phase 2: docker install (guarded) -----------------------------------------
echo "-- phase 2: docker install"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "   docker + compose already installed — skipping install."
else
  # Official Docker CE apt repo (docs.docker.com/engine/install/ubuntu). If the
  # release codename has no channel yet (brand-new Ubuntu), fall back to the
  # latest LTS channel. This is a read-only network probe to detect channel availability.
  codename="${VERSION_CODENAME:-noble}"
  if ! curl -fsIo /dev/null "https://download.docker.com/linux/ubuntu/dists/${codename}/Release"; then
    echo "   NOTE: no Docker apt channel for '${codename}' — falling back to 'noble'."
    codename=noble
  fi
  run_priv install -m 0755 -d /etc/apt/keyrings
  if confirm "download Docker GPG key -> /etc/apt/keyrings/docker.asc (sudo tee)"; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc >/dev/null
  fi
  if confirm "add Docker apt repository for '${codename}' (sudo tee sources.list.d/docker.list)"; then
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${codename} stable" \
      | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  fi
  run_priv apt-get update
  run_priv apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

# --- phase 3: docker group ------------------------------------------------------
echo "-- phase 3: docker group"
if id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
  echo "   $USER already in the docker group."
else
  run_priv usermod -aG docker "$USER"
fi
if ! groups | tr ' ' '\n' | grep -qx docker; then
  echo "   NOTE: docker group is NOT active in this session — log out and back in"
  echo "         before running 'docker compose' without sudo."
fi

# --- phase 4: ufw ----------------------------------------------------------------
echo "-- phase 4: ufw (deny incoming; allows preserve the co-tenants)"
echo "   current listeners (for the record):"
if command -v ss >/dev/null 2>&1; then ss -tlnp 2>/dev/null | sed 's/^/   /' || true; fi
run_priv ufw status verbose
run_priv ufw default deny incoming
run_priv ufw default allow outgoing
for port in 22 443 80 7070 5443 3389; do
  run_priv ufw allow "${port}/tcp"
done
if confirm "sudo ufw --force enable  (verifies the 22/tcp allow first — anti-lockout)"; then
  # NOTE: this only recognizes a plain "allow 22/tcp" rule. A pre-existing
  # "allow OpenSSH" profile or a "limit 22/tcp" rule is NOT matched — the
  # guard then fails SAFE (refuses to enable). If that happens, add a plain
  # "allow 22/tcp" rule and re-run.
  if ! sudo ufw show added | grep -qE '(^| )allow 22/tcp$'; then
    echo "ERROR: no 22/tcp allow rule staged — refusing to enable ufw (lockout guard)." >&2
    exit 1
  fi
  sudo ufw --force enable
  sudo ufw status verbose | sed 's/^/   /'
fi

# --- phase 5: data root -----------------------------------------------------------
echo "-- phase 5: data root"
run_priv bash "$SCRIPT_DIR/preflight.sh" "$ROOT"
run_priv bash "$SCRIPT_DIR/init-data-root.sh" "$ROOT"
echo "   NOTE: ownership (--chown) runs during deploy, after the image build"
echo "         (the backend uid is only known then)."

# --- phase 6: app checkout + .env ---------------------------------------------------
echo "-- phase 6: app checkout + .env"
if [ -d "$APP_DIR/.git" ]; then
  echo "   $APP_DIR already cloned."
  if confirm "git -C $APP_DIR pull --ff-only"; then
    git -C "$APP_DIR" pull --ff-only
  fi
else
  if confirm "sudo git clone $REPO_URL $APP_DIR && sudo chown -R $USER:$USER $APP_DIR"; then
    sudo git clone "$REPO_URL" "$APP_DIR"
    sudo chown -R "$USER":"$USER" "$APP_DIR"
  fi
fi
scaffold_env "$APP_DIR"

echo "== bootstrap complete. Next: runbook Phase 2 (build, chown, up -d)."
