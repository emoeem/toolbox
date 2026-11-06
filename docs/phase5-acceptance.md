# Phase 5 验收清单（Linux 目标环境执行）

> 状态口径：Phase 5 = `code_complete` / `static_reviewed`（总纲 §14.2）。本清单
> 通过后才算 `runtime_verified`；通过前迁移矩阵相关行保持 `待迁移`
> （ui-migration-matrix.md 头部状态取值规则：只有 `待迁移` / `已迁移` 两种取值，
> `已迁移` 要求新 UI 中真实可用并验收）。
> 分工口径：§1 为 CI 已覆盖的逻辑层项（实机不重复执行）；§2 起为必须在 Linux
> 目标环境（真实 Worker 进程 + 真实桌面 GUI 会话）执行的项。
> 依赖：Phase 3 跨进程垂直切片（docs/phase3-acceptance.md §3）与 Phase 4 GUI
> 验收（docs/phase4-acceptance.md）截至本清单撰写均**尚未在目标环境执行**
> （两清单复选框未回填；CHANGELOG Phase 1-4 条目口径一致）。本清单 §2 的
> 端到端项天然覆盖 Phase 3 切片的核心路径（启动/握手/打开/预览/保存/崩溃），
> 执行时按 docs/phase3-acceptance.md、docs/phase4-acceptance.md 一并回填。
> 覆盖范围：总纲 §7 Phase 5（核心图像编辑工作流）中本批实际交付的 5A 文件工作流
> / 5B 画布接线 / 5C 基础编辑 / 5D 图像状态；未交付项见 §8 偏差记录。

## 准备

```bash
cd ~/toolbox
git fetch origin && git checkout <phase5 分支>
uv sync --extra dev                       # Worker 依赖沿用现有锁定环境
cmake --preset linux-debug && cmake --build --preset linux-debug
```

## 1. CI 已覆盖（实机不重复执行；推送后以 GitHub Actions 实际结果为准）

> 以下项由 CI 两个 job 的现有机制自动纳入：test job 的
> `unittest discover` 会发现 `tests/test_worker_edit.py`，native job 的 CTest
> 注册了 `document_service` 目标（tests/native/CMakeLists.txt）。截至本清单
> 撰写，Phase 5 改动尚未提交推送——清单中"CI 已覆盖"均指测试已就位并随既有
> CI 机制执行，推送后的实际运行结果回填 §8。

- [ ] Worker 编辑动作逻辑单测（Python，`tests/test_worker_edit.py`，12 个用例，
      进程内 Dispatcher + TaskRuntime，不启动 QProcess）：
      - `image.adjust` 预览（写临时文件、`version` 不递增、像素/历史/modified
        不变）与全分辨率（`version`+1、进历史）；undo → redo → reset 往返的
        sha256 像素对照
      - `image.transform` 五个 op：crop（改尺寸+进历史）、scale（预览）、
        flip_h / flip_v（历史推进）、rotate（像素变化+尺寸不变+可撤销）；
        未知 op / crop 越界 / 缺参 / sx≤0 提交前同步 `INVALID_PARAMS`
      - `image.undo` / `image.redo` 栈空：提交前同步 `UNREDOABLE`，不产生任务
      - `image.reset`：清空历史、像素回源图、未编辑文档同样成功且 `version`+1
      - `image.history`：entries / current / canUndo / canRedo 随操作演进，
        非栈顶新变更截断 redo 分支
      - 历史深度淘汰（512MB 预算压到 2 快照强制触发）：entries[0] 恒为
        open、undo 到底像素回到源图（底条目钉在源图上）、条目名与可达状态
        一一对齐、redo 分支按重做顺序对齐（§3.3 契约在任意淘汰深度下保持）
      - `UNKNOWN_DOCUMENT`：undo / redo / reset / history 同步拒绝；
        adjust / 非 crop transform 走异步 task.failed（运行时归一
        `ENGINE_ERROR`，现状行为，见 §8）；crop 因越界判定先取文档，同步拒绝
      - `filter.apply` 与历史衔接：进历史、`version` 字段、可 undo
