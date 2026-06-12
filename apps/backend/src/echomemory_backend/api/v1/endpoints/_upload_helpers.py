"""上传辅助模块，提供文件上传至 OSS 的公共函数。"""

import logging

from fastapi import HTTPException, UploadFile, status

from echomemory_backend.core import oss_client

logger = logging.getLogger(__name__)


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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{name} must be an image file",
        )
    try:
        return await oss_client.upload_image_to_oss(
            file.file, folder=folder, filename_prefix=prefix
        )
    except ValueError as exc:
        logger.warning("Invalid image upload for %s: %s", name, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid image file",
        ) from exc
    except RuntimeError as exc:
        logger.warning("OSS upload failed for %s: %s", name, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="File upload failed",
        ) from exc
