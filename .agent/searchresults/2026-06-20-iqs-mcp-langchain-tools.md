# IQS Search MCP 与 LangChain Tools 官方资料核对（2026-06-20）

## 结论

- 阿里云 IQS Search MCP 的标准搜索工具名为 `common_search`，参数为 `query`，长度要求为 2~500，返回 Markdown。
- 标准搜索 MCP 的 Streamable HTTP 地址为：
  `https://iqs-mcp.aliyuncs.com/mcp-servers/iqs-mcp-server-search`
- MCP 鉴权支持请求头 `X-API-Key: <API-Key>`。
- LangChain 官方推荐使用 `langchain-mcp-adapters` 的
  `MultiServerMCPClient` 加载远程 MCP 工具；HTTP transport 可通过 `headers`
  传递鉴权信息。
- `@tool` 默认把函数 docstring 作为工具 description，类型标注用于生成输入
  schema；不需要在系统提示词重复声明工具使用说明。
- LangChain 官方明确支持运行时动态筛选预注册工具，适用场景包括用户权限、
  feature flag 和会话阶段。

## 对本项目的影响

- `search_web` 应保留为本项目面向模型的稳定工具名和 docstring，但执行应委托给
  IQS MCP 的 `common_search`，不再直接请求 UnifiedSearch REST API。
- 工具注册中心仍注册本地 `search_web`，从而隔离远程 MCP 工具命名和连接细节，
  便于后续替换供应商或增加网页解析等工具。
- 工具动态筛选必须同时作用于模型绑定与执行阶段，避免模型历史消息或恶意工具名
  绕过当前权限。

## 官方来源

- 阿里云 IQS MCP：
  https://help.aliyun.com/zh/document_detail/2881063.html
- LangChain Tools：
  https://docs.langchain.com/oss/python/langchain/tools
- LangChain MCP：
  https://docs.langchain.com/oss/python/langchain/mcp

