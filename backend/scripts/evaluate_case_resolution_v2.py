"""Validate authored artifacts or score already persisted observations; no provider calls."""

import argparse
import json
from pathlib import Path

from app.evaluation.case_resolution_v2.corpus import ROOT, validate_corpus
from app.evaluation.case_resolution_v2.runner import score_run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate-corpus", "score"])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--split", choices=["development", "regression", "holdout", "time_study"])
    parser.add_argument("--run", type=Path)
    args = parser.parse_args()
    if args.command == "validate-corpus":
        print(json.dumps({"static_validation": validate_corpus(args.root), "product_runs": 0}))
    else:
        if args.run is None or args.split is None:
            parser.error("score requires --run and --split")
        report = score_run(root=args.root, split=args.split, output=args.run)
        print(json.dumps({"scored": report["scored"], "report": str(args.run / "report.json")}))


if __name__ == "__main__":
    main()
