"""Create an S3-compatible client for Cloudflare R2 on explicit use."""

from collections.abc import Mapping

import boto3

from app.settings import (
    R2_ACCESS_KEY_ID_ENV,
    R2_ACCOUNT_ID_ENV,
    R2_BUCKET_NAME_ENV,
    R2_SECRET_ACCESS_KEY_ENV,
)

_REQUIRED_R2_SETTINGS = (
    R2_ACCOUNT_ID_ENV,
    R2_ACCESS_KEY_ID_ENV,
    R2_SECRET_ACCESS_KEY_ENV,
    R2_BUCKET_NAME_ENV,
)


def create_r2_client(config: Mapping[str, object]) -> object:
    """Create the configured R2 S3 client without making a network request."""
    values = {name: config.get(name) for name in _REQUIRED_R2_SETTINGS}
    missing = [
        name
        for name, value in values.items()
        if not isinstance(value, str) or not value.strip()
    ]
    if missing:
        raise ValueError(
            "Cloudflare R2 configuration is incomplete: " + ", ".join(missing)
        )

    account_id = str(values[R2_ACCOUNT_ID_ENV]).strip()
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=str(values[R2_ACCESS_KEY_ID_ENV]).strip(),
        aws_secret_access_key=str(values[R2_SECRET_ACCESS_KEY_ENV]).strip(),
        region_name="auto",
    )
