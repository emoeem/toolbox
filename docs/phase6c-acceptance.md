# Phase 6C 验收清单（Linux 目标环境执行）

> 状态口径：Phase 6C = `code_complete` / `static_reviewed`（总纲 §14.2）。本清单
> 通过后才算 `runtime_verified`；通过前迁移矩阵 §3 相关行保持 `待迁移`
> （ui-migration-matrix.md 头部状态取值规则：`已迁移` 要求"新 UI 中真实可用
> 并验收"，CI 单测不构成改判依据）。
> 分工口径：§1 为 CI 已覆盖的逻辑层项（实机不重复执行）；§2 起为必须在 Linux
> 目标环境（真实 Worker 进程 + 真实桌面 GUI 会话）执行的项。
> 覆盖范围：总纲 §7 Phase 6（滤镜系统与创作工作区）迁移顺序的**第 8-11 项
> （Fractal Studio / Texture Studio / Shader Studio / Gradient 等参数驱动
> 生成器）以统一 Studio 工作区交付的垂直切片**——协议 `generate.list` /
> `generate.render`（docs/ipc-protocol.md §3.7）的 Worker 侧交付、C++ 侧
> StudioService/GeneratorModel 消费、QML StudioPage + AppStudioPage 导航接线，
> 工作流 = **选生成器 → 调参 → 渲染预览 → 导出编辑器/另存**。
> **如实边界（不得把本批当成分 Studio 完工）**：
> - 三个分 Studio 页未分流：FractalPage/TexturePage/ShaderPage 仍是 Phase 2
>   占位页，一级导航"创作"路由到统一 StudioPage（application.cpp:74-76）；
>   ui-page-spec.md §5 的分页面布局要点（Julia 常数联动显隐、平铺预览切换、
>   GLSL 编辑器 + 编译诊断）不在本批，见 §6。
> - `shader:preview` 恒为 `available=false`（Worker 无 OpenGL 运行时，优雅
>   降级）——Shader Studio 本体（GLSL 编辑/GL 预览/导入导出）未迁移，矩阵
>   §3 该行状态不变。
> - photomosaic / fusion / SVG / 拼接等矩阵 §3 其余行不在本批（协议 §3.7
>   复查注：photomosaic/fusion 在 1.0 是文件→文件工具，非参数驱动生成器，
>   不注册）。
> - 另存为：QML 已接线（FileDialog + savePreviewAs typeof 探测），C++ 侧
>   `StudioService.savePreviewAs` **尚未实现**——当前实机表现为"另存为暂
>   不可用"警示 Toast（诚实降级，绝不静默无操作），见 §2/§6。
> 依赖：Phase 5/6A/6B 验收（docs/phase5-acceptance.md、docs/phase6a-acceptance.md、
> docs/phase6b-acceptance.md）截至本清单撰写均**尚未在目标环境执行**（复选框
> 未回填）。本清单复用其机制：置灰卡片 AppFilterCard 与依赖 Tooltip（6A §3
> 同源）、任务抽屉/Toast（Phase 4 组件）、ImageCanvas（Phase 5 编辑器画布）、
> 导出到编辑器经 DocumentService::openDocument（Phase 5 文件工作流）——执行
> 时按对应清单一并回填。
> 实现锚点：Worker 侧 `python_worker/dispatcher.py`（动作表 dispatcher.py:50、
> dispatcher.py:65，`_generate_list`/`_generate_render_job`
> dispatcher.py:200-217）与 `python_worker/adapters/generate_adapter.py`
> （list_generators generate_adapter.py:301-316、validate_render_request
> generate_adapter.py:422-437、render_generator generate_adapter.py:456-511、
> write_render generate_adapter.py:514-523、尺寸上限 MAX_RENDER_SIDE=4096
> generate_adapter.py:49）；复用 1.0 资产不重写——`processors/fractal.py`
> （formula_keys/formula_info fractal.py:750-755、render_fractal
> fractal.py:631-642、render_mandelbulb fractal.py:733-737）、
> `processors/texture_studio/`（presets.py BUILTIN_PRESETS 缺省参数表 +
> generators.py generate generators.py:10-20 + gmic.py 的 CLI/numpy 降级
> gmic.py:37-41）、`processors/gradients.py`（linear/radial/mesh +
> MESH_PRESETS）、`processors/filter_defs.py` `FilterParam.validate`
> （filter_defs.py:90-137）、`python_worker/adapters/filter_adapter.py`
> `write_preview`（filter_adapter.py:86-100，§4 临时 PNG 通道）、
> `processors/cancellation.py` CancelToken。C++ 侧
> `native/services/studio_service.*`（loadGenerators studio_service.cpp:78-85、
> render studio_service.cpp:87-128、exportToEditor studio_service.cpp:130-140、
> 受理/事件关联 studio_service.cpp:142-226）与 `native/models/generator_model.*`
> （reloadFrom generator_model.cpp:10-40、六角色 roleNames
> generator_model.cpp:99-105）；QML 侧 `ui/components/AppStudioPage.qml` 与
> `ui/pages/StudioPage.qml`（宿主），导航接线 `native/app/application.cpp`
> （navModel "create" → StudioPage.qml，application.cpp:74-76）与
> `ui/Main.qml`（Loader 路由，Main.qml:94-97）。协议形状见
> docs/ipc-protocol.md §3.7（Phase 6C 复查注：color 参数双形状、`data`
> 内联兜底为消费方防御分支、`description` 无 UI 消费）。

