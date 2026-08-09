from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

ALLOWED_SUFFIXES = frozenset({".wav", ".mp3", ".json", ".tmp", ".cache"})


@dataclass(frozen=True)
class DataPaths:
    root: Path
    references: Path
    consent: Path
    generated: Path
    cache: Path
    temporary: Path


@dataclass(frozen=True)
class DeletionTargets:
    reference_audio: tuple[Path, ...] = ()
    consent_audio: tuple[Path, ...] = ()
    cache: tuple[Path, ...] = ()
    generated_audio: tuple[Path, ...] = ()
    sidecars: tuple[Path, ...] = ()
    temporary: tuple[Path, ...] = ()

    def categories(self) -> dict[str, tuple[Path, ...]]:
        return {
            "reference_audio": self.reference_audio,
            "consent_audio": self.consent_audio,
            "cache": self.cache,
            "generated_audio": self.generated_audio,
            "sidecars": self.sidecars,
            "temporary": self.temporary,
        }

    def all_paths(self) -> tuple[Path, ...]:
        return tuple(
            path for paths in self.categories().values() for path in paths
        )


def create_data_directories(root: Path) -> DataPaths:
    paths = DataPaths(
        root=root,
        references=root / "references",
        consent=root / "consent",
        generated=root / "generated",
        cache=root / "cache",
        temporary=root / "tmp",
    )
    for path in (
        paths.root,
        paths.references,
        paths.consent,
        paths.generated,
        paths.cache,
        paths.temporary,
    ):
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)
    return paths


def storage_path(
    directory: Path,
    identifier: UUID | str,
    suffix: str,
) -> Path:
    asset_id = identifier if isinstance(identifier, UUID) else UUID(identifier)
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"Unsupported storage suffix: {suffix}")
    return directory / f"{asset_id.hex}{suffix}"


def download_filename(job_id: UUID | str, generated_at: datetime) -> str:
    identifier = job_id if isinstance(job_id, UUID) else UUID(job_id)
    if generated_at.tzinfo is None:
        raise ValueError("generated_at must include a timezone")
    timestamp = generated_at.astimezone(UTC).strftime("%Y%m%d_%H%M%S")
    return f"koeclone_{timestamp}_{identifier.hex[:8]}.wav"


def collect_deletion_targets(
    paths: DataPaths,
    *,
    reference_id: UUID | str,
    consent_id: UUID | str | None,
    job_ids: Sequence[UUID | str],
) -> DeletionTargets:
    consent_audio = (
        ()
        if consent_id is None
        else (storage_path(paths.consent, consent_id, ".wav"),)
    )
    return DeletionTargets(
        reference_audio=(storage_path(paths.references, reference_id, ".wav"),),
        consent_audio=consent_audio,
        cache=(storage_path(paths.cache, reference_id, ".cache"),),
        generated_audio=tuple(
            storage_path(paths.generated, job_id, ".wav") for job_id in job_ids
        ),
        sidecars=tuple(
            storage_path(paths.generated, job_id, ".json") for job_id in job_ids
        ),
        temporary=tuple(
            sorted(
                path
                for path in paths.temporary.rglob("*")
                if path.is_file() or path.is_symlink()
            )
        ),
    )


def delete_targets(data_root: Path, targets: DeletionTargets) -> None:
    root = data_root.resolve()
    resolved_targets: list[Path] = []
    for path in targets.all_paths():
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError(f"Deletion target is outside data root: {path}")
        resolved_targets.append(resolved)

    for path in resolved_targets:
        path.unlink(missing_ok=True)
