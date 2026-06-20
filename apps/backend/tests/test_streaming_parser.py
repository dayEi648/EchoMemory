import pytest

from echomemory_backend.ai.graphs.conversation.nodes.streaming_parser import (
    StreamingTagParser,
    parse_legacy_tagged_response,
)


def feed_chunks(parser: StreamingTagParser, chunks: list[str]):
    """辅助函数：依次喂入 chunk 并收集所有 delta。"""
    reasoning_parts = []
    answer_parts = []
    reasoning_complete = False
    answer_complete = False
    for chunk in chunks:
        delta = parser.feed(chunk)
        if delta.reasoning:
            reasoning_parts.append(delta.reasoning)
        if delta.answer:
            answer_parts.append(delta.answer)
        reasoning_complete = delta.reasoning_complete
        answer_complete = delta.answer_complete
    return (
        "".join(reasoning_parts),
        "".join(answer_parts),
        reasoning_complete,
        answer_complete,
    )


def test_parse_complete_tagged_response():
    parser = StreamingTagParser()
    reasoning, answer, reasoning_done, answer_done = feed_chunks(
        parser,
        ["<thinking>思考1\n思考2</thinking><answer>最终答案</answer>"],
    )
    assert reasoning == "思考1\n思考2"
    assert answer == "最终答案"
    assert reasoning_done is True
    assert answer_done is True


def test_parse_streaming_tagged_response():
    parser = StreamingTagParser()
    chunks = [
        "<think",
        "ing>思考",
        "中</thinking>",
        "<answer>答案",
        "分段</answer>",
    ]
    reasoning, answer, reasoning_done, answer_done = feed_chunks(parser, chunks)
    assert reasoning == "思考中"
    assert answer == "答案分段"
    assert reasoning_done is True
    assert answer_done is True


def test_parse_non_tagged_response():
    parser = StreamingTagParser()
    reasoning, answer, reasoning_done, answer_done = feed_chunks(
        parser,
        ["你好", "，", "世界"],
    )
    assert reasoning == ""
    assert answer == "你好，世界"
    assert reasoning_done is True
    assert answer_done is False


def test_parse_only_thinking_no_answer():
    parser = StreamingTagParser()
    reasoning, answer, reasoning_done, answer_done = feed_chunks(
        parser,
        ["<thinking>只思考</thinking>"],
    )
    assert reasoning == "只思考"
    assert answer == ""
    assert reasoning_done is True
    assert answer_done is False


def test_partial_tag_waits_for_detection():
    parser = StreamingTagParser()
    # 先给 partial tag，不应误输出为 answer
    delta1 = parser.feed("<thin")
    assert delta1.reasoning == ""
    assert delta1.answer == ""

    delta2 = parser.feed("king>内容</thinking><answer>答案</answer>")
    assert "内容" in delta2.reasoning
    assert "答案" in delta2.answer


def test_parse_legacy_tagged_response_accepts_malformed_answer_closing_tag():
    answer, reasoning = parse_legacy_tagged_response(
        "<thinking>分析用户意图</thinking><answer>最终回答<answer>"
    )

    assert answer == "最终回答"
    assert reasoning == "分析用户意图"