## 准备

```bash
cd ~/toolbox
git fetch origin && git checkout <phase6c 分支>
uv sync --extra dev                       # Worker 依赖沿用现有锁定环境
cmake --preset linux-debug && cmake --build --preset linux-debug
```

测试素材：**无需图像素材**（生成器从参数渲染图像）。建议主验证机为**未装
gmic** 的 Linux 环境（§3 置灰路径）；如另有装 gmic CLI 的环境，回填 §3 的
gmic 真实输出对照与 §6 记录。

## 1. CI 已覆盖（实机不重复执行；推送后以 GitHub Actions 实际结果为准）

> 以下项由 CI 两个 job 的现有机制自动纳入：test job 的 `unittest discover`
> 发现 tests/ 下全部用例（ci.yml，`unittest.TestLoader().discover("tests")`），
> native job 的 CTest 注册了 generator_model / studio_service 两个目标
> （tests/native/CMakeLists.txt 末段两段 qt_add_executable + add_test）。
> 截至本清单撰写，Phase 6C 改动尚未提交推送——"CI 已覆盖"均指测试已就位并
> 随既有 CI 机制执行，推送后的实际运行结果回填 §6。Phase 6C 覆盖核对后
> 补齐的用例见 §6 首条。

- [ ] 生成器协议全路径（Python，`tests/test_worker_generate.py`，37 用例，
      进程内 Dispatcher + TaskRuntime(max_workers=1)，渲染一律 ≤48 边，
      G'MIC 依赖用 mock 不要求 CI 机器装/不装 G'MIC）：capabilities.list
      注册 generate.list/generate.render；generate.list 目录形状与
      filter.list 同构（条目字段集、category 取值 fractal|texture|gradient|
      shader、key 唯一、params 参数描述词汇 int/float/bool/enum/color、
      enum 必带 choices、目录 JSON 可走 JSON Lines 通道）；分形公式全覆盖
      （formula_keys() 全部 2D 公式 + mandelbulb）与公式能力裁剪的参数集
      断言（mandelbrot 有 power/bailout 无 julia、julia 有 julia_c、
      phoenix/nova/magnet 逐公式、mandelbulb 仅 power/iterations）；texture
      噪声/图案/gmic/raymarch 与 gradient 三族键全覆盖；缺省参数来自
      1.0 内置预设（perlin seed=42、mesh preset choices）；shader:preview
      恒不可用 + optional_deps 含 opengl；texture:gmic:* 的 available 跟随
      gmic CLI mock 双路径（available=false + optional_deps=["gmic"] /
      available=true）；渲染往返（mandelbrot 像素语义——逃逸集与内部集并存、
      julia 常数生效、mandelbulb、perlin 同种子 sha256 可重复、checker、
      raymarch、linear 端点颜色精确、radial 显式颜色中心精确、mesh 预设）；
      `generator` 别名接受；完成 result 字段集与 §4 按生成器 key 覆盖命名
      （preview-generate-<key>.png，同 key 同名覆盖、异 key 不同名）；颜色
      参数双形状（`[r,g,b]` 数组与 #RGB/#RRGGBB hex 文本，hex 3 位展开）；
      texture:gmic:paper 渲染通道（可用性 mock 后经 1.0 既有 generate() 的
      numpy 降级实现往返——锁定协议通道，不锁 gmic 本体像素）；取消路径
      （texture 族任务体边界检查 → task.cancel → task.failed(CANCELLED)、
      结果零落盘、迟到取消如实 `cancelling:false`；分形 cancel_token 直通
      render_fractal 的装配锁定；进度回调 message 包装）；提交前同步
      INVALID_PARAMS 全参数面（缺/空/非字符串 generator_key、未知生成器、
      不可用生成器含 gmic mock、width/height 缺失/0/负/超 4096/浮点/布尔/
      字符串、params 非对象、参数值越界（FilterParam 下界/上界/enum/color
      非法）——均不产生任务）
