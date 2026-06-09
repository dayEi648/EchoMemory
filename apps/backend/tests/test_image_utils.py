"""图像处理工具测试。"""

import io

import pytest
from PIL import Image

from echomemory_backend.core.image_utils import compress_image_to_memory


def _make_image_bytes() -> io.BytesIO:
    """生成测试用图片字节流。"""
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


class TestCompressImageToMemory:
    """测试图片压缩工具函数。"""

    def test_final_output_must_not_exceed_max_size(self):
        """最终压缩结果仍超过限制时必须抛出 ValueError。"""
        with pytest.raises(ValueError, match="Unable to compress image"):
            compress_image_to_memory(_make_image_bytes(), max_size=1)
