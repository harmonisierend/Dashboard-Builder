"""Filesystem storage for uploaded design-reference images.

No DB row is created for a raw upload -- it's an ephemeral working file
under /data/uploads/<uuid>.<ext>, per the M1-session decision that full
upload/generation history is Milestone 6's ("Projekte") concern, not M2's.
Only an explicit "save as preset" action (see routes_design.py) creates a
TokenPreset row.

`resolve()` treats the incoming `upload_id` as untrusted input even though
it round-trips through our own client: it must be a well-formed UUID
*before* it's ever joined into a filesystem path, ruling out path
traversal regardless of what a client sends.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal, cast

# Matches (a subset of) anthropic.types.Base64ImageSourceParam's media_type
# Literal, so a validated upload's media type flows straight into the
# vision call without a cast at that boundary.
AllowedMediaType = Literal["image/png", "image/jpeg", "image/webp"]

ALLOWED_MEDIA_TYPES: dict[AllowedMediaType, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}

# Raw bytes, not the base64-encoded payload size. Base64 inflates by ~4/3,
# so 6,000,000 raw bytes -> ~8MB encoded, safely under the Anthropic direct
# API's documented 10MB (base64-encoded) per-image limit.
MAX_UPLOAD_BYTES = 6_000_000


class UploadValidationError(ValueError):
    """Raised when an upload fails MIME-type or size validation."""


class DesignUploadStore:
    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir / "uploads"

    def save(self, content: bytes, media_type: str) -> tuple[str, Path]:
        if media_type not in ALLOWED_MEDIA_TYPES:
            raise UploadValidationError(
                f"Nicht unterstützter Dateityp: {media_type}. "
                f"Erlaubt sind PNG, JPEG und WebP."
            )
        if len(content) > MAX_UPLOAD_BYTES:
            max_mb = MAX_UPLOAD_BYTES / 1_000_000
            raise UploadValidationError(
                f"Datei ist zu groß (Limit: {max_mb:.1f} MB)."
            )

        validated_media_type = cast(AllowedMediaType, media_type)
        self._dir.mkdir(parents=True, exist_ok=True)
        upload_id = str(uuid.uuid4())
        path = self._dir / f"{upload_id}{ALLOWED_MEDIA_TYPES[validated_media_type]}"
        path.write_bytes(content)
        return upload_id, path

    def resolve(self, upload_id: str) -> Path | None:
        try:
            uuid.UUID(upload_id)
        except ValueError:
            return None

        for extension in ALLOWED_MEDIA_TYPES.values():
            candidate = self._dir / f"{upload_id}{extension}"
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def media_type_for(path: Path) -> AllowedMediaType | None:
        for media_type, extension in ALLOWED_MEDIA_TYPES.items():
            if path.suffix == extension:
                return media_type
        return None
