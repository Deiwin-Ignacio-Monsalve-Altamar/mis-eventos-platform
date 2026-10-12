"""Prepare event images, store WebP objects, and persist gallery references."""

import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from io import BytesIO
from logging import getLogger
from typing import BinaryIO
from urllib.parse import quote, urlsplit
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import EventImageStorageError, ValidationError
from app.domain.entities.event_image import EventImageRecord
from app.domain.repositories.event_image_repository import EventImageRepository
from app.settings import (
    ALLOWED_EVENT_IMAGE_FORMATS,
    MAX_EVENT_IMAGE_COUNT,
    MAX_EVENT_IMAGE_SIZE_BYTES,
    R2_BUCKET_NAME_ENV,
    R2_PUBLIC_BASE_URL_ENV,
)

logger = getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StagedEventImages:
    """Hold uploaded references until the event database operation commits."""

    records: tuple[EventImageRecord, ...]
    client: object = field(repr=False)
    bucket: str = field(repr=False)


class EventImageService:
    """Convert images in memory and coordinate R2 with gallery persistence."""

    def __init__(
        self,
        repository: EventImageRepository,
        config: dict[str, object],
        client_factory: Callable[[], object],
    ) -> None:
        self._repository = repository
        self._config = config
        self._client_factory = client_factory

    def stage(self, files: list[BinaryIO]) -> StagedEventImages:
        """Validate, convert, and upload all files before changing database rows."""
        prepared = self._prepare(files)
        public_base_url = self._config.get(R2_PUBLIC_BASE_URL_ENV)
        bucket = self._config.get(R2_BUCKET_NAME_ENV)
        if not isinstance(public_base_url, str) or not public_base_url.strip():
            raise EventImageStorageError("Public image storage is not configured.")
        try:
            parsed_url = urlsplit(public_base_url.strip())
        except ValueError as error:
            raise EventImageStorageError(
                "Public image storage URL is invalid."
            ) from error
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise EventImageStorageError("Public image storage URL is invalid.")
        parsed_url = urlsplit(public_base_url.strip())
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise EventImageStorageError("Public image storage URL is invalid.")
        if not isinstance(bucket, str) or not bucket.strip():
            raise EventImageStorageError("Image storage is not configured.")

        try:
            client = self._client_factory()
        except Exception as error:
            raise EventImageStorageError("Image storage is unavailable.") from error

        records: list[EventImageRecord] = []
        try:
            for position, content in enumerate(prepared):
                key = f"events/{uuid4().hex}.webp"
                records.append(
                    EventImageRecord(
                        event_id=0,
                        storage_key=key,
                        url=f"{public_base_url.rstrip('/')}/{quote(key, safe='/')}",
                        position=position,
                    )
                )
                client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=content,
                    ContentType="image/webp",
                )
        except Exception as error:
            self._delete_objects(
                client, bucket, [image.storage_key for image in records]
            )
            raise EventImageStorageError("Image upload failed.") from error
        return StagedEventImages(tuple(records), client, bucket)

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
        self._delete_objects(
            staged.client, staged.bucket, [image.storage_key for image in previous]
        )
        return list(images)

    def cleanup(self, staged: StagedEventImages) -> None:
        """Remove newly uploaded objects when their database operation fails."""
        self._delete_objects(
            staged.client,
            staged.bucket,
            [image.storage_key for image in staged.records],
        )

    def stored_for_event(self, event_id: int) -> list[EventImageRecord]:
        """Return persisted image references for event deletion handling."""
        return self._repository.list_by_event(event_id)

    def prepare_deletion(self, images: list[EventImageRecord]):
        """Validate storage configuration before deleting the event row."""
        if not images:
            return None
        bucket = self._config.get(R2_BUCKET_NAME_ENV)
        if not isinstance(bucket, str) or not bucket.strip():
            raise EventImageStorageError("Image storage is not configured.")
        try:
            return self._client_factory(), bucket
        except Exception as error:
            raise EventImageStorageError("Image storage is unavailable.") from error

    def delete_stored(self, images: list[EventImageRecord], deletion) -> None:
        """Delete object files after their database references have been removed."""
        if not images or deletion is None:
            return
        client, bucket = deletion
        self._delete_objects(client, bucket, [image.storage_key for image in images])

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
    def _delete_objects(client: object, bucket: str, keys: list[str]) -> None:
        if not keys:
            return
        try:
            result = client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": key} for key in keys], "Quiet": True},
            )
            if result.get("Errors"):
                logger.warning("Some event image objects could not be removed.")
        except Exception:
            logger.warning("Could not remove stored event images.")