- [ ] C++ 目录模型（CTest，`tests/native/test_generator_model.cpp`，8 用例，
      QAbstractItemModelTester）：六角色名锁定（generatorKey/generatorName/
      categoryLabel/paramsJson/available/optionalDeps）、reloadFrom 协议
      形状解析与参数定义透传、category_label 缺省回落 category、整表重建
      （clear-and-replace 发 modelReset）、无 key 条目防御性跳过、search
      标题/关键词（key + category_label + optional_deps）大小写不敏感匹配
      与空查询全量、非法索引返回空
- [ ] C++ 服务（CTest，`tests/native/test_studio_service.cpp`，11 槽
      （9 用例 + initTestCase/cleanupTestCase），信号模拟不启动 Worker）：
      默认态与未绑定后端如实报错（INTERNAL/INVALID_PARAMS）零上送、
      generate.list 填充 generatorModel + loadingGenerators 生命周期、
      generate.list 失败收在途标志且目录保持旧数据、同步拒绝（UNKNOWN_ACTION）
      如实上报、render 本地拒绝（空 key/非正尺寸/paramsJson 非对象）恰好
      一次 studioError 零上送、受理缺 task_id 按协议违约上报、受理交付
      renderAccepted + 任务行"生成渲染"（bindTaskModel 登记）、完成事件
      path/data 两种形状经 notifyPreviewReady 交付、完成缺预览图按协议违约
      上报、未知任务帧忽略、task.failed（含 CANCELLED）→ studioError 不发
      预览信号、exportToEditor 真实委托 DocumentService::openDocument
      （文档层错误不经 studioError 通道）
- [ ] CI 环境边界（为何仍需实机）：ubuntu runner、`QT_QPA_PLATFORM=offscreen`、
      C++ 测试直接 emit BackendManager 信号模拟协议帧（不启动真实进程）、
      Python 测试渲染走 numpy 降级路径（不触达真实 gmic CLI）、无 GUI 交互
      （目录卡片点击/置灰 Tooltip/参数控件/FileDialog/画布缩放/导航跳转全
      不可测）、AppStudioPage.qml 组件无 QML 测试机制。Studio 工作流的跨
      进程全链路（QProcess + JSON Lines + 临时 PNG → QSG 纹理）必须实机（§2）。

## 2. Studio 工作流端到端（必须实机）

