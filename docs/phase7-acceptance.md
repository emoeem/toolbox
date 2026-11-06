# Phase 7 验收清单（Linux 目标环境执行）

> 状态口径：Phase 7 = `code_complete` / `static_reviewed`（总纲 §14.2）。本清单
> 通过后才算 `runtime_verified`；通过前迁移矩阵对应行保持 `待迁移`
> （ui-migration-matrix.md 头部状态取值规则：`已迁移` 要求"新 UI 中真实可用
> 并验收"，CI 单测不构成改判依据）。
> 分工口径：§1 为 CI 已覆盖的逻辑层项（实机不重复执行）；§2 起为必须在 Linux
> 目标环境（真实 Worker 进程 + 真实桌面 GUI 会话）执行的项——本清单按任务
> 要求把 **AI 降级说明**单列（§4）、**依赖缺失置灰路径**单列（§3）。
> 覆盖范围：总纲 §13 Phase 7（AI 与辅助工具）以**统一工具页**交付的垂直切片
> ——协议 `assist.list` 与 assist 动作族共 32 个工具动作 + §5 错误码
> `DEPENDENCY_MISSING`（docs/ipc-protocol.md §3.8，2026-11-07 复查注），工作流
> = **工具目录浏览 → 选择工具 → 参数提交 → 运行 → 结果呈现/导出**；OCR / PDF
> / 条形码 / ASCII / 对比 / 校验和 / 直方图 / LUT / 媒体 / EXIF / 水印 / 归档 /
> 加密 / Base64 / AI 逐族见 §2。
> **如实边界（不得把本批当成 1.0 辅助能力全量迁移）**：
> - 未注册为协议动作的 1.0 辅助能力不在本批：EXIF 按 Tag 编辑（1.0
>   `parity.edit_exif` 的写入面——协议只收 `exif.extract`/`exif.strip`）、
>   PDF→图片之外的反向"图片→PDF"、压缩实验室 / 按体积压缩（`parity.compress`
>   系）、查找重复/相似图片（`parity.duplicate-finder` 系）、AI 深度图
>   （`ai.depth_map`）、DataMatrix 条码（1.0 实现是 QR 伪实现，按"不凭空造
>   实现"不注册）、EAN-13 的 PIL 兜底伪条码（依赖缺失即拒绝）。清单化逐项
>   状态见 ui-migration-matrix.md 对应行。
> - AI 模型的**安装/卸载（网络下载）不在本批动作面**：`ai.models.list` 只读
>   （注册表安装状态 / 后端探测 / 模型路径配置视图）；模型缺失即降级（§4）。
> - 工具页参数面板为**参数 JSON 编辑器**（AppToolsPage 按"值对象 JSON"提交
>   runTool），非逐工具表单化控件（ui-page-spec.md §4 工具页模板的表单化
>   属后续批次）；目录 `description` 字段协议面保留、未进模型角色面（同
>   §3.7 GeneratorModel 处置）。
> - `ai.upscale` 在配置了 EDSR 模型路径（settings.json `model_paths` 或
>   `TOOLBOX_AI_MODEL_DIR`）时走 OpenCV DNN（无外部二进制），否则要求
>   upscayl 二进制 + Real-ESRGAN 系统模型——两条路径都要在 §4 如实验证。
> 依赖：Phase 5/6A/6B/6C 验收截至本清单撰写均**尚未在目标环境执行**。本清单
> 复用其机制：置灰卡片 AppFilterCard 与依赖 Tooltip（6A/6C 同源）、任务抽屉
> /Toast（Phase 4 组件）、导出编辑器经 StudioService.exportToEditor →
> DocumentService::openDocument（Phase 5/6C 通道）。
> 实现锚点：Worker 侧 `python_worker/adapters/assist_adapter.py`
> （目录表 _TOOL_TABLE assist_adapter.py:214-324、list_tools
> assist_adapter.py:327-346、依赖探测函数 assist_adapter.py:77-143、
> 模型路径配置 model_path_config assist_adapter.py:148-187）与
> `python_worker/dispatcher.py`（sync 动作表 dispatcher.py:52-58、async
> 动作表 dispatcher.py:75-103、处理器 dispatcher.py:285-384）、错误码
> `ERR_DEPENDENCY_MISSING`（python_worker/protocol.py:21）；复用 1.0 资产
> 不重写——`processors/parity.py`（ocr_image/extract_exif/strip_exif/
> watermark/archive_images/encrypt_file/decrypt_file/base64_encode/
> base64_decode）、`processors/pdf_tools.py` 全部 7 函数、
> `processors/barcode.py`、`processors/ascii.py`、`processors/lut.py`、
> `processors/media.py`、`processors/compare.py`、`processors/histogram.py`、
> `processors/checksum.py`、`processors/ai.py`、`processors/ai_models.py`、
> `python_worker/adapters/filter_adapter.py` `write_preview`（§4 临时 PNG
> 通道）。C++ 侧 `native/models/assist_model.*`（reloadFrom
> assist_model.cpp:9-39，五角色 roleNames assist_model.cpp:65-73）与
> `native/services/assist_service.*`（loadTools assist_service.cpp:76-83、
> runTool assist_service.cpp:85-115、响应关联与 sync/async 形状判定
> assist_service.cpp:129-172、任务终态 assist_service.cpp:174-205）；QML 侧
> `ui/components/AppToolsPage.qml`（选择/认领 AppToolsPage.qml:206-222、
> 运行单飞 AppToolsPage.qml:226-238、结果解析 AppToolsPage.qml:248-292、
> 120s 运行看门狗 AppToolsPage.qml:899-909）与 `ui/pages/ToolsPage.qml`
> （宿主）；导航接线 `native/app/application.cpp:86-91`（navModel `files` →
> ToolsPage.qml，替代 Phase 4 PlannedPage 占位）。协议形状见
> docs/ipc-protocol.md §3.8 与 §3 动作表 assist 段。

