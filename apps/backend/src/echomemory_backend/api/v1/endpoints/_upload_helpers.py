"""上传辅助模块，提供文件上传至 OSS 的公共函数。"""
from echomemory_backend.core.exceptions.codes import HttpStatus

import logging
from typing import TypeVar

from fastapi import HTTPException, UploadFile

from echomemory_backend.core.clients import oss_client

logger = logging.getLogger(__name__)

T = TypeVar("T")


def form_to_schema(cls: type[T], **fields) -> T:
    """将 Form 字段值过滤 None 后构造 Pydantic Schema。

    Args:
        cls: 目标 Pydantic Schema 类。
        **fields: Form 字段键值对。

    Returns:
        构造好的 Schema 实例。
    """
    return cls(**{k: v for k, v in fields.items() if v is not None})


class UploadCollector:
    """管理上传过程中的 URL 收集与异常时自动清理。"""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def add(self, url: str | None) -> None:
        """记录一个已上传的 URL，None 时忽略。

        Args:
            url: OSS 文件 URL，或 None。
        """
        if url:
            self.urls.append(url)

    async def __aenter__(self) -> "UploadCollector":
        return self

    async def __aexit__(self, exc_type, *_):
        if exc_type is not None:
            for url in self.urls:
                await oss_client.delete_object_by_url(url)
        return False


async def upload_optional_image(
    file: UploadFile | None,
    folder: str,
    prefix: str,
    detail_name: str | None = None,
) -> str | None:
    """上传可选图片文件到 OSS，失败时抛出 HTTPException。

    Args:
        file: 上传的文件对象，None 时直接返回 None。
        folder: Bucket 中的目标文件夹路径。
        prefix: 生成文件名时使用的前缀。
        detail_name: 错误文案中使用的名称，默认使用 prefix。

    Returns:
        上传后的 OSS URL；file 为 None 时返回 None。

    Raises:
        HTTPException: 文件类型非法时抛出 422；OSS 上传失败时抛出 503。
    """
    if file is None:
        return None
    name = detail_name or prefix
    if file.content_type is None or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=HttpStatus.UNPROCESSABLE_ENTITY,
            detail=f"{name} must be an image file",
        )
    try:
        return await oss_client.upload_image_to_oss(
            file.file, folder=folder, filename_prefix=prefix
        )
    except ValueError as exc:
        logger.warning("Invalid image upload for %s: %s", name, exc)
        raise HTTPException(
            status_code=HttpStatus.UNPROCESSABLE_ENTITY,
            detail="Invalid image file",
        ) from exc
    except RuntimeError as exc:
        logger.warning("OSS upload failed for %s: %s", name, exc)
        raise HTTPException(
            status_code=HttpStatus.SERVICE_UNAVAILABLE,
            detail="File upload failed",
        ) from exc
