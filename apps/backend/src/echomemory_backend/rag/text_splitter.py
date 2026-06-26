"""文本切分工具，用于 RAG 知识库文档分块。

提供基于字符长度的滑动窗口切分器，优先在段落、换行、空格等自然边界处断开，
避免暴力截断语义单元。
"""

from __future__ import annotations


class TextSplitter:
    """按字符长度切分长文本，支持重叠窗口。

    切分流程：
    1. 若文本长度不超过 ``chunk_size``，直接返回单一块。
    2. 否则从当前位置取 ``chunk_size`` 长度窗口，在窗口末端向前回溯，
       优先选择 ``\\n\\n``、``\\n``、空格作为断点，形成自然语义边界。
    3. 下一块起始位置 = 当前断点 - ``chunk_overlap``，保证相邻块之间有上下文重叠。

    参数:
        chunk_size: 每块最大字符数，必须大于 0。
        chunk_overlap: 相邻块之间的重叠字符数，必须大于等于 0 且小于 chunk_size。
    """

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100) -> None:
        """初始化切分器并校验参数。

        异常:
            ValueError: 参数非法时抛出。
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap 必须大于等于 0")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap 必须小于 chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str) -> list[str]:
        """切分文本为若干块。

        参数:
            text: 原始文本。

        返回:
            非空文本块列表；空文本返回空列表。
        """
        if not text:
            return []

        text = text.strip()
        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            if end == text_len:
                chunk = text[start:].strip()
                if chunk:
                    chunks.append(chunk)
                break

            break_point = self._find_break_point(text, start, end)
            chunk = text[start:break_point].strip()
            if chunk:
                chunks.append(chunk)

            # 计算下一起点，保留 overlap 但不倒退
            next_start = break_point - self.chunk_overlap
            if next_start <= start:
                # overlap 过大或段落过长导致断点紧邻起点，强制前进至少 1 个字符
                next_start = min(break_point, start + max(1, self.chunk_size // 4))
            start = next_start

        return chunks

    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """在 ``[start, end]`` 窗口内寻找最佳断点。

        优先在窗口末端附近寻找自然分隔符；找不到时直接截断在 end。

        参数:
            text: 原始文本。
            start: 窗口起始索引（含）。
            end: 窗口结束索引（不含），已被限制在文本长度内。

        返回:
            最佳断点索引（相对于 text）。
        """
        # 搜索范围：窗口末端往前最多 1/4 窗口长度，避免回退太远损失信息密度
        search_start = max(start, end - self.chunk_size // 4)

        # 优先查找段落分隔符
        paragraph_pos = text.rfind("\n\n", search_start, end)
        if paragraph_pos != -1 and paragraph_pos > start:
            return paragraph_pos

        # 其次查找换行
        newline_pos = text.rfind("\n", search_start, end)
        if newline_pos != -1 and newline_pos > start:
            return newline_pos

        # 最后查找空格
        space_pos = text.rfind(" ", search_start, end)
        if space_pos != -1 and space_pos > start:
            return space_pos

        return end
