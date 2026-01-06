#!/usr/bin/env python3
"""Convert JSONL/NDJSON files to a single JSON array.

Usage:
  python jsonl_to_json.py input.jsonl output.json
  cat input.jsonl | python jsonl_to_json.py - - > output.json

The script streams input and writes the output array without loading
all documents into memory.
"""
import sys
import json
import argparse
import os


def convert_jsonl_to_json(infile, outfile, pretty=False):
    first = True
    indent = 2 if pretty else None

    outfile.write("[")

    for raw in infile:
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON line: {e}\nLine: {line}") from e

        if not first:
            outfile.write(",\n" if pretty else ",")
        else:
            if pretty:
                outfile.write("\n")
            first = False

        # Dump object
        if pretty:
            json.dump(obj, outfile, indent=indent, ensure_ascii=False)
        else:
            json.dump(obj, outfile, separators=(',', ':'), ensure_ascii=False)

    if pretty and not first:
        outfile.write("\n")
    outfile.write("]")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert JSONL/NDJSON to JSON array")
    parser.add_argument("input", help="Input file path or - for stdin")
    parser.add_argument("output", help="Output file path or - for stdout")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output JSON")

    args = parser.parse_args(argv)

    # Validate input
    if args.input != "-" and not os.path.exists(args.input):
        print(f"Input file not found: {args.input}", file=sys.stderr)
        sys.exit(2)

    # Ensure output directory exists
    if args.output != "-":
        out_dir = os.path.dirname(args.output)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

    infile = sys.stdin if args.input == "-" else open(args.input, "r", encoding="utf-8")
    try:
        outfile = sys.stdout if args.output == "-" else open(args.output, "w", encoding="utf-8")
    except FileNotFoundError as e:
        print(f"Failed to open output file: {e}", file=sys.stderr)
        if infile is not sys.stdin:
            infile.close()
        sys.exit(2)

    try:
        convert_jsonl_to_json(infile, outfile, pretty=args.pretty)
    finally:
        if infile is not sys.stdin:
            infile.close()
        if outfile is not sys.stdout:
            outfile.close()


if __name__ == "__main__":
    main()