> 按工作流顺序执行：选生成器 → 调参 → 渲染预览 → 导出编辑器/另存。全部经
> "创作"入口真实控件操作，不使用测试驱动。前置：Worker 已在设置页启动
> （应用顶部无降级横幅）。主验证机未装 gmic（§3 依赖本节目录状态）。

- [ ] **导航入口**：侧栏点"创作"（application.cpp navModel "create"）→
      StudioPage 宿主 AppStudioPage 三栏布局出现：左"生成器"目录列表、中
      预览画布 + 顶部条（尺寸 512/1024/2048、进度指示、缩放控件 −/适配/+/100%
      与尺寸度量）、右"参数"检查器（参数面板 + [重置参数] + "导出"分组）
- [ ] **目录加载**：进入页面后目录自动拉取（Component.onCompleted）——
      Loading 态（loadingGenerators）→ Ready 态；目录条目按 category 排序、
      显示"分形 · Mandelbrot"等 category_label 本地化名；分类计数与
      processors 资产一致（15 个 2D 分形公式 + mandelbulb + 纹理 15 +
      渐变 3 + shader 1——未装 gmic 机器 texture:gmic:* 四项置灰仍显示）
- [ ] **选生成器**：点击任一可用卡片 → 选中态（selected 高亮）、右侧参数
      面板随该生成器 paramsJson 重建、画布出现引导文案被渲染替换；未做任何
      选择前画布显示"在左侧选择生成器开始创作"空态；目录加载完成后首个
      可用项自动入选（claimSelection，模型序）
- [ ] **调参（类型映射）**：逐类型核对 AppFilterParameterGroup 自动控件——
      float → AppSliderField（分形 cx/cy/scale）、int → AppNumberField
      （iterations）、bool → AppToggleField（图案 anti_alias）、enum →
      AppSelectField（coloring：smooth/banded/grayscale；mesh preset）、
      color → AppColorField（渐变 color_a/color_b、图案前景/背景色）；双击
      滑杆标签重置该参数默认值（AppSliderField defaultValue 语义）
- [ ] **调参 → 防抖渲染**：任一参数变化 → 300ms 防抖后自动渲染（无独立
      [渲染] 按钮）；快速连改参数只发最新一次（单飞在途门：在途时新请求只
      置 renderQueued，解除后补发一次最新参数）；拖动滑杆释放后才触发
      高清渲染（AppSliderField dragFinished → paramsChanged → 防抖）
- [ ] **重置参数**：[重置参数] → 参数面板回到该生成器默认值 → 防抖自动
      重渲染默认图
- [ ] **渲染预览**：渲染期间画布上方出现 indeterminate 进度指示与
      "正在渲染 512 × 512 预览…"占位；完成后画布显示成品（ImageCanvas 解码
      Worker 交付的临时 PNG，顶部条尺寸度量显示真实宽高，如 512×512）；对
      同一参数重复渲染同路径临时文件 → `?v=` 递增进位保证画布刷新（不是
      旧图残留）
- [ ] **渲染预览（缩放）**：[−]/[+]/[适配]/[100%] 对预览画布生效（缩放语义
      与编辑器 ImageCanvas 一致）；未渲染前缩放控件禁用
- [ ] **尺寸切换**：512/1024/2048 分段切换 → 防抖自动重渲染 → 完成后度量
      显示对应尺寸、文件按请求尺寸原样落盘（协议 §3.7 不降采样——导出后
      在编辑器核对图像尺寸为请求值）
- [ ] **逐生成器抽查**：至少各渲染一例——fractal（默认 mandelbrot；
      mandelbulb 渲染耗时如实记录）、texture（perlin 同种子重渲染两次输出
      一致——种子可重复，总纲 §9.7；pattern:checker）、gradient（linear
      端点颜色 = 参数 color_a/color_b；mesh preset 切换换图）
