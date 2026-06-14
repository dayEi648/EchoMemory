"""AI 基础设施包。

按职责分层：
- ``clients``：底层 LLM HTTP 客户端。
- ``langchain``：LangChain 兼容的模型与适配器。
- ``tools``：跨 Graph/Chain 复用的 LangChain 工具。
- ``graphs``：LangGraph 工作流与共享设施。

导入规则：
- ``clients/`` 可被 ``langchain/``、``tools/``、``graphs/`` 导入。
- ``langchain/`` 可被 ``tools/``、``graphs/`` 导入。
- ``tools/`` 可被 ``graphs/`` 导入，禁止反向导入 ``graphs/``。
- 各工作流之间禁止互相导入。
"""
