#!/usr/bin/env python3
"""OpenAPI 文档导出脚本。

从 FastAPI 应用导出完整的 OpenAPI JSON，并按模块（tags）拆分为独立文档。
输出目录：.agent/api-documentations/
已存在的文件会被直接替换。

用法：
    cd apps/backend
    python scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path


def _discover_project_root() -> Path:
    """根据脚本位置自动发现项目根目录。"""
    script_dir = Path(__file__).resolve().parent
    # scripts 在 apps/backend/scripts/，项目根目录需要向上回溯 3 层
    project_root = script_dir.parent.parent.parent
    return project_root


def _ensure_output_dir(output_dir: Path) -> None:
    """确保输出目录存在。"""
    output_dir.mkdir(parents=True, exist_ok=True)


def _collect_tags(openapi_schema: dict) -> set[str]:
    """从 OpenAPI schema 的所有 operation 中收集唯一的 tag 名称。"""
    tags = set()
    paths = openapi_schema.get("paths", {})
    for path_item in paths.values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for tag in operation.get("tags", []):
                tags.add(tag)
    return tags


def _filter_schema_by_tag(full_schema: dict, target_tag: str) -> dict:
    """按指定 tag 过滤 OpenAPI schema，只保留属于该 tag 的 paths 和 tags 声明。"""
    filtered = {
        "openapi": full_schema.get("openapi", "3.1.0"),
        "info": full_schema.get("info", {}),
        "paths": {},
        "components": full_schema.get("components", {}),
    }

    # 可选保留的顶层字段
    for key in ("servers", "security"):
        if key in full_schema:
            filtered[key] = full_schema[key]

    # 过滤 paths：只保留包含目标 tag 的 operation
    full_paths = full_schema.get("paths", {})
    for path, path_item in full_paths.items():
        filtered_methods = {}
        for method, operation in path_item.items():
            if method in ("parameters",):
                # 保留 path-level 参数
                filtered_methods[method] = operation
                continue
            if not isinstance(operation, dict):
                continue
            op_tags = operation.get("tags", [])
            if target_tag in op_tags:
                filtered_methods[method] = operation
        if filtered_methods:
            filtered["paths"][path] = filtered_methods

    # 过滤 tags 声明：只保留目标 tag 的文档元数据
    full_tags = full_schema.get("tags", [])
    filtered["tags"] = [t for t in full_tags if t.get("name") == target_tag]
    if not filtered["tags"]:
        # 若原 schema 没有 tags 元数据声明，则补一个占位
        filtered["tags"] = [{"name": target_tag}]

    return filtered


def _write_json(path: Path, data: dict) -> None:
    """将字典以格式化的 JSON 写入文件（UTF-8，2 空格缩进）。"""
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> int:
    """主入口。"""
    project_root = _discover_project_root()

    # 将后端 src 加入 Python 路径，以便导入
    backend_src = project_root / "apps" / "backend" / "src"
    if str(backend_src) not in sys.path:
        sys.path.insert(0, str(backend_src))

    try:
        from echomemory_backend.main import app
    except Exception as exc:
        print(f"[错误] 无法导入 FastAPI 应用: {exc}", file=sys.stderr)
        return 1

    # 获取完整 OpenAPI schema（不需要启动服务）
    try:
        openapi_schema = app.openapi()
    except Exception as exc:
        print(f"[错误] 无法生成 OpenAPI schema: {exc}", file=sys.stderr)
        return 1

    output_dir = project_root / ".agent" / "api-documentations"
    _ensure_output_dir(output_dir)

    # 1. 导出完整文档
    full_path = output_dir / "openapi-full.json"
    _write_json(full_path, openapi_schema)
    print(f"[已导出] {full_path.relative_to(project_root)}")

    # 2. 按 tag 分模块导出
    tags = _collect_tags(openapi_schema)
    if not tags:
        print("[警告] 未在 OpenAPI schema 中发现任何 tags，跳过模块拆分。")
        return 0

    for tag in sorted(tags):
        filtered = _filter_schema_by_tag(openapi_schema, tag)
        # 文件命名：tag 中的连字符保留，其余小写
        filename = f"openapi-{tag.lower()}.json"
        tag_path = output_dir / filename
        _write_json(tag_path, filtered)
        path_count = len(filtered.get("paths", {}))
        print(f"[已导出] {tag_path.relative_to(project_root)}  ({path_count} 个 path)")

    print(f"\n完成：共导出 {len(tags) + 1} 个文档到 .agent/api-documentations/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
