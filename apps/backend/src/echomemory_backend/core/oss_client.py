"""OSS（阿里云对象存储服务）客户端封装 —— 异步接口，同步实现跑在线程池中。"""

import uuid
from typing import BinaryIO

import oss2
from anyio import to_thread

from echomemory_backend.core.config import settings
from echomemory_backend.core.image_utils import compress_image_to_memory


def _get_bucket() -> oss2.Bucket:
    """返回一个已初始化的 OSS Bucket 实例。

    Raises:
        RuntimeError: 当任一必需的 OSS 配置缺失时抛出。
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


def _build_oss_url(object_key: str) -> str:
    """根据 object_key 构建公开访问 URL。"""
    endpoint = (settings.oss_endpoint or "").removeprefix("https://").removeprefix("http://")
    return f"https://{settings.oss_bucket_name}.{endpoint}/{object_key}"


# ---------------------------------------------------------------------------
# 同步内部实现
# ---------------------------------------------------------------------------

def _upload_image_to_oss_sync(
    file: BinaryIO,
    folder: str,
    filename_prefix: str = "",
    ext: str = "jpg",
) -> str:
    """压缩图像并上传到 OSS（同步实现）。"""
    bucket = _get_bucket()
    compressed = compress_image_to_memory(file)
    object_key = f"{folder}/{filename_prefix}_{uuid.uuid4().hex}.{ext}"
    try:
        bucket.put_object(object_key, compressed)
    except oss2.exceptions.OssError as exc:
        raise RuntimeError(f"OSS upload failed: {exc}") from exc
    return _build_oss_url(object_key)


_MAX_AUDIO_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
_MAX_LYRICS_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB

_ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/flac",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/aac",
}

_ALLOWED_LYRICS_TYPES = {
    "text/plain",
    "application/octet-stream",
}


def _upload_file_to_oss_sync(
    file: BinaryIO,
    folder: str,
    filename_prefix: str,
    ext: str,
    allowed_types: set[str],
    max_size: int,
) -> str:
    """通用文件上传到 OSS（同步实现）。"""
    content_type = getattr(file, "content_type", None)
    if content_type is not None and content_type not in allowed_types:
        raise ValueError(
            f"Invalid file type: {content_type}. Allowed: {', '.join(allowed_types)}"
        )

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > max_size:
        raise ValueError(
            f"File too large: {size} bytes. Maximum allowed: {max_size} bytes"
        )

    bucket = _get_bucket()
    object_key = f"{folder}/{filename_prefix}_{uuid.uuid4().hex}.{ext}"

    try:
        bucket.put_object(object_key, file)
    except oss2.exceptions.OssError as exc:
        raise RuntimeError(f"OSS upload failed: {exc}") from exc

    return _build_oss_url(object_key)


def _delete_object_by_url_sync(url: str) -> None:
    """根据 URL 删除 OSS 对象（同步实现）。删除失败时静默忽略。"""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    object_key = parsed.path.lstrip("/")
    if not object_key:
        return
    try:
        bucket = _get_bucket()
        bucket.delete_object(object_key)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 异步公开接口
# ---------------------------------------------------------------------------

async def upload_image_to_oss(
    file: BinaryIO,
    folder: str,
    filename_prefix: str = "",
    ext: str = "jpg",
) -> str:
    """压缩图像并上传到 OSS。

    Args:
        file: 包含原始图像数据的类文件对象。
        folder: Bucket 中的目标文件夹路径（例如 avatars）。
        filename_prefix: 生成文件名时使用的前缀（例如用户 ID）。
        ext: 存储对象的文件扩展名（默认 jpg）。

    Returns:
        上传对象的公开访问 URL。

    Raises:
        RuntimeError: OSS 未配置或上传失败时抛出。
        ValueError: 文件不是有效图像时抛出。
    """
    return await to_thread.run_sync(
        _upload_image_to_oss_sync, file, folder, filename_prefix, ext
    )


async def upload_audio_to_oss(
    file: BinaryIO,
    prefix: str = "temp",
    ext: str = "mp3",
) -> str:
    """上传音频文件到 OSS。"""
    return await to_thread.run_sync(
        _upload_file_to_oss_sync,
        file,
        "musics",
        prefix,
        ext,
        _ALLOWED_AUDIO_TYPES,
        _MAX_AUDIO_SIZE_BYTES,
    )


async def upload_lyrics_to_oss(
    file: BinaryIO,
    prefix: str = "temp",
    ext: str = "lrc",
) -> str:
    """上传歌词文件到 OSS。"""
    return await to_thread.run_sync(
        _upload_file_to_oss_sync,
        file,
        "lyrics",
        prefix,
        ext,
        _ALLOWED_LYRICS_TYPES,
        _MAX_LYRICS_SIZE_BYTES,
    )


async def delete_object_by_url(url: str) -> None:
    """根据 URL 删除 OSS 对象。删除失败时静默忽略。"""
    await to_thread.run_sync(_delete_object_by_url_sync, url)
