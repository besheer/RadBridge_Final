"""Print aggregate offline metrics for an approved, sanitized JSONL evaluation set."""
import json
from pathlib import Path
import sys

from app.evaluation import evaluate


def main() -> int:
    if len(sys.argv) != 2:
        print('Usage: python tools/evaluate_provider_results.py <sanitized-results.jsonl>', file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    try:
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        result = evaluate(rows)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f'Evaluation input rejected: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
