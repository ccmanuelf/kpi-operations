#!/usr/bin/env bash
# Regenerate the hash-pinned dependency locks HERMETICALLY (inside the
# digest-pinned python base image) so output is byte-reproducible across hosts.
# Run after editing backend/requirements.txt or backend/requirements-dev.txt,
# then commit both backend/*.lock.
set -euo pipefail
IMAGE="python:3.11.11-slim-bookworm@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5"
ROOT="$(git rev-parse --show-toplevel)"
# --platform linux/amd64 pins generation to the CI/Render/Docker target arch so
# the lock is byte-identical regardless of the maintainer's host arch.
docker run --rm --platform linux/amd64 -v "$ROOT/backend:/work" -w /work "$IMAGE" sh -ec '
  pip install --quiet --no-cache-dir pip-tools==7.5.3
  pip-compile --generate-hashes --no-header --output-file=requirements.lock requirements.txt
  pip-compile --generate-hashes --no-header --output-file=requirements-dev.lock requirements-dev.txt
'
echo "Regenerated backend/requirements.lock + backend/requirements-dev.lock"