## 准备

```bash
cd ~/toolbox
git fetch origin && git checkout <phase7 分支>
uv sync --extra dev                       # Worker 依赖沿用现有锁定环境
cmake --preset linux-debug && cmake --build --preset linux-debug
```

测试素材：

- 一组真实图片（含带 EXIF 的 JPEG、纯色 PNG）、一个多页 PDF、一个 `.cube`
  LUT 文件、一段 GIF/视频帧序列（媒体项用；无则该项如实记录"素材缺，跳过"
  而非伪造）。
- **主验证机建议为"裸"环境**（未装 tesseract/poppler/qrcode/pystrich/pyzbar/
  magick/ffmpeg/rembg/upscayl 中至少若干项）——§3 置灰路径依赖真实缺失状态；
  如验证机全装齐了，§3 的真实置灰观察改为 §1 的 mock 路径 + §3 协议级手工
  演练（用容器/临时 PATH 隐藏二进制），并在 §6 如实记录采用方式。
- AI 降级（§4）在**无模型文件**（`~/.rembg/models` 为空、无 upscayl/EDSR
  配置）的机器上观察默认降级态；有条件再补"装好模型后可用性翻转"的对照。

## 1. CI 已覆盖（实机不重复执行；推送后以 GitHub Actions 实际结果为准）

> 以下项由 CI 两个 job 的既有机制自动纳入：test job 的 `unittest discover`
> 发现 tests/ 下全部用例；native job 的 CTest 注册了 assist_model /
> assist_service 两目标（tests/native/CMakeLists.txt 末段两段
> qt_add_executable + add_test）。截至本清单撰写，Phase 7 改动尚未提交推送
> ——"CI 已覆盖"均指测试已就位并随既有 CI 机制执行，推送后的实际运行结果
> 回填 §6。

