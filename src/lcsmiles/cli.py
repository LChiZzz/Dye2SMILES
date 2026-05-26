from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import ConversionError, convert_files, write_csv
from .ocsr import OCSRError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert ChemDraw/image files to RDKit SMILES.")
    parser.add_argument("inputs", nargs="+", help="Input files: cdxml, cdx, mol, sdf, smi, png, jpg, pdf")
    parser.add_argument("-o", "--output", help="Output CSV path")
    parser.add_argument("--no-canonical", action="store_true", help="Do not canonicalize SMILES")
    parser.add_argument("--no-isomeric", action="store_true", help="Do not include stereochemistry")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        records = convert_files(
            [Path(p) for p in args.inputs],
            canonical=not args.no_canonical,
            isomeric=not args.no_isomeric,
        )
    except (ConversionError, OCSRError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.output:
        write_csv(records, args.output)
        print(f"Wrote {len(records)} record(s) to {args.output}")
    else:
        for record in records:
            status = "" if record.status == "ok" else f"\t{record.status}: {record.message}"
            print(f"{record.smiles}\t{record.source}\t{record.index}{status}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

