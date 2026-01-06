# data_processor

Small utility to convert JSONL/NDJSON into a single JSON array.

Usage examples:

Convert a file to another file:

```bash
python data_processor/jsonl_to_json.py data/input.jsonl data/output.json
```

Use stdin/stdout to pipe:

```bash
cat data/input.jsonl | python data_processor/jsonl_to_json.py - - > data/output.json
```

Pretty-print output:

```bash
python data_processor/jsonl_to_json.py data/input.jsonl data/output.json --pretty
```

Notes:
- The script streams input and writes the output array incrementally to avoid high memory usage.
- It will raise an error on malformed JSON lines.