- [ ] Worker 协议全路径（Python，`tests/test_worker_assist.py`，68 用例，
      进程内 Dispatcher + TaskRuntime(max_workers=1)；外部依赖路径一律 mock
      强制（patch assist_adapter.missing_deps_*），成功路径 mock 到 processors
      资产函数，不假设 CI 机器装/不装任何可选依赖）：capabilities.list 注册
      assist.list 与全部工具动作（条目 key 即动作名）；assist.list 目录形状
      与 filter.list 同构（八字段、type ∈ sync|async、available 与
      optional_deps 严格互斥、按 (category, key) 排序、key 唯一、响应可过
      JSON Lines 编码）与 15 类别族覆盖；目录探测与提交判定同一函数
      （强制 ocr 依赖缺失 → 条目置灰且 optional_deps 与提交时
      details.missing 同源）；`DEPENDENCY_MISSING` 提交前同步返回（不产生
      task_id/任务事件）且 details.missing 如实；参数校验先于依赖判定
      （ocr 缺 path、ean13 数据非法时即使依赖缺失也报 INVALID_PARAMS）；
      OCR 成功接线（lang/psm 透传）；pdf.* 七资产函数往返（merge/split/
      rotate/rotate 非法角度/remove_pages/extract_text（reportlab 夹具，
      缺则跳过）/set_metadata/protect 加密标记）+ paths 非空数组 + 输出
      父目录必须已存在 + to_images 依赖双路径（poppler 缺失拒绝 / 成功
      mock）；条形码三动作（qr 依赖缺失与成功、ean13 依赖缺失、非法数据
      先于依赖、成功接线含 §4 通道 sha256 核对、decode 依赖缺失与 Rect
      形状裁剪）；小工具真实执行（checksum 对 hashlib/zlib、直方图
      rgb/luma/hsv 形状与像素计数、非法 mode、ascii 往返与 cols 越界、
      compare 六指标与图像全同 PSNR→null）；lut.apply 往返与 .cube 解析
      失败提交前拒绝；media 依赖缺失（magick/ffmpeg）与成功 mock、fmt
      非法拒绝、convert_animation fmt 缺省取 output 扩展名；EXIF 读取/
      去除往返、水印落盘与非法 position；归档/加密解密往返/依赖缺失/
      Base64 往返；AI（模型注册表无模型文件时 installed 全 false、task
      过滤中英文别名等价、模型路径配置 settings 优先 + 环境目录 + 覆盖
      顺序、background.remove 依赖缺失与未知模型与成功、upscale 无模型
      依赖缺失/显式路径缺失为参数错误/配置路径命中走 upscale_sr、
      denoise/colorize 真实执行（OpenCV 核心无外部依赖）与取值越界）
- [ ] C++ 目录模型（CTest，`tests/native/test_assist_model.cpp`，6 用例，
      QAbstractItemModelTester）：五角色名锁定、reloadFrom 协议形状解析、
      category_label 缺省回落 category、整表重建（modelReset）、无 key 条目
      防御性跳过、非法索引返回空
- [ ] C++ 服务（CTest，`tests/native/test_assist_service.cpp`，8 用例，信号
      模拟不启动 Worker）：默认态与未绑定后端如实报错（INTERNAL）零上送、
      assist.list 填充 assistModel + loadingTools 生命周期、失败收在途标志
      且目录保持旧数据、同步拒绝（UNKNOWN_ACTION——旧 Worker 未含 §3.8 动作
      表）如实上报、runTool 本地拒绝（空 key/paramsJson 非对象）恰好一次
      assistError 零上送、sync 工具直答 notifyToolResult 不产生任务行、
      async 工具 toolAccepted + 任务行（目录显示名，未收录回落 key）→
      completed result 经 notifyToolResult 交付、task.failed（含 CANCELLED）
      → assistError 不发结果信号、未知任务帧忽略
