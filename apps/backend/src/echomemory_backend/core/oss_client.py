"""OSS (Aliyun Object Storage Service) client wrapper."""

import uuid
from typing import BinaryIO

import oss2

from echomemory_backend.core.config import settings
from echomemory_backend.core.image_utils import compress_image_to_memory


def _get_bucket() -> oss2.Bucket:
    """Return an initialized OSS Bucket instance.

    Raises:
        RuntimeError: If any required OSS configuration is missing.
    """
    required = {
        "OSS_ACCESS_KEY_ID": settings.oss_access_key_id,
        "OSS_ACCESS_KEY_SECRET": settings.oss_access_key_secret,
        "OSS_ENDPOINT": settings.oss_endpoint,
        "OSS_BUCKET_NAME": settings.oss_bucket_name,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"Missing OSS configuration: {', '.join(missing)}")

    auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
    return oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket_name)


def upload_image_to_oss(
    file: BinaryIO,
    folder: str,
    filename_prefix: str = "",
    ext: str = "jpg",
) -> str:
    """Compress an image and upload it to OSS.

    Args:
        file: A file-like object containing the original image data.
        folder: Destination folder path inside the bucket (e.g. ``avatars``).
        filename_prefix: Prefix for the generated filename (e.g. user id).
        ext: File extension for the stored object (default ``jpg``).

    Returns:
        The public URL of the uploaded object.

    Raises:
        RuntimeError: If OSS is not configured or the upload fails.
        ValueError: If the file is not a valid image.
    """
    bucket = _get_bucket()

    compressed = compress_image_to_memory(file)
    object_key = f"{folder}/{filename_prefix}_{uuid.uuid4().hex}.{ext}"

    try:
        bucket.put_object(object_key, compressed)
    except oss2.exceptions.OssError as exc:
        raise RuntimeError(f"OSS upload failed: {exc}") from exc

    # Build URL: https://bucket.endpoint/object_key
    url = f"https://{settings.oss_bucket_name}.{settings.oss_endpoint.lstrip('https://').lstrip('http://')}/{object_key}"
    return url
