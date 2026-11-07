# Toolbox 2.0.0-alpha.2

alpha.1 实机反馈修复版：**Wayland 平台插件缺失**与 **QML 运行时验证缺口**。

相对 alpha.1 的变化：

- **Wayland 首启修复**：Linux 包改用发行版 Qt（含 qt6-wayland），Wayland
  会话首启不再报 `Could not find the Qt platform plugin "wayland"`；
  Arch pacman 包 depends 补 `qt6-wayland`。
- **打包自检**：四个安装包在 CI 内各真实启动一次（`--qml-smoke`，
  offscreen 加载主壳 QML），"构建绿但运行时坏"的缺口关闭。
- **QML 烟雾门禁进 CI**：ctest 新增 `qml_smoke`（真加载 Main.qml），
  QML 类型解析错误自此在 CI 必拦。
- Linux 包基准 ubuntu-22.04 → ubuntu-24.04（GLIBC ≥ 2.39）。
- 版本定版 2.0.0-alpha.2（pyproject + 应用常量对齐）。

完整功能面与已知限制见 [alpha.1 发布说明](releases/tag/v2.0.0-alpha.1)
与本仓库 `CHANGELOG.md`。alpha 口径：三平台 CI 构建通过；GUI 实机验收
进行中，欢迎继续反馈（issues）。
