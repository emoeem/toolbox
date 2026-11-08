import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

// Editor workspace (Phase 5): the real single-image workflow of
// docs/user-flows.md 流程 1 over DocumentService — open → adjust (debounced
// preview) → apply → transform → undo/redo/reset → save, per
// docs/ui-page-spec.md §2. The inspector is tabbed (调整 / 滤镜,
// ui-page-spec §2: 页签:调整|滤镜); the 滤镜 tab implements
// docs/user-flows.md 流程 2 over FilterService (catalog → params → chain →
// presets → preview/apply), reusing the same canvas refresh paths.
//
// Phase 9 增补（编辑器界面工程师-9 批次）：
// - 检查器新增"变换"页签：自由旋转（防抖预览 300ms，同调整页签路径）/
//   缩放 / 裁剪与透视的画布模式入口；既有旋转90/翻转按钮自顶部工具栏并入
//   本页签。新接口 DocumentService.applyTransform(transform, preview,
//   maxSide)（native/core/document_service.h Phase 9 签名，crop/rotate_free/
//   perspective/scale 组包形状见各 apply* 函数注释）。
// - 标注画布模式：AppAnnotateToolbar（工具/参数）+ AppAnnotateOverlay
//   （点序列/矩形采集 + Canvas 近似预览层），[完成标注] →
//   DocumentService.applyAnnotate(ops) 全分辨率；已提交的撤销走既有 undo
//   （Worker 参数化 replay，协议 §3.3）。
// - 对比模式：AppCompareSlider 原图/当前图滑块对比，进入后禁用其他交互，
//   Esc/再点退出。
// - 保存选项对话框：目标大小 KB（AppNumberField，勾选"限制目标大小"才生效
//   ——AppNumberField 无空值形态，"空=不限"以开关关闭表达）→
//   image.save target_kb 透传（协议 §3.9；DocumentService.saveDocument 第三参
//   targetKb，>0 时随请求携带，不勾选走默认质量），完成后 Toast 显示实际
//   大小（documentSaved 的 fileSize 扩展未接线时 undefined，按原样提示，
//   见 Connections.onDocumentSaved）。
//
// 画布模式总纲：crop / perspective / annotate / compare 互斥
// （page.canvasModeActive）。进入画布模式前 canvas.fitToWindow() ——
// ImageCanvas 的显示矩形恒为"图像中心 = 视口中心"（image_canvas.cpp:105-133
// 的三种视图操作都保持该性质），叠加层据此自行推算显示矩形；模式激活期间
// 叠加层吞掉鼠标与滚轮、工具栏缩放按钮与检查器一并禁用，视图因此冻结，
// 坐标换算（视口 → 预览像素 → 文档像素）全程成立。documentWidth/Height 由
// documentOpened 种入、确定性几何应用后本地推演更新（各 apply* 注释标明
// 推演式：rotate_free 展开按 Worker 端 PIL 引擎的角点外接框公式，见
// pilRotateExpandedSize 注；perspective 按四角包围盒假设，见 applyPerspective
// 注释）。
//
// Rules kept verbatim (总纲 §9: UI 主线程零像素计算):
// - QML does no pixel math; every long-running image operation is an async
//   Worker task submitted through DocumentService (never sendAction directly).
// - The canvas shows the picked local file immediately (fast display); after
//   documentOpened the source stays that local file URL and only the recorded
//   documentId changes state.
// - Slider previews: any change while dragging → 300ms debounce →
//   DocumentService.adjust(adjustments, true, 768); dragFinished → one
//   immediate preview at the same max_side. previewReady(result) feeds
//   canvas.source with "file:// + result.path". The Worker writes every
//   preview of a document to the SAME temp path (preview-<document_id>.png,
//   python_worker/adapters/filter_adapter.py write_preview) and
//   ImageCanvas::setSource early-returns on an equal URL — so the URL carries
//   an incrementing ?v= query as a reload trigger; QUrl::toLocalFile() strips
//   the query and decodes back to the exact file path.
// - Filter chain previews (流程 2) ride the identical channel: chain/param
//   changes → 300ms debounce → FilterService.previewChain(768)（组包在
//   FilterService，经 DocumentService::applyFilters 提交）→ 完成结果携带
//   preview 文件路径（§3.1 filter.preview 不递增 version）→ previewReady →
//   同一画布刷新。[预览] 按钮也走同一防抖出口（两次快速点击只发一次）。
// - Apply/transform/filter-apply full-resolution results carry no pixel path
//   (§3.2), so the post-completion canvas refresh requests one preview of the
//   *current* pixels via a fully-neutral adjustments object: the Worker skips
//   near-default keys (python_worker/adapters/image_adapter.py adjust_chain)
//   and renders the document as-is. undo/redo/reset deliver their restored
//   canvas file through DocumentService.previewReady themselves (§3.3).
// - Applied adjustments bake into the document: after a full-resolution apply
//   the sliders return to neutral (the "已应用状态" baseline of ui-page-spec
//   §2), so the next preview/apply cannot double-apply on top of the result.
//   The filter chain follows the same discipline: after filter.apply the
//   chain is cleared — a surviving chain would re-apply itself on top of the
//   baked result on the next preview/apply.
Page {
    id: page

    background: Rectangle { color: Theme.canvasBackdrop }

    // ---- document / session state -----------------------------------------
    // hasDocument follows the service (never faked locally); canvas emptiness
    // follows the canvas itself (viewer may still show data without a Worker).
    readonly property bool hasDocument: DocumentService.currentDocumentId !== ""
    property string openedDocumentId: ""        // 流程 1: documentOpened 记录 documentId
    property string savedAsPath: ""             // 最近一次 documentSaved 目标（另存为后的显示路径）
    readonly property string displayPath:
        savedAsPath !== "" ? savedAsPath : DocumentService.documentPath
    readonly property string documentFileName: fileNameOf(displayPath)
    readonly property bool backendReady: Application.backend.running

    property int previewSeq: 0                  // ?v= 递增序号：同路径预览强制重载
    property bool openPending: false            // image.open 在途（同步响应未回）
    property bool fullResInFlight: false        // apply/transform/链应用/标注 任务在途
    property bool applyRequested: false         // 本次 version 变更来自"应用"
    property bool transformRequested: false     // 本次 version 变更来自"变换"
    property bool annotateRequested: false      // 本次 version 变更来自"完成标注"
    property bool filterApplyRequested: false   // 本次 version 变更来自"滤镜链应用"（流程 2）
    property bool suppressPreview: false        // 程序化写滑杆值时抑制预览请求
    property bool suppressTransform: false      // 程序化写变换控件值时抑制预览请求

    // ---- Phase 9：文档像素尺寸与画布模式 -------------------------------------
    // documentWidth/Height 是文档像素真值的页面镜像（画布 imageSize 是预览
    // 文件尺寸，非文档尺寸）：documentOpened 种入；确定性几何应用（crop/
    // rotate90/rotate_free 展开/缩放）完成后按其输出尺寸更新，翻转不变，
    // perspective 按四角包围盒假设更新（applyPerspective 注释）。overlay 的
    // 视口→文档像素换算依赖它，见各组件文件头。
    property int documentWidth: 0
    property int documentHeight: 0
    property url sourceFileUrl: ""              // 打开时的本地文件 URL（对比"原图"）
    property var pendingDocDims: null           // 在途几何应用的确定性输出尺寸 {width,height}
    property var pendingAnnotateOps: []         // 完成标注已提交的 ops（完成后清空）
    // undo/redo/reset 在途：其完成事件经 previewReady 携带**恢复后的文档尺寸**
    // （协议 §3.3，与预览任务的"预览图尺寸"不同名同信号）——previewReady 消费
    // 该旗标把 documentWidth/Height 镜像回准（撤销/重做几何应用后镜像不失准）。
    // 残余竞态（点击撤销前已在途的 adjust/transform 预览先于撤销完成事件到达
    // 且被误认）以"旗标期间不发新预览"收窄，见 requestPreview 门与 notes。
    property bool historyRestorePending: false

    // 画布刷新（requestDocumentRefresh 的取回预览）在途：全分辨率几何应用
    // 完成时 documentWidth/Height 镜像已更新、但 canvas.imageSize 仍是被替换
    // 前的旧预览尺寸——overlay 的 视口→文档像素 换算 k 因子在此窗口失配，
    // 故 crop/perspective/annotate 的画布模式入口以本旗标门控（预览到达 /
    // 动作失败 / 换文档 / Worker 崩溃时清除）。窗口期内提交的调整预览渲染
    // 的同样是当前文档像素，先到先解窗口；残余竞态与 historyRestorePending
    // 同类收窄——完成前已在途的旧像素预览跨过完成边界先到会提前开门，由
    // 随后的刷新预览自愈。翻转/撤销路径的尺寸与像素同帧到达（previewReady
    // 携带恢复后尺寸），本旗标不改变其行为。
    property bool refreshPending: false

    // 画布模式（互斥）：叠加层吞鼠标/滚轮 + 工具栏缩放/历史与检查器禁用。
    property bool cropActive: false
    property bool perspectiveActive: false
    property bool annotateActive: false
    property bool compareActive: false
    readonly property bool canvasModeActive:
        cropActive || perspectiveActive || annotateActive || compareActive

    // 与 Worker 的 no-op 阈值一致（adjust_chain 跳过 |Δ| ≤ 1e-6 的键）。
    readonly property bool adjustmentsDirty:
        sliderDirty(brightnessSlider) || sliderDirty(contrastSlider)
        || sliderDirty(saturationSlider) || sliderDirty(gammaSlider)
        || sliderDirty(exposureSlider) || sliderDirty(hueSlider)
        || sliderDirty(vibranceSlider) || sliderDirty(highlightsSlider)
        || sliderDirty(shadowsSlider)

    Component.onCompleted: {
        // document_service.h：QML 侧负责接线。bindBackend 接 Worker 帧，
        // bindTaskModel 把 Application.taskModel 注入服务——dispatch 受理异步
        // 动作时经 TaskModel.trackRequest 登记任务行，任务抽屉/状态栏摘要与
        // 行内取消才对编辑动作生效。两个绑定都幂等，重复调用无害。
        DocumentService.bindBackend(Application.backend)
        DocumentService.bindTaskModel(Application.taskModel)
        // 滤镜页签接线（filter_service.h 同款约定）：bindBackend 接响应帧；
        // 页面打开时拉一次滤镜目录（流程 2 数据源）与预设缓存。Worker 未就绪
        // 时两者都跳过——未绑定的请求只会发 filterError(INTERNAL)（无意义
        // Toast），就绪兜底见 Application.backend Connections 的
        // onRunningChanged 与 AppFilterInspector 的 onBackendReadyChanged。
        FilterService.bindBackend(Application.backend)
        if (page.backendReady) {
            FilterService.loadFilters()
            filterInspector.pullPresets()
        }
    }

    // ---- helpers ------------------------------------------------------------
    function fileNameOf(path) {
        const normalized = String(path).replace(/\\/g, "/");
        return normalized.substring(normalized.lastIndexOf("/") + 1);
    }

    function sliderDirty(slider) {
        return Math.abs(slider.value - slider.defaultValue) > 1e-6;
    }

    // 本地路径 → file:// URL（encodeURIComponent 逐段编码，QUrl::toLocalFile
    // 解码还原；POSIX 与 Windows 盘符两种形态都覆盖）。
    function toFileUrl(path) {
        const segments = String(path).replace(/\\/g, "/").split("/");
        let encoded = "";
        for (let i = 0; i < segments.length; ++i)
            encoded += (i > 0 ? "/" : "") + encodeURIComponent(segments[i]);
        return encoded.charAt(0) === "/" ? "file://" + encoded : "file:///" + encoded;
    }

    // file:// URL → 本地路径（保存/另存为落盘用；openDocument 走 QUrl 原值）。
    function urlToPath(fileUrl) {
        const text = String(fileUrl);
        if (text.indexOf("file://") !== 0)
            return text;  // 非本地 URL：原样交给服务端校验（INVALID_PARAMS 路径）
        let path = text.substring("file://".length);
        try {
            path = decodeURIComponent(path);
        } catch (e) {
            // 畸形百分号序列：保留原样，由 Worker 校验报错
        }
        // file:///C:/dir/x.png → C:/dir/x.png；file:///home/u/x.png → /home/u/x.png
        if (path.length > 2 && path.charAt(0) === "/" && path.charAt(2) === ":")
            path = path.substring(1);
        return path;
    }

    // 剥离 ?v= 查询（Image 元素按文件名取本地文件，预览 URL 的重载查询只属
    // 于 ImageCanvas 的刷新通道；对比层直接取文件，不需要它）。
    function stripUrlQuery(url) {
        const text = String(url);
        const q = text.indexOf("?");
        return q >= 0 ? text.substring(0, q) : text;
    }

    // 字节 → 人类可读（保存 Toast 的实际大小；target_kb 语义为 KB）。
    function formatBytes(bytes) {
        const b = Number(bytes);
        if (!isFinite(b) || b < 0)
            return "";
        if (b < 1024)
            return b + " B";
        if (b < 1024 * 1024)
            return (b / 1024).toFixed(1) + " KB";
        return (b / (1024 * 1024)).toFixed(2) + " MB";
    }

    function showToast(message, toastType) {
        toast.type = toastType;
        toast.text = message;
        if (toast.visible)
            toast.close();
        toast.open();
    }

    // Worker 未就绪时的诚实入口：请求会被 PythonWorker::sendLine 静默丢弃
    // （backend/python_worker.cpp:92-96），先明说，绝不假装已受理。
    function ensureBackendReady() {
        if (page.backendReady)
            return true;
        showToast(qsTr("后端未就绪（%1）：请先到设置页启动 Worker")
                  .arg(Application.backend.state), AppToast.Type.Warning);
        return false;
    }

    // 调整键名与协议 image.adjust 的 adjustments 字段一致（docs/ipc-protocol.md
    // §3.2：brightness/contrast/saturation/gamma/exposure/hue/vibrance/
    // highlights/shadows）。整表发送，中性值由 Worker 的 no-op 剪枝跳过。
    function collectAdjustments() {
        return {
            brightness: brightnessSlider.value,
            contrast: contrastSlider.value,
            saturation: saturationSlider.value,
            gamma: gammaSlider.value,
            exposure: exposureSlider.value,
            hue: hueSlider.value,
            vibrance: vibranceSlider.value,
            highlights: highlightsSlider.value,
            shadows: shadowsSlider.value
        };
    }

    // 与 Worker 步进默认值一致（adapters/image_adapter.py _ADJUST_STEPS：
    // gamma 中性 1.0，其余 0.0）。全默认 → adjust_chain 跳过全部键 → 预览
    // 文件即当前文档像素（"最新像素"取回通道）。
    function neutralAdjustments() {
        return {
            brightness: 0, contrast: 0, saturation: 0, gamma: 1, exposure: 0,
            hue: 0, vibrance: 0, highlights: 0, shadows: 0
        };
    }

    function resetAdjustSliders() {
        // 程序化赋值不经过滑杆的 valueModified 通道；仍用 suppressPreview
        // 兜底 onValueChanged，保证不触发预览请求。
        page.suppressPreview = true;
        brightnessSlider.value = brightnessSlider.defaultValue;
        contrastSlider.value = contrastSlider.defaultValue;
        saturationSlider.value = saturationSlider.defaultValue;
        gammaSlider.value = gammaSlider.defaultValue;
        exposureSlider.value = exposureSlider.defaultValue;
        hueSlider.value = hueSlider.defaultValue;
        vibranceSlider.value = vibranceSlider.defaultValue;
        highlightsSlider.value = highlightsSlider.defaultValue;
        shadowsSlider.value = shadowsSlider.defaultValue;
        page.suppressPreview = false;
    }

    // ---- actions -------------------------------------------------------------
    function openFile(url) {
        // 画布先行：本地文件 URL 直接解码 → 快速显示（ui-page-spec §2 加载态）。
        // 已知代价：首帧解码在 ImageCanvas::setSource 的 GUI 线程同步完成，
        // 大图会阻塞界面（docs/phase5-acceptance.md §8 偏差 1，异步化留待
        // 后续批次）。
        canvas.source = url;
        page.sourceFileUrl = url;  // 对比模式的"原图"（未编辑源）
        if (!page.ensureBackendReady())
            return;  // 画布仍可查看已加载数据（ui-page-spec §2 Worker 不可用）
        page.openPending = true;
        DocumentService.openDocument(url);
    }

    function openSaveDialog() {
        if (!page.hasDocument)
            return;
        // 预选当前文件名（FileDialog.selectedFile 可在 open 前预设）
        saveDialog.selectedFile = page.toFileUrl(page.displayPath);
        saveDialog.open();
    }

    // Phase 9：保存选项（FileDialog 无法内嵌字段，选完文件后补这一步）。
    function openSaveOptions(path) {
        saveOptionsDialog.openFor(path);
    }

    function applyAdjustments() {
        if (!page.hasDocument || !page.adjustmentsDirty || !page.ensureBackendReady())
            return;
        page.applyRequested = true;
        page.fullResInFlight = true;
        DocumentService.adjust(page.collectAdjustments(), false, 0);
    }

    // ---- Phase 9：画布模式（互斥；进入前先 fit，见文件头画布模式总纲）--------
    function exitCanvasModes() {
        page.cropActive = false;
        page.perspectiveActive = false;
        page.compareActive = false;
        if (page.annotateActive) {
            page.annotateActive = false;
            annotateOverlay.clearOps();
        }
    }

    // 三个带坐标换算的画布模式（crop/perspective/annotate）进入前查
    // refreshPending：全分辨率应用完成 → 刷新预览到达前，documentWidth/
    // Height 镜像已更新而 canvas.imageSize 仍是旧预览尺寸，此时进入会在
    // 失配的 k 因子上拉框（选区换算偏差直到刷新到达才消失，属性注）。
    // compare 无坐标换算，不在此列。退出方向（on=false）不受任何门控。
    function setCropMode(on) {
        if (on === page.cropActive)
            return;
        page.exitCanvasModes();
        if (on) {
            if (!page.hasDocument || page.refreshPending || !page.ensureBackendReady())
                return;
            canvas.fitToWindow();
            page.cropActive = true;
        }
    }

    function setPerspectiveMode(on) {
        if (on === page.perspectiveActive)
            return;
        page.exitCanvasModes();
        if (on) {
            if (!page.hasDocument || page.refreshPending || !page.ensureBackendReady())
                return;
            canvas.fitToWindow();
            page.perspectiveActive = true;
        }
    }

    function setAnnotateMode(on) {
        if (on === page.annotateActive)
            return;
        page.exitCanvasModes();
        if (on) {
            if (!page.hasDocument || page.refreshPending || !page.ensureBackendReady())
                return;
            canvas.fitToWindow();
            page.annotateActive = true;
        }
    }

    function setCompareMode(on) {
        if (on === page.compareActive)
            return;
        page.exitCanvasModes();
        if (on) {
            if (!page.hasDocument)
                return;
            page.compareActive = true;
        }
    }

    // ---- Phase 9：变换提交（新接口 applyTransform，见 document_service.h）----
    // 组包形状（Worker 端 image.transform 的 Phase 9 批式增补，既有 op/params
    // 形式不变，向后兼容）：{crop:{x,y,width,height}} / {rotate_free:{angle,
    // expand}} / {perspective:{corners:[[x,y]×4]}} / {scale:{width,height,
    // resample}}。preview=true 走 768 预览（previewReady 既有通道）。
    function requestTransformPreview() {
        if (!page.hasDocument || !page.backendReady || page.fullResInFlight
                || page.canvasModeActive || page.historyRestorePending)
            return;
        DocumentService.applyTransform(
            { rotate_free: { angle: rotateFreeSlider.value, expand: expandToggle.checked } },
            true, 768);
    }

    function runTransform(op, params, expectedDims) {
        if (!page.hasDocument || !page.ensureBackendReady() || page.fullResInFlight
                || page.canvasModeActive)
            return;
        page.pendingDocDims = expectedDims !== undefined ? expectedDims : null;
        page.transformRequested = true;
        page.fullResInFlight = true;
        DocumentService.transform(op, params, false, 0);
    }

    function applyCrop(crop) {
        if (!page.hasDocument || !page.ensureBackendReady() || page.fullResInFlight)
            return;
        page.setCropMode(false);
        // crop 输出尺寸 = 矩形本身（确定性），完成时据此更新文档尺寸镜像。
        page.pendingDocDims = { width: crop.width, height: crop.height };
        page.transformRequested = true;
        page.fullResInFlight = true;
        DocumentService.applyTransform({ crop: crop }, false, 0);
    }

    function applyPerspective(corners) {
        if (!page.hasDocument || !page.ensureBackendReady() || page.fullResInFlight)
            return;
        page.setPerspectiveMode(false);
        // 输出尺寸假设 = 四角的轴对齐包围盒（透视校正把四边形拉直为矩形的
        // 常见约定；Worker 端实现若不同，此处镜像会失准直至下次打开——
        // 见 notes/risks 的假设声明）。
        let minX = corners[0][0], maxX = corners[0][0];
        let minY = corners[0][1], maxY = corners[0][1];
        for (let i = 1; i < corners.length; ++i) {
            minX = Math.min(minX, corners[i][0]);
            maxX = Math.max(maxX, corners[i][0]);
            minY = Math.min(minY, corners[i][1]);
            maxY = Math.max(maxY, corners[i][1]);
        }
        page.pendingDocDims = { width: Math.max(1, Math.round(maxX - minX)),
                                height: Math.max(1, Math.round(maxY - minY)) };
        page.transformRequested = true;
        page.fullResInFlight = true;
        DocumentService.applyTransform({ perspective: { corners: corners } }, false, 0);
    }

    // Pillow Image.rotate(expand=true) 的输出尺寸（Worker 端 rotate_free 的
    // 实际引擎，image_adapter.py _rotate_free）。Pillow 先走 0/90/180/270 的
    // transpose/copy 快速路径（精确换轴，无取整——奇数边长在 90° 上与通用
    // 公式差 1 px，如 100×65@90° 快速路径 = 65 而外接框公式给 66）；其余角
    // 按旋转后角点外接框取整：nw = ceil(max(xx)) − floor(min(xx))（Pillow
    // Image.py rotate，矩阵分量经 round(·, 15)）。角点关于中心对称 ⇒ 闭式：
    // ceil(w/2 + S/2) − floor(w/2 − S/2)，S 为该方向角点跨度
    // （|round(cos)|·w + |round(sin)|·h）。注意不得改用 processors/core.py
    // rotate 的 cv2 截断公式 int(w·cos+h·sin)——与 PIL 在多数非 90° 倍角上
    // 差 1–2 px（64×64@45°：PIL=92，截断=90）；2·ceil(S/2) 的简化也只对
    // 偶数边长成立（奇数边长外接框跨度恒为奇数）。round(·,15) 模拟 Pillow
    // 的矩阵分量取整：接近 90° 的浮点残差（cos(π/2)=6.1e-17）须归零。
    function pilRotateExpandedSize(width, height, angleDeg) {
        // Python angle % 360.0 语义（负角折到 [0, 360)），对齐 Pillow 快速
        // 路径的判定值。
        const a = ((angleDeg % 360.0) + 360.0) % 360.0;
        if (a === 0 || a === 180)
            return { width: width, height: height };
        if (a === 90 || a === 270)
            return { width: height, height: width };
        const rad = angleDeg * Math.PI / 180.0;
        const c = Math.round(Math.cos(rad) * 1e15) / 1e15;
        const s = Math.round(Math.sin(rad) * 1e15) / 1e15;
        const sx = Math.abs(c) * width + Math.abs(s) * height;
        const sy = Math.abs(s) * width + Math.abs(c) * height;
        return {
            width: Math.ceil(width / 2 + sx / 2) - Math.floor(width / 2 - sx / 2),
            height: Math.ceil(height / 2 + sy / 2) - Math.floor(height / 2 - sy / 2)
        };
    }

    function applyFreeRotate() {
        const angle = rotateFreeSlider.value;
        if (Math.abs(angle) < 0.5) {
            page.showToast(qsTr("角度为 0，无需应用"), AppToast.Type.Info);
            return;
        }
        if (!page.hasDocument || !page.ensureBackendReady() || page.fullResInFlight
                || page.canvasModeActive)
            return;
        const expand = expandToggle.checked;
        // expand=true 的输出尺寸按 Worker 端实际引擎（PIL Image.rotate）的
        // 角点外接框公式推演（见 pilRotateExpandedSize 注）；expand=false
        // 裁回原框，尺寸不变。
        let dims = null;
        if (expand)
            dims = pilRotateExpandedSize(page.documentWidth, page.documentHeight, angle);
        page.pendingDocDims = dims;
        page.transformRequested = true;
        page.fullResInFlight = true;
        DocumentService.applyTransform(
            { rotate_free: { angle: angle, expand: expand } }, false, 0);
    }

    function applyScale() {
        if (!page.hasDocument || !page.ensureBackendReady() || page.fullResInFlight
                || page.canvasModeActive)
            return;
        const w = Math.round(scaleWidthField.value);
        const h = Math.round(scaleHeightField.value);
        if (w < 1 || h < 1) {
            page.showToast(qsTr("缩放尺寸无效（宽高须 ≥ 1 像素）"), AppToast.Type.Warning);
            return;
        }
        const resampleKeys = ["lanczos", "bilinear", "nearest", "bicubic"];
        page.pendingDocDims = { width: w, height: h };
        page.transformRequested = true;
        page.fullResInFlight = true;
        DocumentService.applyTransform(
            { scale: { width: w, height: h, resample: resampleKeys[resampleSelect.currentIndex] } },
            false, 0);
    }

    // 变换页签控件回基准（文档打开 / 全分辨率变换完成后调用）。程序化赋值
    // 经 suppressTransform 抑制自由旋转的防抖预览。
    function resetTransformFields() {
        page.suppressTransform = true;
        rotateFreeSlider.value = 0;
        expandToggle.checked = true;
        scaleWidthField.value = page.documentWidth;
        scaleHeightField.value = page.documentHeight;
        resampleSelect.currentIndex = 0;
        page.suppressTransform = false;
    }

    // ---- Phase 9：标注提交（新接口 applyAnnotate，见 document_service.h）-----
    function applyAnnotateOps() {
        const ops = annotateOverlay.ops;
        if (!page.hasDocument || !page.ensureBackendReady() || page.fullResInFlight
                || ops.length === 0)
            return;
        page.pendingAnnotateOps = ops;
        page.annotateRequested = true;
        page.fullResInFlight = true;
        // 全分辨率一次提交（预览即本地 Canvas 近似层，无 Worker 预览任务）。
        DocumentService.applyAnnotate(ops);
    }

    // ---- 流程 2：滤镜链（docs/user-flows.md 流程 2）---------------------------
    // 链预览：链/参数变化与 [预览] 按钮共用同一 300ms 防抖（filterPreviewDebounce
    //），出口统一在此：空链/无文档/未就绪静默跳过——空链提交会被
    // DocumentService::applyFilters 本地拒绝（INVALID_PARAMS + actionFailed），
    // 弹错误 Toast 纯属噪音（文档切换后的自动清链也会短暂经过这里）。
    function requestChainPreview() {
        if (!page.hasDocument || !page.backendReady || page.historyRestorePending
                || FilterService.chainModel.stepCount === 0)
            return;
        FilterService.previewChain(768);
    }

    function applyFilterChain() {
        if (!page.hasDocument || !page.ensureBackendReady()
                || FilterService.chainModel.stepCount === 0 || page.fullResInFlight)
            return;
        page.filterApplyRequested = true;
        page.fullResInFlight = true;
        // 组包与提交都在 FilterService（currentChainSteps → DocumentService::
        // applyFilters 全分辨率，§3.1 version+1 / modified）；QML 不 sendAction。
        FilterService.applyChain()
    }

    // ---- 历史（undo/redo/reset 的旗标式封装，见 historyRestorePending 注）--
    function requestUndo() {
        page.historyRestorePending = true;
        DocumentService.undo();
    }

    function requestRedo() {
        page.historyRestorePending = true;
        DocumentService.redo();
    }

    function requestReset() {
        page.historyRestorePending = true;
        DocumentService.reset();
    }

    // dragging 期间的重分送（300ms 防抖，见底部 previewDebounce）。
    function requestPreview() {
        if (!page.hasDocument || !page.ensureBackendReady() || page.historyRestorePending)
            return;
        DocumentService.adjust(page.collectAdjustments(), true, 768);
    }

    // apply/transform 完成后的画布刷新：completed result 无像素路径（§3.2），
    // 以全默认 adjustments 请求一次预览 = 取回最新像素。置 refreshPending：
    // 预览替换画布源前 documentWidth/Height 镜像与 canvas.imageSize 短暂
    // 失配，画布模式入口据此门控（属性注）。
    function requestDocumentRefresh() {
        if (!page.hasDocument || !page.ensureBackendReady())
            return;
        page.refreshPending = true;
        DocumentService.adjust(page.neutralAdjustments(), true, 768);
    }

    // ---- top toolbar ---------------------------------------------------------
    // ui-page-spec §2: [打开][保存][另存] │ [↶撤销][↷重做] │ 缩放控件 │ 文件名●
    //
    // 历史与保存的串行化：撤销/重做/重置/保存与全分辨率应用/变换共用同一
    // 文档历史栈，而 Worker 任务池是多线程的（settings concurrentTasks，默认
    // 2）——在途应用/变换未落定前提交 undo/redo/reset/save，历史栈改写与保存
    // 像素取决于执行时序，会拼出错误历史。故这些入口一律加
    // !page.fullResInFlight 门控（在途标记由 onDocumentVersionChanged /
    // onDocumentOpened / onDocumentActionFailed / onErrorOccurred 统一解除：
    // 换文档即在途结果作废，只有当前文档的全分辨率提交失败才解锁）。
    // 撤销/重做/重置另受 backendReady 门控：Worker 未运行时 sendAction 静默
    // 丢帧（python_worker.cpp:92-96），点击是无反馈的空操作且泄漏 pending，
    // 与打开/预览/应用/保存的 ensureBackendReady 口径保持一致。
    AppTopToolbar {
        id: pageToolbar

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right

        AppButton {
            kind: AppButton.Kind.Primary
            text: qsTr("打开")
            onClicked: openDialog.open()
        }
        AppButton {
            text: qsTr("保存")
            enabled: DocumentService.documentModified && !page.fullResInFlight
                     && !page.canvasModeActive
            onClicked: page.openSaveDialog()
        }
        AppButton {
            text: qsTr("另存为")
            enabled: page.hasDocument && !page.fullResInFlight && !page.canvasModeActive
            onClicked: page.openSaveDialog()
        }

        contentCenter: [
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("↶")
                tooltipText: qsTr("撤销")
                enabled: page.hasDocument && historyModel.canUndo
                         && !page.fullResInFlight && page.backendReady
                         && !page.canvasModeActive
                onClicked: page.requestUndo()
            },
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("↷")
                tooltipText: qsTr("重做")
                enabled: page.hasDocument && historyModel.canRedo
                         && !page.fullResInFlight && page.backendReady
                         && !page.canvasModeActive
                onClicked: page.requestRedo()
            },
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("重置")
                tooltipText: qsTr("重置到初始状态")
                enabled: page.hasDocument && historyModel.canUndo
                         && !page.fullResInFlight && page.backendReady
                         && !page.canvasModeActive
                onClicked: page.requestReset()
            }
        ]

        contentRight: [
            // Phase 9：画布模式开关（标注 / 对比）。非 checkable：模式显隐由
            // 画布上的浮层呈现，避免 ToolButton checkable 内部写 checked 打断
            // checked 绑定（页面状态在完成标注后退出时按钮无法回弹）。
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("标注")
                tooltipText: qsTr("画布标注（画笔/文字/形状/模糊）")
                // refreshPending 门控同裁剪/透视入口（setCropMode 注）：
                // 标注叠加层的 视口→文档像素 换算依赖尺寸镜像。
                enabled: page.hasDocument && page.backendReady && !page.fullResInFlight
                         && (page.annotateActive || !page.refreshPending)
                onClicked: page.setAnnotateMode(!page.annotateActive)
            },
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("对比")
                tooltipText: qsTr("原图/当前图滑块对比（Esc 退出）")
                enabled: page.hasDocument
                onClicked: page.setCompareMode(!page.compareActive)
            },

            AppTopToolbar.GroupRule {},

            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("−")
                tooltipText: qsTr("缩小")
                enabled: page.hasDocument && !page.canvasModeActive
                onClicked: canvas.zoomBy(1 / 1.25)
            },
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("+")
                tooltipText: qsTr("放大")
                enabled: page.hasDocument && !page.canvasModeActive
                onClicked: canvas.zoomBy(1.25)
            },
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("适配")
                tooltipText: qsTr("适配窗口")
                enabled: page.hasDocument && !page.canvasModeActive
                onClicked: canvas.fitToWindow()
            },
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("100%")
                tooltipText: qsTr("实际大小")
                enabled: page.hasDocument && !page.canvasModeActive
                onClicked: canvas.setActualSize()
            },
            Label {
                text: canvas.zoom >= 0.01
                      ? Math.round(canvas.zoom * 100) + "%"
                      : "—"
                font.pixelSize: Theme.fontSizeNumeric
                color: Theme.textPrimary
                Layout.alignment: Qt.AlignVCenter
            },

            AppTopToolbar.GroupRule {},

            Label {
                Layout.maximumWidth: 220
                Layout.alignment: Qt.AlignVCenter
                text: page.documentFileName
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textPrimary
                elide: Text.ElideMiddle
            },
            Label {
                Layout.alignment: Qt.AlignVCenter
                text: "●"   // 未保存修改（ui-page-spec §2 文件名●）
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.warning
                visible: DocumentService.documentModified
            },
            AppProgressIndicator {
                form: AppProgressIndicator.Form.Inline
                indeterminate: true
                visible: canvas.busy
                Layout.alignment: Qt.AlignVCenter
            }
        ]
    }

    // ---- canvas + inspector --------------------------------------------------
    RowLayout {
        id: mainArea

        anchors.top: pageToolbar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: pageStatusBar.top
        spacing: 0

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ImageCanvas {
                id: canvas
                anchors.fill: parent
                showCheckerboard: true

                onImageDropped: function (url) { page.openFile(url) }
                onLoadFailed: function (reason) {
                    // 置空复位（source 为空）引起的失败不弹错。
                    if (canvas.source.toString() !== "")
                        page.showToast(qsTr("打开失败：%1").arg(reason), AppToast.Type.Error)
                }
            }

            // Empty state: no image on canvas. Double-click fit is implemented
            // inside ImageCanvas (mouseDoubleClickEvent → fitToWindow).
            ColumnLayout {
                anchors.centerIn: parent
                visible: canvas.imageSize.isEmpty
                spacing: Theme.spacingMd

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("拖放图像到此处，或点击\"打开\"")
                    font.pixelSize: Theme.fontSizeBody
                    color: Theme.textSecondary
                }

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("滚轮缩放 · 拖动平移 · 双击适配 · 打开后可在右侧调整并应用")
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textDisabled
                }
            }

            // ---- Phase 9 画布模式层（互斥，z 高于空态、低于 Toast）-----------
            // 各层吞掉画布的鼠标/滚轮（视图冻结，见文件头画布模式总纲）；
            // 显示矩形推演所需的状态从画布/页面注入。
            AppCompareSlider {
                id: compareOverlay
                anchors.fill: parent
                z: 3
                visible: page.compareActive
                originalSource: page.sourceFileUrl
                currentSource: page.stripUrlQuery(canvas.source)
            }

            AppCropOverlay {
                id: cropOverlay
                anchors.fill: parent
                z: 3
                visible: page.cropActive
                zoom: canvas.zoom
                imageWidth: canvas.imageSize.width
                imageHeight: canvas.imageSize.height
                documentWidth: page.documentWidth
                documentHeight: page.documentHeight
                onApplyRequested: function (crop) { page.applyCrop(crop) }
                onCancelled: page.setCropMode(false)
            }

            AppPerspectiveOverlay {
                id: perspectiveOverlay
                anchors.fill: parent
                z: 3
                visible: page.perspectiveActive
                zoom: canvas.zoom
                imageWidth: canvas.imageSize.width
                imageHeight: canvas.imageSize.height
                documentWidth: page.documentWidth
                documentHeight: page.documentHeight
                onApplyRequested: function (transform) { page.applyPerspective(transform.corners) }
                onCancelled: page.setPerspectiveMode(false)
            }

            AppAnnotateOverlay {
                id: annotateOverlay
                anchors.fill: parent
                z: 3
                visible: page.annotateActive
                zoom: canvas.zoom
                imageWidth: canvas.imageSize.width
                imageHeight: canvas.imageSize.height
                documentWidth: page.documentWidth
                documentHeight: page.documentHeight
                tool: annotateToolbar.tool
                strokeColor: annotateToolbar.color
                strokeWidth: annotateToolbar.strokeWidth
                textSize: annotateToolbar.textSize
                strength: annotateToolbar.strength
                blockSize: annotateToolbar.blockSize
            }

            AppAnnotateToolbar {
                id: annotateToolbar
                anchors.top: parent.top
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.topMargin: Theme.spacingMd
                z: 4
                visible: page.annotateActive
                opCount: annotateOverlay.ops.length
                onFinishRequested: page.applyAnnotateOps()
                onCancelled: page.setAnnotateMode(false)
                onUndoLastRequested: annotateOverlay.undoLast()
                onClearRequested: annotateOverlay.clearOps()
            }

            // Toast host: autoPosition docks to this area's bottom-right.
            AppToast {
                id: toast
            }
        }

        AppInspectorPanel {
            id: inspector

            Layout.fillHeight: true
            visible: page.hasDocument   // 空态：检查器隐藏（ui-page-spec §2）
            // 画布模式激活期间检查器整体禁用（任务口径"进入后禁用其他交互"；
            // 模式退出走画布浮层的 [取消]/Esc）。
            enabled: !page.canvasModeActive
            tabs: [{ id: "adjust", title: qsTr("调整") },
                   { id: "filters", title: qsTr("滤镜") },
                   { id: "transform", title: qsTr("变换") }]
            currentIndex: 0

            // Worker 不可用的降级横幅（ui-page-spec §2）：画布仍可查看。
            Rectangle {
                width: parent.width
                height: bannerLabel.implicitHeight + Theme.spacingSm * 2
                radius: Theme.radiusSm
                color: "transparent"
                border.color: Theme.warning
                border.width: 1
                visible: page.hasDocument && !page.backendReady

                Label {
                    id: bannerLabel
                    anchors.fill: parent
                    anchors.margins: Theme.spacingSm
                    text: qsTr("Worker 未就绪（%1）——预览与应用不可用，画布仍可查看已加载数据")
                          .arg(Application.backend.state)
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.warning
                    wrapMode: Text.WordWrap
                    verticalAlignment: Text.AlignVCenter
                }
            }

            // AppInspectorPanel 的默认槽是各页签共用的一条滚动 Column，不随
            // currentIndex 切换内容——页签内容各自带 visible 开关（隐藏项不占
            // 布局，Column 会跳过不可见子项）。
            //
            // 调整页签（ui-page-spec §2）：滑杆 + 数值输入双向绑定；
            // 中性默认值与 Worker _ADJUST_STEPS 一致（gamma 1.0，其余 0.0）。
            Column {
                id: adjustContent
                visible: inspector.currentTabId === "adjust"
                width: parent.width
                spacing: Theme.spacingMd

                AppSliderField {
                    id: brightnessSlider
                    width: parent.width
                    label: qsTr("亮度")
                    from: -1; to: 1; step: 0.05; defaultValue: 0
                    onValueChanged: if (!page.suppressPreview) previewDebounce.restart()
                    onValueModified: previewDebounce.restart()
                    onDragFinished: {
                        previewDebounce.stop();
                        page.requestPreview();   // 松手立即发一次 max 768 预览
                    }
                }
                AppSliderField {
                    id: contrastSlider
                    width: parent.width
                    label: qsTr("对比度")
                    from: -1; to: 1; step: 0.05; defaultValue: 0
                    onValueChanged: if (!page.suppressPreview) previewDebounce.restart()
                    onValueModified: previewDebounce.restart()
                    onDragFinished: {
                        previewDebounce.stop();
                        page.requestPreview();
                    }
                }
                AppSliderField {
                    id: saturationSlider
                    width: parent.width
                    label: qsTr("饱和度")
                    from: 0; to: 3; step: 0.05; defaultValue: 0
                    onValueChanged: if (!page.suppressPreview) previewDebounce.restart()
                    onValueModified: previewDebounce.restart()
                    onDragFinished: {
                        previewDebounce.stop();
                        page.requestPreview();
                    }
                }
                AppSliderField {
                    id: gammaSlider
                    width: parent.width
                    label: qsTr("伽马")
                    // value 必须与 defaultValue 一并落在中性 1.0：组件默认 value 是 0，
                    // 而 gamma=0 会被 Worker 钳到 0.01（近乎全黑）。
                    from: 0.1; to: 3; step: 0.05; value: 1; defaultValue: 1
                    onValueChanged: if (!page.suppressPreview) previewDebounce.restart()
                    onValueModified: previewDebounce.restart()
                    onDragFinished: {
                        previewDebounce.stop();
                        page.requestPreview();
                    }
                }
                AppSliderField {
                    id: exposureSlider
                    width: parent.width
                    label: qsTr("曝光")
                    from: -3; to: 3; step: 0.1; defaultValue: 0
                    onValueChanged: if (!page.suppressPreview) previewDebounce.restart()
                    onValueModified: previewDebounce.restart()
                    onDragFinished: {
                        previewDebounce.stop();
                        page.requestPreview();
                    }
                }
                AppSliderField {
                    id: hueSlider
                    width: parent.width
                    label: qsTr("色相")
                    suffix: "°"
                    from: -180; to: 180; step: 1; defaultValue: 0
                    onValueChanged: if (!page.suppressPreview) previewDebounce.restart()
                    onValueModified: previewDebounce.restart()
                    onDragFinished: {
                        previewDebounce.stop();
                        page.requestPreview();
                    }
                }
                AppSliderField {
                    id: vibranceSlider
                    width: parent.width
                    label: qsTr("自然饱和度")
                    from: -1; to: 1; step: 0.05; defaultValue: 0
                    onValueChanged: if (!page.suppressPreview) previewDebounce.restart()
                    onValueModified: previewDebounce.restart()
                    onDragFinished: {
                        previewDebounce.stop();
                        page.requestPreview();
                    }
                }
                AppSliderField {
                    id: highlightsSlider
                    width: parent.width
                    label: qsTr("高光")
                    from: -1; to: 1; step: 0.05; defaultValue: 0
                    onValueChanged: if (!page.suppressPreview) previewDebounce.restart()
                    onValueModified: previewDebounce.restart()
                    onDragFinished: {
                        previewDebounce.stop();
                        page.requestPreview();
                    }
                }
                AppSliderField {
                    id: shadowsSlider
                    width: parent.width
                    label: qsTr("阴影")
                    from: -1; to: 1; step: 0.05; defaultValue: 0
                    onValueChanged: if (!page.suppressPreview) previewDebounce.restart()
                    onValueModified: previewDebounce.restart()
                    onDragFinished: {
                        previewDebounce.stop();
                        page.requestPreview();
                    }
                }

                AppButton {
                    id: applyButton
                    width: parent.width
                    kind: AppButton.Kind.Primary
                    text: qsTr("应用")
                    enabled: page.hasDocument && page.adjustmentsDirty && !page.fullResInFlight
                    loading: page.fullResInFlight && page.applyRequested
                    onClicked: page.applyAdjustments()
                }
            }

            // 滤镜页签（docs/user-flows.md 流程 2）：搜索 / FilterCard 网格 /
            // 参数面板 / 链列表 / 预设行。组件只读写 FilterService 的模型与预设
            // API 并发信号——防抖、在途门控与服务提交都归页面
            // （requestChainPreview / applyFilterChain），画布刷新复用
            // previewReady / documentVersionChanged 既有路径。
            AppFilterInspector {
                id: filterInspector

                visible: inspector.currentTabId === "filters"
                width: parent.width
                backendReady: page.backendReady
                fullResInFlight: page.fullResInFlight
                applyInFlight: page.filterApplyRequested && page.fullResInFlight
                onPreviewRequested: filterPreviewDebounce.restart()
                onChainChanged: filterPreviewDebounce.restart()
                onApplyRequested: page.applyFilterChain()
            }

            // 变换页签（Phase 9）：旋转与翻转（既有按钮自顶部工具栏并入）+
            // 自由旋转（防抖预览 300ms 同调整页签路径）+ 缩放 + 裁剪/透视的
            // 画布模式入口。提交经 DocumentService.applyTransform（组包形状见
            // page.applyCrop/applyPerspective/applyFreeRotate/applyScale 注释）。
            Column {
                id: transformContent
                visible: inspector.currentTabId === "transform"
                width: parent.width
                spacing: Theme.spacingMd

                AppSectionGroup {
                    title: qsTr("旋转与翻转")
                    width: parent.width
                    defaultExpanded: true

                    Column {
                        width: parent.width
                        spacing: Theme.spacingMd

                        RowLayout {
                            width: parent.width
                            spacing: Theme.spacingSm

                            AppButton {
                                Layout.fillWidth: true
                                size: AppButton.Size.Small
                                text: qsTr("旋转90°")
                                enabled: page.hasDocument && !page.fullResInFlight
                                         && !page.canvasModeActive && page.backendReady
                                onClicked: page.runTransform(
                                               "rotate", { angle: 90 },
                                               { width: page.documentHeight,
                                                 height: page.documentWidth })
                            }
                            AppButton {
                                Layout.fillWidth: true
                                size: AppButton.Size.Small
                                text: qsTr("水平翻转")
                                enabled: page.hasDocument && !page.fullResInFlight
                                         && !page.canvasModeActive && page.backendReady
                                onClicked: page.runTransform("flip_h", {})
                            }
                            AppButton {
                                Layout.fillWidth: true
                                size: AppButton.Size.Small
                                text: qsTr("垂直翻转")
                                enabled: page.hasDocument && !page.fullResInFlight
                                         && !page.canvasModeActive && page.backendReady
                                onClicked: page.runTransform("flip_v", {})
                            }
                        }

                        AppSliderField {
                            id: rotateFreeSlider
                            width: parent.width
                            label: qsTr("自由旋转")
                            suffix: "°"
                            from: -180; to: 180; step: 1; defaultValue: 0
                            // 拖动即 300ms 防抖预览（同调整页签路径，出口
                            // requestTransformPreview → applyTransform 预览 768）；
                            // 松手立即一次（dragFinished 先于 valueThrottle 落定，
                            // stop() 去重的口径与 previewDebounce 一致）。
                            onValueChanged: if (!page.suppressTransform) transformPreviewDebounce.restart()
                            onValueModified: transformPreviewDebounce.restart()
                            onDragFinished: {
                                transformPreviewDebounce.stop();
                                page.requestTransformPreview();
                            }
                        }

                        AppToggleField {
                            id: expandToggle
                            width: parent.width
                            text: qsTr("扩展画布（旋转后露出完整内容）")
                            checked: true
                            onToggled: transformPreviewDebounce.restart()
                        }

                        AppButton {
                            width: parent.width
                            kind: AppButton.Kind.Primary
                            text: qsTr("应用自由旋转")
                            enabled: page.hasDocument && !page.fullResInFlight
                                     && !page.canvasModeActive && page.backendReady
                            loading: page.fullResInFlight && page.transformRequested
                                     && !page.canvasModeActive
                            onClicked: page.applyFreeRotate()
                        }
                    }
                }

                AppSectionGroup {
                    title: qsTr("缩放")
                    width: parent.width
                    defaultExpanded: true

                    Column {
                        width: parent.width
                        spacing: Theme.spacingMd

                        RowLayout {
                            width: parent.width
                            spacing: Theme.spacingSm

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: Theme.spacingXs

                                Label {
                                    text: qsTr("宽")
                                    font.pixelSize: Theme.fontSizeSmall
                                    color: Theme.textSecondary
                                }
                                AppNumberField {
                                    id: scaleWidthField
                                    Layout.fillWidth: true
                                    from: 1; to: 100000; step: 1; decimals: 0
                                    value: page.documentWidth
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: Theme.spacingXs

                                Label {
                                    text: qsTr("高")
                                    font.pixelSize: Theme.fontSizeSmall
                                    color: Theme.textSecondary
                                }
                                AppNumberField {
                                    id: scaleHeightField
                                    Layout.fillWidth: true
                                    from: 1; to: 100000; step: 1; decimals: 0
                                    value: page.documentHeight
                                }
                            }
                        }

                        RowLayout {
                            width: parent.width
                            spacing: Theme.spacingSm

                            Label {
                                text: qsTr("重采样")
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textSecondary
                            }
                            AppSelectField {
                                id: resampleSelect
                                Layout.fillWidth: true
                                // 词表 = 协议 RESAMPLE_CHOICES（image_adapter.py，
                                // lanczos/bilinear/nearest/bicubic；bicubic 在
                                // core 里映射为 cubic）。
                                model: [qsTr("Lanczos"), qsTr("Bilinear"),
                                        qsTr("Nearest"), qsTr("Bicubic")]
                                currentIndex: 0
                            }
                        }

                        Label {
                            width: parent.width
                            text: qsTr("目标尺寸为文档像素（当前 %1 × %2）；画布显示的是降采样预览")
                                  .arg(page.documentWidth).arg(page.documentHeight)
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textDisabled
                            wrapMode: Text.WordWrap
                        }

                        AppButton {
                            width: parent.width
                            kind: AppButton.Kind.Primary
                            text: qsTr("应用缩放")
                            enabled: page.hasDocument && !page.fullResInFlight
                                     && !page.canvasModeActive && page.backendReady
                            loading: page.fullResInFlight && page.transformRequested
                                     && !page.canvasModeActive
                            onClicked: page.applyScale()
                        }
                    }
                }

                AppSectionGroup {
                    title: qsTr("裁剪")
                    width: parent.width
                    defaultExpanded: true

                    Column {
                        width: parent.width
                        spacing: Theme.spacingMd

                        Label {
                            width: parent.width
                            text: qsTr("在画布上拖拽八向手柄选取区域，支持比例锁定；[应用] 全分辨率裁剪")
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textDisabled
                            wrapMode: Text.WordWrap
                        }

                        AppButton {
                            width: parent.width
                            text: page.cropActive ? qsTr("退出裁剪模式") : qsTr("进入裁剪模式")
                            // 刷新在途（refreshPending）时禁进：文档尺寸镜像与
                            // 画布预览尺寸短暂失配（setCropMode 注），退出方向
                            // 不受影响。
                            enabled: page.hasDocument && !page.fullResInFlight
                                     && (page.cropActive
                                         || (page.backendReady && !page.refreshPending))
                            onClicked: page.setCropMode(!page.cropActive)
                        }
                    }
                }

                AppSectionGroup {
                    // 任务口径：透视校正放"高级折叠区"（默认收起）。
                    title: qsTr("透视校正（高级）")
                    width: parent.width
                    defaultExpanded: false

                    Column {
                        width: parent.width
                        spacing: Theme.spacingMd

                        Label {
                            width: parent.width
                            text: qsTr("拖动画布四角到目标边缘，[应用] 将四边形校正为矩形")
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textDisabled
                            wrapMode: Text.WordWrap
                        }

                        AppButton {
                            width: parent.width
                            text: page.perspectiveActive ? qsTr("退出透视模式") : qsTr("进入透视模式")
                            // 同裁剪入口：refreshPending 门控只禁进入（setCropMode 注）。
                            enabled: page.hasDocument && !page.fullResInFlight
                                     && (page.perspectiveActive
                                         || (page.backendReady && !page.refreshPending))
                            onClicked: page.setPerspectiveMode(!page.perspectiveActive)
                        }
                    }
                }
            }
        }
    }

    // ---- status bar + task drawer -------------------------------------------
    // ui-page-spec §2 StatusBar：尺寸 · 缩放 · 鼠标坐标 · 任务摘要；
    // Phase 5 增接 documentVersion（vN）。
    AppStatusBar {
        id: pageStatusBar

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom

        leftText: {
            if (canvas.imageSize.isEmpty)
                return qsTr("未打开图像");
            let text = canvas.imageSize.width + "×" + canvas.imageSize.height;
            if (page.hasDocument)
                text += " · v" + DocumentService.currentVersion;
            return text + " · " + qsTr("鼠标") + " "
                   + Math.max(0, Math.floor(canvas.mousePosition.x)) + ","
                   + Math.max(0, Math.floor(canvas.mousePosition.y));
        }

        AppButton {
            kind: AppButton.Kind.Ghost
            size: AppButton.Size.Small
            text: taskSummary.activeTasks > 0
                  ? qsTr("任务 · %1 进行中").arg(taskSummary.activeTasks)
                  : qsTr("任务")
            onClicked: taskDrawer.expanded = !taskDrawer.expanded
        }
    }

    // Phase 4 TaskQueuePanel 复用：摘要按钮展开/收起，停靠在页面状态栏之上。
    AppTaskQueuePanel {
        id: taskDrawer

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: pageStatusBar.top
        z: 1
        visible: expanded
        model: Application.taskModel
    }

    // 任务摘要计数：TaskModel 没有 active 计数属性，用隐藏 Repeater 探测每行
    // taskStatus（roleNames 见 native/models/task_model.cpp:178-183）聚合。
    Item {
        id: taskProbe
        visible: false

        Repeater {
            model: Application.taskModel

            delegate: Item {
                required property string taskStatus

                readonly property bool isActive:
                    taskStatus === "queued" || taskStatus === "running"
                    || taskStatus === "cancelling"

                onIsActiveChanged: taskSummary.recount()
                Component.onCompleted: taskSummary.recount()
            }
        }
    }

    QtObject {
        id: taskSummary

        property int activeTasks: 0

        function recount() {
            let active = 0;
            const rows = taskProbe.children;
            for (let i = 0; i < rows.length; ++i) {
                if (rows[i].isActive === true)
                    active += 1;
            }
            taskSummary.activeTasks = active;
        }
    }

    // ---- history -------------------------------------------------------------
    // HistoryModel 由 DocumentService.historyReady 驱动（history_model.h），
    // 撤销/重做按钮按 canUndo/canRedo 启停。
    HistoryModel {
        id: historyModel
    }

    // ---- dialogs -------------------------------------------------------------
    FileDialog {
        id: openDialog
        title: qsTr("打开图像")
        nameFilters: [
            qsTr("图像文件 (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif)"),
            qsTr("所有文件 (*)")
        ]
        onAccepted: page.openFile(selectedFile)
    }

    FileDialog {
        id: saveDialog
        title: qsTr("保存图像")
        fileMode: FileDialog.SaveFile
        nameFilters: [
            qsTr("图像文件 (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif)"),
            qsTr("所有文件 (*)")
        ]
        onAccepted: {
            // 对话框打开期间在途状态可能变化（模态下通常不可达，兜底防御）：
            // 全分辨率任务在途时保存像素取决于执行时序，不提交。
            if (page.fullResInFlight)
                return;
            if (!page.ensureBackendReady())
                return;
            // Phase 9：FileDialog 是平台对话框，无法内嵌字段——选完文件后经
            // 应用内"保存选项"对话框补目标大小 KB（空=不限）再提交。
            page.openSaveOptions(page.urlToPath(selectedFile));
        }
    }

    // ---- 保存选项（Phase 9）：目标大小 KB → image.save target_kb 透传 -------
    // "空=不限"的落地形态：AppNumberField 无空值（SpinBox 整数内态），以
    // "限制目标大小"开关表达——关=不传 target_kb（不限），开=字段值 KB。
    // 开关关闭时字段禁用，语义与空输入一致。完成 Toast 的实际大小显示待
    // documentSaved 的 fileSize 扩展（未接线时按原样提示，见
    // Connections.onDocumentSaved）。
    AppDialog {
        id: saveOptionsDialog
        title: qsTr("保存选项")
        modal: true

        // 表单状态挂在本体上（AppDialog.content 是 Loader 装载的内嵌
        // Component——其内部 id 不进入本文件的词法作用域，submit/openFor
        // 只读这里；content 里的控件经 onCheckedChanged/onValueChanged
        // 单向同步回来）。
        property string targetPath: ""
        property bool limitSize: false        // false = 不限（"空=不限"的落地形态）
        property int targetKbValue: 1024

        function openFor(path) {
            targetPath = path;
            open();
        }

        function submit() {
            if (targetPath === "" || page.fullResInFlight)
                return;
            close();
            // 第三参数 targetKb 为 saveDocument 的 Phase 9 可选扩展（协议
            // §3.9：>0 时随请求携带 target_kb，Worker 二分 JPEG/WebP quality，
            // 仅对 JPEG/WebP 输出适用——.png 等扩展名由 Worker 提交前同步
            // 拒绝并经 documentError 如实呈现）。"不限"（开关关）传 -1，
            // C++ 侧不携带该字段，请求形状与两参调用一致。
            DocumentService.saveDocument(
                targetPath, -1,
                limitSize ? Math.max(1, Math.round(targetKbValue)) : -1);
        }

        content: ColumnLayout {
            spacing: Theme.spacingMd

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingSm

                Label {
                    text: qsTr("目标文件")
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textSecondary
                }
                Label {
                    Layout.fillWidth: true
                    text: saveOptionsDialog.targetPath
                    font.pixelSize: Theme.fontSizeNumeric
                    color: Theme.textPrimary
                    elide: Text.ElideMiddle
                }
            }

            AppToggleField {
                id: limitToggle
                Layout.fillWidth: true
                text: qsTr("限制目标大小（KB）")
                checked: false
                onCheckedChanged: saveOptionsDialog.limitSize = checked
            }

            AppNumberField {
                id: targetKbField
                Layout.fillWidth: true
                enabled: limitToggle.checked
                from: 1
                to: 1048576
                step: 64
                decimals: 0
                value: 1024
                onValueChanged: saveOptionsDialog.targetKbValue = value
            }

            Label {
                Layout.fillWidth: true
                text: qsTr("不勾选=不限大小（按格式默认质量保存）；对 JPEG/WebP 等有损格式生效")
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textDisabled
                wrapMode: Text.WordWrap
            }
        }

        footer: DialogButtonBox {
            AppButton {
                text: qsTr("取消")
                kind: AppButton.Kind.Ghost
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
            }
            AppButton {
                text: qsTr("保存")
                kind: AppButton.Kind.Primary
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
            }
        }

        onAccepted: saveOptionsDialog.submit()
    }

    // ---- DocumentService wiring ---------------------------------------------
    Connections {
        target: DocumentService

        function onDocumentOpened(documentId, path, width, height) {
            page.openPending = false;
            page.openedDocumentId = documentId;
            page.savedAsPath = "";
            // Phase 9：文档像素尺寸镜像种入（画布 imageSize 是预览文件尺寸，
            // 不是文档尺寸——overlay 的坐标换算依赖本镜像，见文件头）；画布
            // 模式全部退出（换文档即作废在画交互），标注待提交 ops 清空。
            page.documentWidth = width;
            page.documentHeight = height;
            page.pendingDocDims = null;
            page.pendingAnnotateOps = [];
            page.historyRestorePending = false;
            page.refreshPending = false;  // 换文档：旧文档的刷新窗口随之作废
            page.exitCanvasModes();
            // 换文档后，旧文档的在途全分辨率结果已不可能触达任何文档状态
            // （document_service.cpp 按提交时 documentId 丢弃陈旧完成，不发
            // 任何信号），在途标志必须在此显式作废：applyOpened 的版本复位
            // 只在旧 version != 0 时才发射 documentVersionChanged，旧文档尚
            // 在 v0 时若无此清理，fullResInFlight 会永久卡死（latch），门控
            // 的保存/撤销/重做/重置/变换/应用全部失效。
            page.fullResInFlight = false;
            page.applyRequested = false;
            page.transformRequested = false;
            page.annotateRequested = false;
            page.filterApplyRequested = false;
            // 滤镜链是"待提交管线"，随文档切换作废（旧链预览不能打在新文档
            // 上）。replaceFrom([]) → modelReset → AppFilterInspector 汇成
            // chainChanged → 防抖出口被空链门挡下，不产生预览请求。
            FilterService.chainModel.replaceFrom([]);
            // 画布保持本地文件 URL（openFile 已设置）→ 快速显示，不换源；
            // 新文档从中性滑杆开始（进入文档的调整基线），变换页签控件回基准
            // （scale 字段 = 新文档尺寸，rotate_free 回 0）。
            page.resetAdjustSliders();
            page.resetTransformFields();
            DocumentService.requestHistory();
        }

        function onDocumentSaved(path, fileSize) {
            // 另存为后的显示路径。DocumentService.documentPath 不随保存更新
            // （document_service.cpp handleCompleted Save 只清 modified），
            // 页面以 documentSaved 补偿；仅当目标与原路径不同才覆盖。
            if (path !== DocumentService.documentPath)
                page.savedAsPath = path;
            // Phase 9：image.save 完成 result 携带 file_size（协议 §3 表），
            // 但 documentSaved 信号的 fileSize 扩展参数截至本批未接线
            // （document_service.h 只有 path 形参）——fileSize 恒为
            // undefined，按原样提示不谎报大小；原生端补扩展后本分支自动生效。
            if (fileSize !== undefined && fileSize !== null)
                page.showToast(qsTr("已保存：%1（实际大小 %2）")
                               .arg(path).arg(page.formatBytes(fileSize)),
                               AppToast.Type.Success);
            else
                page.showToast(qsTr("已保存：%1").arg(path), AppToast.Type.Success);
        }

        function onDocumentVersionChanged(version) {
            // 全分辨率变更完成：历史随版本刷新（§3.1/§3.3）。
            DocumentService.requestHistory();
            if (page.applyRequested) {
                page.applyRequested = false;
                page.fullResInFlight = false;
                // 已应用的调整进入文档：滑杆回中性基线，避免下一次预览/应用叠加。
                page.resetAdjustSliders();
                page.requestDocumentRefresh();
            } else if (page.transformRequested) {
                page.transformRequested = false;
                page.fullResInFlight = false;
                // Phase 9：确定性几何应用完成 → 文档尺寸镜像按其输出更新
                // （pendingDocDims 为 null（翻转）表示尺寸不变）；变换页签
                // 控件回基准，避免残留参数叠在新像素上。
                if (page.pendingDocDims !== null) {
                    page.documentWidth = page.pendingDocDims.width;
                    page.documentHeight = page.pendingDocDims.height;
                    page.pendingDocDims = null;
                }
                page.resetTransformFields();
                page.requestDocumentRefresh();
            } else if (page.annotateRequested) {
                page.annotateRequested = false;
                page.fullResInFlight = false;
                // 已提交的标注进入文档（Worker 参数化历史条目，撤销走既有
                // undo 的参数化 replay，协议 §3.3）。待提交 ops 清空并退出
                // 标注模式，画布取回最新像素（含标注的全分辨率渲染）。
                page.pendingAnnotateOps = [];
                page.exitCanvasModes();
                page.requestDocumentRefresh();
            } else if (page.filterApplyRequested) {
                page.filterApplyRequested = false;
                page.fullResInFlight = false;
                // 已应用的链进入文档（§3.1：filter.apply version+1 / modified）。
                // 链随之清空：残留链会在下一次预览/应用时把同一链再叠加一遍——
                // 与调整页签"应用后滑杆回中性"同一纪律。清链的 modelReset 汇成
                // chainChanged，防抖出口被空链门挡下；画布取回最新像素走下面的
                // requestDocumentRefresh（与调整/变换同一刷新路径）。
                FilterService.chainModel.replaceFrom([]);
                page.requestDocumentRefresh();
            }
            // undo/redo/reset：画布刷新文件由 DocumentService 经 previewReady 交付（§3.3）。
        }

        function onPreviewReady(result) {
            const path = result.path;
            if (path === undefined || path === "")
                return;
            // 任一预览到达即关闭画布刷新窗口：窗口内提交的预览渲染的都是
            // 当前文档像素（adjust 作用于最新 doc.image），先到先解 k 因子
            // 失配；跨完成边界在途的旧像素预览会提前开门（残余竞态，见
            // refreshPending 属性注，随后到达的刷新预览自愈）。
            page.refreshPending = false;
            if (page.historyRestorePending && result.version !== undefined
                    && result.width !== undefined && result.height !== undefined) {
                // undo/redo/reset 的完成事件（§3.3：携带恢复后的文档尺寸，经
                // previewReady 交付画布刷新文件）——文档像素尺寸镜像据此回准，
                // 撤销/重做几何应用（crop/rotate_free/scale/perspective）后
                // 后续 crop/标注的坐标换算不失准。
                page.historyRestorePending = false;
                page.documentWidth = result.width;
                page.documentHeight = result.height;
                page.resetTransformFields();
            }
            page.previewSeq += 1;
            canvas.source = page.toFileUrl(path) + "?v=" + page.previewSeq;
        }

        function onDocumentError(code, message) {
            // 纯用户呈现（Toast）。错误不携带动作上下文，不得在此解除在途
            // 门控——应用在途时一次无关的预览失败会提前解锁保存/撤销，重新
            // 打开门控要阻止的历史栈竞态窗口；状态机迁移走 onDocumentActionFailed。
            if (page.openPending) {
                // 打开失败 → Toast（ui-page-spec §2 错误态）。文档未切换成功，
                // openedDocumentId 保留原值：在途的全分辨率任务仍属于原文档，
                // onDocumentActionFailed 以 documentId === openedDocumentId 判定
                // 相关性——置空会让"打开失败 + 原文档任务失败"的双失败场景在
                // 在途门控上永久卡死（fullResInFlight 失去唯一解除路径）。
                page.openPending = false;
                if (page.hasDocument)
                    page.requestDocumentRefresh();  // 已有文档：取回其当前像素
                else
                    canvas.source = "";             // 回到空态
                page.showToast(code + " · " + message, AppToast.Type.Error);
                return;
            }
            page.showToast(code + " · " + message, AppToast.Type.Error);
        }

        function onDocumentActionFailed(documentId, action) {
            // 刷新预览自身失败（image.adjust-preview）不会有 previewReady 跟进，
            // 门控必须在此解除（其余失败路径清本旗标无害：旗标语义只是
            // "等下一次预览"，见 refreshPending 属性注）。
            page.refreshPending = false;
            // 只解除"当前文档的全分辨率提交未落定"：
            // - documentId 区分换文档后的旧文档失败（新文档的在途提交不受影响）；
            // - action 白名单区分同文档的预览任务失败（预览不触碰历史栈，提前
            //   解锁会重开竞态窗口）：image.adjust / image.transform 是全分辨率
            //   提交（applyTransform 的 Phase 9 批式变换同样走 image.transform
            //   动作面），image.annotate 是标注全分辨率提交（新动作），
            //   filter.apply 是流程 2 的全分辨率链应用（filter.preview /
            //   filter.apply 本身就是不同动作名，无 "-preview" 后缀，见
            //   document_service.cpp actionId()）。fullResInFlight 只由
            //   apply/transform/applyAnnotateOps/applyFilterChain 置位且按钮
            //   在途时禁用，故这些标签的错误必属在途提交本身。
            if (page.fullResInFlight && documentId === page.openedDocumentId
                    && (action === "image.adjust" || action === "image.transform"
                        || action === "image.annotate" || action === "filter.apply")) {
                page.fullResInFlight = false;
                page.applyRequested = false;
                page.transformRequested = false;
                page.annotateRequested = false;
                page.filterApplyRequested = false;
                page.pendingDocDims = null;  // 输出尺寸没有落地，镜像保持原值
            }
            // 历史/保存类提交失败（UNREDOABLE 同步拒绝、UNKNOWN_DOCUMENT 等）
            // 同样要解除自己的旗标：historyRestorePending 的正常消耗路径只有
            // 撤销/重做/重置完成事件的 previewReady（onPreviewReady），提交未
            // 落定时必须在此显式解除，否则下一次无关预览会被误认（见
            // historyRestorePending 属性注）。
            if (action === "image.undo" || action === "image.redo"
                    || action === "image.reset")
                page.historyRestorePending = false;
        }

        function onHistoryReady(history) {
            historyModel.refreshFrom(history);
        }
    }

    // Worker 进程层错误（启动失败 / 握手超时 / 崩溃）：在途任务全部作废，
    // 不会有任何 task.completed 跟进 —— 按钮必须按真实状态恢复（§6.4）。
    Connections {
        target: Application.backend

        function onErrorOccurred(code, message) {
            page.openPending = false;
            page.fullResInFlight = false;
            page.applyRequested = false;
            page.transformRequested = false;
            page.annotateRequested = false;
            page.filterApplyRequested = false;
            page.pendingDocDims = null;
            page.historyRestorePending = false;  // Worker 层崩溃：不会有完成事件跟进
            page.refreshPending = false;         // 同上：刷新预览永不到达
            page.showToast(code + " · " + message, AppToast.Type.Error);
        }

        function onRunningChanged() {
            // Worker 就绪后补拉一次滤镜目录（流程 2 数据源）：页面打开时若
            // Worker 未就绪，首轮 loadFilters 被跳过（未绑定后端只会发无意义
            // 的 filterError(INTERNAL)）。条件收敛：在途/已加载不重发（幂等）。
            if (Application.backend.running && !FilterService.loadingFilters
                    && FilterService.filterModel.rowCount() === 0)
                FilterService.loadFilters();
        }
    }

    // FilterService 信号 → 用户呈现（Toast）。预设 API 的同步错误经
    // filterError（filter_service.h），预览/应用失败另有 DocumentService 的
    // documentError / documentActionFailed 通道（上方已接）。
    Connections {
        target: FilterService

        function onFilterError(code, message) {
            page.showToast(code + " · " + message, AppToast.Type.Error);
        }

        function onPresetSaved(name) {
            page.showToast(qsTr("预设已保存：%1").arg(name), AppToast.Type.Success);
        }

        function onPresetLoaded(steps) {
            page.showToast(qsTr("预设已载入（%1 步，链已替换）").arg(steps.length),
                           AppToast.Type.Success);
        }

        function onPresetDeleted(name) {
            page.showToast(qsTr("预设已删除：%1").arg(name), AppToast.Type.Success);
        }
    }

    // ---- keyboard shortcuts (docs/user-flows.md 流程 1) ----------------------
    // 与对应按钮同一门控（见顶部工具栏的串行化与 backendReady 说明）；Phase 9
    // 增补画布模式的 !canvasModeActive 门控与 Esc 退出（模式互斥，同一时刻至
    // 多一个 Esc Shortcut 处于启用态）。
    Shortcut {
        sequence: "Ctrl+Z"
        enabled: page.hasDocument && historyModel.canUndo
                 && !page.fullResInFlight && page.backendReady
                 && !page.canvasModeActive
        onActivated: page.requestUndo()
    }
    Shortcut {
        sequence: "Ctrl+Shift+Z"
        enabled: page.hasDocument && historyModel.canRedo
                 && !page.fullResInFlight && page.backendReady
                 && !page.canvasModeActive
        onActivated: page.requestRedo()
    }
    Shortcut {
        sequence: "Ctrl+S"
        enabled: DocumentService.documentModified && !page.fullResInFlight
                 && !page.canvasModeActive
        onActivated: page.openSaveDialog()
    }
    Shortcut {
        sequence: "Ctrl+Shift+S"
        enabled: page.hasDocument && !page.fullResInFlight && !page.canvasModeActive
        onActivated: page.openSaveDialog()
    }
    Shortcut {
        sequence: "Esc"
        enabled: page.compareActive
        onActivated: page.setCompareMode(false)
    }
    Shortcut {
        sequence: "Esc"
        enabled: page.cropActive
        onActivated: page.setCropMode(false)
    }
    Shortcut {
        sequence: "Esc"
        enabled: page.perspectiveActive
        onActivated: page.setPerspectiveMode(false)
    }
    Shortcut {
        sequence: "Esc"
        enabled: page.annotateActive
        onActivated: page.setAnnotateMode(false)
    }

    // ---- preview debounce ----------------------------------------------------
    // 任一滑杆变更 → 300ms 防抖 → adjust(preview=true, max 768)；
    // dragFinished 已在 AppSliderField 内先发 valueModified 再发 dragFinished，
    // 这里 stop() 去重，松手只发一次立即预览。
    Timer {
        id: previewDebounce
        interval: 300
        onTriggered: page.requestPreview()
    }

    // ---- 滤镜链预览防抖（流程 2）--------------------------------------------
    // 链变化（加入/删除/排序/启停/载入预设，AppFilterInspector.chainChanged）与
    // [预览] 按钮共用同一 300ms 防抖 → previewChain(768)（与调整页签同一
    // max_side 口径）；完成结果经 DocumentService.previewReady 走同一画布刷新。
    // 连续变化只发一次（防抖出口 requestChainPreview 内再做空链/就绪门检）。
    Timer {
        id: filterPreviewDebounce
        interval: 300
        onTriggered: page.requestChainPreview()
    }

    // ---- 自由旋转预览防抖（Phase 9 变换页签）---------------------------------
    // 口径与调整页签 previewDebounce 一致：拖动中 300ms 防抖 →
    // applyTransform({rotate_free}, preview=true, 768)；dragFinished 已先发
    // valueModified 再发 dragFinished，这里 stop() 去重，松手立即发一次。
    // 完成结果经 previewReady 走既有画布刷新（预览不递增 version，§3.2）。
    Timer {
        id: transformPreviewDebounce
        interval: 300
        onTriggered: page.requestTransformPreview()
    }
}
