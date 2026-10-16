"""Exit 2 while prerequisites fail; a saved report is not a successful Phase 4 gate."""

import argparse
import json
from pathlib import Path

from app.evaluation.case_resolution_v2.storage import write_new
from app.evaluation.phase4_readiness import assess_development

ROOT = Path(__file__).resolve().parents[1] / "evaluations" / "case_resolution_v2_phase4"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = assess_development(ROOT)
    write_new(args.output, report)
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "gate",
                    "development_cases",
                    "cases_with_unavailable_actions",
                    "holdout_executed",
                )
            }
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
