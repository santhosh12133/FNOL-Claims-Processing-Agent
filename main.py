#!/usr/bin/env python3
"""
CLI entry point for the FNOL Claims Processing Agent.

Usage:
    python main.py path/to/document.pdf
    python main.py path/to/document.txt
    python main.py --batch sample_docs/            # process every .txt/.pdf in a folder
    python main.py --batch sample_docs/ --save      # also write JSON results to output/
"""
import argparse
import json
import sys
from pathlib import Path

from agent.pipeline import process_document


def _process_and_print(filepath: Path, save: bool) -> dict:
    try:
        result = process_document(str(filepath))
    except Exception as exc:  # keep batch runs going even if one file fails
        result = {"sourceFile": filepath.name, "error": str(exc)}

    print(json.dumps(result, indent=2))

    if save:
        out_path = Path("output") / f"{filepath.stem}.json"
        out_path.parent.mkdir(exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2))
        print(f"[saved] {out_path}", file=sys.stderr)

    return result


def main():
    parser = argparse.ArgumentParser(description="FNOL Claims Processing Agent")
    parser.add_argument("path", nargs="?", help="Path to a single .txt or .pdf FNOL document")
    parser.add_argument("--batch", metavar="DIR", help="Process every .txt/.pdf file in a directory")
    parser.add_argument("--save", action="store_true", help="Save each result as JSON in output/")
    args = parser.parse_args()

    if not args.path and not args.batch:
        parser.print_help()
        sys.exit(1)

    if args.batch:
        folder = Path(args.batch)
        files = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".txt", ".pdf"))
        if not files:
            print(f"No .txt or .pdf files found in {folder}", file=sys.stderr)
            sys.exit(1)

        results = []
        for f in files:
            results.append(_process_and_print(f, args.save))
            print("-" * 60)

        print("\nSummary:")
        for f, r in zip(files, results):
            print(f"  {f.name:35s} -> {r.get('recommendedRoute', 'ERROR: ' + str(r.get('error')))}")
    else:
        _process_and_print(Path(args.path), args.save)


if __name__ == "__main__":
    main()