- [ ] **导出编辑器**：渲染完成后 [导出到编辑器] 点亮 → 点击 → 跳转"编辑"
      页且该成品在编辑器画布打开（StudioService.exportToEditor 委托
      DocumentService::openDocument，通道与状态归文档层）；编辑器内可对该
      图继续调整/滤镜/保存（Phase 5 工作流，按 phase5-acceptance.md §2 回填）
- [ ] **另存为（如实降级）**：[另存为] → FileDialog 选择目标 → 因
      savePreviewAs 未实现显示"另存为暂不可用：savePreviewAs 尚未在
      StudioService 实现"警示 Toast（**不静默失败、不谎报已保存**）→ §6
      记录；产物可经"导出编辑器 → 编辑器另存为"间接落盘（等价路径）
- [ ] **失败呈现**：Worker 侧失败（如把输出临时目录置只读）→ 错误 Toast
      `code · message`（studioError 通道，含 task.failed 转发）；在途门
      解除、可再次渲染；无半成品文件
- [ ] **任务抽屉与取消**：渲染受理后任务抽屉出现"生成渲染"行（bindTaskModel
      登记，queued → running → completed 状态色点/进度）；行内 [取消] →
      任务 failed(CANCELLED) → 行转取消态 + `CANCELLED` Toast（studioError
      通道）、画布保持上一张预览、可立即再次渲染；分形（逐行检查点）取消
      立竿见影、texture/gradient（同步计算，任务体边界检查）取消在下一次
      渲染边界生效——两者都如实观察记录
- [ ] **本地拒绝路径（如实演练）**：CI 已覆盖本地拒绝（空 key/非正尺寸/
      paramsJson 非对象零上送），UI 入口不产生这些状态（参数面板整表发送、
      尺寸枚举固定），如实记录即可，不强行构造
- [ ] **协议级实机验证（补 CI 不触达的真实进程链路）**：
      ```bash
      echo '{"protocol":1,"request_id":"req-g1","action":"generate.list","params":{}}' | \
        uv run python python_worker/main.py --repo-root .
      echo '{"protocol":1,"request_id":"req-g2","action":"generate.render","params":{"generator_key":"gradient:linear","width":64,"height":48}}' | \
        uv run python python_worker/main.py --repo-root .
      ```
      前者返回 `{generators: [...]}` 目录（未装 gmic 机器 texture:gmic:*
      四条 `available:false` + `optional_deps:["gmic"]`、shader:preview
      `available:false`）；后者受理 `{task_id, status}` → completed result
      `{path, width, height, sha256, generator_key}`，`sha256` 与文件一致、
      图像 64×48 PNG

## 3. 无依赖生成器置灰路径（必须实机）

> 机制：Worker generate.list 的 `available` / `optional_deps`（§3.7）→
> GeneratorModel（缺 available 按不可用处理，宁可置灰不谎称可用）→
> AppFilterCard 置灰 + Tooltip 原因（与 Phase 6A 滤镜卡片同一组件、同一
> 语义）。与 6A §3 的区别：生成器目录**现成有置灰条目**（未装 gmic 机器的
> texture:gmic:* 四项 + 恒不可用的 shader:preview），不需要临时改代码演练。

- [ ] **G'MIC 系置灰呈现**（未装 gmic 主验证机）：texture:gmic:paper/canvas/
      grunge/noise_blend 四卡片置灰、Tooltip"缺少可选依赖：gmic"；点击与
      键盘激活无效——无法选中、参数面板不切换、不发起渲染
- [ ] **shader:preview 恒置灰**：着色器条目置灰、Tooltip 原因含 opengl
      （glslangValidator 缺失时并列）；自动认领跳过置灰项（首个可用项为
      分形/纹理/渐变中的可用条目，不会落在 shader 上）
