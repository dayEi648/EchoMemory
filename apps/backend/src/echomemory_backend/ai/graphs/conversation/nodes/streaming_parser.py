"""旧版标签化回复解析器。

仅保留 ``<thinking>...</thinking><answer>...</answer>`` 标签常量与
``parse_legacy_tagged_response``，用于兼容早期写入 checkpoint 的标签格式。
流式解析能力已不再使用。
"""

THINKING_OPEN = "<thinking>"
THINKING_CLOSE = "</thinking>"
ANSWER_OPEN = "<answer>"
ANSWER_CLOSE = "</answer>"


def parse_legacy_tagged_response(raw: str) -> tuple[str, str | None]:
    """解析早期版本写入 checkpoint 的标签化回复。

    兼容 ``</answer>`` 与误写成 ``<answer>`` 的结束标签。无法确认格式时，
    保留原文，避免误删正常回答。
    """
    if not raw.startswith(THINKING_OPEN):
        return raw, None

    thinking_end = raw.find(THINKING_CLOSE, len(THINKING_OPEN))
    if thinking_end == -1:
        return raw, None

    reasoning = raw[len(THINKING_OPEN) : thinking_end]
    answer_section = raw[thinking_end + len(THINKING_CLOSE) :]
    if not answer_section.startswith(ANSWER_OPEN):
        return raw, reasoning or None

    answer = answer_section[len(ANSWER_OPEN) :]
    if answer.endswith(ANSWER_CLOSE):
        answer = answer[: -len(ANSWER_CLOSE)]
    elif answer.endswith(ANSWER_OPEN):
        answer = answer[: -len(ANSWER_OPEN)]

    return answer, reasoning or None