- [ ] 协议形状与任务运行时（Python，`tests/test_worker_protocol.py`）：消息
      编解码、`protocol` 版本、取消到终态、进度节流 ≥100ms、store 层
      UNKNOWN_DOCUMENT（`image.*` 新动作复用同一 Dispatcher/TaskRuntime 语义）
- [ ] 引擎像素基线（Python，`tests/test_engine_baseline.py` +
      `tests/baselines/engine_baseline.json`）：`processors/core` 42 个算子
      （含 brightness / contrast / saturation / gamma / exposure / hue_shift /
      vibrance / highlights_shadows / rotate / scale / flip_h / flip_v / crop）
      的 sha256 输出锁定——undo 像素回归的算子级对照基准（Phase 0 固定）
- [ ] C++ 服务与模型（CTest，`tests/native/test_document_service.cpp`，21 个
      用例，信号模拟不启动 Worker）：DocumentService 的 version / modified /
      previewReady 状态机、异步动作受理经 bindTaskModel 登记 TaskModel 任务行
      （任务抽屉/摘要与行内取消的数据源）、reset 完成 version+1 且清
      modified（与 Worker 端语义一致）、undo/redo/reset 完成携带画布刷新
      文件、陈旧任务丢弃、本地拒绝（未开文档 / 未绑定后端）、失败与取消归一
      documentError 且未落定动作另发 documentActionFailed（携带提交
      documentId 与动作标识，预览带 -preview 后缀，QML 在途门控的解锁依据）、
      HistoryModel 的 refreshFrom / 角色名 / canUndo / canRedo
- [ ] CI 环境边界（为何仍需实机）：ubuntu runner、`QT_QPA_PLATFORM=offscreen`、
      C++ 测试以信号模拟 Worker 帧（不启动真实进程、无 GUI 交互、无真实
      图像文件打开）。逻辑层之上的进程、图形与交互项全部归 §2-§6。

## 2. 垂直切片端到端（必须实机）

> 对应 docs/user-flows.md 流程 1 与 docs/ui-page-spec.md §2。全部经 EditorPage
> 真实控件操作，不使用测试驱动。

- [ ] **打开**：工具栏"打开"FileDialog 选择图像 → 画布立即显示本地文件（快速
      显示），`documentOpened` 后状态栏显示 `宽×高 · v0`；Worker 未就绪时
      Toast 提示且画布仍显示已加载数据（降级横幅出现在检查器）
- [ ] **拖放打开**：从文件管理器拖图像到画布 → 同上；非图像文件拖入有失败
      Toast（不崩溃）
- [ ] **调整预览**：拖动亮度/对比度等滑杆 → 300ms 防抖后画布更新（预览）；
      松手立即再出一次高清晰预览；预览期间 `v0`、`●`、撤销按钮均不变
- [ ] **应用**：点"应用" → `v0 → v1`、文件名旁出现 `●`、滑杆回中性基线、
      画布刷新为已应用像素、历史条目 `image.adjust` 入栈（撤销按钮点亮）
- [ ] **变换**：旋转90° / 水平翻转 / 垂直翻转按钮 → `version` 递增、尺寸变化
      反映到状态栏（旋转方形样本尺寸不变时核对历史与 `●`）
- [ ] **撤销 / 重做**：`Ctrl+Z` 与工具栏 ↶ → 画布回到上一状态、`version` 仍
      递增（协议 §3.1）、重做按钮点亮；`Ctrl+Shift+Z` 与 ↷ 前进；按钮启停与
      HistoryModel canUndo / canRedo 一致（撤销到底后 ↶ 禁用）
- [ ] **重置**：工具栏"重置" → 画布回到打开时的初始像素、历史清空（撤销/
      重做/重置全部禁用）、`●` 依据 modified 如实显示
