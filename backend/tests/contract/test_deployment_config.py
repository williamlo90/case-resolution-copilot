import json
from pathlib import Path


def test_vercel_functions_run_with_the_database_region() -> None:
    project_root = Path(__file__).resolve().parents[2]
    configuration = json.loads((project_root / "vercel.json").read_text())

    assert configuration["$schema"] == "https://openapi.vercel.sh/vercel.json"
    assert configuration["regions"] == ["sin1"]
