"""Prepare event images, store WebP objects, and persist gallery references."""

import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from io import BytesIO
from logging import getLogger
from traceback import format_tb
from typing import BinaryIO
from urllib.parse import urlsplit
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import EventImageStorageError, ValidationError
from app.domain.entities.event_image import EventImageRecord
from app.domain.repositories.event_image_repository import EventImageRepository
from app.settings import (
    ALLOWED_EVENT_IMAGE_FORMATS,
    EVENT_IMAGE_FOLDER,
    MAX_EVENT_IMAGE_COUNT,
    MAX_EVENT_IMAGE_SIZE_BYTES,
)

logger = getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StagedEventImages:
    """Hold uploaded references until the event database operation commits."""

    records: tuple[EventImageRecord, ...]
    storage: object = field(repr=False)


class EventImageService:
    """Convert images in memory and coordinate Cloudinary with persistence."""

    def __init__(
        self,
        repository: EventImageRepository,
        client_factory: Callable[[], object],
    ) -> None:
        self._repository = repository
        self._client_factory = client_factory

    def stage(self, files: list[BinaryIO]) -> StagedEventImages:
        """Validate, convert, and upload all files before changing database rows."""
        prepared = self._prepare(files)
        try:
            storage = self._client_factory()
        except Exception as error:
            raise EventImageStorageError("Image storage is unavailable.") from error

        records: list[EventImageRecord] = []
        cleanup_public_ids: list[str] = []
        try:
            for position, content in enumerate(prepared):
                requested_public_id = f"{EVENT_IMAGE_FOLDER}/{uuid4().hex}"
                response = storage.upload(content, requested_public_id)
                public_id = response.get("public_id")
                secure_url = response.get("secure_url")
                if public_id != requested_public_id:
                    raise ValueError("Cloudinary did not return an image identifier.")
                # Only compensate assets confirmed by a successful provider response.
                cleanup_public_ids.append(public_id)
                if not isinstance(secure_url, str):
                    raise TypeError("Cloudinary did not return a secure image URL.")
                parsed_url = urlsplit(secure_url)
                if parsed_url.scheme != "https" or not parsed_url.netloc:
                    raise ValueError("Cloudinary returned an invalid secure image URL.")
                records.append(
                    EventImageRecord(
                        event_id=0,
                        storage_key=public_id,
                        url=secure_url,
                        position=position,
                    )
                )
        except Exception as error:
            logger.error(
                "Cloudinary event image upload failed; error_type=%s.",
                type(error).__name__,
            )
            logger.debug(
                "Cloudinary upload traceback:\n%s",
                "".join(format_tb(error.__traceback__)),
            )
            self._delete_objects(storage, cleanup_public_ids)
            raise EventImageStorageError("Image upload failed.") from error
        return StagedEventImages(tuple(records), storage)

    def replace(
        self, event_id: int, staged: StagedEventImages
    ) -> list[EventImageRecord]:
        """Commit the new gallery before removing any superseded objects."""
        images = tuple(
            EventImageRecord(
                event_id=event_id,
                storage_key=image.storage_key,
                url=image.url,
                position=image.position,
            )
            for image in staged.records
        )
        try:
            previous = self._repository.replace_for_event(event_id, list(images))
        except Exception as error:
            raise EventImageStorageError(
                "Image metadata could not be saved."
            ) from error
        self._delete_objects(staged.storage, [image.storage_key for image in previous])
        return list(images)

    def cleanup(self, staged: StagedEventImages) -> None:
        """Remove newly uploaded objects when their database operation fails."""
        self._delete_objects(
            staged.storage, [image.storage_key for image in staged.records]
        )

    def stored_for_event(self, event_id: int) -> list[EventImageRecord]:
        """Return persisted image references for event deletion handling."""
        return self._repository.list_by_event(event_id)

    def prepare_deletion(self, images: list[EventImageRecord]):
        """Validate storage configuration before deleting the event row."""
        if not images:
            return None
        public_ids = self._cloudinary_public_ids(images)
        if not public_ids:
            return None
        try:
            return self._client_factory()
        except Exception as error:
            raise EventImageStorageError("Image storage is unavailable.") from error

    def delete_stored(self, images: list[EventImageRecord], deletion) -> None:
        """Delete object files after their database references have been removed."""
        if not images or deletion is None:
            return
        self._delete_objects(deletion, [image.storage_key for image in images])

    @staticmethod
    def _prepare(files: list[BinaryIO]) -> list[bytes]:
        if not files:
            return []
        if len(files) > MAX_EVENT_IMAGE_COUNT:
            raise ValidationError(
                f"An event can have at most {MAX_EVENT_IMAGE_COUNT} images."
            )

        prepared: list[bytes] = []
        for file in files:
            content = file.read(MAX_EVENT_IMAGE_SIZE_BYTES + 1)
            if len(content) > MAX_EVENT_IMAGE_SIZE_BYTES:
                raise ValidationError("Each event image must be 5 MB or smaller.")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(BytesIO(content)) as image:
                        image_format = image.format
                        image.verify()
                if image_format not in ALLOWED_EVENT_IMAGE_FORMATS:
                    raise ValidationError("Event images must be JPEG, PNG, or WebP.")
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(BytesIO(content)) as image:
                        image = ImageOps.exif_transpose(image)
                        mode = "RGBA" if "A" in image.getbands() else "RGB"
                        output = BytesIO()
                        image.convert(mode).save(output, format="WEBP", quality=85)
                        prepared.append(output.getvalue())
            except ValidationError:
                raise
            except (
                UnidentifiedImageError,
                OSError,
                ValueError,
                SyntaxError,
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
            ) as error:
                raise ValidationError(
                    "The uploaded file is not a valid image."
                ) from error
        return prepared

    @staticmethod
    def _cloudinary_public_ids(images: list[EventImageRecord]) -> list[str]:
        return [
            image.storage_key
            for image in images
            if image.storage_key.startswith(f"{EVENT_IMAGE_FOLDER}/")
        ]

    @staticmethod
    def _delete_objects(storage: object, public_ids: list[str]) -> None:
        for public_id in public_ids:
            if not public_id.startswith(f"{EVENT_IMAGE_FOLDER}/"):
                continue
            try:
                result = storage.delete(public_id)
                if result.get("result") not in {"ok", "not found"}:
                    logger.warning("A Cloudinary event image could not be removed.")
            except Exception as error:  # noqa: BLE001 - cleanup must not mask the original failure
                # Provider exception text can contain request details. Keep the stack
                # frames and exception type for local diagnosis without logging values.
                logger.warning(
                    "Could not remove stored event images; error_type=%s.",
                    type(error).__name__,
                )
                logger.debug(
                    "Cloudinary cleanup traceback:\n%s",
                    "".join(format_tb(error.__traceback__)),
                )
