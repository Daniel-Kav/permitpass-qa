"""CLI: python -m permitpass.migrate_legacy <export.csv> [--rejects rejects.csv]

Exit code 0 only if every reconciliation check passes.
"""
import argparse
import json
import sys

from .db import SessionLocal, init_db
from .migration import migrate, reconcile
from .migration.importer import write_rejects


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv")
    ap.add_argument("--rejects", default="rejects.csv")
    args = ap.parse_args(argv)
    init_db()
    with SessionLocal() as db:
        report = migrate(db, args.csv)
        checks = reconcile(db, report)
    write_rejects(report, args.rejects)
    print(json.dumps(report.as_dict(), indent=2))
    print(f"Rejects written to {args.rejects}")
    for c in checks:
        print(f"[{'PASS' if c.ok else 'FAIL'}] {c.name}: expected {c.expected}, got {c.actual}")
    return 0 if all(c.ok for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
