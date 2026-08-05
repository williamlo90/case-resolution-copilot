import importlib
import json
import os
import shutil
import subprocess
import zipfile
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal

import httpx

from app.evaluation.public_benchmark.models import (
    ArtifactManifest,
    BenchmarkInputRecord,
    BenchmarkLabelRecord,
    CfpbSourceConfig,
    FosSourceConfig,
    PublicBenchmarkManifest,
    PublicBenchmarkSources,
    SourceRecord,
    SourceSnapshot,
    SuiteName,
    UciSourceConfig,
)
from app.evaluation.public_benchmark.storage import (
    atomic_write_bytes,
    atomic_write_json,
    canonical_json_bytes,
    ensure_within,
    relative_manifest_path,
    sha256_bytes,
    sha256_file,
    write_jsonl,
)
from app.evaluation.public_benchmark.transforms import (
    UciRow,
    build_uci_pairs,
    transform_cfpb_hit,
    transform_fos_decision,
    uci_row_from_mapping,
)
from app.evaluation.public_benchmark.validation import validate_public_benchmark
from app.evaluation.public_benchmark.xlsx_stream import iter_xlsx_rows

BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = BACKEND_ROOT / "benchmarks" / "public" / "sources.json"
DEFAULT_DATA_ROOT = BACKEND_ROOT / ".benchmark-data"

_CFPB_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
_FOS_MAX_PDF_BYTES = 5 * 1024 * 1024
_UCI_MAX_ARCHIVE_BYTES = 70 * 1024 * 1024
_UCI_MAX_WORKBOOK_BYTES = 60 * 1024 * 1024


def load_sources(path: Path = DEFAULT_CONFIG_PATH) -> PublicBenchmarkSources:
    return PublicBenchmarkSources.model_validate_json(path.read_text(encoding="utf-8"))


def prepare_public_benchmark(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    data_root: Path = DEFAULT_DATA_ROOT,
    refresh: bool = False,
) -> PublicBenchmarkManifest:
    root = data_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    sources = load_sources(config_path)
    generated_at = datetime.now(UTC)
    artifacts: list[ArtifactManifest] = []
    snapshots: list[SourceSnapshot] = []

    with httpx.Client(
        timeout=httpx.Timeout(30.0, connect=15.0),
        follow_redirects=True,
    ) as client:
        cfpb_inputs, cfpb_labels, cfpb_artifacts, cfpb_snapshot = _prepare_cfpb(
            client,
            root=root,
            config=sources.cfpb,
            refresh=refresh,
        )
        artifacts.extend(cfpb_artifacts)
        snapshots.append(cfpb_snapshot)

        fos_inputs, fos_labels, fos_artifacts, fos_snapshot = _prepare_fos(
            client,
            root=root,
            config=sources.fos,
            refresh=refresh,
        )
        artifacts.extend(fos_artifacts)
        snapshots.append(fos_snapshot)

        uci_inputs, uci_labels, uci_artifacts, uci_snapshot = _prepare_uci(
            client,
            root=root,
            config=sources.uci,
            refresh=refresh,
        )
        artifacts.extend(uci_artifacts)
        snapshots.append(uci_snapshot)

    prepared_sets: tuple[tuple[SuiteName, Sequence[SourceRecord], Sequence[SourceRecord]], ...] = (
        ("cfpb", cfpb_inputs, cfpb_labels),
        ("fos", fos_inputs, fos_labels),
        ("uci", uci_inputs, uci_labels),
    )
    for suite, inputs, labels in prepared_sets:
        prepared_root = ensure_within(root, root / "prepared" / suite)
        input_path = prepared_root / "inputs.jsonl"
        label_path = prepared_root / "labels.jsonl"
        sorted_inputs: list[SourceRecord] = sorted(
            inputs,
            key=lambda item: item.record_id,
        )
        sorted_labels: list[SourceRecord] = sorted(
            labels,
            key=lambda item: item.record_id,
        )
        write_jsonl(root, input_path, sorted_inputs)
        write_jsonl(root, label_path, sorted_labels)
        artifacts.extend(
            (
                _artifact_manifest(
                    root,
                    input_path,
                    suite=suite,
                    kind="prepared_input",
                    records=len(inputs),
                ),
                _artifact_manifest(
                    root,
                    label_path,
                    suite=suite,
                    kind="prepared_label",
                    records=len(labels),
                ),
            )
        )

    summary = validate_public_benchmark(root, require_manifest=False)
    config_hash = sha256_bytes(canonical_json_bytes(sources.model_dump(mode="json")))
    manifest = PublicBenchmarkManifest(
        generated_at=generated_at,
        config_sha256=config_hash,
        sources=snapshots,
        artifacts=artifacts,
        validation=summary,
    )
    atomic_write_json(root, root / "manifest.json", manifest.model_dump(mode="json"))
    validate_public_benchmark(root, require_manifest=True)
    return manifest


