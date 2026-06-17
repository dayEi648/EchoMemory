"""OSS（阿里云对象存储服务）客户端封装 —— 异步接口，同步实现跑在线程池中。"""

import logging
import uuid
from typing import BinaryIO

import oss2
from anyio import to_thread

from echomemory_backend.core.config import settings
from echomemory_backend.core.utils.image_utils import compress_image_to_memory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 音频文件 magic header 校验
# ---------------------------------------------------------------------------

_AUDIO_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"ID3", "mp3"),
    (b"\xff\xfb", "mp3"),
    (b"\xff\xf3", "mp3"),
    (b"\xff\xf2", "mp3"),
    (b"\xff\xf1", "aac"),
    (b"fLaC", "flac"),
    (b"OggS", "ogg"),
]


def _detect_audio_format(file: BinaryIO) -> str | None:
    """读取文件 magic header 检测真实音频格式。

    Args:
        file: 类文件对象。

    Returns:
        检测到的扩展名，无法识别时返回 None。
    """
    header = file.read(16)
    file.seek(0)

    for sig, ext in _AUDIO_MAGIC_SIGNATURES:
        if header.startswith(sig):
            return ext

    # WAV: RIFF....WAVE
    if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WAVE":
        return "wav"

    return None


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
# 内容类型到扩展名的安全映射
# ---------------------------------------------------------------------------

_CONTENT_TYPE_TO_EXT = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/flac": "flac",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/aac": "aac",
    "text/plain": "lrc",
    "application/octet-stream": "lrc",
}

_DANGEROUS_EXTS = {"exe", "bat", "sh", "cmd", "ps1", "dll", "jar", "msi", "vbs", "js"}


def _resolve_ext(file: BinaryIO, fallback_ext: str) -> str:
    """根据文件的 content_type 映射安全扩展名，未映射时使用 fallback_ext。"""
    content_type = getattr(file, "content_type", None)
    if content_type in _CONTENT_TYPE_TO_EXT:
        return _CONTENT_TYPE_TO_EXT[content_type]
    return fallback_ext


def _resolve_audio_ext(file: BinaryIO, fallback_ext: str) -> str:
    """根据 magic header 检测音频真实格式并决定扩展名。

    若声明的 content_type 与检测结果不兼容则拒绝上传。

    Args:
        file: 类文件对象。
        fallback_ext: 无法从 content_type 校验时使用的回退扩展名。

    Returns:
        安全的音频文件扩展名。

    Raises:
        ValueError: 无法识别音频格式或 content_type 与检测结果不兼容时抛出。
    """
    detected = _detect_audio_format(file)
    if detected is None:
        raise ValueError(
            "Invalid audio file: format not recognized from file header"
        )

    content_type = getattr(file, "content_type", None)
    if content_type is not None:
        expected_ext = _CONTENT_TYPE_TO_EXT.get(content_type)
        if expected_ext is not None and expected_ext != detected:
            raise ValueError(
                f"content_type {content_type} does not match detected audio format {detected}"
            )

    return detected


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


_MAX_AUDIO_SIZE_BYTES = 30 * 1024 * 1024  # 30 MB
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

    # 对音频文件做 magic header 校验，扩展名以检测结果为准
    if allowed_types == _ALLOWED_AUDIO_TYPES:
        resolved_ext = _resolve_audio_ext(file, ext)
    else:
        resolved_ext = _resolve_ext(file, ext)
    if resolved_ext.lower() in _DANGEROUS_EXTS:
        raise ValueError(f"Dangerous file extension not allowed: {resolved_ext}")

    bucket = _get_bucket()
    object_key = f"{folder}/{filename_prefix}_{uuid.uuid4().hex}.{resolved_ext}"

    try:
        bucket.put_object(object_key, file)
    except oss2.exceptions.OssError as exc:
        raise RuntimeError(f"OSS upload failed: {exc}") from exc

    return _build_oss_url(object_key)


def _object_key_from_url(url: str) -> str | None:
    """从 OSS 公开 URL 解析 object_key。

    Args:
        url: OSS 对象的公开访问 URL。

    Returns:
        合法的 object_key；URL 不属于本项目 bucket 时返回 None。
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    endpoint = (settings.oss_endpoint or "").removeprefix("https://").removeprefix("http://")
    expected_host = f"{settings.oss_bucket_name}.{endpoint}"
    if parsed.netloc != expected_host:
        return None
    object_key = parsed.path.lstrip("/")
    return object_key or None


def _sign_url_by_url_sync(url: str, expires_seconds: int = 600) -> str:
    """根据 OSS URL 生成临时签名访问 URL。

    Args:
        url: 本项目 OSS 对象 URL。
        expires_seconds: 签名 URL 有效期秒数，默认 10 分钟。

    Returns:
        临时签名 URL。

    Raises:
        ValueError: URL 非法时抛出。
        RuntimeError: OSS 签名失败时抛出。
    """
    object_key = _object_key_from_url(url)
    if not object_key:
        raise ValueError(f"Invalid OSS URL: {url}")

    try:
        bucket = _get_bucket()
        return bucket.sign_url("GET", object_key, expires_seconds)
    except oss2.exceptions.OssError as exc:
        raise RuntimeError(f"OSS sign url failed: {exc}") from exc


def _delete_object_by_url_sync(url: str) -> None:
    """根据 URL 删除 OSS 对象（同步实现）。删除失败时记录日志但不抛异常。

    删除前校验 URL 的 host 是否属于本项目 bucket，以及 object_key
    是否以预期的业务前缀开头，防止误删或处理外部 URL。
    """
    object_key = _object_key_from_url(url)
    if not object_key:
        logger.warning("Refusing to delete OSS object from foreign or invalid URL: %s", url)
        return

    # 校验 object_key 是否以允许的业务前缀开头
    _ALLOWED_PREFIXES = (
        "avatars/",
        "album_covers/",
        "playlist_covers/",
        "music_covers/",
        "musics/",
        "lyrics/",
        "space_post_images/",
    )
    if not any(object_key.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
        logger.warning(
            "Refusing to delete OSS object with disallowed prefix: %s",
            object_key,
        )
        return

    try:
        bucket = _get_bucket()
        bucket.delete_object(object_key)
    except Exception as exc:
        logger.warning(
            "Failed to delete OSS object: %s, url=%s, object_key=%s",
            exc,
            url,
            object_key,
        )


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
    """根据 URL 删除 OSS 对象。删除失败时记录日志但不抛异常。"""
    await to_thread.run_sync(_delete_object_by_url_sync, url)


async def sign_url_by_url(url: str, expires_seconds: int = 600) -> str:
    """根据 OSS URL 异步生成临时签名访问 URL。"""
    return await to_thread.run_sync(_sign_url_by_url_sync, url, expires_seconds)