- [ ] **保存**：`Ctrl+S` / "保存"（仅 modified 时可用）→ FileDialog 预选当前
      文件名 → 保存成功 Toast、`●` 消失；"另存为"落盘新路径后标题路径跟随；
      目标文件可被旧程序（`python main.py`）正常打开
- [ ] 全程状态栏任务摘要按钮可展开任务抽屉，任务行与操作一一对应

## 3. undo 像素回归（与 Phase 0 引擎基线一致，必须实机）

> 算子输出已由 CI 锁定（§1 engine_baseline）；本节验证的是实机整链路：
> Worker 像素快照恢复 → 降采样预览文件（§4 临时文件）→ ImageCanvas 纹理，
> 三段之间不串图、不串版本。

- [ ] 用确定性样本打开（`uv run python tools/make_test_samples.py --force`
      生成，取 `gradient.png`）
- [ ] brightness 0.3 应用（`v1`）→ 撤销（`v2`）→ 画布与打开时肉眼一致；
      再重做 → 画布与应用时一致
- [ ] 无 GUI 的像素级核对（对真实 Worker 进程 stdio 发消息；原理：undo 的
      画布刷新文件与"新开同一文件 + 全默认调整预览"都出自同一个
      `write_preview` 确定性 PNG 编码，两者 sha256 相等 ⇔ undo 恢复的像素
      与打开时一致）：

```bash
cd ~/toolbox
uv run python - <<'PY'
import json, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, 'tools')
from make_test_samples import generate

tmp = Path(tempfile.mkdtemp())
generate(tmp, force=True)
sample = tmp / 'gradient.png'

proc = subprocess.Popen(
    [sys.executable, 'python_worker/main.py', '--repo-root', '.', '--temp-dir', str(tmp)],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL, text=True, encoding='utf-8')

def run(action, params, rid, timeout=30):
    """发送请求，返回同步 result 或 task.completed 的 result；失败即退出非 0。"""
    proc.stdin.write(json.dumps({'protocol': 1, 'request_id': rid,
                                 'action': action, 'params': params}) + '\n')
    proc.stdin.flush()
    deadline, task_id = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            raise SystemExit(f'{action}: worker stdout 意外关闭')
        msg = json.loads(line)
        if msg.get('request_id') == rid:
            if not msg.get('success'):
                raise SystemExit(f'{action}: 同步拒绝 {msg.get("error")}')
            task_id = (msg.get('result') or {}).get('task_id')
            if not task_id:
                return msg['result']            # 同步动作（open/history/close）
        elif task_id and msg.get('task_id') == task_id \
                and msg.get('type') in ('task.completed', 'task.failed'):
            if msg['type'] == 'task.failed':
                raise SystemExit(f'{action}: 任务失败 {msg.get("error")}')
            return msg['result']
    raise SystemExit(f'{action}: 等待超时')

run('worker.hello', {}, 'r0')
doc = run('image.open', {'path': str(sample)}, 'r1')['document_id']
run('image.adjust', {'document_id': doc,
                     'adjustments': {'brightness': 0.3}, 'preview': False}, 'r2')
undone = run('image.undo', {'document_id': doc}, 'r3')          # v2，带画布刷新文件
fresh_doc = run('image.open', {'path': str(sample)}, 'r4')['document_id']
fresh = run('image.adjust', {'document_id': fresh_doc,
                             'adjustments': {'gamma': 1}, 'preview': True}, 'r5')  # 全默认 = 原样
run('worker.shutdown', {}, 'r6')
proc.stdin.close()
proc.wait(timeout=10)

ok = undone['sha256'] == fresh['sha256']
print('undo 恢复像素 sha256 :', undone['sha256'])
print('打开基准像素 sha256 :', fresh['sha256'])
print('PASS' if ok else 'FAIL: undo 恢复的像素与打开时不一致')
sys.exit(0 if ok else 1)
PY
```

