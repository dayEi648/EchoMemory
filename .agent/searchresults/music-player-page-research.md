# 音乐播放页 / 歌词滚动 — 业界调研摘要

调研时间：2026-06-12

## 网易云音乐（PC / Web 仿作）

常见实现模式（多篇 Qt / Vue / WPF 仿网易云教程共识）：

1. **全屏播放层**：非 Tab 路由页；从底栏封面进入；下拉/向下箭头收起；专辑图高斯模糊背景。
2. **歌词容器**：`ScrollView` / `overflow-y: auto` 包裹歌词列表，**保留滚动条**，当前行高亮。
3. **同步**：`timeupdate` / `positionChanged` 取当前秒数 → 二分/遍历找 LRC 行索引。
4. **滚动居中**：
   - Web 常见：`translateY` 累加行高，使高亮行保持在容器垂直中心；
   - 桌面常见：`scrollTo` / `ScrollViewer` 滚到「当前行相对于列表中心」。
5. **交互**：点击歌词 seek；用户手动滚动后暂停自动跟随，提供「回到当前」。
6. **视觉**：当前行高亮（白/品牌色）；前后行降低透明度；旋转唱片。

参考：
- [Vue3 仿网易云歌词滚动](https://blog.csdn.net/xzwwjl1314/article/details/115232534)
- [WPF 低仿网易云歌词控件](https://developer.aliyun.com/article/676701)
- [博客园 仿网易云播放页](https://www.cnblogs.com/cheryshi/p/14781536.html)

## QQ 音乐

1. **播放页权重极高**：聚合分享、海报、弹幕、一起听等；默认 Tab 含「歌曲 / 评论 / 推荐」。
2. **沉浸式歌词**：点击歌词区域进入全屏；装扮中心可选歌词动效模板（水波、光点等）。
3. **歌词能力**：字号、简繁、进度微调、歌词海报分享。
4. **技术侧（官方披露）**：ASS 特效字幕 + 客户端绘制；序列帧/视频背景；手势滑动。

参考：
- [QQ音乐11.0 设计总结](https://geekdaxue.co/read/weijin_is_wiki@ykf0s9/kqk1tu)
- [QQ音乐产品设计拆解](https://news.qq.com/rain/a/20220713A06ECS00)

## 开源 / 国际实践

### Koel（Web 自托管播放器）PR #2154

- 100ms 轮询播放进度
- LRC 正则解析
- 当前行居中 `scrollIntoView` / 自动滚动
- 无时间戳行：首行 0、末行沿用前一行、中间取相邻均值

### La Urban Radio Player 歌词系统

- **100ms** 更新间隔（平滑与 CPU 平衡）
- iOS 流延迟补偿（4.5s vs 1.5s）
- Tab 隐藏时暂停更新
- **仅歌词索引变化时改 DOM**，减少重排
- CSS：`transition` + `opacity` + `translateY` 做行间过渡
- 非 LRC 时静默降级

参考：https://www.mintlify.com/isanchezcigna/laurban-repro-simple/features/lyrics-system

### Apple Music 风格（react-native-skia）

- ELRC 字级时间戳 + 逐词高亮
- Reanimated 60fps 滚动

### Lyricify（Android）

- 60 FPS 滚动
- 三档渲染引擎
- 点击行 seek；手动滚动与自动跟随分离

## 对我们项目的启示（echomemory 桌面端）

| 能力 | 业界共识 | 我们当前 | 建议 |
|------|----------|----------|------|
| 播放页形态 | 全屏 overlay，非路由 Tab | ✅ 已实现 overlay | 保持 |
| 歌词容器 | 真实 scroll + 可见滚动条 | ✅ 已改回 | 保持 |
| 滚动方式 | 100ms 跟拍或 rAF 插值 | rAF + lerp | 可加 100ms 节流减 DOM 压力 |
| 高亮 | 固定行高 + 透明度梯度 | 透明度梯度 | 避免 scale/改字号造成跳动 |
| 手动滚动 | 锁定 +「回到当前」 | ✅ 已有 | 保持 |
| 背景 | 封面模糊 + 渐变遮罩 | ✅ 有 | 可加强暗角 |
| 唱片 | 播放时旋转 | ✅ 有 | 保持 |
| 字级歌词 | ELRC（可选高级） | 仅 LRC 行级 | 后期可选 |
| 播放页 Tab | 歌曲 / 评论 / 相关 | 歌词+评论同屏 | 可考虑 Tab 分离 |