- [ ] **置灰条目不得发起渲染（协议面）**：手工对置灰 key 发渲染请求
      ```bash
      echo '{"protocol":1,"request_id":"req-g3","action":"generate.render","params":{"generator_key":"texture:gmic:paper","width":32,"height":32}}' | \
        uv run python python_worker/main.py --repo-root .
      ```
      → 同步 `INVALID_PARAMS`（错误消息含缺失依赖名 gmic）、不产生 task_id
      （CI 已锁 mock 路径；实机补的是真实目录状态下的同一判定）
- [ ] **装有 gmic 的环境（如有，回填 §6）**：texture:gmic:* 四卡片可用 →
      渲染输出为真实 gmic CLI 效果（CI 走 numpy 降级实现，像素与 CLI 不同
      是 1.0 既有双路径行为，协议语义相同）；`gmic.check` 诊断动作输出
      `{available: true, version, source: "cli"}` 可作旁证
- [ ] **探测时点如实观察**：依赖可用性在 Worker 注册表构建时探测并固化
      （generate_adapter reset_registry_cache 注释）——运行中安装/卸载 gmic
      后需重启 Worker 才反映到目录；如实记录观察结果，不强行构造
- [ ] Shader Studio 本体不在本批：GLSL 编辑器/GL 预览/uniform 参数不随本批
      验收（矩阵 §3 Shader Studio 行保持原状）；`shader:preview` 置灰是
      优雅降级路径而非功能交付

## 4. 非模态、导航与恢复（必须实机）

- [ ] **非模态**：渲染进行中切到编辑/首页等其他页面 → 渲染继续（C++ 单例
      上的后台任务，导航不中断）；2048 渲染期间其他页面操作全程无卡顿
      （像素计算全在 Worker，主线程零像素计算——总纲 §9）
- [ ] **重进恢复**：渲染进行中离开 Studio 页 → 重进 → 在途状态恢复（在途
      门、任务行、目录选中态按组件重建逻辑如实观察）；notifyPreviewReady
      到达后画布更新
- [ ] **Worker 未就绪降级**：设置页停止 Worker → Studio 页整体进入
      BackendDown 态（AppWorkspaceLayout backendDown 插槽："处理引擎未连接
      （state）——请到设置页启动 Worker"，目录与画布不显示假数据）；重新
      启动 Worker → onRunningChanged 兜底自动拉取目录（rowCount===0 且非
      在途），页面回到 Ready
- [ ] **Worker 崩溃恢复**：渲染在途时杀掉 Worker 进程 → onErrorOccurred →
      Toast（code · message）+ 在途门立即解除（不等看门狗）+ 可再次渲染；
      重启后目录重拉（§6.5 协议语义：document_id 全失效与本页无关——本页
      不持有文档）
- [ ] **看门狗自愈（如实观察，不强行构造）**：120s 无终态 →"渲染超时未返回
      （120s），已恢复可再次渲染"警示（AppStudioPage renderWatchdog）；
      正常渲染远短于 120s，本项只确认机制存在，实测不触发即如实记录
- [ ] **页面切换与主题**：深浅主题切换后目录卡片/参数面板/画布底色（棋盘格）
      渲染一致；面板收缩/展开（AppInspectorPanel collapsed）不丢失参数

## 5. 大尺寸渲染与资源（必须实机）

- [ ] 2048×2048 分形渲染：运行期间拖动窗口、切换页面、滚动目录全程无卡顿；
      记录实测耗时 → §6（mandelbulb 3D 光线步进单独记录，预期显著更慢）
- [ ] 2048 渲染在途时再次改参数 → 防抖入队、不并发提交（单飞门）；完成后
      补发最新参数
- [ ] **临时文件不堆积**：对同一生成器连续渲染 ≥10 次（改参数）→ 临时目录
      该生成器只有一个 preview-generate-<key>.png（§4 按 key 覆盖命名）；
      Worker 会话结束后临时目录随会话清理
- [ ] 4096 边界（协议上限）：width=4097 手工请求 → 同步 INVALID_PARAMS；
      4096 合法受理（可选执行，渲染耗时如实记录）

## 6. 偏差与记录（回填）

