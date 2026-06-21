from echomemory_backend.ai.graphs.conversation.nodes.streaming_parser import (
    parse_legacy_tagged_response,
)


def test_parse_legacy_complete_tagged_response():
    answer, reasoning = parse_legacy_tagged_response(
        "<thinking>思考1\n思考2</thinking><answer>最终答案</answer>"
    )
    assert answer == "最终答案"
    assert reasoning == "思考1\n思考2"


def test_parse_legacy_accepts_malformed_answer_closing_tag():
    answer, reasoning = parse_legacy_tagged_response(
        "<thinking>分析用户意图</thinking><answer>最终回答<answer>"
    )
    assert answer == "最终回答"
    assert reasoning == "分析用户意图"


def test_parse_legacy_only_thinking_no_answer():
    answer, reasoning = parse_legacy_tagged_response("<thinking>只思考</thinking>")
    assert answer == "<thinking>只思考</thinking>"
    assert reasoning == "只思考"


def test_parse_legacy_non_tagged_response_passthrough():
    raw = "你好，世界"
    answer, reasoning = parse_legacy_tagged_response(raw)
    assert answer == raw
    assert reasoning is None


def test_parse_legacy_missing_thinking_close_passthrough():
    raw = "<thinking>只思考"
    answer, reasoning = parse_legacy_tagged_response(raw)
    assert answer == raw
    assert reasoning is None
