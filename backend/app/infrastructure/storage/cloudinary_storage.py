"""Adapt Cloudinary's Python SDK to the event image storage workflow."""

from collections.abc import Mapping
from io import BytesIO
from urllib.parse import urlsplit

import cloudinary
import cloudinary.uploader

from app.settings import CLOUDINARY_URL_ENV


class CloudinaryStorage:
    """Upload processed event images and delete them by Cloudinary public ID."""

    def upload(self, content: bytes, public_id: str) -> dict[str, object]:
        """Upload one already converted WebP and return the SDK response."""
        return cloudinary.uploader.upload(
            BytesIO(content),
            public_id=public_id,
            resource_type="image",
            format="webp",
            overwrite=False,
            unique_filename=False,
        )

    def delete(self, public_id: str) -> dict[str, object]:
        """Delete one image by its persisted public ID and invalidate its CDN URL."""
        return cloudinary.uploader.destroy(
            public_id,
            resource_type="image",
            invalidate=True,
        )


def create_cloudinary_storage(config: Mapping[str, object]) -> CloudinaryStorage:
    """Configure the SDK lazily, validating CLOUDINARY_URL without logging it."""
    cloudinary_url = config.get(CLOUDINARY_URL_ENV)
    if not isinstance(cloudinary_url, str) or not cloudinary_url.strip():
        raise ValueError("Cloudinary is not configured.")

    try:
        parsed_url = urlsplit(cloudinary_url.strip())
        if (
            parsed_url.scheme != "cloudinary"
            or not parsed_url.hostname
            or not parsed_url.username
            or not parsed_url.password
            or parsed_url.path
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError
    except ValueError as error:
        raise ValueError("Cloudinary configuration is invalid.") from error

    cloudinary.config(
        cloud_name=parsed_url.hostname,
        api_key=parsed_url.username,
        api_secret=parsed_url.password,
        secure=True,
    )
    return CloudinaryStorage()
