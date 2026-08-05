from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.api.schemas.cases import (
    CaseActivityPageResponse,
    CaseDetailResponse,
    CaseListResponse,
)
from app.api.schemas.conversations import ConversationMessagePageResponse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "contracts" / "case-transport.schema.json"
CONTRACT_MODELS: dict[str, type[BaseModel]] = {
    "CaseListResponse": CaseListResponse,
    "CaseDetailResponse": CaseDetailResponse,
    "ConversationMessagePageResponse": ConversationMessagePageResponse,
    "CaseActivityPageResponse": CaseActivityPageResponse,
}


def build_contract() -> dict[str, Any]:
    return {
        "schema_version": "support-copilot-case-transport-v1",
        "models": {
            name: model.model_json_schema(mode="serialization")
            for name, model in CONTRACT_MODELS.items()
        },
    }


def canonical_contract(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def contract_matches(path: Path = CONTRACT_PATH) -> bool:
    if not path.is_file():
        return False
    expected = canonical_contract(build_contract())
    return path.read_text(encoding="utf-8") == expected


def write_contract(path: Path = CONTRACT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_contract(build_contract()), encoding="utf-8")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the committed case transport contract against Pydantic schemas."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Regenerate the committed contract instead of checking it.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    if arguments.write:
        write_contract()
        print(f"status=written path={CONTRACT_PATH.relative_to(PROJECT_ROOT)}")
        return 0
    if not contract_matches():
        print(
            "status=failed reason=case_transport_contract_out_of_date "
            f"path={CONTRACT_PATH.relative_to(PROJECT_ROOT)}"
        )
        return 1
    print(
        "status=passed "
        f"models={len(CONTRACT_MODELS)} "
        f"path={CONTRACT_PATH.relative_to(PROJECT_ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
