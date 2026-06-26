"""音乐知识库文档解析器。

支持从 .docx、.pdf、.md 文件中提取纯文本，供后续切分与向量化使用。
"""

from __future__ import annotations

import logging
import re
from typing import BinaryIO

import markdown
from docx import Document as DocxDocument
from pypdf import PdfReader

logger = logging.getLogger(__name__)


_SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".md", ".markdown"}


def _normalize_extension(filename: str) -> str:
    """返回小写扩展名，支持 .markdown 映射为 .md。"""
    lower = filename.lower()
    if lower.endswith(".markdown"):
        return ".md"
    if "." in filename:
        return filename[filename.rfind("."):].lower()
    return ""


def _strip_markdown_html(html: str) -> str:
    """将 markdown 渲染后的 HTML 粗略剥离为可读文本。

    使用简单替换而非引入 bs4，避免额外依赖；用于知识库存储足够。
    """
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_docx(file: BinaryIO) -> str:
    """从 Word 文档中提取纯文本。

    参数:
        file: 二进制文件对象。

    返回:
        提取出的文本内容。

    异常:
        ValueError: 文件无法解析时抛出。
    """
    try:
        document = DocxDocument(file)
        paragraphs: list[str] = []
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if text:
                paragraphs.append(text)
        return "\n\n".join(paragraphs)
    except Exception as exc:
        logger.warning("Failed to parse docx: %s", exc)
        raise ValueError(f"无法解析 docx 文件: {exc}") from exc


def parse_pdf(file: BinaryIO) -> str:
    """从 PDF 文档中提取纯文本。

    参数:
        file: 二进制文件对象。

    返回:
        提取出的文本内容。

    异常:
        ValueError: 文件无法解析时抛出。
    """
    try:
        reader = PdfReader(file)
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                stripped = text.strip()
                if stripped:
                    pages.append(stripped)
        return "\n\n".join(pages)
    except Exception as exc:
        logger.warning("Failed to parse pdf: %s", exc)
        raise ValueError(f"无法解析 pdf 文件: {exc}") from exc


def parse_markdown(file: BinaryIO) -> str:
    """从 Markdown 文件中提取纯文本。

    参数:
        file: 二进制文件对象。

    返回:
        提取出的文本内容。

    异常:
        ValueError: 文件无法解析时抛出。
    """
    try:
        content = file.read().decode("utf-8", errors="replace")
        html = markdown.markdown(content)
        return _strip_markdown_html(html)
    except Exception as exc:
        logger.warning("Failed to parse markdown: %s", exc)
        raise ValueError(f"无法解析 markdown 文件: {exc}") from exc


def parse_document(file: BinaryIO, filename: str) -> str:
    """根据文件名扩展名分发到对应解析器。

    参数:
        file: 二进制文件对象；解析前会被 seek 到开头。
        filename: 原始文件名，用于判断扩展名。

    返回:
        提取出的纯文本内容。

    异常:
        ValueError: 扩展名不支持或解析失败时抛出。
    """
    ext = _normalize_extension(filename)
    if ext not in _SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(_SUPPORTED_EXTENSIONS))
        raise ValueError(f"不支持的文件类型: {ext}；支持的类型: {supported}")

    if hasattr(file, "seek"):
        file.seek(0)

    if ext == ".docx":
        return parse_docx(file)
    if ext == ".pdf":
        return parse_pdf(file)
    return parse_markdown(file)


def is_supported_file_type(filename: str) -> bool:
    """判断文件名扩展名是否在支持列表中。"""
    return _normalize_extension(filename) in _SUPPORTED_EXTENSIONS
