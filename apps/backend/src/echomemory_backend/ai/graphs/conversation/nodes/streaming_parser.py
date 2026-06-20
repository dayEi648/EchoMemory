"""流式输出标签解析器。

将模型按系统提示词生成的 <thinking>...</thinking><answer>...</answer> 格式输出，
在流式过程中实时拆分为 reasoning 与 answer 两段内容。
"""

from dataclasses import dataclass


@dataclass
class _ParseResult:
    reasoning: str = ""
    answer: str = ""
    reasoning_complete: bool = False
    answer_complete: bool = False


@dataclass
class StreamDelta:
    """一次 feed 后产出的增量信息。"""

    reasoning: str = ""
    answer: str = ""
    reasoning_complete: bool = False
    answer_complete: bool = False


class StreamingTagParser:
    """流式解析 <thinking> 与 <answer> 标签。

    设计假设：模型在系统提示词约束下，输出严格以 <thinking> 开始，
    因此解析器会等待确认是否出现 <thinking> 标签后再开始分发内容，
    避免 partial tag 导致的内容误分类。
    """

    THINKING_OPEN = "<thinking>"
    THINKING_CLOSE = "</thinking>"
    ANSWER_OPEN = "<answer>"
    ANSWER_CLOSE = "</answer>"

    def __init__(self) -> None:
        self.buffer: str = ""
        self.emitted_reasoning: str = ""
        self.emitted_answer: str = ""
        self.reasoning_complete: bool = False
        self.answer_complete: bool = False
        self._format_detected: bool | None = None
        self._header_len: int = len(self.THINKING_OPEN)

    def feed(self, chunk: str) -> StreamDelta:
        """摄入新的文本块，返回 reasoning / answer 增量。"""
        self.buffer += chunk

        if self._format_detected is None:
            self._format_detected = self._detect_format()
            if self._format_detected is None:
                # 还无法判断，先不输出
                return StreamDelta()

        result = self._parse()

        delta = StreamDelta(
            reasoning_complete=result.reasoning_complete,
            answer_complete=result.answer_complete,
        )

        if len(result.reasoning) > len(self.emitted_reasoning):
            delta.reasoning = result.reasoning[len(self.emitted_reasoning) :]
            self.emitted_reasoning = result.reasoning

        if len(result.answer) > len(self.emitted_answer):
            delta.answer = result.answer[len(self.emitted_answer) :]
            self.emitted_answer = result.answer

        self.reasoning_complete = result.reasoning_complete
        self.answer_complete = result.answer_complete
        return delta

    def _detect_format(self) -> bool | None:
        """检测当前缓冲是否已能确定是否为 tag 格式。

        返回:
            True:  确定是 <thinking> 格式
            False: 确定不是 <thinking> 格式
            None:  尚无法判断
        """
        buf = self.buffer
        if buf.startswith(self.THINKING_OPEN):
            return True
        if not buf.startswith("<"):
            return False
        # 以 < 开头但不是 <thinking>，等长度超过 thinking 标签后判定不是
        if len(buf) >= self._header_len:
            return False
        return None

    def _parse(self) -> _ParseResult:
        """从当前 buffer 解析出 reasoning 与 answer。"""
        if self._format_detected is False:
            # 非 tag 格式，全部作为 answer
            return _ParseResult(
                answer=self.buffer,
                reasoning_complete=True,
                answer_complete=False,
            )

        buffer = self.buffer
        result = _ParseResult()

        think_open_idx = buffer.find(self.THINKING_OPEN)
        if think_open_idx == -1:
            # 理论上 detect 阶段已确认，不会走到这里
            result.answer = buffer
            result.reasoning_complete = True
            return result

        think_start = think_open_idx + len(self.THINKING_OPEN)
        think_close_idx = buffer.find(self.THINKING_CLOSE, think_start)

        if think_close_idx != -1:
            result.reasoning = buffer[think_start:think_close_idx]
            result.reasoning_complete = True
            rest = buffer[think_close_idx + len(self.THINKING_CLOSE) :]
        else:
            result.reasoning = buffer[think_start:]
            result.reasoning_complete = False
            rest = ""

        answer_open_idx = rest.find(self.ANSWER_OPEN)
        if answer_open_idx != -1:
            answer_start = answer_open_idx + len(self.ANSWER_OPEN)
            answer_close_idx = rest.find(self.ANSWER_CLOSE, answer_start)
            if answer_close_idx != -1:
                result.answer = rest[answer_start:answer_close_idx]
                result.answer_complete = True
            else:
                result.answer = rest[answer_start:]
                result.answer_complete = False

        return result


def parse_legacy_tagged_response(raw: str) -> tuple[str, str | None]:
    """解析早期版本写入 checkpoint 的标签化回复。

    兼容 ``</answer>`` 与误写成 ``<answer>`` 的结束标签。无法确认格式时，
    保留原文，避免误删正常回答。
    """
    thinking_open = StreamingTagParser.THINKING_OPEN
    thinking_close = StreamingTagParser.THINKING_CLOSE
    answer_open = StreamingTagParser.ANSWER_OPEN
    answer_close = StreamingTagParser.ANSWER_CLOSE

    if not raw.startswith(thinking_open):
        return raw, None

    thinking_end = raw.find(thinking_close, len(thinking_open))
    if thinking_end == -1:
        return raw, None

    reasoning = raw[len(thinking_open) : thinking_end]
    answer_section = raw[thinking_end + len(thinking_close) :]
    if not answer_section.startswith(answer_open):
        return raw, reasoning or None

    answer = answer_section[len(answer_open) :]
    if answer.endswith(answer_close):
        answer = answer[: -len(answer_close)]
    elif answer.endswith(answer_open):
        answer = answer[: -len(answer_open)]

    return answer, reasoning or None