def _prepare_cfpb(
    client: httpx.Client,
    *,
    root: Path,
    config: CfpbSourceConfig,
    refresh: bool,
) -> tuple[
    list[BenchmarkInputRecord],
    list[BenchmarkLabelRecord],
    list[ArtifactManifest],
    SourceSnapshot,
]:
    raw_root = ensure_within(root, root / "raw" / "cfpb")
    inputs: list[BenchmarkInputRecord] = []
    labels: list[BenchmarkLabelRecord] = []
    artifacts: list[ArtifactManifest] = []
    selected_ids: set[str] = set()
    api_last_updated: set[str] = set()
    retrieved_times: list[datetime] = []

    for response_label in config.response_labels:
        slug = _slug(response_label)
        raw_path = raw_root / f"{slug}.json"
        params: dict[str, str | int] = {
            "date_received_min": config.date_received_min.isoformat(),
            "date_received_max": config.date_received_max.isoformat(),
            "has_narrative": "true",
            "company_response": response_label,
            "size": min(100, config.records_per_label * 2),
            "sort": "created_date_asc",
            "no_aggs": "true",
            "no_highlight": "true",
        }
        if refresh or not raw_path.exists():
            response = client.get(config.api_url, params=params)
            response.raise_for_status()
            if len(response.content) > _CFPB_MAX_RESPONSE_BYTES:
                raise ValueError(f"CFPB response exceeded {_CFPB_MAX_RESPONSE_BYTES} bytes.")
            atomic_write_bytes(root, raw_path, response.content)
        raw_hash = sha256_file(raw_path)
        retrieved_at = _file_timestamp(raw_path)
        retrieved_times.append(retrieved_at)
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        metadata = payload.get("_meta", {})
        if isinstance(metadata, dict) and metadata.get("last_updated"):
            api_last_updated.add(str(metadata["last_updated"]))
        hits = payload.get("hits", {}).get("hits", [])
        if not isinstance(hits, list):
            raise ValueError("CFPB API response has no hits list.")

        selected = 0
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            source = hit.get("_source")
            if not isinstance(source, dict):
                continue
            if source.get("company_response") != response_label:
                continue
            try:
                input_record, label_record = transform_cfpb_hit(
                    hit,
                    retrieved_at=retrieved_at,
                    source_artifact_sha256=raw_hash,
                    api_url=config.api_url,
                )
            except ValueError:
                continue
            if input_record.source_record_id in selected_ids:
                continue
            selected_ids.add(input_record.source_record_id)
            inputs.append(input_record)
            labels.append(label_record)
            selected += 1
            if selected >= config.records_per_label:
                break
        if selected < config.records_per_label:
            raise ValueError(
                f"CFPB label {response_label!r} produced {selected} valid records; "
                f"{config.records_per_label} required."
            )
        artifacts.append(
            _artifact_manifest(
                root,
                raw_path,
                suite="cfpb",
                kind="raw",
                records=len(hits),
            )
        )

    return (
        inputs,
        labels,
        artifacts,
        SourceSnapshot(
            suite="cfpb",
            name="CFPB Consumer Complaint Database",
            canonical_url=config.dataset_url,
            license=config.license,
            retrieved_at=max(retrieved_times),
            details={
                "date_received_min": config.date_received_min.isoformat(),
                "date_received_max_exclusive": config.date_received_max.isoformat(),
                "records_per_response_label": config.records_per_label,
                "response_labels": config.response_labels,
                "api_last_updated": sorted(api_last_updated),
            },
        ),
    )