- [ ] CI 环境边界（为何仍需实机）：ubuntu runner、C++ 测试直接 emit
      BackendManager 信号模拟协议帧（不启动真实进程）、Python 测试依赖路径
      mock（不触达真实 tesseract/poppler/magick 等二进制）、无 GUI 交互
      （目录网格点击/置灰 Tooltip/参数编辑器/结果导出/任务抽屉全不可测）、
      AppToolsPage.qml 无 QML 测试机制。工具页的跨进程全链路（QProcess +
      JSON Lines + 临时 PNG/文本结果 → QML 呈现）必须实机（§2）。

## 2. 工具目录浏览 → 运行工作流端到端（必须实机）

> 按工作流顺序执行：目录浏览 → 选工具 → 参数提交 → 运行 → 结果呈现/导出。
> 全部经一级导航"文件工具"真实控件操作。前置：Worker 已在设置页启动（应用
> 顶部无降级横幅）。

- [ ] **导航入口**：侧栏点"文件工具"（application.cpp navModel `files`）→
      ToolsPage 宿主 AppToolsPage 出现：左工具目录网格、右参数检查器（参数
      JSON 编辑器 + [清空参数] + [运行工具]）、结果区
- [ ] **目录加载**：进入页面后目录自动拉取（Component.onCompleted）——
      Loading 态（loadingTools）→ Ready 态；条目按 category 排序、显示
      `category_label` 本地化名（如"PDF 工具""OCR 文字识别"）；条目数与
      类别数和 `assist.list` 协议级输出一致（§2 末协议级命令可交叉核对）
- [ ] **选工具**：点击任一可用卡片 → 选中态、参数编辑器清空（不同工具参数
      形状不同，不跨工具携带陈旧参数——AppToolsPage selectTool 语义）；
      未选择前显示引导空态；目录加载完成后首个可用项自动入选
      （claimSelection，模型序，跳过置灰项）
- [ ] **搜索/滚动（如组件提供）**：目录滚动流畅、网格在窗口缩放下无重叠
      裁切（ui-component-spec §4 通用状态要求）
- [ ] **sync 工具直答**：选 `checksum.file`，参数编辑器输入
      `{"path": "<素材文件>"}` → [运行工具] → 结果区直接出现七算法 + size
      JSON（无任务抽屉行产生——sync 动作不留任务痕迹）；再试
      `histogram.compute`（`{"path": "...", "mode": "rgb"}`）与
      `ascii.render`（文本结果在结果区呈现，可复制）
- [ ] **async 工具受理**：选 `pdf.merge`，提交 `{"paths": [...], "output":
      "/tmp/merged.pdf"}` → 运行按钮进入装载态（单飞在途门）→ 任务抽屉出现
      以目录显示名命名的任务行（bindTaskModel 登记，queued → running →
      completed 状态色点/进度）→ 完成后结果区显示输出 path
- [ ] **结果呈现四态**：文本结果（`text` 键：ocr.run / pdf.extract_text /
      ascii.render）、文件列表结果（`files` 键：pdf.split /
      media.extract_frames / pdf.to_images——图像项可缩略呈现、PDF 项导出
      按钮如实禁用）、单图像结果（§4 临时 PNG 通道：barcode.*/lut.apply/
      ai.* 的 path+width+height+sha256——可[导出到编辑器]）、通用 JSON
      （crypto/base64/compare 等）——逐形态核对
- [ ] **导出编辑器**：图像类结果 [导出到编辑器] → 跳转"编辑"页且该图在画布
      打开（StudioService.exportToEditor 委托链，Phase 5/6C 同通道）
- [ ] **结果文件真实性核对**：对 lut.apply / barcode.qr.generate / ai.denoise
      各一例，用 `sha256sum` 核对结果区文件与 completed result `sha256`
      一致（§4 临时 PNG 通道完整性）
