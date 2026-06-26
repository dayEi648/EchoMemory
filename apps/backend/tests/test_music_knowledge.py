"""音乐知识库（RAG）功能测试。

覆盖文档解析、文本切分、服务层入库、管理后台 API 与 AI 检索工具。
"""

from __future__ import annotations

import hashlib
import io
from typing import Any
from urllib.parse import quote

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.ai.tools import music_knowledge as music_knowledge_tool_module
from echomemory_backend.ai.tools.music_knowledge import search_music_knowledge
from echomemory_backend.core.security.security import create_access_token, get_password_hash
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.user import User
from echomemory_backend.models.vector_document import VectorDocument
from echomemory_backend.rag.document_parser import (
    is_supported_file_type,
    parse_document,
    parse_docx,
    parse_markdown,
    parse_pdf,
)
from echomemory_backend.rag.text_splitter import TextSplitter
from echomemory_backend.rag.vector_store import VectorStore
from echomemory_backend.services import music_knowledge_service
from echomemory_backend.services.music_knowledge_service import MUSIC_KNOWLEDGE_NAMESPACE
from tests.api_helpers import api_data, api_error

BASE_URL = "/api/v1/admin/music-knowledge"


class _FakeEmbeddingClient:
    """确定性假嵌入客户端，避免调用外部 API。"""

    def __init__(self, dimensions: int = 1024) -> None:
        self.dimensions = dimensions
        self.model = "fake-embedding"

    def _vector_for(self, text: str) -> list[float]:
        digest = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        index = digest % self.dimensions
        vector = [0.0] * self.dimensions
        vector[index] = 1.0
        return vector

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(t) for t in texts]

    async def embed_one(self, text: str) -> list[float]:
        return self._vector_for(text)


@pytest.fixture
def fake_embedding_client(monkeypatch):
    """用 Fake EmbeddingClient 替换真实客户端。"""
    from echomemory_backend.rag import embeddings as embeddings_module

    def _make_fake(*args, **kwargs):
        return _FakeEmbeddingClient()

    monkeypatch.setattr(embeddings_module, "EmbeddingClient", _make_fake)
    yield _make_fake


