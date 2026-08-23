import ast
from pathlib import Path

DOMAIN_ROOT = Path(__file__).parents[2] / "app" / "domain"
FORBIDDEN_PREFIXES = (
    "app.api",
    "app.integrations",
    "app.persistence",
    "app.services",
    "app.tools",
    "fastapi",
    "sqlalchemy",
)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_domain_does_not_depend_on_framework_or_outer_layers() -> None:
    violations: list[str] = []

    for path in sorted(DOMAIN_ROOT.rglob("*.py")):
        for module in sorted(imported_modules(path)):
            if module.startswith(FORBIDDEN_PREFIXES):
                violations.append(f"{path.relative_to(DOMAIN_ROOT)}: {module}")

    assert violations == []