- [ ] **本地参数拒绝**：参数编辑器输入非法 JSON（如 `[1,2]` 或 `{`）→
      内联错误提示、[运行工具] 禁用（本地校验，不上送、不弹 Toast）；
      修正后恢复可用
- [ ] **失败呈现**：提交注定失败参数（如 pdf.rotate `degrees: 45`）→ 错误
      Toast `code · message`（assistError 通道：提交前同步拒绝）→ 在途门
      解除、可再次提交；async 任务体失败（如输出路径指向只读目录）→
      `ENGINE_ERROR` Toast + 任务行转失败态
- [ ] **任务取消**：长任务（大 PDF 的 pdf.to_images）受理后行内 [取消] →
      任务 failed(CANCELLED) → 行转取消态 + `CANCELLED` Toast（§7：取消以
      task.failed 呈现，assistError 同一通道不特判）→ 可再次运行
- [ ] **看门狗自愈（如实观察，不强行构造）**：120s 无响应静默 → "工具运行
      超时未返回（120s）"警示并恢复可再次运行（AppToolsPage runWatchdog）；
      正常工具远短于 120s，本项只确认机制存在
- [ ] **协议级实机验证（补 CI 不触达的真实进程链路）**：
      ```bash
      echo '{"protocol":1,"request_id":"req-a1","action":"assist.list","params":{}}' | \
        uv run python python_worker/main.py --repo-root .
      echo '{"protocol":1,"request_id":"req-a2","action":"checksum.file","params":{"path":"README.md"}}' | \
        uv run python python_worker/main.py --repo-root .
      ```
      前者返回 `{tools: [...]}`（32 条目、缺失依赖的条目 `available:false` +
      `optional_deps` 如实列出）；后者直答 `{md5, sha1, sha256, sha512,
      crc32, blake2b, blake2s, size}`（`sha256` 与 `sha256sum README.md`
      一致）

## 3. OCR / PDF / 小工具逐项 + 依赖缺失置灰路径（必须实机）

> 逐项表按"目录族"组织：每族至少一例真实输入→输出核对；置灰路径用**真实
> 缺失依赖**的条目观察（裸机策略见"准备"），并用协议级命令补"置灰条目提交
> 被拒"的协议面证据（CI 已锁 mock 路径，实机补真实目录状态下的同一判定）。

- [ ] **OCR**：装有 tesseract 的环境（如有）：`ocr.run`
      `{"path": "<含清晰文字的图>", "lang": "eng"}` → 结果区文本真实可读；
      无 tesseract 主验证机：该卡片置灰 + Tooltip 列出
      `pytesseract`/`tesseract` 缺失名
- [ ] **PDF 七动作逐项**：merge（两份合成、页数正确）、split（逐页单文件
      `{stem}_{NNN}.pdf`）、rotate（`degrees: 90`，阅读器确认转向；`45`
      拒绝）、remove_pages（删后页数正确）、extract_text（文本层 PDF 出文
      本、无文本层如实空串）、set_metadata（读回 Title 生效）、protect
      （读回 is_encrypted）；to_images（装 poppler 环境：逐页 PNG 命名
      `{stem}_{NNN}.png`、result `pages/dpi` 如实；无 poppler：置灰）
- [ ] **条形码**：qr.generate（size/error_correction 参数生效、扫码可读）、
      ean13.generate（pystrich 环境：12 位数据出码、缺 pystrich 置灰——
      **不得出现 1.0 PIL 兜底的伪条码**）、decode（含码图解码出 data/type）
- [ ] **小工具**：checksum.file（与 `sha256sum`/`md5sum` 交叉核对）、
      histogram.compute（rgb/luma/hsv 三模式形状）、ascii.render（文本
      呈现）、compare.images（同图 PSNR→`null`、异图指标非空——协议面
      null 语义）、exif.extract（带 EXIF 的 JPEG 读出 ImageDescription）、
      exif.strip（读回 EXIF 为空）、watermark.text（五 position 任选落盘）
