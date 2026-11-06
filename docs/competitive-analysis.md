# 同类项目对比与技术调研（2026-11-06）

> 依据《全自主项目研发执行规范》§4：调研必须转化为实际行动。本文记录调研
> 结论、对比表与已排入的改进项。后续每轮持续优化阶段更新一次。

## 1. 调研来源

- [Photoflare（C++/Qt 开源图像编辑器）](https://github.com/photoflare/photoflare)与
  [Photoflare Studio](https://github.com/PhotoFlare/photoflare-studio)（商业姊妹版）
- [Qt 6.12 LTS 发布公告（2026-09-30）](https://www.qt.io/blog/qt-6.12-released)、
  [Qt Releases](https://doc.qt.io/qt-6/qt-releases.html)
- [Qt Quick Scene Graph](https://doc.qt.io/qt-6/qtquick-visualcanvas-scenegraph.html)、
  [Canvas2D WatchUI Demo（Qt 6.12 新原语）](https://www.qt.io/blog/canvas2d-watchui-demo)
- [Adobe 非破坏性编辑文档](https://helpx.adobe.com/photoshop/desktop/create-manage-layers/create-layer-compositions/non-destructive-editing-techniques.html)、
  [Max Liani: Undo, the art of](https://maxliani.wordpress.com/2021/09/01/undo-the-art-of-part-1)、
  [You Don't Know Undo/Redo](https://dev.to/isaachagoel/you-dont-know-undoredo-4hol)

## 2. 版本情报：Qt 6.12 LTS（2026-09-30 发布）

- 开源支持至约 2027-04（商业至 2031）；**确认总纲 §4.2 的"LTS 候选"猜测成立**。
- 亮点：UI 性能、QML 热重载、StyleKit、**Canvas2D（Qt Canvas Painter，GPU-only）**。
- 对本项目：CMake 下限保持 6.4（CI runner 兼容）；**产品目标锁定 Qt 6.12 LTS**，
  Canvas2D 列为画布光标/辅助线渲染的候选优化路径（替代逐帧 CPU 绘制）。
- 行动项：Arch/CachyOS 验收时记录实际 Qt 版本；`qt_add_qml_module` 的
  QML 热重载用于开发流程（Phase 8 评估）。

## 3. 对比表

| 维度 | 本项目（Toolbox 2.0） | Photoflare / Studio | darktable / Lightroom 思路 | 差距与借鉴 |
|---|---|---|---|---|
| 定位 | 图像处理+创作工具箱（批处理/生成器/AI/文档工具广度） | 轻量编辑器+批处理（Studio 加图层/笔刷） | 摄影参数化工作流 | 广度是我们的差异化；深度编辑（图层/笔刷）不在当前定位 |
| 架构 | C++/QML 壳 + Python Worker 引擎（JSON Lines IPC） | 纯 C++/Qt 单进程 | 参数管道（编辑列表重放） | 双进程边界已验证；参数管道启发 undo 演进（见 §4） |
| 滤镜 | FilterDef 声明式 + 78 内置 + G'MIC | 内置滤镜集 + 插件 SDK（Qt6 共享库） | 模块化处理单元 | Photoflare 插件 SDK 形态值得 Phase 8 后评估（backends/ 已有雏形） |
| 批处理 | 目录扫描+滤镜链/转换+任务队列 | 批处理是核心卖点之一 | — | 我们已具备；Phase 6B 迁移 UI |
| undo | Worker 端像素快照（512MB 预算）+ redo | 常规命令栈 | **参数管道重放（近乎无限 undo）** | 快照→参数重放演进（见 §4 行动项） |
| 画布 | QSG 纹理节点（已验证） | QPainter 栈 | GPU 管线 | Qt 6.12 Canvas2D 为候选增强 |
| 测试 | 319 Python + 6 C++ 目标 + CI 三关 | 未知（较少公开） | 成熟 | 我们已领先同类小型项目 |
| 发布 | Phase 8 待做 | 多平台包 | 多平台包 | AppImage/Flatpak 按计划 |

## 4. 调研转化的行动项（按价值排序）

1. **【已排入 Phase 6+】滤镜链操作的参数化 undo**：FilterChain 本身就是参数管道——
   链内操作的 undo 可以用"链版本回滚 + 重放"替代像素快照（内存从 O(像素×历史)
   降到 O(参数)），像素快照仅保留给不可参数化的操作（transform/crop 类）。
   这是 8000×5000 大图 undo 内存的主要出路。实施窗口：Phase 6A 滤镜链落地后的
   独立改进批次（需基线对比验证）。
2. **【已排入 Phase 6+】滑杆拖动命令合并（coalescing）**：拖动期间产生的多次
   adjust 预览在应用时应合并为单条历史记录（对齐行业惯例；当前 300ms 防抖已
   部分覆盖，应用侧需显式合并）。
3. **【Phase 8 评估】Qt 6.12 目标**：Arch 包升级后把 CMake 产品目标提到 6.12，
   评估 Canvas2D 替代 ImageCanvas 的辅助线/选区层。
4. **【观察项】插件 SDK 形态**：Photoflare 的 Qt6 共享库插件接口与本项目
   backends/ 抽象同源；若未来出现第三方扩展需求，参考其 SDK 头文件组织。
   当前不引入（维护成本 > 收益）。
5. **【观察项】libmypaint 笔刷引擎**：仅当项目定位扩展到绘画（不在当前路线图）。
