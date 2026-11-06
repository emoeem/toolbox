import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

// Editor workspace (Phase 5): the real single-image workflow of
// docs/user-flows.md 流程 1 over DocumentService — open → adjust (debounced
// preview) → apply → transform → undo/redo/reset → save, per
// docs/ui-page-spec.md §2.
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
// - Apply/transform full-resolution results carry no pixel path (§3.2), so
//   the post-completion canvas refresh requests one preview of the *current*
//   pixels via a fully-neutral adjustments object: the Worker skips
//   near-default keys (python_worker/adapters/image_adapter.py adjust_chain)
//   and renders the document as-is. undo/redo/reset deliver their restored
//   canvas file through DocumentService.previewReady themselves (§3.3).
// - Applied adjustments bake into the document: after a full-resolution apply
//   the sliders return to neutral (the "已应用状态" baseline of ui-page-spec
//   §2), so the next preview/apply cannot double-apply on top of the result.
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
    property bool fullResInFlight: false        // apply/transform 任务在途
    property bool applyRequested: false         // 本次 version 变更来自"应用"
    property bool transformRequested: false     // 本次 version 变更来自"变换"
    property bool suppressPreview: false        // 程序化写滑杆值时抑制预览请求

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

    function applyAdjustments() {
        if (!page.hasDocument || !page.adjustmentsDirty || !page.ensureBackendReady())
            return;
        page.applyRequested = true;
        page.fullResInFlight = true;
        DocumentService.adjust(page.collectAdjustments(), false, 0);
    }

    function runTransform(op, params) {
        if (!page.hasDocument || !page.ensureBackendReady())
            return;
        page.transformRequested = true;
        page.fullResInFlight = true;
        DocumentService.transform(op, params, false, 0);
    }

    // dragging 期间的重分送（300ms 防抖，见底部 previewDebounce）。
    function requestPreview() {
        if (!page.hasDocument || !page.ensureBackendReady())
            return;
        DocumentService.adjust(page.collectAdjustments(), true, 768);
    }

    // apply/transform 完成后的画布刷新：completed result 无像素路径（§3.2），
    // 以全默认 adjustments 请求一次预览 = 取回最新像素。
    function requestDocumentRefresh() {
        if (!page.hasDocument || !page.ensureBackendReady())
            return;
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
            onClicked: page.openSaveDialog()
        }
        AppButton {
            text: qsTr("另存为")
            enabled: page.hasDocument && !page.fullResInFlight
            onClicked: page.openSaveDialog()
        }

        contentCenter: [
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("↶")
                tooltipText: qsTr("撤销")
                enabled: page.hasDocument && historyModel.canUndo
                         && !page.fullResInFlight && page.backendReady
                onClicked: DocumentService.undo()
            },
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("↷")
                tooltipText: qsTr("重做")
                enabled: page.hasDocument && historyModel.canRedo
                         && !page.fullResInFlight && page.backendReady
                onClicked: DocumentService.redo()
            },
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("重置")
                tooltipText: qsTr("重置到初始状态")
                enabled: page.hasDocument && historyModel.canUndo
                         && !page.fullResInFlight && page.backendReady
                onClicked: DocumentService.reset()
            },

            AppTopToolbar.GroupRule {},

            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("旋转90°")
                tooltipText: qsTr("顺时针旋转 90 度")
                enabled: page.hasDocument && !page.fullResInFlight
                onClicked: page.runTransform("rotate", { angle: 90 })
            },
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("水平翻转")
                tooltipText: qsTr("水平镜像")
                enabled: page.hasDocument && !page.fullResInFlight
                onClicked: page.runTransform("flip_h", {})
            },
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("垂直翻转")
                tooltipText: qsTr("垂直镜像")
                enabled: page.hasDocument && !page.fullResInFlight
                onClicked: page.runTransform("flip_v", {})
            }
        ]

        contentRight: [
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("−")
                tooltipText: qsTr("缩小")
                enabled: page.hasDocument
                onClicked: canvas.zoomBy(1 / 1.25)
            },
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("+")
                tooltipText: qsTr("放大")
                enabled: page.hasDocument
                onClicked: canvas.zoomBy(1.25)
            },
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("适配")
                tooltipText: qsTr("适配窗口")
                enabled: page.hasDocument
                onClicked: canvas.fitToWindow()
            },
            AppToolButton {
                display: AbstractButton.TextOnly
                text: qsTr("100%")
                tooltipText: qsTr("实际大小")
                enabled: page.hasDocument
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

            // Toast host: autoPosition docks to this area's bottom-right.
            AppToast {
                id: toast
            }
        }

        AppInspectorPanel {
            id: inspector

            Layout.fillHeight: true
            visible: page.hasDocument   // 空态：检查器隐藏（ui-page-spec §2）
            tabs: [{ id: "adjust", title: qsTr("调整") }]
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

            // 调整页签（ui-page-spec §2）：滑杆 + 数值输入双向绑定；
            // 中性默认值与 Worker _ADJUST_STEPS 一致（gamma 1.0，其余 0.0）。
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
            DocumentService.saveDocument(page.urlToPath(selectedFile));
        }
    }

    // ---- DocumentService wiring ---------------------------------------------
    Connections {
        target: DocumentService

        function onDocumentOpened(documentId, path, width, height) {
            page.openPending = false;
            page.openedDocumentId = documentId;
            page.savedAsPath = "";
            // 换文档后，旧文档的在途全分辨率结果已不可能触达任何文档状态
            // （document_service.cpp 按提交时 documentId 丢弃陈旧完成，不发
            // 任何信号），在途标志必须在此显式作废：applyOpened 的版本复位
            // 只在旧 version != 0 时才发射 documentVersionChanged，旧文档尚
            // 在 v0 时若无此清理，fullResInFlight 会永久卡死（latch），门控
            // 的保存/撤销/重做/重置/变换/应用全部失效。
            page.fullResInFlight = false;
            page.applyRequested = false;
            page.transformRequested = false;
            // 画布保持本地文件 URL（openFile 已设置）→ 快速显示，不换源；
            // 新文档从中性滑杆开始（进入文档的调整基线）。
            page.resetAdjustSliders();
            DocumentService.requestHistory();
        }

        function onDocumentSaved(path) {
            // 另存为后的显示路径。DocumentService.documentPath 不随保存更新
            // （document_service.cpp handleCompleted Save 只清 modified），
            // 页面以 documentSaved 补偿；仅当目标与原路径不同才覆盖。
            if (path !== DocumentService.documentPath)
                page.savedAsPath = path;
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
                page.requestDocumentRefresh();
            }
            // undo/redo/reset：画布刷新文件由 DocumentService 经 previewReady 交付（§3.3）。
        }

        function onPreviewReady(result) {
            const path = result.path;
            if (path === undefined || path === "")
                return;
            page.previewSeq += 1;
            canvas.source = page.toFileUrl(path) + "?v=" + page.previewSeq;
        }

        function onDocumentError(code, message) {
            // 纯用户呈现（Toast）。错误不携带动作上下文，不得在此解除在途
            // 门控——应用在途时一次无关的预览失败会提前解锁保存/撤销，重新
            // 打开门控要阻止的历史栈竞态窗口；状态机迁移走 onDocumentActionFailed。
            if (page.openPending) {
                // 打开失败 → 空态 + Toast（ui-page-spec §2 错误态）。
                page.openPending = false;
                page.openedDocumentId = "";
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
            // 只解除"当前文档的全分辨率 adjust/transform 未落定"：
            // - documentId 区分换文档后的旧文档失败（新文档的在途提交不受影响）；
            // - action 不含 "-preview" 后缀，区分同文档的预览任务失败（预览
            //   不触碰历史栈，提前解锁会重开竞态窗口）。fullResInFlight 只由
            //   apply/transform 置位且按钮在途时禁用，故这两个标签的错误必属
            //   在途提交本身。
            if (page.fullResInFlight && documentId === page.openedDocumentId
                    && (action === "image.adjust" || action === "image.transform")) {
                page.fullResInFlight = false;
                page.applyRequested = false;
                page.transformRequested = false;
            }
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
            page.showToast(code + " · " + message, AppToast.Type.Error);
        }
    }

    // ---- keyboard shortcuts (docs/user-flows.md 流程 1) ----------------------
    // 与对应按钮同一门控（见顶部工具栏的串行化与 backendReady 说明）。
    Shortcut {
        sequence: "Ctrl+Z"
        enabled: page.hasDocument && historyModel.canUndo
                 && !page.fullResInFlight && page.backendReady
        onActivated: DocumentService.undo()
    }
    Shortcut {
        sequence: "Ctrl+Shift+Z"
        enabled: page.hasDocument && historyModel.canRedo
                 && !page.fullResInFlight && page.backendReady
        onActivated: DocumentService.redo()
    }
    Shortcut {
        sequence: "Ctrl+S"
        enabled: DocumentService.documentModified && !page.fullResInFlight
        onActivated: page.openSaveDialog()
    }
    Shortcut {
        sequence: "Ctrl+Shift+S"
        enabled: page.hasDocument && !page.fullResInFlight
        onActivated: page.openSaveDialog()
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
}
