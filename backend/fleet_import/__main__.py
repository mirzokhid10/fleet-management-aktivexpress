"""Command line for the data templates.

    python -m fleet_import template out.xlsx   # write the blank template
    python -m fleet_import check filled.xlsx    # validate a filled template
"""

from __future__ import annotations

import argparse
import sys

from .validate import validate_workbook
from .workbook import write_template


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fleet_import")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("template", help="write the blank template").add_argument("path")
    sub.add_parser("check", help="validate a filled template").add_argument("path")
    args = parser.parse_args(argv)

    if args.command == "template":
        print(f"Template written to {write_template(args.path)}")
        return 0

    report = validate_workbook(args.path)
    print(report.summary())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
