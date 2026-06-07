# 后端异步改造审查修复计划

## 目标
修复后端代码审查中发现的 7 个确认问题，确保修复后全部 103 个测试通过。

## 问题清单与修复步骤

### H1. pyproject.toml 缺失 asyncpg
**文件**: `apps/backend/pyproject.toml`
**修改**: 在 dependencies 中添加 `"asyncpg"`。
**验证**: 安装后 `python -c "import asyncpg"` 成功。

### H2. AsyncSessionLocal 未设置 expire_on_commit=False
**文件**: `apps/backend/src/echomemory_backend/db/session.py`
**修改**: `AsyncSessionLocal = async_sessionmaker(..., expire_on_commit=False, bind=async_engine)`
**验证**: 运行全部测试通过。

### M1. lifespan 中未释放 async_engine 和 Redis
**文件**: `apps/backend/src/echomemory_backend/main.py`
**修改**: 在 lifespan yield 后添加 `await async_engine.dispose()` 和 `await redis_client.close()`，需导入对应对象。
**验证**: 运行全部测试通过（TestClient 不触发 lifespan shutdown，逻辑通过代码审查验证）。

### M2. clean_tables 不完整
**文件**: `apps/backend/tests/conftest.py`
**修改**: 扩展 TRUNCATE 列表覆盖所有业务表。
**验证**: 运行全部测试通过。

### M3. PIL Image 未显式关闭
**文件**: `apps/backend/src/echomemory_backend/core/image_utils.py`
**修改**: 使用 `with Image.open(file) as img:` 包裹图像处理逻辑，内部代码整体缩进一层。
**验证**: 运行全部测试通过（头像上传测试覆盖此路径）。

### M4. 黑名单 TTL 与 JWT 过期硬编码耦合
**文件**: `apps/backend/src/echomemory_backend/core/redis_client.py`
**修改**: `blacklist_access_token` 默认 TTL 读取 `settings.jwt_access_token_expire_minutes * 60`。
**验证**: 运行全部测试通过（test_auth.py 中 logout 测试覆盖此路径）。

### M5. conftest 中 AsyncTestingSessionLocal 重复定义
**文件**: `apps/backend/tests/conftest.py`
**修改**: 删除 db_session fixture 中第 1 次重复定义（保留带 expire_on_commit=False 的版本）。
**验证**: 运行全部测试通过。

### L1. 测试中 time.sleep 阻塞事件循环
**文件**: `apps/backend/tests/test_redis_client.py`, `tests/test_security.py`
**修改**: `time.sleep` → `await asyncio.sleep`。
**验证**: 运行全部测试通过。

## 执行顺序
1. H1 → H2 → M1（基础设施层）
2. M4（核心工具层）
3. M3（图像工具层）
4. M2 → M5 → L1（测试层）
5. 全量测试验证

## 成功标准
- `pytest tests/ -v` 103 个测试全部通过
- 无新增警告或错误
