"""从 ErrorCode 枚举生成错误码文档。

用法:
    python scripts/generate_error_code_doc.py

输出:
    planning/api-documentations/error-codes.md
"""

import sys
from pathlib import Path

# 将 src 加入路径，以便直接导入后端模块
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from echomemory_backend.core.exceptions.codes import ErrorCode, HttpStatus


_OUTPUT = ROOT.parent.parent / "planning" / "api-documentations" / "error-codes.md"


def _layer_name(code: ErrorCode) -> str:
    value = code.value
    if value == 0:
        return "成功"
    if 10000 <= value < 20000:
        return "业务规则错误"
    if 20000 <= value < 30000:
        return "认证 / 授权错误"
    if 30000 <= value < 40000:
        return "外部 / 第三方服务错误"
    if 40000 <= value < 50000:
        return "客户端请求 / 校验错误"
    if 50000 <= value < 60000:
        return "系统内部错误"
    return "未知 / 兜底错误"


def _layer_anchor(layer: str) -> str:
    return (
        layer.replace(" / ", "-")
        .replace(" ", "-")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "")
    )


def generate() -> str:
    lines: list[str] = []
    lines.append("# echomemory 错误码与 HTTP 状态码规范\n")
    lines.append(
        "> 本文档由 `apps/backend/scripts/generate_error_code_doc.py` 自动生成，"
        "请勿手动修改。新增或变更错误码后，请重新运行该脚本。\n"
    )

    # HTTP 状态码语义
    lines.append("## HTTP 状态码语义\n")
    lines.append("| 状态码 | 常量名 | 使用场景 |")
    lines.append("| ---: | --- | --- |")
    http_items = [
        (HttpStatus.OK, "OK", "请求成功，返回业务数据"),
        (HttpStatus.CREATED, "CREATED", "资源创建成功"),
        (HttpStatus.NO_CONTENT, "NO_CONTENT", "操作成功但无返回体；中间件会转换为 200 + data=null"),
        (HttpStatus.BAD_REQUEST, "BAD_REQUEST", "请求语法或语义错误，无法被服务端理解"),
        (HttpStatus.UNAUTHORIZED, "UNAUTHORIZED", "未认证或认证凭据无效"),
        (HttpStatus.FORBIDDEN, "FORBIDDEN", "已认证但无权访问该资源"),
        (HttpStatus.NOT_FOUND, "NOT_FOUND", "请求的资源不存在"),
        (HttpStatus.CONFLICT, "CONFLICT", "业务冲突，如重复注册"),
        (HttpStatus.UNPROCESSABLE_ENTITY, "UNPROCESSABLE_ENTITY", "请求参数校验失败"),
        (HttpStatus.TOO_MANY_REQUESTS, "TOO_MANY_REQUESTS", "请求过于频繁，触发限流"),
        (HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL_SERVER_ERROR", "系统内部未捕获异常"),
        (HttpStatus.BAD_GATEWAY, "BAD_GATEWAY", "网关或上游服务异常"),
        (HttpStatus.SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE", "服务暂时不可用"),
    ]
    for value, name, scenario in http_items:
        lines.append(f"| {value} | `{name}` | {scenario} |")
    lines.append("")

    # 错误码分层
    lines.append("## 错误码空间分层\n")
    lines.append("| 区间 | 分层 | 说明 |")
    lines.append("| --- | --- | --- |")
    layers = [
        ("0", "成功", "请求成功"),
        ("10000 - 19999", "业务规则错误", "用户、音乐、专辑、歌单、评论等业务规则被违反"),
        ("20000 - 29999", "认证 / 授权错误", "登录、Token、权限相关"),
        ("30000 - 39999", "外部 / 第三方服务错误", "AI、OSS、歌词加载等外部依赖"),
        ("40000 - 49999", "客户端请求 / 校验错误", "参数校验、格式错误、限流"),
        ("50000 - 59999", "系统内部错误", "未捕获异常、系统级失败"),
        ("90000 - 99999", "未知 / 兜底错误", "未明确分类的兜底错误"),
    ]
    for scope, name, desc in layers:
        lines.append(f"| {scope} | {name} | {desc} |")
    lines.append("")

    # 按分层组织的错误码列表
    current_layer = ""
    for code in ErrorCode:
        layer = _layer_name(code)
        if layer != current_layer:
            if current_layer:
                lines.append("")
            current_layer = layer
            anchor = _layer_anchor(layer)
            lines.append(f"## {layer} {{#{anchor}}}")
            lines.append("")
            lines.append("| 错误码 | 枚举名 | HTTP 状态码 | 说明 |")
            lines.append("| ---: | --- | ---: | --- |")
        lines.append(
            f"| {code.value} | `{code.name}` | {code.http_status} | {code.description} |"
        )
    lines.append("")
    lines.append("")

    lines.append("## 使用约定\n")
    lines.append("1. 后端抛出业务异常时，应优先使用 `BusinessError(detail, code=ErrorCode.XXX)`。\n")
    lines.append("2. HTTP 状态码仅作为传输层语义，业务识别应以 `code` 字段为准。\n")
    lines.append("3. 前端判断具体错误时，应使用 `ErrorCode.XXX`，避免对 `msg` 或 HTTP 状态码做字符串匹配。\n")
    lines.append("4. 新增错误码需同步更新 `apps/frontend/src/shared/constants/errorCode.ts`。\n")

    return "\n".join(lines)


def main() -> None:
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    content = generate()
    _OUTPUT.write_text(content, encoding="utf-8")
    print(f"Generated {_OUTPUT}")


if __name__ == "__main__":
    main()