- [ ] 备选（推荐，免脚本）：同一张图连续执行 应用→撤销→重做→重置 各两次，
      画布无残影、无上一版本缓存串显（编辑器 URL `?v=` 强制重载生效）
- [ ] numba 与纯 Python 两种引擎路径各跑一次（`TOOLBOX_NO_NUMBA=1` 对照），
      undo 后画布一致（CI 算子基线分平台锁定，实机确认所选路径）

## 4. Worker 崩溃后 document_id 失效提示（必须实机）

- [ ] 打开文档并做一次未保存修改（`●` 出现）→ `kill -9 <worker_pid>`
      （`pgrep -f python_worker/main.py` 取 pid）
- [ ] UI 立即收到 `WORKER_CRASHED`：Toast 显示错误码与"未保存的编辑状态不可
      恢复，请从源文件重新打开"（backend_manager.cpp:166-173），状态栏转
      `已崩溃`，EditorPage 在途按钮（应用/变换）复位（ui/pages/EditorPage.qml
      onErrorOccurred）
- [ ] 自动重启：1s 退避、上限 3 次（backend_manager.h `kMaxRestarts = 3`），
      重启后状态栏回 `就绪`
- [ ] 旧 document_id 失效：重启后继续对旧文档撤销/调整 → Worker 返回
      `UNKNOWN_DOCUMENT`，UI 以 Toast 如实呈现，**不得**出现"已恢复"类
      谎报；用户从源文件重新打开后一切恢复正常
- [ ] 已知缺口（如实验收，验收结论回填 §8）：BackendManager 崩溃不清空
      DocumentService 的 currentDocumentId（document_service.cpp 未连接
      errorOccurred），失效提示依赖下一次操作的 UNKNOWN_DOCUMENT 兜底，
      崩溃后到下一次操作前 UI 仍显示旧文件名与旧 `●` 状态。若该窗口期被
      判定为不可接受，随修复更新本节与 CHANGELOG，不改口径。
- [ ] 启动失败路径：设置页填入不存在的 python 路径启动 →
      `WORKER_START_FAILED` 可读提示，状态栏不谎称就绪

## 5. 大图不卡 UI（必须实机）

- [ ] 准备 ≥40MP 图像（可用 ImageMagick 生成：`magick -size 8000x5000
      gradient:red-blue big.png`）
- [ ] 打开大图：画布显示 ProgressIndicator（`canvas.busy`）。**已知代价
      （§8 偏差 1）**：打开首帧由 ImageCanvas 在 GUI 线程同步解码本地文件
      （`native/graphics/image_canvas.cpp` setSource：QImageReader 全图解码，
      alpha 图另有整图逐格棋盘格合成），40MP 级别会阻塞界面秒级——本项如实
      记录实测阻塞时长回填 §8，不把"打开期间可交互"作为通过条件；"打开
      完成前界面可切换页面"仅在打开耗时低于可感知阈值时自然成立
- [ ] 调整预览与应用期间：拖动窗口、切换滑杆、缩放画布全程无卡顿（这些
      阶段的像素计算全在 Worker 进程，QML/C++ 主线程零像素计算——总纲 §9；
      打开首帧的本地同步解码是已知例外，见上条与 §8 偏差 1）
- [ ] 任务抽屉中该任务行 queued → running → completed 可见，进度条随
      task.progress 事件更新且节流 ≥100ms 可观察（相邻时间戳）
- [ ] 记录大图 open（含首帧同步解码阻塞时长）/ preview / apply / undo 实测
      耗时 → §8

## 6. 取消行为（必须实机）

- [ ] 大图调整预览进行中：展开任务抽屉 → 行内"取消"按钮 → 行变 `cancelling`
      → Worker 回报后转 `cancelled`（显示"已取消"，非"失败"，TaskModel 呈现）