@pytest.fixture(autouse=True)
def use_test_session_for_tools(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """让工具复用当前测试事件循环中的 Session，避免全局连接池跨 loop。"""

    class _SessionContext:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(
        music_knowledge_tool_module,
        "AsyncSessionLocal",
        lambda: _SessionContext(),
    )


async def _create_user(
    db: AsyncSession,
    username: str,
    role: int = UserRole.USER.value,
) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash("secret"),
        nickname=username,
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


def _make_docx_bytes(text: str) -> bytes:
    buffer = io.BytesIO()
    doc = DocxDocument()
    for paragraph in text.split("\n\n"):
        doc.add_paragraph(paragraph)
    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()


def _make_pdf_bytes(text: str) -> bytes:
    """创建一个最小可解析的 PDF 文件（不保证包含可提取文本）。"""
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(buffer)
    buffer.seek(0)
    return buffer.read()


def _make_markdown_bytes(text: str) -> bytes:
    return text.encode("utf-8")


# -----------------------------------------------------------------------------
# 文档解析测试
# -----------------------------------------------------------------------------

def test_is_supported_file_type():
    assert is_supported_file_type("music.md")
    assert is_supported_file_type("music.docx")
    assert is_supported_file_type("music.pdf")
    assert is_supported_file_type("music.markdown")
    assert not is_supported_file_type("music.txt")
    assert not is_supported_file_type("music")


def test_parse_docx():
    text = "第一段内容\n\n第二段内容"
    file = io.BytesIO(_make_docx_bytes(text))
    result = parse_docx(file)
    assert "第一段内容" in result
    assert "第二段内容" in result


def test_parse_markdown():
    text = "# 标题\n\n这是正文内容。"
    file = io.BytesIO(_make_markdown_bytes(text))
    result = parse_markdown(file)
    assert "标题" in result
    assert "这是正文内容" in result


def test_parse_pdf():
    # pypdf 对纯空白页的 extract_text 返回空字符串，这里仅验证解析不抛异常。
    file = io.BytesIO(_make_pdf_bytes("PDF content"))
    result = parse_pdf(file)
    assert isinstance(result, str)


def test_parse_document_unsupported():
    file = io.BytesIO(b"hello")
    with pytest.raises(ValueError):
        parse_document(file, "hello.txt")


# -----------------------------------------------------------------------------
# 文本切分测试
# -----------------------------------------------------------------------------

def test_text_splitter_short_text():
    splitter = TextSplitter(chunk_size=100, chunk_overlap=10)
    chunks = splitter.split("短文本")
    assert chunks == ["短文本"]


def test_text_splitter_respects_chunk_size():
    splitter = TextSplitter(chunk_size=20, chunk_overlap=5)
    text = "这是一个很长的句子，需要被切分成多个块。" * 10
    chunks = splitter.split(text)
    assert len(chunks) > 1
    assert all(len(chunk) <= 20 for chunk in chunks)


def test_text_splitter_overlap():
    splitter = TextSplitter(chunk_size=30, chunk_overlap=10)
    text = "A" * 100
    chunks = splitter.split(text)
    # 相邻块之间应有重叠
    for i in range(len(chunks) - 1):
        assert chunks[i][-10:] == chunks[i + 1][:10]


def test_text_splitter_empty():
    splitter = TextSplitter()
    assert splitter.split("") == []
    assert splitter.split("   \n  ") == []


def test_text_splitter_invalid_params():
    with pytest.raises(ValueError):
        TextSplitter(chunk_size=0)
    with pytest.raises(ValueError):
        TextSplitter(chunk_size=100, chunk_overlap=100)
    with pytest.raises(ValueError):
        TextSplitter(chunk_size=100, chunk_overlap=-1)


# -----------------------------------------------------------------------------
# 服务层测试
# -----------------------------------------------------------------------------

async def test_ingest_document(db_session: AsyncSession, fake_embedding_client):
    text = "周杰伦的晴天是一首经典华语流行歌曲。" * 20
    file = io.BytesIO(_make_docx_bytes(text))

    result = await music_knowledge_service.ingest_document(
        db_session,
        filename="test.docx",
        file=file,
    )

    assert result.source == "test.docx"
    assert result.chunk_count > 0

    # 验证数据库写入
    docs = await VectorStore(embedding_client=_FakeEmbeddingClient()).search(
        db_session,
        namespace=MUSIC_KNOWLEDGE_NAMESPACE,
        query="周杰伦 晴天",
        top_k=5,
    )
    assert len(docs) > 0
    assert docs[0].meta["source"] == "test.docx"
    assert docs[0].meta["file_type"] == "docx"
    assert "chunk_index" in docs[0].meta


async def test_list_and_delete_sources(db_session: AsyncSession, fake_embedding_client):
    file1 = io.BytesIO(_make_markdown_bytes("文档一内容" * 50))
    file2 = io.BytesIO(_make_markdown_bytes("文档二内容" * 50))

    await music_knowledge_service.ingest_document(db_session, "doc1.md", file1)
    await music_knowledge_service.ingest_document(db_session, "doc2.md", file2)

    items, total = await music_knowledge_service.list_sources(db_session)
    assert total == 2
    assert sorted(items) == ["doc1.md", "doc2.md"]

    deleted = await music_knowledge_service.delete_by_source(db_session, "doc1.md")
    await db_session.commit()
    assert deleted > 0

    items, total = await music_knowledge_service.list_sources(db_session)
    assert total == 1
    assert items == ["doc2.md"]


async def test_reingest_overwrites(db_session: AsyncSession, fake_embedding_client):
    file1 = io.BytesIO(_make_markdown_bytes("旧内容" * 50))
    file2 = io.BytesIO(_make_markdown_bytes("新内容" * 50))

    await music_knowledge_service.ingest_document(db_session, "same.md", file1)
    first_count = (
        await music_knowledge_service.list_sources(db_session)
    )[1]
    assert first_count == 1

    await music_knowledge_service.ingest_document(db_session, "same.md", file2)
    items, total = await music_knowledge_service.list_sources(db_session)
    assert total == 1

    docs = await VectorStore(embedding_client=_FakeEmbeddingClient()).search(
        db_session,
        namespace=MUSIC_KNOWLEDGE_NAMESPACE,
        query="新内容",
        top_k=5,
    )
    assert len(docs) > 0
    assert "旧内容" not in docs[0].content


# -----------------------------------------------------------------------------
# 管理后台 API 测试
# -----------------------------------------------------------------------------

async def test_admin_upload_document(client: TestClient, db_session: AsyncSession, fake_embedding_client):
    admin = await _create_user(db_session, "admin_mk_upload", role=UserRole.ADMIN.value)
    file_content = _make_docx_bytes("API 测试文档内容" * 50)

    response = client.post(
        f"{BASE_URL}/documents",
        files={"file": ("api_test.docx", io.BytesIO(file_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=_auth_header(admin),
    )

    data = api_data(response)
    assert data["source"] == "api_test.docx"
    assert data["chunk_count"] > 0


async def test_admin_upload_unsupported_file(client: TestClient, db_session: AsyncSession):
    admin = await _create_user(db_session, "admin_mk_unsupported", role=UserRole.ADMIN.value)

    response = client.post(
        f"{BASE_URL}/documents",
        files={"file": ("bad.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=_auth_header(admin),
    )

    error = api_error(response)
    assert error["code"] != 0


async def test_admin_list_documents(client: TestClient, db_session: AsyncSession, fake_embedding_client):
    admin = await _create_user(db_session, "admin_mk_list", role=UserRole.ADMIN.value)
    await music_knowledge_service.ingest_document(
        db_session,
        "list_doc.md",
        io.BytesIO(_make_markdown_bytes("列出测试" * 50)),
    )

    response = client.get(
        f"{BASE_URL}/documents",
        headers=_auth_header(admin),
    )

    data = api_data(response)
    assert data["total"] == 1
    assert "list_doc.md" in data["items"]


async def test_admin_delete_document(client: TestClient, db_session: AsyncSession, fake_embedding_client):
    admin = await _create_user(db_session, "admin_mk_delete", role=UserRole.ADMIN.value)
    await music_knowledge_service.ingest_document(
        db_session,
        "del_doc.md",
        io.BytesIO(_make_markdown_bytes("删除测试" * 50)),
    )

    response = client.delete(
        f"{BASE_URL}/documents/{quote('del_doc.md')}",
        headers=_auth_header(admin),
    )

    data = api_data(response)
    assert data["deleted_chunks"] > 0

    # 再次删除应返回 404
    response2 = client.delete(
        f"{BASE_URL}/documents/{quote('del_doc.md')}",
        headers=_auth_header(admin),
    )
    assert api_error(response2)["code"] != 0


# -----------------------------------------------------------------------------
# AI 工具测试
# -----------------------------------------------------------------------------

async def test_search_music_knowledge_tool(db_session: AsyncSession, fake_embedding_client):
    await music_knowledge_service.ingest_document(
        db_session,
        "tool_doc.md",
        io.BytesIO(_make_markdown_bytes("肖邦是浪漫主义钢琴作曲家。" * 50)),
    )

    result = await search_music_knowledge.ainvoke({"query": "肖邦"})

    assert result["total"] >= 1
    assert len(result["items"]) >= 1
    assert "肖邦" in result["items"][0]["content"]
    assert result["items"][0]["source"] == "tool_doc.md"


async def test_search_music_knowledge_tool_empty(db_session: AsyncSession, fake_embedding_client):
    result = await search_music_knowledge.ainvoke({"query": "不存在的知识"})
    assert result["total"] == 0
    assert result["items"] == []
