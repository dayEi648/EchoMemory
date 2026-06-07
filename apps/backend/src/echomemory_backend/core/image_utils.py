"""图像处理工具：压缩、格式转换、校验。"""

import io
from typing import BinaryIO

from PIL import Image

MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB 限制


def compress_image_to_memory(
    file: BinaryIO,
    max_size: int = MAX_IMAGE_SIZE_BYTES,
) -> io.BytesIO:
    """将图像文件压缩到不超过 max_size 字节。

    该函数读取上传的图像，通过降低 JPEG 质量或缩小尺寸来减小文件体积，
    并返回一个新的内存缓冲区供上传使用。

    Args:
        file: 包含图像数据的类文件对象。
        max_size: 目标最大文件大小，单位为字节（默认 2 MB）。

    Returns:
        包含压缩后图像的 BytesIO 缓冲区。

    Raises:
        ValueError: 输入不是有效图像时抛出。
    """
    try:
        with Image.open(file) as img:
            # 转换为 RGB 以确保输出一致（处理 PNG 透明度等情况）
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # 先降低质量，再缩小尺寸，尝试压缩到 max_size 以内
            quality_levels = [85, 75, 65, 55, 45]
            scale_factors = [1.0, 0.8, 0.6, 0.5, 0.4, 0.3]

            for scale in scale_factors:
                resized = img
                if scale < 1.0:
                    new_size = (int(img.width * scale), int(img.height * scale))
                    resized = img.resize(new_size, Image.Resampling.LANCZOS)

                for quality in quality_levels:
                    buffer = io.BytesIO()
                    resized.save(buffer, format="JPEG", quality=quality, optimize=True)
                    if buffer.tell() <= max_size:
                        buffer.seek(0)
                        return buffer

            # 回退策略：如果仍然过大，则大幅缩小尺寸并降低质量
            final_size = (int(img.width * 0.25), int(img.height * 0.25))
            resized = img.resize(final_size, Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            resized.save(buffer, format="JPEG", quality=30, optimize=True)
            buffer.seek(0)
            return buffer
    except Exception as exc:
        raise ValueError("Invalid image file") from exc