def _prepare_fos(
    client: httpx.Client,
    *,
    root: Path,
    config: FosSourceConfig,
    refresh: bool,
) -> tuple[
    list[BenchmarkInputRecord],
    list[BenchmarkLabelRecord],
    list[ArtifactManifest],
    SourceSnapshot,
]:
    raw_root = ensure_within(root, root / "raw" / "fos")
    inputs: list[BenchmarkInputRecord] = []
    labels: list[BenchmarkLabelRecord] = []
    artifacts: list[ArtifactManifest] = []
    retrieved_times: list[datetime] = []
    outcome_counts: Counter[str] = Counter()

    for case in config.cases:
        raw_path = raw_root / f"{case.decision_id}.pdf"
        _download_to_file(
            client,
            root=root,
            url=case.source_url,
            path=raw_path,
            max_bytes=_FOS_MAX_PDF_BYTES,
            refresh=refresh,
            expected_content_type="application/pdf",
        )
        raw_hash = sha256_file(raw_path)
        retrieved_at = _file_timestamp(raw_path)
        retrieved_times.append(retrieved_at)
        input_record, label_record = transform_fos_decision(
            _extract_pdf_text(raw_path),
            case,
            retrieved_at=retrieved_at,
            source_artifact_sha256=raw_hash,
        )
        inputs.append(input_record)
        labels.append(label_record)
        outcome_counts[label_record.payload.outcome] += 1
        artifacts.append(
            _artifact_manifest(
                root,
                raw_path,
                suite="fos",
                kind="raw",
            )
        )

    return (
        inputs,
        labels,
        artifacts,
        SourceSnapshot(
            suite="fos",
            name="Financial Ombudsman Service published decisions",
            canonical_url=config.dataset_url,
            license=config.license,
            retrieved_at=max(retrieved_times),
            details={
                "decision_ids": [case.decision_id for case in config.cases],
                "upheld": outcome_counts["upheld"],
                "partially_upheld": outcome_counts["partially_upheld"],
                "not_upheld": outcome_counts["not_upheld"],
                "raw_documents_committed": False,
            },
        ),
    )


def _prepare_uci(
    client: httpx.Client,
    *,
    root: Path,
    config: UciSourceConfig,
    refresh: bool,
) -> tuple[
    list[BenchmarkInputRecord],
    list[BenchmarkLabelRecord],
    list[ArtifactManifest],
    SourceSnapshot,
]:
    raw_root = ensure_within(root, root / "raw" / "uci")
    archive_path = raw_root / "online-retail-ii.zip"
    workbook_path = raw_root / "online_retail_II.xlsx"
    _download_to_file(
        client,
        root=root,
        url=config.download_url,
        path=archive_path,
        max_bytes=_UCI_MAX_ARCHIVE_BYTES,
        refresh=refresh,
        expected_content_type=None,
    )
    _extract_single_xlsx(
        root=root,
        archive_path=archive_path,
        workbook_path=workbook_path,
        max_bytes=_UCI_MAX_WORKBOOK_BYTES,
        refresh=refresh,
    )
    workbook_hash = sha256_file(workbook_path)
    retrieved_at = _file_timestamp(archive_path)
    parsed_rows: list[UciRow] = []
    sheet_counts: Counter[str] = Counter()
    scanned_rows = 0
    for sheet_name, row in iter_xlsx_rows(
        workbook_path,
        max_rows_per_sheet=config.max_rows_per_sheet,
    ):
        scanned_rows += 1
        sheet_counts[sheet_name] += 1
        parsed = uci_row_from_mapping(row)
        if parsed is not None:
            parsed_rows.append(parsed)

    inputs, labels = build_uci_pairs(
        parsed_rows,
        positive_pair_limit=config.positive_pairs,
        retrieved_at=retrieved_at,
        source_artifact_sha256=workbook_hash,
        source_url=config.dataset_url,
    )
    artifacts = [
        _artifact_manifest(root, archive_path, suite="uci", kind="raw"),
        _artifact_manifest(
            root,
            workbook_path,
            suite="uci",
            kind="raw",
            records=scanned_rows,
        ),
    ]
    return (
        list(inputs),
        list(labels),
        artifacts,
        SourceSnapshot(
            suite="uci",
            name="UCI Online Retail II",
            canonical_url=config.dataset_url,
            license=config.license,
            retrieved_at=retrieved_at,
            details={
                "doi": config.doi,
                "max_rows_per_sheet": config.max_rows_per_sheet,
                "scanned_rows": scanned_rows,
                "usable_rows": len(parsed_rows),
                "sheet_counts": [
                    f"{sheet_name}:{count}" for sheet_name, count in sorted(sheet_counts.items())
                ],
                "positive_pairs": config.positive_pairs,
                "negative_pairs": config.positive_pairs,
                "label_basis": "derived exact-match rule plus constructed negatives",
            },
        ),
    )