- **本批覆盖核对补齐的用例**（tests/test_worker_generate.py，随 CI 执行）：
  颜色参数双形状（hex 文本 + 3 位展开）、完成 result 字段集与按 key 覆盖
  命名、texture:gmic:paper 渲染通道（numpy 降级往返）、取消路径（texture
  任务体边界 CANCELLED 全路径 + 分形 cancel_token 直通装配 + 进度 message
  包装）。
- **另存为未实现（C++ 契约缺口，诚实降级）**：QML 已接 savePreviewAs
  typeof 探测（AppStudioPage.qml:670-684），`StudioService` 当前无该
  Q_INVOKABLE → FileDialog 提交后显示"另存为暂不可用"警示 Toast，绝不静默
  无操作；C++ 补齐后 QML 调用形状不变（mkpath + 覆盖语义、同步 bool）。
  导出/另存在内联 data 预览下禁用（无落盘文件）——Worker 实现只走 path
  形状，该状态理论上不可达，属防御分支。
- **`data` 内联兜底为消费方防御分支**：C++ notifyPreviewReady 接受完成
  result 的 `data` 字段（studio_service.cpp:209-223）——协议 §3.7 形状无
  `data`（§4 禁止 Base64 大图），Worker 从不发送；按"消费方忽略未知字段"
  口径如实记录，不视为协议扩展。
- **分 Studio 页未分流**：FractalPage/TexturePage/ShaderPage 仍是 Phase 2
  占位页，"创作"入口路由统一 StudioPage；ui-page-spec §5 的分页面特有项
  （Julia 常数联动显隐、平铺预览切换、GLSL 编辑器/编译诊断、Photomosaic
  素材数量校验）不在本批。GradientStudio 以 gradient:* 生成器条目进入统一
  目录，独立分页不分流。
- **`description` 字段无 UI 消费**：generate.list 条目的 description 当前
  未进 GeneratorModel 角色面（目录卡片 description 为空串）——协议面保留，
  后续批次接 AppFilterCard.description。
- **native 侧头注释过期**：studio_service.h:30-41（协议状态注记）、
  generator_model.h:17-19、test_studio_service.cpp:14-21、
  test_generator_model.cpp:5-7 均写"generate.* 尚未写入 docs/ipc-protocol.md
  §3 nor dispatcher"——native 侧先行交付时点的快照；本批协议（§3.7）与
  Worker 侧已同步落地，现状已过期（test_batch_service.cpp:17-23 在 6B 的
  同类先例）。测试本体锁定的契约不受影响，注释修订不属本批文件清单。
- **gmic 系渲染像素双路径**：CI/未装 gmic 环境走 numpy 降级实现（
  texture_studio/gmic.py _fallback），装 gmic 环境走 CLI——像素不同是 1.0
  既有行为，协议语义相同；真实 gmic 输出观感回填本节（如适用）。
- **渲染并发语义（如实记录）**：服务端允许多渲染并发（各自 task_id 关联，
  studio_service.h 头注）；QML 单飞串行化（notifyPreviewReady 不携带 task
  关联，并发到达序会互相覆盖画布——串行化保证显示顺序与参数一致）；
  notifyPreviewReady 的迟到响应无 id 可甄别、120s 看门狗放行后的迟到预览
  可能覆盖新图——已知取舍（宁可重复渲染，不无信号焊死），如实回填实测。
- **分形/纹理取消粒度差异**：分形逐行检查点即时中断；texture/gradient 为
  同步 CPU 计算，取消在任务体边界检查（§3.7）——2048 纹理渲染期间取消的
  实际等待时长回填本节。
- 回填项：CI 实际结果链接与结论（test + native 双 job）；§2-§5 逐项勾选；
  §2 协议级实机输出；§3 置灰观察与（如适用）gmic 真实输出对照；§5 耗时
  数据；实际桌面会话（X11 / Wayland）→ 直接写入本文件对应小节。
