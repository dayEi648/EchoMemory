# 2026-06-10 React 白屏调试资料

## 搜索目的

确认 React 19 下组件渲染期异常与白屏表现的官方说明，用于分析 EchoMemory 首页白屏问题。

## 使用来源

- React 官方文档 `Component`：渲染期间抛出异常时，默认会移除屏幕上的 UI；可通过 Error Boundary 显示降级 UI。
- React 官方博客 `React 19`：React 19 改进了捕获/未捕获错误的日志能力，`createRoot` 提供 `onCaughtError`、`onUncaughtError`、`onRecoverableError` 等选项。

## 与本次问题的关系

当前前端未在首页主树外层设置 Error Boundary，因此若页面组件在 render 阶段访问不存在字段（例如 `item.music.authors.map(...)`）并抛出异常，React 会卸载 UI，用户看到纯白屏。
