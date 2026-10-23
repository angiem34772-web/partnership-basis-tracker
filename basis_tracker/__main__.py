"""Command line entry point: python -m basis_tracker"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .excel_export import export
from .loader import load_inputs
from .rollforward import run

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Roll partner tax basis and capital accounts forward.")
    parser.add_argument("--data", default=ROOT / "sample_data", help="folder with the input CSV files")
    parser.add_argument("--out", default=ROOT / "output" / "partnership_basis_report.xlsx", help="Excel file to write")
    args = parser.parse_args(argv)

    inputs = load_inputs(args.data)
    results = run(inputs)
    path = export(inputs, results, args.out)

    years = [y.tax_year for y in results.years]
    print(f"Rolled forward {len(inputs.partners)} partners in {len(inputs.entities)} partnerships, "
          f"{min(years)}-{max(years)} ({len(results.years)} partner-years).")
    print("Flags:")
    for code, count in sorted(Counter(f.code for f in results.flags).items()):
        print(f"  {code:<26} {count}")
    exceptions = sum(1 for y in results.years if abs(y.unexplained_difference) > 1)
    print(f"Reconciliation exceptions: {exceptions}")
    print(f"Excel report: {path}")


if __name__ == "__main__":
    main()
