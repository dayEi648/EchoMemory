"""Image processing utilities: compression, format conversion, validation."""

import io
from typing import BinaryIO

from PIL import Image

MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB


def compress_image_to_memory(
    file: BinaryIO,
    max_size: int = MAX_IMAGE_SIZE_BYTES,
) -> io.BytesIO:
    """Compress an image file to fit within *max_size* bytes.

    The function reads the uploaded image, attempts to reduce its file size
    by lowering JPEG quality and/or scaling down dimensions, and returns a
    new in-memory buffer ready for upload.

    Args:
        file: A file-like object containing image data.
        max_size: Target maximum file size in bytes (default 2 MB).

    Returns:
        A ``BytesIO`` buffer containing the compressed image.

    Raises:
        ValueError: If the input is not a valid image.
    """
    try:
        img = Image.open(file)
    except Exception as exc:
        raise ValueError("Invalid image file") from exc

    # Convert to RGB to ensure consistent output (handles PNG transparency, etc.)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Try to fit within max_size by reducing quality first, then scaling.
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

    # Fallback: if still too large, aggressive scale + low quality
    final_size = (int(img.width * 0.25), int(img.height * 0.25))
    resized = img.resize(final_size, Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    resized.save(buffer, format="JPEG", quality=30, optimize=True)
    buffer.seek(0)
    return buffer
