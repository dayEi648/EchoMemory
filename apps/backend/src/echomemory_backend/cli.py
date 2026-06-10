"""CLI 入口模块，提供快捷启动命令。"""

import uvicorn


def start() -> None:
    """启动开发服务器（带热重载）。

    使用 uv run start 即可一键启动后端服务。
    """
    uvicorn.run(
        "echomemory_backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
