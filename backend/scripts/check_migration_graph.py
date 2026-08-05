from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = BACKEND_ROOT / "alembic.ini"


@dataclass(frozen=True, slots=True)
class MigrationGraphSummary:
    head: str
    base: str
    revisions: int


def inspect_migration_graph(
    config_path: Path = ALEMBIC_CONFIG,
) -> MigrationGraphSummary:
    config = Config(str(config_path))
    config.set_main_option(
        "script_location",
        str(config_path.parent / "migrations"),
    )
    scripts = ScriptDirectory.from_config(config)
    heads = scripts.get_heads()
    bases = scripts.get_bases()
    revisions = list(scripts.walk_revisions())
    if len(heads) != 1:
        raise RuntimeError(f"Expected one migration head; found {len(heads)}.")
    if len(bases) != 1:
        raise RuntimeError(f"Expected one migration base; found {len(bases)}.")
    if not revisions:
        raise RuntimeError("The migration graph is empty.")
    return MigrationGraphSummary(
        head=heads[0],
        base=bases[0],
        revisions=len(revisions),
    )


def main() -> int:
    summary = inspect_migration_graph()
    print(
        "status=passed "
        f"head={summary.head} base={summary.base} revisions={summary.revisions}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