def _download_to_file(
    client: httpx.Client,
    *,
    root: Path,
    url: str,
    path: Path,
    max_bytes: int,
    refresh: bool,
    expected_content_type: str | None,
) -> None:
    destination = ensure_within(root, path)
    if destination.is_file() and not refresh:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = ensure_within(root, destination.with_name(f".{destination.name}.download"))
    written = 0
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";", maxsplit=1)[0]
            if expected_content_type and content_type != expected_content_type:
                raise ValueError(f"Unexpected content type for {url}: {content_type or 'missing'}")
            declared_size = response.headers.get("content-length")
            if declared_size and int(declared_size) > max_bytes:
                raise ValueError(f"Download exceeds the {max_bytes}-byte limit: {url}")
            with temporary.open("wb") as handle:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    written += len(chunk)
                    if written > max_bytes:
                        raise ValueError(f"Download exceeds the {max_bytes}-byte limit: {url}")
                    handle.write(chunk)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _extract_single_xlsx(
    *,
    root: Path,
    archive_path: Path,
    workbook_path: Path,
    max_bytes: int,
    refresh: bool,
) -> None:
    destination = ensure_within(root, workbook_path)
    if destination.is_file() and not refresh:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = ensure_within(root, destination.with_name(f".{destination.name}.extract"))
    try:
        with zipfile.ZipFile(archive_path) as archive:
            candidates = [
                info
                for info in archive.infolist()
                if PurePosixPath(info.filename.replace("\\", "/")).suffix.casefold() == ".xlsx"
            ]
            if len(candidates) != 1:
                raise ValueError(f"Expected one XLSX file in UCI archive; found {len(candidates)}.")
            member = candidates[0]
            member_path = PurePosixPath(member.filename.replace("\\", "/"))
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"Unsafe UCI archive member: {member.filename}")
            if member.file_size > max_bytes:
                raise ValueError("UCI workbook exceeds the configured extraction limit.")
            written = 0
            with archive.open(member) as source, temporary.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    written += len(chunk)
                    if written > max_bytes:
                        raise ValueError("UCI workbook exceeds the extraction limit.")
                    target.write(chunk)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _extract_pdf_text(path: Path) -> str:
    executable = shutil.which("pdftotext")
    if executable:
        result = subprocess.run(
            [executable, "-layout", "-enc", "UTF-8", "-nopgbrk", str(path), "-"],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return result.stdout.decode("utf-8", errors="replace")

    try:
        pypdf = importlib.import_module("pypdf")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "FOS setup requires pdftotext on PATH or an existing pypdf installation."
        ) from exc
    reader = pypdf.PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def _artifact_manifest(
    root: Path,
    path: Path,
    *,
    suite: SuiteName,
    kind: Literal["raw", "prepared_input", "prepared_label"],
    records: int | None = None,
) -> ArtifactManifest:
    resolved = ensure_within(root, path)
    return ArtifactManifest(
        suite=suite,
        kind=kind,
        path=relative_manifest_path(root, resolved),
        sha256=sha256_file(resolved),
        bytes=resolved.stat().st_size,
        records=records,
    )


def _file_timestamp(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC)


def _slug(value: str) -> str:
    return "-".join(
        part
        for part in "".join(
            character.casefold() if character.isalnum() else " " for character in value
        ).split()
    )
