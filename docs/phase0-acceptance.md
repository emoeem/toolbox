# Phase 0 验收清单（在 Linux 虚拟机执行）

> Phase 0 的代码与文档已在 `phase0-font-system` 分支完成（Windows 侧编写）。
> 本清单全部命令需在 Linux 虚拟机执行；执行结果回填到每节末尾的"结果"处。
> 对应升级计划 §7 Phase 0 的验收条款。

## 准备

```bash
cd ~/toolbox                    # 仓库位置
git fetch origin
git checkout phase0-font-system
uv sync --extra dev             # 依赖由 uv.lock 锁定（清华镜像）
uv run python -c "import PySide6; print(PySide6.__version__)"
```

## 1. 原有测试不回退（对照 CI 口径：无 numba）

```bash
TOOLBOX_NO_NUMBA=1 QT_QPA_PLATFORM=offscreen \
  uv run python -m unittest discover -s tests -v
```

预期：

- 全部通过或 skip，无 FAIL/ERROR（skip 仅允许出现在：缺外部后端 gmic、
  无 numba、无候选字体/CJK/Emoji 字体的环境守卫）。
- 首次运行会自动生成 `tests/baselines/engine_baseline.json`
  （样本 + 42 个核心算子 + IO 往返的 sha256）并 skip 基线对照 ——
  **该文件需要提交**，作为迁移期引擎行为基线。

结果：（待回填）

## 2. 基线复验（生成后再次运行必须严格对照）

```bash
TOOLBOX_NO_NUMBA=1 QT_QPA_PLATFORM=offscreen \
  uv run python -m unittest tests.test_engine_baseline -v
```

预期：`test_samples_unchanged` / `test_ops_match_baseline` /
`test_save_load_roundtrip_deterministic` 全部真实通过（非 skip）。

结果：（待回填）

## 3. Ruff（CI 门禁）

```bash
uv run ruff check .
```

结果：（待回填）

## 4. 旧程序真实启动 + 字体验收（GUI，非 offscreen）

```bash
# Wayland 优先（对应升级计划 Phase 1 验收口径，本阶段先确认不劣化）
QT_QPA_PLATFORM=wayland uv run python main.py
# 若虚拟机无 Wayland 会话：QT_QPA_PLATFORM=x11
```

检查项（逐条勾选）：

- [ ] 程序正常启动，侧栏 45 项工具可见
- [ ] 中文界面文字渲染正常，无字体意外回退（标题/面板/按钮）
- [ ] 设置 → 字体：默认显示"(系统默认)"
- [ ] 设置 → 字体改为任一已安装字体（如 Noto Sans CJK SC）+ 字号改 14 →
      确定后**全局立即生效**（此前 QSS 强制 13px 导致字号无效）
- [ ] 设置 → 等宽字体选择后，打开 Shader Studio：代码编辑器字体跟随设置
      （此前硬编码 Maple Mono，设置无效）
- [ ] 恢复默认 → 字体回"(系统默认)"、字号回 11
- [ ] 深色/浅色主题切换正常，文字样式无异常
- [ ] 打开一张图片 → 调整亮度滑杆 → 预览 → 应用 → 撤销，全链路正常

结果：（待回填）

## 5. 字体解析诊断（可诊断性要求，升级计划 §9）

```bash
QT_QPA_PLATFORM=offscreen uv run python - <<'PY'
import json
from PySide6.QtWidgets import QApplication
from app.settings_store import DesktopSettings
from app.fonts import diagnose
app = QApplication([])
print(json.dumps(diagnose(DesktopSettings()), ensure_ascii=False, indent=2))
PY
```

预期：输出 `ui.resolved` / `mono.resolved` 为真实存在的字体族，
`coverage` 五项（latin/digit/cjk/symbol/emoji）布尔值符合虚拟机字体安装情况，
未覆盖项的 `fallback` 列出可用回退字体。

结果：（待回填）

## 6. Wayland 实机项说明

Phase 0 验收不含完整 Wayland 专项（那是 Phase 1 验收条款 §7）。本阶段只需
确认 GUI 在虚拟机桌面会话中可正常启动与交互（上述第 4 节）。

## 7. 完成后动作

```bash
git add tests/baselines/engine_baseline.json
git commit -m "test: 固定核心图像处理引擎基线（Phase 0 验收）"
```

注意：除基线文件与验收记录外，若发现任何代码问题需要修复，请继续在
`phase0-font-system` 分支提交，不要混入无关改动。
