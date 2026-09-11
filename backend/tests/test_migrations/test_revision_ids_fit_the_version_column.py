"""A revision id longer than 32 characters breaks MariaDB and not SQLite.

Alembic's `alembic_version.version_num` is `VARCHAR(32)`. SQLite does not
enforce declared string lengths, so an over-long revision id upgrades cleanly
there and fails on MariaDB at the very last statement of the migration --
`UPDATE alembic_version SET version_num = ...` -- with

    (1406, "Data too long for column 'version_num' at row 1")

which is the worst possible moment: on MariaDB the DDL has already committed
implicitly, so the schema is changed while the version table still names the
previous revision.

Found the hard way. `0009_global_kpi_threshold_defaults` was 34 characters and
passed the entire SQLite suite, including nine migration tests that ran a real
`alembic upgrade`. It only surfaced against a throwaway MariaDB 11.4 container.
`0008_coverage_active_uniqueness` is 31 -- the cliff was one character away and
nothing was watching it.

This is the repository's recurring defect class (a difference between the two
dialects that the SQLite suite cannot see), so it gets a structural guard rather
than a fixed filename.
"""

import re
from pathlib import Path

import pytest

#: Alembic's own default, and what `alembic_version` is actually created with --
#: verified against MariaDB 11.4: `version_num varchar(32) NOT NULL`.
VERSION_NUM_LENGTH = 32

VERSIONS_DIR = Path(__file__).resolve().parents[2] / "alembic" / "versions"

_REVISION = re.compile(r"^revision(?::\s*str)?\s*=\s*[\"']([^\"']+)[\"']", re.M)
_DOWN_REVISION = re.compile(r"^down_revision(?::\s*[^=]+)?\s*=\s*[\"']([^\"']+)[\"']", re.M)


def _migration_files():
    files = sorted(p for p in VERSIONS_DIR.glob("*.py") if p.name != "__init__.py")
    assert files, f"no migrations found under {VERSIONS_DIR}"
    return files


@pytest.mark.parametrize("path", _migration_files(), ids=lambda p: p.name)
def test_the_revision_id_fits_the_version_column(path):
    match = _REVISION.search(path.read_text())
    assert match, f"{path.name} declares no revision"
    revision = match.group(1)

    assert len(revision) <= VERSION_NUM_LENGTH, (
        f"{path.name}: revision id {revision!r} is {len(revision)} characters, "
        f"over the {VERSION_NUM_LENGTH} that alembic_version.version_num holds. "
        "SQLite will not complain; MariaDB fails AFTER the DDL has implicitly committed."
    )


@pytest.mark.parametrize("path", _migration_files(), ids=lambda p: p.name)
def test_the_down_revision_fits_too(path):
    # A down_revision is written into the version table by `downgrade`, so it is
    # subject to exactly the same limit as the revision itself.
    match = _DOWN_REVISION.search(path.read_text())
    if not match:
        return  # the baseline has down_revision = None
    down = match.group(1)

    assert len(down) <= VERSION_NUM_LENGTH, f"{path.name}: down_revision {down!r} is {len(down)} characters"


def test_the_guard_is_watching_every_migration():
    # Anti-vacuity: if the glob ever stops matching, both tests above pass by
    # running zero times. Pin the count so that silence is a failure.
    assert len(_migration_files()) >= 9, f"only found {len(_migration_files())} migrations"
