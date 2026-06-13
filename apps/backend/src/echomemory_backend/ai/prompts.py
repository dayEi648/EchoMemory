"""AI 提示词加载模块。

所有提示词存放于 ``ai/prompts/`` 目录下的 Markdown 文件中，
便于非开发人员查看、编辑和维护。
"""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    """加载指定名称的提示词文件内容。

    参数:
        name: 提示词文件名（不含 ``.md`` 后缀）。

    返回:
        提示词文本内容，去除首尾空白。

    异常:
        FileNotFoundError: 提示词文件不存在时抛出。
    """
    file_path = _PROMPTS_DIR / f"{name}.md"
    if not file_path.exists():
        raise FileNotFoundError(f"提示词文件不存在: {file_path}")
    return file_path.read_text(encoding="utf-8").strip()


def get_system_prompt() -> str:
    """返回 AI 对话默认系统提示词。"""
    return load_prompt("system")