- [ ] **LUT**：lut.apply（真实 `.cube`）→ 结果图色调变化、sha256 核对；
      坏 `.cube` → 提交前 INVALID_PARAMS Toast、无任务行
- [ ] **媒体**：装 magick 环境：extract_frames（GIF 抽帧出文件列表）、
      convert_animation（帧序列合成 gif；`fmt: jxl` 需 ffmpeg——缺失时该
      提交被拒、卡片按 fmt 无关地依赖 magick 置灰口径如实观察记录）；无
      magick 机器：两卡片置灰
- [ ] **文件工具**：archive.create（ZIP 内容核对）、crypto.encrypt →
      crypto.decrypt 往返（密文非明文、解密还原）、base64.encode →
      base64.decode 往返（与 `base64` 命令交叉核对编码文本）
- [ ] **置灰呈现（真实缺失依赖）**：主验证机上每个 `available:false` 条目
      ——卡片置灰、Tooltip 列出缺失名（AppFilterCard 同源机制）；点击与
      键盘激活无效——无法选中、参数面板不切换、[运行工具] 不发起；自动
      认领跳过置灰项
- [ ] **置灰条目不得发起动作（协议面）**：对置灰 key 手工提交运行请求
      ```bash
      echo '{"protocol":1,"request_id":"req-a3","action":"ocr.run","params":{"path":"<素材图>"}}' | \
        uv run python python_worker/main.py --repo-root .
      ```
      （未装 tesseract 机器）→ 同步错误 `DEPENDENCY_MISSING`、
      `details.missing` 列出缺失名、不产生 task_id
- [ ] **参数校验先于依赖判定（协议面）**：同机提交
      `{"action":"ocr.run","params":{}}` → `INVALID_PARAMS`（不是
      DEPENDENCY_MISSING——缺失依赖不掩盖参数错误）；输出粘贴 §6
- [ ] **探测时点如实观察**：会话中途安装某依赖（如 `pip install qrcode`）→
      下一次 `assist.list` 即反映（协议 §3.8：可用性探测不做缓存）——重进
      工具页或触发目录重拉后条目翻绿；如实记录观察结果

## 4. AI 降级说明与验证（必须实机）

> 总纲 Phase 7："模型和外部依赖状态必须真实；缺少模型或二进制时不得显示
> 虚假的可用状态"。本节验证四条 AI 动作的降级矩阵——**每一条都对应一个
> 真实依赖组合**，不存在"恒可用"的重模型动作（denoise/colorize 为 OpenCV
> 核心启发式，1.0 的神经降噪/上色路径本就不存在，如实按算法工具呈现）。

- [ ] **模型管理只读视图**：无模型机器上 `ai.models.list`（目录卡片或协议
      级命令）→ `models` 每条 `installed:false`（真实文件探测
      `~/.rembg/models` / 系统模型目录，无模型文件即 false——不谎报）；
      `backends` 至少含 CPU（CUDA/Vulkan 如实探测）；`cache_root` 与
      `model_paths` 如实（空配置为空对象）。**工具页无任何"安装模型"按钮
      或下载入口**（网络下载不在本批动作面）
- [ ] **AI 抠图降级**：无 rembg/onnxruntime/模型文件的机器：`ai.background.remove`
      卡片置灰、Tooltip 含 `rembg`/`onnxruntime`/`model:u2net` 缺失名；
      协议级提交 → `DEPENDENCY_MISSING` + `details.missing` 同源三连。
      装齐环境（如有）：`model: u2net` 出抠图结果（透明背景 PNG）、
      `background: [r,g,b]` 合成底色生效、`model: nope` → INVALID_PARAMS
