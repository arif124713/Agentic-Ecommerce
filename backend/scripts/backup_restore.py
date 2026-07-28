"""Backup/restore drill (spec §26 — Deployment, Backup & Disaster Recovery).

No Docker/cloud storage in this native-Windows setup (documented throughout done.MD), so this is a
real `mysqldump`/`mysql` round trip against the local MySQL install rather than a managed snapshot
service — the actual mechanism spec §26 cares about (can a backup actually be restored and verified,
not just taken) works the same way regardless of where the dump eventually lives.

Subcommands:
  backup   - mysqldump the configured database to backend/backups/<db>_<timestamp>.sql.gz
  restore  - restore a .sql.gz dump into a target database (creating it if needed)
  drill    - backup the real database, restore it into a disposable *_restore_drill database,
             compare row counts across the tables that matter most (orders/payments are the
             financial record; users/products are everything else depends on), then drop the
             drill database. This is the actual DR exit criterion: prove a backup is restorable,
             not just that `mysqldump` exits 0.

Run: python scripts/backup_restore.py drill
"""

import argparse
import gzip
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import get_settings  # noqa: E402

BACKUP_DIR = Path(__file__).resolve().parents[1] / "backups"

# Tables whose row counts must match exactly after a restore for the drill to be considered a
# pass — the financial record (spec §8.5's 7-year retention set) plus the core catalogue/identity
# tables everything else is built on.
DRILL_CHECK_TABLES = [
    "users", "products", "product_variants", "orders", "order_items", "payments", "refunds",
]


def _mysql_bin(name: str) -> str:
    """Resolve mysqldump/mysql on a machine where it isn't on PATH (this project's own documented
    Windows-native gotcha — see done.MD's "stack deviations"). Falls back to the bare name so this
    still works unmodified on a machine where it IS on PATH."""
    if shutil.which(name):
        return name
    candidates = [
        Path(r"C:\Program Files\MySQL\MySQL Server 8.0\bin") / f"{name}.exe",
        Path(r"C:\Program Files\MySQL\MySQL Server 8.4\bin") / f"{name}.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return name  # let subprocess raise a clear FileNotFoundError if it's genuinely missing


def _run_env(settings) -> dict:
    import os
    env = os.environ.copy()
    if settings.mysql_password:
        env["MYSQL_PWD"] = settings.mysql_password  # never on the command line / never logged
    return env


def backup(db_name: str, out_path: Path | None = None) -> Path:
    settings = get_settings()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if out_path is None:
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        out_path = BACKUP_DIR / f"{db_name}_{stamp}.sql.gz"

    cmd = [
        _mysql_bin("mysqldump"),
        "-h", settings.mysql_host,
        "-P", str(settings.mysql_port),
        "-u", settings.mysql_user,
        "--single-transaction",  # consistent snapshot without locking InnoDB tables
        "--routines", "--triggers",
        db_name,
    ]
    print(f"Dumping {db_name} -> {out_path}")
    # Buffered through memory rather than passing a gzip.GzipFile as `stdout=` directly: subprocess
    # redirects at the raw OS file-descriptor level (GzipFile.fileno() just proxies to the
    # underlying file), so the child process's output would bypass Python's gzip layer entirely
    # and write plain, uncompressed bytes to a file merely *named* .gz. Caught by actually checking
    # the resulting file with `file`/reading its first bytes, not by assuming `gzip.open` made it
    # correct — the dump was plain "-- MySQL dump 10.13..." text on disk despite the .gz name.
    proc = subprocess.run(cmd, capture_output=True, env=_run_env(settings))
    if proc.returncode != 0:
        raise RuntimeError(f"mysqldump failed: {proc.stderr.decode(errors='replace')}")
    with gzip.open(out_path, "wb") as gz:
        gz.write(proc.stdout)
    size_kb = out_path.stat().st_size / 1024
    print(f"OK: {out_path} ({size_kb:.1f} KB)")
    return out_path


def restore(dump_path: Path, target_db: str) -> None:
    settings = get_settings()
    env = _run_env(settings)

    create_cmd = [
        _mysql_bin("mysql"),
        "-h", settings.mysql_host, "-P", str(settings.mysql_port), "-u", settings.mysql_user,
        "-e", f"DROP DATABASE IF EXISTS `{target_db}`; "
              f"CREATE DATABASE `{target_db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci",
    ]
    subprocess.run(create_cmd, check=True, env=env)

    restore_cmd = [
        _mysql_bin("mysql"),
        "-h", settings.mysql_host, "-P", str(settings.mysql_port), "-u", settings.mysql_user,
        target_db,
    ]
    print(f"Restoring {dump_path} -> {target_db}")
    with gzip.open(dump_path, "rb") as gz:
        sql_bytes = gz.read()  # same reasoning as backup(): decompress in Python, not via fileno()
    proc = subprocess.run(restore_cmd, input=sql_bytes, stderr=subprocess.PIPE, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"mysql restore failed: {proc.stderr.decode(errors='replace')}")
    print(f"OK: restored into {target_db}")


def _row_counts(db_name: str, settings) -> dict[str, int]:
    url = (
        f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
        f"@{settings.mysql_host}:{settings.mysql_port}/{db_name}?charset=utf8mb4"
    )
    engine = create_engine(url)
    counts = {}
    with engine.connect() as conn:
        for table in DRILL_CHECK_TABLES:
            counts[table] = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar_one()
    engine.dispose()
    return counts


def drill() -> None:
    settings = get_settings()
    source_db = settings.mysql_db
    drill_db = f"{source_db}_restore_drill"

    dump_path = backup(source_db)
    restore(dump_path, drill_db)

    print("\nComparing row counts: source vs restored drill database")
    source_counts = _row_counts(source_db, settings)
    drill_counts = _row_counts(drill_db, settings)

    all_match = True
    print(f"{'table':<20}{'source':>10}{'restored':>10}{'match':>8}")
    for table in DRILL_CHECK_TABLES:
        s, d = source_counts[table], drill_counts[table]
        match = s == d
        all_match &= match
        print(f"{table:<20}{s:>10}{d:>10}{'OK' if match else 'MISMATCH':>8}")

    settings_for_cleanup = settings
    env = _run_env(settings_for_cleanup)
    subprocess.run(
        [
            _mysql_bin("mysql"), "-h", settings.mysql_host, "-P", str(settings.mysql_port),
            "-u", settings.mysql_user, "-e", f"DROP DATABASE `{drill_db}`",
        ],
        check=True, env=env,
    )
    print(f"\nDropped drill database {drill_db}")

    if not all_match:
        print("\nDRILL FAILED: row counts did not match after restore", file=sys.stderr)
        sys.exit(1)
    print("\nDRILL PASSED: backup is restorable and every checked table matches exactly")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)

    p_backup = sub.add_parser("backup")
    p_backup.add_argument("--db", default=None)

    p_restore = sub.add_parser("restore")
    p_restore.add_argument("--file", required=True)
    p_restore.add_argument("--target-db", required=True)

    sub.add_parser("drill")

    args = parser.parse_args()
    settings = get_settings()

    if args.action == "backup":
        backup(args.db or settings.mysql_db)
    elif args.action == "restore":
        restore(Path(args.file), args.target_db)
    elif args.action == "drill":
        drill()


if __name__ == "__main__":
    main()