- [ ] 取消后：画布保持当前文档像素、`version` 不变、滑杆值不动（可继续
      重新预览）；`task.failed` 事件 `code=CANCELLED` 在任务行显示为已取消
- [ ] 全分辨率应用（大图）进行中取消：同上，且文档不被半途修改（协作检查
      点在应用前抛出 CancelledError，§7）
- [ ] 已终结任务的取消按钮无效（TaskModel 本地拒绝，不发 task.cancel）
- [ ] 已知偏差（如实记录）：ui-page-spec §2 的"Esc 取消在途预览"未实现
      （ImageCanvas 无 Esc 处理），取消入口当前只有任务抽屉行按钮；偏差
      回填 §8 并同步修订页面规格

## 7. 最近文件（5A 收尾项）

- [ ] 打开文档 → HomePage 最近文件行出现该文件；重复打开去重置顶；累计
      超过 10 条按上限裁剪（服务层语义已由 CTest 锁定，此处验 GUI 展示）
- [ ] 重启应用后最近文件仍在（`~/.config/Emo/Toolbox2.conf`）
- [ ] 已知缺口（如实记录）：HomePage 最近文件行为只读展示，点击打开未
      接线（ui/pages/HomePage.qml 头注释：打开属文件工作流，本批未交付），
      从最近文件打开留待后续批次，验收时不得当作可用入口

## 8. 偏差与记录（回填）

- 与 docs/ui-page-spec.md §2 的偏差逐条列出：Esc 取消未实现；检查器仅
  "调整"页签（滤镜页签属流程 2，未在本批）；裁剪/缩放（crop / scale）有
  协议与 Worker 支持但无 UI 入口（本批仅旋转 90°/翻转按钮）；调整页签实现
  为 9 个滑杆（含伽马，EditorPage.qml gammaSlider，中性 1.0），ui-page-spec
  §2 只列 8 个（无伽马）；检查器内无[重置]按钮——重置为工具栏入口且语义是
  §3.3 的重置到源图，ui-page-spec §2 的检查器[重置]（回滚到已应用状态）未
  实现，两者语义不等价。ui-page-spec §2 对应两行（滑杆清单、检查器按钮）
  的修订与偏差 1 的加载态表述修订同批进行（该文档不在本批清单，偏差在此
  与 CHANGELOG 已知限制如实记录）
- 偏差 1（打开首帧为 GUI 线程本地同步解码）：EditorPage 打开/拖放采取
  "画布先行"（本地文件 URL 直接交 ImageCanvas 快速显示），
  `native/graphics/image_canvas.cpp` setSource 在 GUI 线程 QImageReader
  同步解码全图（alpha 图再整图逐格合成棋盘格），大图打开会阻塞界面——
  ui-page-spec §2 加载态"先显示低清快速预览"按现状不成立；打开链路
  异步化（Worker 低清首显或解码移出 GUI 线程）与该表述的修订留待后续
  批次，本批验收只考察预览/应用/撤销阶段的零像素计算（§5 已同步弱化）
- 偏差 2（换文档回收的在途豁免）：DocumentService 在打开成功后对旧
  document_id 发 `image.close`（fire-and-forget，协议 §3）回收 Worker 内
  的旧文档像素与快照；旧文档仍有在途任务时跳过本次回收（close 会让任务体
  的 store.get 抛 `UNKNOWN_DOCUMENT`，把合法的保存/应用打成失败），被跳过
  的旧文档随下次切换或 Worker 退出回收
- 本清单未覆盖、留待后续批次的 Phase 5 计划项：格式转换入口（5A）、
  高 DPI 与纹理释放细化（5B）、图像元信息面板（5A）
- 回填项：CI 实际结果链接与结论；§3 的 sha256 脚本输出；§4 崩溃重启次数与
  UNKNOWN_DOCUMENT 提示原文；§5 耗时数据（含打开首帧解码阻塞时长）；§6
  取消时延；实际桌面会话（X11 / Wayland）→ 直接写入本文件对应小节。
