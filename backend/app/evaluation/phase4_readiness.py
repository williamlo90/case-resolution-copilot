"""Development-only coverage audit. Never execute or inspect the sealed holdout."""

import ast
import inspect
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.analysis import deterministic_decision_engine as engine
from app.domain.controlled_operations import OPERATIONS
from app.evaluation.case_resolution_v2.corpus import case_path, inputs
from app.evaluation.case_resolution_v2.models import GoldenLabel
from app.evaluation.case_resolution_v2.storage import digest, file_digest, read_json


def proposed_action_types() -> set[str]:
    """Inspect the current finite action branches, not the generic gateway's accepted strings.

    This is a conservative static inventory, not evidence of successful execution. Refuse
    unfamiliar engine structure so a future dynamic planner cannot silently pass this audit.
    """
    tree = ast.parse(inspect.getsource(engine._actions))
    result: set[str] = set()
    mappings = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Tuple)
            and [item.id for item in target.elts if isinstance(item, ast.Name)]
            == ["action_type", "label", "expected"]
            for target in node.targets
        ):
            if not isinstance(node.value, ast.Subscript) or not isinstance(
                node.value.value, ast.Dict
            ):
                raise ValueError("Review the changed production action selector")
            mappings += 1
            for value in node.value.value.values:
                if not isinstance(value, ast.Tuple):
                    raise ValueError("Non-literal production action template")
                name = ast.literal_eval(value.elts[0])
                if not isinstance(name, str):
                    raise ValueError("Non-string production action type")
                result.add(name)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "ProposedActionDraft"
        ):
            for keyword in node.keywords:
                if keyword.arg == "type" and isinstance(keyword.value, ast.Constant):
                    result.add(str(keyword.value.value))
    if mappings != 1 or not result:
        raise ValueError("Production action inventory requires review")
    return result | set(OPERATIONS)


def assess_development(root: Path) -> dict[str, Any]:
    spec, cases = inputs(root, "development")
    available = proposed_action_types()
    rows = []
    missing: Counter[str] = Counter()
    for entry, case in zip(spec.entries, cases, strict=True):
        label = GoldenLabel.model_validate(
            read_json(case_path(root, "development", case.case_id, "labels"))
        )
        if digest(label) != entry.label_sha256 or label.oracle.case_id != case.case_id:
            raise ValueError("Development oracle identity changed")
        required = {action.action_type for action in label.oracle.expected_actions}
        unsupported = required - available
        supplied = {key for item in case.evidence for key in item.facts}
        missing_values = sorted(
            {
                f"requested_{key}"
                for action in required
                if action in OPERATIONS
                for key in OPERATIONS[action].value_fields
                if f"requested_{key}" not in supplied
            }
        )
        missing.update(unsupported)
        rows.append(
            dict(
                case_id=case.case_id,
                domain=case.domain,
                expected_terminal=label.oracle.expected_terminal,
                required_actions=sorted(required),
                unavailable_action_names=sorted(unsupported),
                missing_business_values=missing_values,
                input_sha256=entry.input_sha256,
                label_sha256=entry.label_sha256,
            )
        )
    source = inspect.getsourcefile(engine)
    assert source is not None
    return dict(
        version="phase4-development-readiness-1",
        recorded_at=datetime.now(UTC).isoformat(),
        profile="static_development_coverage_not_product_evaluation",
        gate="blocked",
        holdout_executed=False,
        provider_calls=0,
        development_cases=len(rows),
        engine_sha256=file_digest(Path(source)),
        model_version=engine.DECISION_MODEL_VERSION,
        prompt_version=engine.DECISION_PROMPT_VERSION,
        proposed_action_types=sorted(available),
        unavailable_action_names=dict(sorted(missing.items())),
        cases_with_unavailable_actions=sum(bool(row["unavailable_action_names"]) for row in rows),
        cases_with_missing_business_values=sum(
            bool(row["missing_business_values"]) for row in rows
        ),
        blockers=[
            "Static readiness does not substitute for a sealed isolated CI product evaluation",
            *(["Required action names are unavailable"] if missing else []),
            *(
                ["Some source inputs omit required operation values"]
                if any(row["missing_business_values"] for row in rows)
                else []
            ),
        ],
        cases=rows,
        limits=[
            "Matching an action name alone never proves capability or correctness",
            "Cases without an expected action are not counted as supported",
            "No accuracy, completion or holdout score is calculated",
        ],
    )
