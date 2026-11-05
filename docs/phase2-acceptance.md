# Phase 2 验收清单（Linux 目标环境执行）

> 状态口径：Phase 2 = `code_complete`（Windows VM 完成代码与静态审查）；
> 以下为 `runtime_verified` / `accepted` 的门槛（总纲 §14.2）。
> CI（ubuntu runner）只证明可编译可测，不替代本清单的桌面会话验收。

## 准备

```bash
cd ~/toolbox
git checkout <phase2 分支>
# Qt 6.8+（Arch/CachyOS 当前包），记录实际版本：
qmake6 --version    # 或 pacman -Q qt6-base
sudo pacman -S cmake ninja qt6-base qt6-declarative-tools   # 依赖以实际情况调整
```

## 1. 独立构建（总纲 §13 Phase 2 验收）

```bash
cmake --preset linux-debug
cmake --build --preset linux-debug
```

- [ ] 配置成功，确认 Qt 实际版本 ≥ 6.4（记录版本：＿＿＿＿）
- [ ] 构建零错误；警告记录到验收记录（不阻塞）
- [ ] 生成的 `build/linux-debug/compile_commands.json` 存在（供 clang-tidy）

## 2. CTest

```bash
QT_QPA_PLATFORM=offscreen ctest --preset linux-ci
```

- [ ] `native_models`、`ipc_protocol` 两个测试通过

## 3. GUI 真实启动（Wayland 优先）

```bash
QT_QPA_PLATFORM=wayland ./build/linux-debug/toolbox
```

- [ ] 主窗口在 Wayland 会话正常显示
- [ ] 左侧导航 8 项可见；P2 三项（分析/AI/文件工具）禁用并显示"P2"
- [ ] 点击"编辑"进入编辑器：打开任意 PNG/JPG → 图像显示正常（GPU 纹理）
- [ ] 滚轮缩放以指针为中心；拖动平移；双击适配；"适配"/"100%" 按钮生效
- [ ] 带透明通道的 PNG 显示棋盘格；状态栏显示尺寸与鼠标坐标
- [ ] 深色/浅色主题切换立即生效且布局不重置（Theme 令牌驱动）
- [ ] 中文字体渲染正常（继承 Phase 0 字体体系的系统默认解析）
- [ ] 缩放窗口至最小尺寸（960×600）无重叠/裁切失控
- [ ] P2 占位页只显示计划状态，无假按钮/假表单
- [ ] 拖放图像文件到画布能打开

## 4. X11 兼容（次要）

- [ ] `QT_QPA_PLATFORM=x11` 下同样可启动与显示

## 5. 记录

- 实际锁定 Qt 版本、CMake 版本、编译器版本 → 回填本文件并更新
  `CMakeLists.txt` 的版本策略注释（总纲 §4.2 要求 Phase 2 形成明确记录）。
- 发现的缺陷 → 在 `phase0-font-system`/后续分支修复，不混杂无关改动。
