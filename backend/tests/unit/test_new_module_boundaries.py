from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"
NEW_CAPABILITY_ROOTS = (
    APP_ROOT / "domain" / "inbox",
    APP_ROOT / "ports",
    APP_ROOT / "integrations" / "gmail",
    APP_ROOT / "persistence" / "inbox",
    APP_ROOT / "persistence" / "policy_indexing",
    APP_ROOT / "retrieval" / "v2",
    APP_ROOT / "services" / "inbox",
)


def test_new_capability_modules_remain_reviewable() -> None:
    oversized: dict[str, int] = {}
    for root in NEW_CAPABILITY_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            if line_count > 400:
                oversized[path.relative_to(BACKEND_ROOT).as_posix()] = line_count

    assert oversized == {}
