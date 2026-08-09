import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from koeclone.storage.files import (
    DeletionTargets,
    collect_deletion_targets,
    create_data_directories,
    delete_targets,
    download_filename,
    storage_path,
)

ASSET_ID = UUID("12345678-1234-5678-1234-567812345678")
CONSENT_ID = UUID("22345678-1234-5678-1234-567812345678")
JOB_ID = UUID("32345678-1234-5678-1234-567812345678")


def test_creates_private_data_directories(tmp_path: Path) -> None:
    paths = create_data_directories(tmp_path / "koeclone-data")

    for path in (
        paths.root,
        paths.references,
        paths.consent,
        paths.generated,
        paths.cache,
        paths.temporary,
    ):
        assert path.is_dir()
        assert path.stat().st_mode & 0o777 == 0o700


def test_storage_name_uses_uuid_only(tmp_path: Path) -> None:
    paths = create_data_directories(tmp_path / "data")

    path = storage_path(paths.references, ASSET_ID, ".wav")

    assert path == paths.references / f"{ASSET_ID.hex}.wav"


@pytest.mark.parametrize(
    "untrusted_identifier",
    ["../etc/passwd", "/etc/passwd", "../../outside"],
)
def test_rejects_non_uuid_identifier(
    tmp_path: Path, untrusted_identifier: str
) -> None:
    paths = create_data_directories(tmp_path / "data")

    with pytest.raises(ValueError):
        storage_path(paths.references, untrusted_identifier, ".wav")

    assert not (tmp_path / "outside").exists()


def test_rejects_unapproved_suffix(tmp_path: Path) -> None:
    paths = create_data_directories(tmp_path / "data")

    with pytest.raises(ValueError):
        storage_path(paths.references, ASSET_ID, "/../../escape")


def test_builds_download_filename() -> None:
    generated_at = datetime(2026, 8, 10, 12, 34, 56, tzinfo=UTC)

    filename = download_filename(ASSET_ID, generated_at)

    assert filename == "koeclone_20260810_123456_12345678.wav"
    assert re.fullmatch(
        r"koeclone_\d{8}_\d{6}_[0-9a-f]{8}\.wav", filename
    )


def test_deletion_targets_cover_all_six_categories(tmp_path: Path) -> None:
    paths = create_data_directories(tmp_path / "data")
    (paths.temporary / "upload.tmp").write_bytes(b"temporary")

    targets = collect_deletion_targets(
        paths,
        reference_id=ASSET_ID,
        consent_id=CONSENT_ID,
        job_ids=[JOB_ID],
    )

    assert len(targets.all_paths()) == 6
    assert all(targets.categories().values())


def test_collected_targets_remove_every_file_under_data_root(tmp_path: Path) -> None:
    paths = create_data_directories(tmp_path / "data")
    expected_files = [
        storage_path(paths.references, ASSET_ID, ".wav"),
        storage_path(paths.consent, CONSENT_ID, ".wav"),
        storage_path(paths.cache, ASSET_ID, ".cache"),
        storage_path(paths.generated, JOB_ID, ".wav"),
        storage_path(paths.generated, JOB_ID, ".json"),
        paths.temporary / "nested" / "upload.tmp",
    ]
    for path in expected_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    targets = collect_deletion_targets(
        paths,
        reference_id=ASSET_ID,
        consent_id=CONSENT_ID,
        job_ids=[JOB_ID],
    )

    delete_targets(paths.root, targets)

    assert [path for path in paths.root.rglob("*") if path.is_file()] == []


def test_upload_mode_omits_only_consent_audio(tmp_path: Path) -> None:
    paths = create_data_directories(tmp_path / "data")
    (paths.temporary / "upload.tmp").write_bytes(b"temporary")

    targets = collect_deletion_targets(
        paths,
        reference_id=ASSET_ID,
        consent_id=None,
        job_ids=[JOB_ID],
    )

    assert targets.consent_audio == ()
    assert all(
        paths
        for name, paths in targets.categories().items()
        if name != "consent_audio"
    )


def test_collects_profile_files_when_there_are_no_jobs(tmp_path: Path) -> None:
    paths = create_data_directories(tmp_path / "data")
    (paths.temporary / "upload.tmp").write_bytes(b"temporary")

    targets = collect_deletion_targets(
        paths,
        reference_id=ASSET_ID,
        consent_id=CONSENT_ID,
        job_ids=[],
    )

    assert targets.reference_audio
    assert targets.consent_audio
    assert targets.cache
    assert targets.temporary
    assert targets.generated_audio == ()
    assert targets.sidecars == ()


def test_deletes_all_profile_files(tmp_path: Path) -> None:
    paths = create_data_directories(tmp_path / "data")
    targets = DeletionTargets(
        reference_audio=(paths.references / "reference.wav",),
        consent_audio=(paths.consent / "consent.wav",),
        cache=(paths.cache / "voice.cache",),
        generated_audio=(paths.generated / "job.wav",),
        sidecars=(paths.generated / "job.json",),
        temporary=(paths.temporary / "upload.tmp",),
    )
    for path in targets.all_paths():
        path.write_bytes(b"fixture")

    delete_targets(paths.root, targets)

    assert all(not path.exists() for path in targets.all_paths())


def test_refuses_to_delete_outside_data_root(tmp_path: Path) -> None:
    paths = create_data_directories(tmp_path / "data")
    outside = tmp_path / "keep.txt"
    outside.write_text("keep", encoding="utf-8")
    targets = DeletionTargets(reference_audio=(outside,))

    with pytest.raises(ValueError):
        delete_targets(paths.root, targets)

    assert outside.exists()
