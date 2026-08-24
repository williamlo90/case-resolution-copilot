from pathlib import Path

import pytest

from scripts.prepare_developer_workflow_benchmark import load_benchmark_target


def _write_target(
    path: Path,
    *,
    endpoint_id: str = "ep-benchmark-123",
    host: str = "ep-benchmark-123.ap-southeast-1.aws.neon.tech",
) -> None:
    path.write_text(
        "\n".join(
            [
                f"TEST_DATABASE_URL=postgresql://user:secret@{host}/app?sslmode=require",
                "TEST_DATABASE_SCOPE=disposable",
                f"TEST_DATABASE_ENDPOINT_ID={endpoint_id}",
            ]
        ),
        encoding="utf-8",
    )


def test_loads_a_matching_disposable_direct_endpoint(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.test.local"
    _write_target(env_file)

    database_url, endpoint_id = load_benchmark_target(env_file)

    assert database_url.startswith("postgresql+psycopg://")
    assert endpoint_id == "ep-benchmark-123"


@pytest.mark.parametrize(
    ("endpoint_id", "host"),
    [
        ("ep-benchmark-123", "ep-other-456.ap-southeast-1.aws.neon.tech"),
        (
            "ep-benchmark-123",
            "ep-benchmark-123-pooler.ap-southeast-1.aws.neon.tech",
        ),
    ],
)
def test_rejects_a_mismatched_or_pooled_endpoint(
    tmp_path: Path,
    endpoint_id: str,
    host: str,
) -> None:
    env_file = tmp_path / ".env.test.local"
    _write_target(env_file, endpoint_id=endpoint_id, host=host)

    with pytest.raises(ValueError, match="matching direct Neon endpoint"):
        load_benchmark_target(env_file)
