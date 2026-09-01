from __future__ import annotations

from pathlib import Path

import pytest

from dashboard_studio.design.uploads import (
    ALLOWED_MEDIA_TYPES,
    MAX_UPLOAD_BYTES,
    DesignUploadStore,
    UploadValidationError,
)


@pytest.mark.parametrize("media_type", list(ALLOWED_MEDIA_TYPES))
def test_save_and_resolve_round_trip(tmp_path: Path, media_type: str) -> None:
    store = DesignUploadStore(tmp_path)

    upload_id, path = store.save(b"fake-image-bytes", media_type)
    resolved = store.resolve(upload_id)

    assert resolved == path
    assert resolved is not None
    assert resolved.read_bytes() == b"fake-image-bytes"
    assert DesignUploadStore.media_type_for(resolved) == media_type


def test_disallowed_media_type_rejected(tmp_path: Path) -> None:
    store = DesignUploadStore(tmp_path)
    with pytest.raises(UploadValidationError):
        store.save(b"data", "application/pdf")


def test_oversized_content_rejected(tmp_path: Path) -> None:
    store = DesignUploadStore(tmp_path)
    with pytest.raises(UploadValidationError):
        store.save(b"x" * (MAX_UPLOAD_BYTES + 1), "image/png")


def test_content_at_exactly_the_limit_is_accepted(tmp_path: Path) -> None:
    store = DesignUploadStore(tmp_path)
    upload_id, _path = store.save(b"x" * MAX_UPLOAD_BYTES, "image/png")
    assert store.resolve(upload_id) is not None


@pytest.mark.parametrize(
    "candidate",
    ["../../etc/passwd", "not-a-uuid", "", "../secrets", "00000000-0000-0000-0000-00000000000g"],
)
def test_resolve_rejects_non_uuid_input(tmp_path: Path, candidate: str) -> None:
    store = DesignUploadStore(tmp_path)
    assert store.resolve(candidate) is None


def test_resolve_returns_none_for_unknown_but_well_formed_uuid(tmp_path: Path) -> None:
    store = DesignUploadStore(tmp_path)
    assert store.resolve("00000000-0000-0000-0000-000000000000") is None


def test_media_type_for_unknown_extension_returns_none(tmp_path: Path) -> None:
    unrelated = tmp_path / "file.txt"
    assert DesignUploadStore.media_type_for(unrelated) is None
