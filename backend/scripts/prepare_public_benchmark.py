import argparse
from pathlib import Path

from app.evaluation.public_benchmark.setup import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_DATA_ROOT,
    prepare_public_benchmark,
)
from app.evaluation.public_benchmark.storage import sha256_file
from app.evaluation.public_benchmark.validation import validate_public_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare bounded, separated public benchmark data."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Replace cached source files with fresh bounded downloads.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate existing local artifacts without network access.",
    )
    arguments = parser.parse_args()

    if arguments.validate_only:
        summary = validate_public_benchmark(arguments.data_root, require_manifest=True)
    else:
        prepare_public_benchmark(
            config_path=arguments.config,
            data_root=arguments.data_root,
            refresh=arguments.refresh,
        )
        summary = validate_public_benchmark(arguments.data_root, require_manifest=True)

    manifest_path = arguments.data_root / "manifest.json"
    counts = (
        f"cfpb={summary.input_records['cfpb']} "
        f"fos={summary.input_records['fos']} "
        f"uci={summary.input_records['uci']}"
    )
    print(
        f"status=passed {counts} checks={len(summary.checks)} "
        f"manifest_sha256={sha256_file(manifest_path)}"
    )


if __name__ == "__main__":
    main()