- [ ] **AI 超分双路径**：
      - 未配置路径且无 upscayl：`ai.upscale` 置灰（Tooltip 含
        `upscayl`/`model:realesrgan-x4plus`）→ 协议级提交
        `DEPENDENCY_MISSING`；
      - `model_paths` 配置 EDSR `.pb`（或 `TOOLBOX_AI_MODEL_DIR` 放置）后：
        条目翻绿 → `{"path": "...", "scale": 4}` 输出 4 倍尺寸图（OpenCV
        DNN，无外部二进制）——"配置覆盖"路径的可用性翻转如实记录；
      - 显式 `model_path` 指向不存在文件 → INVALID_PARAMS（用户输入错误，
        不是依赖缺失）
- [ ] **AI 降噪 / AI 色彩化恒可用（如实标注）**：无外部依赖，裸机即可运行
      ——denoise（strength 越界拒绝、合理值出图）、colorize（simple 出图；
      transfer + style 五取值任一出图、非法 style 拒绝）。**呈现上不得宣
      称"神经网络模型"**——1.0 即为 OpenCV 启发式实现，目录 `description`
      如实写明（协议面字段；AssistModel 角色面未消费该字段，矩阵 §6 该行
      保持"算法模拟"标注）
- [ ] **AI 族失败可解释**：有依赖但任务体失败（如模型文件损坏）→
      `ENGINE_ERROR` Toast + 任务行失败态——失败与取消（§7 CANCELLED）都有
      code · message，无静默无响应按钮（总纲 §9.8 降级要求）

## 5. 非模态、导航与恢复（必须实机）

- [ ] **非模态**：长任务（pdf.to_images 大 PDF）进行中切到编辑/首页等其他
      页面 → 任务继续（C++ 单例上的后台任务）；期间其他页面操作无卡顿
      （处理全在 Worker，主线程零像素计算——总纲 §9）
- [ ] **重进恢复**：任务在途时离开工具页 → 重进 → 目录重拉、在途任务行仍在
      任务抽屉（TaskModel 生命周期）；结果交付后如页面在工具页则呈现
- [ ] **Worker 未就绪降级**：设置页停止 Worker → 工具页整体 BackendDown 态
      （AppWorkspaceLayout backendDown 插槽，目录不显示假数据）；重新启动
      Worker → 目录自动重拉（onStateChanged 兜底，rowCount===0 且非在途）
- [ ] **Worker 崩溃恢复**：任务在途时杀掉 Worker 进程 → Toast（code ·
      message）+ 在途门立即解除 + 可再次运行；重启后目录重拉
- [ ] **页面切换与主题**：深浅主题切换后目录卡片/参数面板/结果区渲染一致；
      窗口缩放无控件失踪

## 6. 偏差与记录（回填）

- **本批覆盖核对补齐的用例**（tests/test_worker_assist.py，64 → 68 用例，
  随 CI 执行）：EAN-13 成功接线（资产 mock + §4 通道 sha256）、
  media.convert_animation 成功接线（fmt 缺省取 output 扩展名 + fps 缺省
  透传）、pdf.merge paths 非空数组校验、histogram luma 256 bin 形状。
- **协议复查修订**（docs/ipc-protocol.md §3.8 末复查注，均为措辞对齐实现、
  协议形状不变）：`barcode.decode` 条目 `rect` 键恒存在（无定位时 null）；
  `cryptography` 虽为 requirements 既有项仍按可选依赖探测（原文"核心依赖
  不列为 optional_deps"清单误列）。
- **消费侧状态口径**：C++/QML 消费侧与本批同步交付（assist_model /
  assist_service / AppToolsPage / ToolsPage / 导航接线），协议文档 Phase 7
  段的"本批未接线"旧记录已按现状修订（ipc-protocol.md Phase 7 段）。
- 回填项：CI 实际结果链接与结论（test + native 双 job）；§2-§5 逐项勾选；
  §2 协议级实机输出；§3 逐项真实输入→输出证据与置灰观察；§4 AI 降级矩阵
  逐格证据（含 EDSR 配置路径的可用性翻转）；实际桌面会话（X11 / Wayland）
  → 直接写入本文件对应小节。
