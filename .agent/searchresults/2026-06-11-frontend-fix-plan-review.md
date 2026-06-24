# 2026-06-11 前端修复计划二次核查搜索记录

## 搜索目的

用于核查 `.agent/plans/修复计划.md` 中涉及 React StrictMode 与 TypeScript Error 继承兼容性的判断是否仍符合当前官方资料。

## 资料

- React 官方文档：`https://react.dev/reference/react/StrictMode`
  - 结论：StrictMode 在开发环境会额外执行渲染和 Effect，以发现非纯渲染与缺少 cleanup 的问题。因此播放器事件监听生命周期问题可作为开发期/热更新风险记录，但不应夸大为生产阻塞 BUG。
- TypeScript / JavaScript Error 继承兼容性资料：
  - TypeScript 编译到较旧目标时，继承 `Error` 等内置对象通常需要显式修复 prototype 链。
  - 本项目 `apps/frontend/tsconfig.json` 当前 `target` 为 `ES2022`，因此 `ApiError instanceof ApiError` 的失败风险不应按 ES5 编译场景定级；更适合作为兼容性增强或防御性修复。

## 对本次文档修订的影响

- 将原 `BUG-6 ApiError 类未修复原型链` 从严重 BUG 降级为 P3 兼容性增强。
- 将原 `DESIGN-4 playerStore 的 Audio 事件监听器使用模块级标志` 保留为 P2 生命周期设计风险，不作为当前生产阻塞问题。
