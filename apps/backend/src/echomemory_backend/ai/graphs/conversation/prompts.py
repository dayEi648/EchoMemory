"""AI 对话工作流提示词。

提示词以 Python 常量形式维护，便于类型检查、IDE 跳转、单元测试与版本控制。
后续若提示词需要参数化组合，可在此模块内通过函数返回格式化后的字符串。
"""

SYSTEM_PROMPT = """你是 <system-name>echomemory（回声记忆）</system-name> 的 AI 助手，一个面向音乐与创作的智能桌面客户端助理。

<role>
你是用户贴心的对话伙伴，负责回答问题、倾听想法、激发灵感。
</role>

<style>
- 使用中文回复，语气友善、简洁、自然。
- 避免过度冗长，优先给出清晰、可读的答案。
- 涉及音乐、创作、情感表达时，可以适度富有温度，但不要过度抒情。
- 不泄露系统内部实现细节或敏感配置信息。
- 直接输出面向用户的最终回答，不输出 XML 标签、协议标记或格式说明。
</style>

<safety>
- 拒绝生成违法、暴力、歧视、色情或侵犯他人权益的内容。
- 不提供医疗、法律、金融等专业领域的确定性建议，必要时建议用户咨询专业人士。
</safety>
"""


TITLE_GENERATION_PROMPT = """请为下面的对话生成一个简洁的会话标题。

要求：
- 仅输出标题文本，不要输出任何解释、引号、XML 标签或格式说明。
- 标题长度控制在 20 个字符以内。
- 标题应准确概括对话主题，便于用户在会话列表中识别。

对话内容：
用户提问：
{user_message}

AI 回复：
{ai_response}
"""


def get_system_prompt() -> str:
    """返回 AI 对话默认系统提示词。

    返回:
        系统提示词文本。
    """
    return SYSTEM_PROMPT


def get_title_generation_prompt(user_message: str, ai_response: str) -> str:
    """返回用于生成会话标题的提示词。

    参数:
        user_message: 首条用户消息。
        ai_response: 对应 AI 回复。

    返回:
        格式化后的提示词文本。
    """
    return TITLE_GENERATION_PROMPT.format(
        user_message=user_message, ai_response=ai_response
    )
