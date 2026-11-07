import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQml.Models

// 批量处理向导（ui-page-spec.md §3 BatchPage 的工作流组件，总纲 §13 Phase 6
// 第 7 项 Batch Processing 的 UI 侧）。宿主是 ui/pages/BatchPage.qml（产品
// 信息架构 §1/§2 的一级导航"批量"入口）；本组件自足：直接读写 BatchService /
// FilterService 单例与 Application.backend，页面无需转发。
//
// 数据源与实际 C++ 契约（native/services/batch_service.h、native/models/
// batch_model.h，QML 层不 sendAction，全部经服务 Q_INVOKABLE）：
// - startBatch(...) 同步返回提交关联号 request_id（空 = 本地拒绝，恰一次
//   batchError）；真实 task_id 异步经 batchStarted(taskId) 交付。本组件把
//   返回值存为 batchRef 作为取消句柄，batchStarted 后替换为 task_id——
//   cancelBatch 两种令牌都接受（batch_service.cpp:88-96 受理后翻译）。
// - 批次终态：batchFinished（成功收口）/ batchError（提交拒绝、task.failed，
//   取消以 CANCELLED 呈现）。计数属性 totalCount/doneCount/failedCount 经
//   batchSummaryChanged 通知，行状态词汇为 pending|running|done|failed|
//   skipped（取消/中断的残余行归 skipped，不计入 failed）。
// - 滤镜链 steps 形状与 filter.preview/apply 一致（{filter_key, params,
//   enabled}），空数组 = 纯格式转换（协议 §3.5）。
//
// 滤镜链预设的选择路径（FilterService.presetsList() 枚举 + loadPreset 取
// steps）：loadPreset 的既定副作用是把 steps 写入全局 FilterChainModel（编辑
// 页签的"待提交管线"）。批量页与编辑页分属不同 Loader 实例，直接载入会把批
// 量选中的预设静默替换进编辑器的链——故向导在 loadPreset 前用 Instantiator
// 探针快照链的当前行（EditorPage.qml:709-743 taskProbe 的行探测同款手法），
// presetLoaded 捕获 steps 后立即 replaceFrom 还原；载入失败/页面卸载同样还原。
//
// 非模态语义（任务要求）：批处理是 C++ 单例上的后台任务，导航离开不中断、
// 不阻塞其他页面；运行中本页仅禁用配置编辑（ui-page-spec §3），允许取消。
// 完成提示在向导存续期间经 AppToast 呈现；离开页面后本期没有全局 Toast 宿主
// （Main.qml 的状态栏/任务抽屉走 TaskModel，而 BatchService 未登记 TaskModel
// 行）——该限制如实记录于任务 notes，非本组件可解。
//
// 恢复语义（诚实原则）：向导是页面实例组件，重进页面后 cancel 句柄已失
// （BatchService 不暴露活动 task_id 查询，SettingsService 无通用写通道，不
// 伪造持久化）。重进时若模型仍有行：按"审查态"呈现最后已知行，并在计数未
// 收敛时提示"可能仍在后台运行或已中断"；此时 [开始] 保持可用——单活动批次
// 语义下重新受理会替换旧跟踪（batch_service.h:35-37），不产生双批次。
Item {
    id: root

    enum Phase { Editing, Running, Settled, Interrupted }

    // ---- 批次状态 -----------------------------------------------------------
    property int phase: AppBatchWizard.Phase.Editing
    property string batchRef: ""          // 取消句柄：request_id → 受理后为 task_id
    property bool cancelRequested: false  // 取消已点、CANCELLED 事件未回的窗口

    // 待处理文件清单（本地路径）。目录条目原样上送，由 Worker 递归展开并按
    // SUPPORTED_READ 过滤（协议 §3.5），UI 不做扩展名判定。
    property var pendingFiles: []         // [{path, dir}]

    property string outputDir: ""

    // 输出格式/命名（协议 §3.5 词汇）。值数组与显示数组按同下标配对。
    readonly property var formatValues: ["png", "jpeg", "webp", "bmp", "tiff"]
    readonly property var namingValues: ["keep", "suffix", "pattern"]
    readonly property string formatValue:
        formatValues[Math.max(0, formatSelector.currentIndex)]
    readonly property string namingValue:
        namingValues[Math.max(0, namingSelector.currentIndex)]
    // 质量仅对有损格式有意义（协议 §3.5：JPEG/WebP 92 缺省，无损不适用）；
    // 无损格式下控件禁用，但值仍随提交上送（协议只在 1-100 内校验，无害）。
    readonly property bool qualityRelevant:
        root.formatValue === "jpeg" || root.formatValue === "webp"

    // ---- 批次模型派生（BatchModel 计数走 batchSummaryChanged 通知）-----------
    readonly property bool backendReady: Application.backend.running
    readonly property int batchTotal: BatchService.batchModel.totalCount
    readonly property int batchDone: BatchService.batchModel.doneCount
    readonly property int batchFailed: BatchService.batchModel.failedCount
    readonly property int batchSkipped:
        Math.max(0, root.batchTotal - root.batchDone - root.batchFailed)

    // ---- 滤镜链（预设选择）---------------------------------------------------
    property var presetNames: []          // presetsList() 缓存的 name 列表
    readonly property var presetOptions:
        [qsTr("跳过（纯格式转换）")].concat(root.presetNames)
    property string selectedPreset: ""    // "" = 跳过（纯格式转换）
    property var chainSteps: []           // 提交给 startBatch 的 steps
    property bool chainLoadPending: false
    property var chainSnapshot: null      // loadPreset 前的编辑器链快照

    readonly property bool configLocked: root.phase === AppBatchWizard.Phase.Running
    // naming=pattern 时 pattern 必填（协议 §3.5，空 → 同步 INVALID_PARAMS），
    // 提交门在 UI 侧先行拦截。
    readonly property bool patternValid:
        root.namingValue !== "pattern" || patternField.text.trim() !== ""

    Component.onCompleted: {
        // 两个服务都要求 QML 侧 bindBackend（幂等，EditorPage.qml:83-90 同款）：
        // 批量页可能先于编辑页被打开。
        BatchService.bindBackend(Application.backend)
        FilterService.bindBackend(Application.backend)
        if (root.backendReady)
            FilterService.presetsList()
        // 恢复：模型仍有行 = 存在上一批次的最后已知状态。不猜它是否仍在运行
        // （信号是单次的，重进后无从补听 batchStarted），按审查态呈现；若批次
        // 仍在跑，batchFinished/batchError 会在此后到达并正常收口。
        if (root.batchTotal > 0)
            root.phase = AppBatchWizard.Phase.Settled
    }

    // 载入预设在途时页面卸载：把编辑器链还原，避免留下批量页选中的预设。
    Component.onDestruction: {
        if (root.chainLoadPending)
            root.restoreChainSnapshot()
    }

    // ---- helpers -------------------------------------------------------------
    // 与 EditorPage.qml:98-132 同款纯 JS 工具（组件间无共享 JS 模块，各文件
    // 自含；如后续抽公共 util 应两处同步）。
    function fileNameOf(path) {
        const normalized = String(path).replace(/\\/g, "/");
        return normalized.substring(normalized.lastIndexOf("/") + 1);
    }

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

    // Worker 未就绪的诚实入口（EditorPage.qml:144-150 同款）：请求会被
    // PythonWorker::sendLine 静默丢弃，先明说，绝不假装已受理。
    function ensureBackendReady() {
        if (root.backendReady)
            return true;
        root.showToast(qsTr("后端未就绪（%1）：请先到设置页启动 Worker")
                       .arg(Application.backend.state), AppToast.Type.Warning);
        return false;
    }

    function stateLabel(state) {
        switch (state) {
        case "pending": return qsTr("待处理");
        case "running": return qsTr("处理中");
        case "done": return qsTr("已完成");
        case "failed": return qsTr("失败");
        case "skipped": return qsTr("已跳过");
        default: return state;  // 未知状态原样显示（AppTaskItem 同款兜底）
        }
    }

    function stateColor(state) {
        switch (state) {
        case "running": return Theme.accent;
        case "done": return Theme.success;
        case "failed": return Theme.error;
        case "skipped": return Theme.textDisabled;
        case "pending": return Theme.textSecondary;
        default: return Theme.textSecondary;
        }
    }

    // AppToast.copyDetails 同款剪贴板写入（隐藏 TextArea 选区复制）。
    function copyToClipboard(text) {
        clipboardHelper.text = text;
        clipboardHelper.selectAll();
        clipboardHelper.copy();
    }

    // ---- 文件/目录添加 --------------------------------------------------------
    function appendPaths(urlList, isDir) {
        const next = root.pendingFiles.slice();
        let added = 0;
        for (let i = 0; i < urlList.length; ++i) {
            const path = root.urlToPath(urlList[i]);
            if (path === "")
                continue;
            let duplicate = false;
            for (let j = 0; j < next.length; ++j) {
                if (next[j].path === path) {
                    duplicate = true;
                    break;
                }
            }
            if (!duplicate) {
                next.push({ path: path, dir: isDir === true });
                added += 1;
            }
        }
        if (added === 0)
            return;
        root.pendingFiles = next;
        root.enterEditing();
        root.showToast(qsTr("已添加 %1 项").arg(added), AppToast.Type.Info);
    }

    function removePending(index) {
        if (index < 0 || index >= root.pendingFiles.length)
            return;
        const next = root.pendingFiles.slice();
        next.splice(index, 1);
        root.pendingFiles = next;
    }

    // 终态 → 编辑态（添加/移除文件时）：清掉上一批次的行（BatchModel.clear
    // 是公开 Q_INVOKABLE；受理本身也会整表重建，这里是让审查视图不残留）。
    function enterEditing() {
        if (root.phase === AppBatchWizard.Phase.Running)
            return;  // 运行中不接受编辑（添加按钮已禁用；防御）
        root.batchRef = "";
        root.cancelRequested = false;
        if (root.phase !== AppBatchWizard.Phase.Editing) {
            root.phase = AppBatchWizard.Phase.Editing;
            BatchService.batchModel.clear();
        }
    }

    // ---- 提交 / 取消 -----------------------------------------------------------
    function submitBatch() {
        if (root.phase === AppBatchWizard.Phase.Running)
            return;
        // [开始] 的 enabled 已含这些门；防御性复述（服务端本地拒绝会发
        // batchError，这里避免明知无效仍上送）。
        if (root.pendingFiles.length === 0 || root.outputDir === ""
                || root.chainLoadPending || !root.patternValid)
            return;
        if (!root.ensureBackendReady())
            return;
        const paths = root.pendingFiles.map(function (entry) { return entry.path; });
        // naming=pattern 时 pattern 必填；keep/suffix 的输出名语义在 Worker
        // 侧固定（{源文件名} / {源文件名}_batch），不传自定义值。
        const pattern = root.namingValue === "pattern" ? patternField.text.trim() : "";
        const requestId = BatchService.startBatch(
            paths, root.outputDir, root.formatValue,
            Math.round(qualitySlider.value), root.namingValue, pattern,
            root.chainSteps);
        if (requestId === "")
            return;  // 本地拒绝：batchError 恰好一次（onBatchError 呈现），不出运行态
        root.cancelRequested = false;
        root.batchRef = requestId;   // 受理后经 batchStarted 替换为 task_id
        root.phase = AppBatchWizard.Phase.Running;
    }

    function cancelBatch() {
        if (root.phase !== AppBatchWizard.Phase.Running || root.batchRef === ""
                || root.cancelRequested)
            return;
        root.cancelRequested = true;
        // 行状态不在本地翻转：由 CANCELLED task.failed 统一驱动
        // （batch_service.cpp:152-161；残余行归 skipped）。
        BatchService.cancelBatch(root.batchRef);
    }

    // ---- 滤镜链预设（快照 → 载入 → 还原，见文件头）----------------------------
    function rebuildPresetModel() {
        const cached = FilterService.presetsList();
        const names = [];
        for (let i = 0; i < cached.length; ++i)
            names.push(String(cached[i].name));
        root.presetNames = names;
        // 缓存刷新后按名字恢复选中；预设已被删除则如实回落到"跳过"并清链。
        if (root.selectedPreset !== "" && names.indexOf(root.selectedPreset) < 0) {
            root.selectedPreset = "";
            root.chainSteps = [];
        }
        presetSelector.currentIndex =
            root.selectedPreset === "" ? 0 : names.indexOf(root.selectedPreset) + 1;
    }

    function snapshotChainSteps() {
        const count = FilterService.chainModel.stepCount;
        const steps = [];
        for (let i = 0; i < count; ++i) {
            const row = chainProbe.objectAt(i);
            if (!row)
                return null;  // 探针未与模型同步：无法安全还原，放弃快照
            steps.push({
                filter_key: row.chainFilterKey,
                params: row.chainParams,
                enabled: row.chainEnabled
            });
        }
        return steps;
    }

    function restoreChainSnapshot() {
        if (root.chainSnapshot === null)
            return;
        // 快照失败（null）时不还原：链保留 loadPreset 的结果（服务的既定
        // "链已替换"语义），绝不能把编辑器链误清为空。
        FilterService.chainModel.replaceFrom(root.chainSnapshot);
        root.chainSnapshot = null;
    }

    function beginPresetLoad(name) {
        if (root.chainLoadPending)
            return;
        root.chainSnapshot = root.snapshotChainSteps();
        root.chainLoadPending = true;
        // fire-and-forget：steps 经 onPresetLoaded 交付；失败经 onFilterError。
        FilterService.loadPreset(name);
    }

    // ---- 布局 -----------------------------------------------------------------
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        AppPanelHeader {
            Layout.fillWidth: true
            title: qsTr("批量处理")

            AppButton {
                text: qsTr("添加文件")
                enabled: !root.configLocked
                onClicked: fileDialog.open()
            }
            AppButton {
                text: qsTr("添加目录")
                enabled: !root.configLocked
                onClicked: folderDialog.open()
            }
        }

        // Worker 不可用降级横幅（EditorPage.qml:487-507 同款；ui-page-spec §6
        // 无后端态）：配置与添加不受影响，仅提交被 ensureBackendReady 拦下。
        Rectangle {
            Layout.fillWidth: true
            Layout.margins: Theme.spacingMd
            implicitHeight: bannerLabel.implicitHeight + Theme.spacingSm * 2
            radius: Theme.radiusSm
            color: "transparent"
            border.color: Theme.warning
            border.width: 1
            visible: !root.backendReady

            Label {
                id: bannerLabel
                anchors.fill: parent
                anchors.margins: Theme.spacingSm
                text: qsTr("Worker 未就绪（%1）——无法开始批处理；添加文件与配置不受影响")
                      .arg(Application.backend.state)
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.warning
                wrapMode: Text.WordWrap
                verticalAlignment: Text.AlignVCenter
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: Theme.spacingMd
            spacing: Theme.spacingLg

            // ---- 任务表（左，填充）--------------------------------------------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Theme.spacingSm

                // 表头：与批次行的 文件(fill) / 状态(64) / 进度(140) 对齐。
                RowLayout {
                    Layout.fillWidth: true
                    visible: root.phase !== AppBatchWizard.Phase.Editing
                    spacing: Theme.spacingSm

                    Label {
                        Layout.fillWidth: true
                        text: qsTr("文件")
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textSecondary
                    }
                    Label {
                        Layout.preferredWidth: 64
                        text: qsTr("状态")
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textSecondary
                    }
                    Label {
                        Layout.preferredWidth: 140
                        text: qsTr("进度")
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textSecondary
                    }
                }

                Label {
                    Layout.fillWidth: true
                    text: root.phase === AppBatchWizard.Phase.Editing
                          ? qsTr("待处理清单 · %1 项").arg(root.pendingFiles.length)
                          : qsTr("批次明细 · %1 项").arg(root.batchTotal)
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textSecondary
                }

                // 恢复态的诚实提示（见文件头"恢复语义"）：计数未收敛 = 可能
                // 仍在后台运行，也可能已中断；两种情形都无取消句柄。
                Label {
                    Layout.fillWidth: true
                    text: qsTr("上一次批处理可能仍在后台运行或已中断；此页没有取消句柄，重新开始将替换它（单活动批次）")
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.warning
                    wrapMode: Text.WordWrap
                    visible: root.phase === AppBatchWizard.Phase.Settled
                             && root.batchTotal > 0
                             && root.batchDone + root.batchFailed < root.batchTotal
                }

                // 中断态的持久提示：Toast 5 秒即逝，这里留下原因可回看的行文。
                Label {
                    Layout.fillWidth: true
                    text: qsTr("上次批处理未完成（提交被拒绝或任务失败）——下方行为中断时的最后已知状态；可重新开始")
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.warning
                    wrapMode: Text.WordWrap
                    visible: root.phase === AppBatchWizard.Phase.Interrupted
                }

                // 编辑态：待处理清单（本地状态，行可移除）。
                ListView {
                    id: pendingList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: Theme.spacingXs
                    visible: root.phase === AppBatchWizard.Phase.Editing
                    model: root.pendingFiles

                    delegate: Rectangle {
                        required property var modelData
                        required property int index

                        width: pendingList.width
                        height: pendingRow.implicitHeight + Theme.spacingSm * 2
                        radius: Theme.radiusSm
                        color: Theme.surface

                        RowLayout {
                            id: pendingRow
                            anchors.fill: parent
                            anchors.margins: Theme.spacingSm
                            spacing: Theme.spacingSm

                            Rectangle {
                                width: 8
                                height: 8
                                radius: Theme.radiusSm
                                color: Theme.textSecondary  // 未提交：待处理色点
                                Layout.alignment: Qt.AlignVCenter
                            }

                            Label {
                                Layout.fillWidth: true
                                text: modelData.dir
                                      ? qsTr("[目录] %1（递归扫描）").arg(root.fileNameOf(modelData.path))
                                      : root.fileNameOf(modelData.path)
                                font.pixelSize: Theme.fontSizeBody
                                color: Theme.textPrimary
                                elide: Text.ElideMiddle
                            }

                            Label {
                                text: modelData.path
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textDisabled
                                elide: Text.ElideMiddle
                                Layout.maximumWidth: pendingList.width / 3
                                visible: pendingList.width > 560
                            }

                            Label {
                                text: qsTr("待处理")
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textSecondary
                            }

                            AppButton {
                                kind: AppButton.Kind.Ghost
                                size: AppButton.Size.Small
                                text: qsTr("移除")
                                onClicked: root.removePending(index)
                            }
                        }
                    }

                    // 空态（ui-page-spec §6）：不发明样式，居中引导文案。
                    Label {
                        anchors.centerIn: parent
                        width: parent.width - Theme.spacingXl * 2
                        visible: pendingList.count === 0
                        text: qsTr("点击右上角\"添加文件\"或\"添加目录\"开始（目录将按支持格式递归扫描）")
                        font.pixelSize: Theme.fontSizeBody
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                // 运行/审查/中断态：批次行（BatchModel 角色，roleNames 见
                // native/models/batch_model.cpp roleNames）。
                ListView {
                    id: batchList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: Theme.spacingXs
                    visible: root.phase !== AppBatchWizard.Phase.Editing
                    model: BatchService.batchModel

                    delegate: Rectangle {
                        id: batchRow

                        required property string batchFile
                        required property string batchState
                        required property int batchProgress
                        required property string batchError
                        required property string batchOutputPath

                        readonly property bool hasErrorDetail:
                            batchState === "failed" && batchError !== ""
                        property bool errorExpanded: false

                        width: batchList.width
                        height: batchRowColumn.implicitHeight + Theme.spacingSm * 2
                        radius: Theme.radiusSm
                        color: batchHover.hovered ? Theme.surfaceElevated : Theme.surface

                        HoverHandler { id: batchHover }

                        ColumnLayout {
                            id: batchRowColumn
                            anchors.fill: parent
                            anchors.margins: Theme.spacingSm
                            spacing: Theme.spacingXs

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Theme.spacingSm

                                Rectangle {  // 状态色点（页规格 §3：色点 + 文本）
                                    width: 8
                                    height: 8
                                    radius: Theme.radiusSm
                                    color: root.stateColor(batchRow.batchState)
                                    Layout.alignment: Qt.AlignVCenter
                                }

                                Label {
                                    Layout.fillWidth: true
                                    text: root.fileNameOf(batchRow.batchFile)
                                    font.pixelSize: Theme.fontSizeBody
                                    color: Theme.textPrimary
                                    elide: Text.ElideMiddle
                                }

                                Label {
                                    text: root.stateLabel(batchRow.batchState)
                                    font.pixelSize: Theme.fontSizeSmall
                                    color: root.stateColor(batchRow.batchState)
                                    Layout.preferredWidth: 64
                                }

                                RowLayout {
                                    Layout.preferredWidth: 140
                                    spacing: Theme.spacingXs

                                    AppProgressIndicator {
                                        form: AppProgressIndicator.Form.Bar
                                        from: 0
                                        to: 100
                                        value: batchRow.batchProgress
                                        visible: batchRow.batchState === "running"
                                        Layout.fillWidth: true
                                    }
                                    Label {
                                        // running 显示百分比，其余显示占位。
                                        text: batchRow.batchState === "running"
                                              ? Math.max(0, batchRow.batchProgress) + "%"
                                              : "—"
                                        font.pixelSize: Theme.fontSizeSmall
                                        color: Theme.textSecondary
                                        Layout.alignment: Qt.AlignVCenter
                                    }
                                }
                            }

                            // 完成行：输出路径（batch_model.h Entry.outputPath）。
                            Label {
                                Layout.fillWidth: true
                                visible: batchRow.batchState === "done"
                                         && batchRow.batchOutputPath !== ""
                                text: qsTr("输出：%1").arg(batchRow.batchOutputPath)
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textSecondary
                                elide: Text.ElideMiddle
                            }

                            // 失败行：可展开错误详情并可复制（页规格 §3）。
                            RowLayout {
                                Layout.fillWidth: true
                                visible: batchRow.hasErrorDetail && batchRow.errorExpanded
                                spacing: Theme.spacingSm

                                Label {
                                    Layout.fillWidth: true
                                    text: batchRow.batchError
                                    font.pixelSize: Theme.fontSizeSmall
                                    color: Theme.error
                                    wrapMode: Text.WordWrap
                                    textFormat: Text.PlainText
                                }

                                AppButton {
                                    kind: AppButton.Kind.Ghost
                                    size: AppButton.Size.Small
                                    text: qsTr("复制")
                                    onClicked: root.copyToClipboard(batchRow.batchError)
                                }
                            }
                        }

                        // 失败行点击展开（AppTaskItem 同款交互）。
                        TapHandler {
                            enabled: batchRow.hasErrorDetail
                            onTapped: batchRow.errorExpanded = !batchRow.errorExpanded
                        }
                    }

                    Label {
                        anchors.centerIn: parent
                        width: parent.width - Theme.spacingXl * 2
                        visible: batchList.count === 0
                        text: root.phase === AppBatchWizard.Phase.Running
                              ? qsTr("等待 Worker 受理…")
                              : qsTr("暂无批处理记录")
                        font.pixelSize: Theme.fontSizeBody
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }

            // ---- 配置（右，固定宽）---------------------------------------------
            ColumnLayout {
                Layout.preferredWidth: 320
                Layout.fillHeight: true
                spacing: Theme.spacingLg
                enabled: !root.configLocked

                AppSectionGroup {
                    Layout.fillWidth: true
                    title: qsTr("输出设置")

                    ColumnLayout {
                        width: parent.width
                        spacing: Theme.spacingSm

                        FieldCaption {
                            Layout.fillWidth: true
                            text: qsTr("输出目录")
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacingSm

                            AppTextField {
                                Layout.fillWidth: true
                                readOnly: true
                                text: root.outputDir
                                placeholderText: qsTr("未选择输出目录")
                            }
                            AppButton {
                                text: qsTr("浏览")
                                onClicked: outputDirDialog.open()
                            }
                        }

                        FieldCaption {
                            Layout.fillWidth: true
                            text: root.qualityRelevant
                                  ? qsTr("输出格式")
                                  : qsTr("输出格式（质量对 %1 不适用）")
                                    .arg(root.formatValue.toUpperCase())
                        }
                        AppSelectField {
                            id: formatSelector
                            Layout.fillWidth: true
                            currentIndex: 0
                            model: ["PNG", "JPEG", "WebP", "BMP", "TIFF"]
                        }

                        FieldCaption {
                            Layout.fillWidth: true
                            text: qsTr("质量（JPEG/WebP）")
                        }
                        AppSliderField {
                            id: qualitySlider
                            Layout.fillWidth: true
                            label: qsTr("质量")
                            from: 1
                            to: 100
                            step: 1
                            value: 92       // 协议 §3.5 缺省（JPEG/WebP 92）
                            defaultValue: 92
                            suffix: "%"
                            enabled: root.qualityRelevant
                        }

                        FieldCaption {
                            Layout.fillWidth: true
                            text: qsTr("输出命名")
                        }
                        AppSelectField {
                            id: namingSelector
                            Layout.fillWidth: true
                            currentIndex: 0
                            model: [qsTr("保留原文件名"), qsTr("追加后缀 _batch"), qsTr("自定义命名模式")]
                        }

                        // 模式行：仅 naming=pattern 需要（协议 §3.5：pattern
                        // 必填，占位符 {name}/{ext}/{i}）。
                        ColumnLayout {
                            Layout.fillWidth: true
                            visible: root.namingValue === "pattern"
                            spacing: Theme.spacingXs

                            FieldCaption {
                                Layout.fillWidth: true
                                text: qsTr("命名模式")
                            }
                            AppTextField {
                                id: patternField
                                Layout.fillWidth: true
                                text: "{name}{ext}"
                                placeholderText: "{name}{ext}"
                            }
                            Label {
                                Layout.fillWidth: true
                                text: qsTr("可用占位符：{name} 源文件名 · {ext} 输出扩展名 · {i} 三位序号")
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textDisabled
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }

                AppSectionGroup {
                    Layout.fillWidth: true
                    title: qsTr("滤镜链（可选）")

                    ColumnLayout {
                        width: parent.width
                        spacing: Theme.spacingSm

                        FieldCaption {
                            Layout.fillWidth: true
                            text: qsTr("套用预设")
                        }
                        AppSelectField {
                            id: presetSelector
                            Layout.fillWidth: true
                            currentIndex: 0
                            enabled: !root.chainLoadPending
                            model: root.presetOptions

                            onActivated: function (index) {
                                if (index === 0) {
                                    root.selectedPreset = "";
                                    root.chainSteps = [];
                                    return;
                                }
                                const name = root.presetNames[index - 1];
                                if (name === undefined)
                                    return;
                                root.selectedPreset = name;
                                root.beginPresetLoad(name);
                            }
                        }

                        Label {
                            Layout.fillWidth: true
                            text: root.chainLoadPending
                                  ? qsTr("载入预设中…")
                                  : root.selectedPreset === ""
                                    ? qsTr("未套用滤镜链：仅做格式转换")
                                    : qsTr("已选预设：%1（%2 步）")
                                      .arg(root.selectedPreset).arg(root.chainSteps.length)
                            font.pixelSize: Theme.fontSizeSmall
                            color: root.chainLoadPending ? Theme.textSecondary : Theme.textPrimary
                            wrapMode: Text.WordWrap
                        }

                        Label {
                            Layout.fillWidth: true
                            text: qsTr("预设列表与编辑页签共用（FilterService.presetsList）；选择只加入本批次，不改动编辑器当前链")
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textDisabled
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Item { Layout.fillHeight: true }
            }
        }

        // ---- 底部：总进度 + 开始/取消 ------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: bottomBar.implicitHeight + Theme.spacingMd * 2
            color: Theme.surface

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 1
                color: Theme.border
            }

            RowLayout {
                id: bottomBar
                anchors.fill: parent
                anchors.margins: Theme.spacingMd
                anchors.leftMargin: Theme.spacingLg
                anchors.rightMargin: Theme.spacingLg
                spacing: Theme.spacingLg

                AppProgressIndicator {
                    form: AppProgressIndicator.Form.Bar
                    from: 0
                    to: Math.max(1, root.batchTotal)   // 空表时避免 0 区间
                    value: root.batchDone              // 总进度 = doneCount/totalCount
                    visible: root.batchTotal > 0
                    Layout.preferredWidth: 200
                }

                Label {
                    Layout.fillWidth: true
                    text: root.batchTotal === 0 && root.phase === AppBatchWizard.Phase.Editing
                          ? qsTr("尚未开始")
                          : qsTr("完成 %1 / %2 · 失败 %3 · 跳过 %4")
                            .arg(root.batchDone).arg(root.batchTotal)
                            .arg(root.batchFailed).arg(root.batchSkipped)
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textSecondary
                }

                AppButton {
                    kind: AppButton.Kind.Primary
                    text: qsTr("开始")
                    // 运行中禁用；后端就绪在 submitBatch 内再检（Toast 说明）。
                    enabled: root.phase !== AppBatchWizard.Phase.Running
                             && root.pendingFiles.length > 0
                             && root.outputDir !== ""
                             && !root.chainLoadPending
                             && root.patternValid
                    onClicked: root.submitBatch()
                }

                AppButton {
                    kind: AppButton.Kind.Danger
                    text: root.cancelRequested ? qsTr("取消中…") : qsTr("取消")
                    // 仅运行中可取消；受理前（request_id 句柄）也接受——
                    // batchStarted 后若取消意图仍在会被再次转发。
                    enabled: root.phase === AppBatchWizard.Phase.Running
                             && root.batchRef !== ""
                             && !root.cancelRequested
                    onClicked: root.cancelBatch()
                }
            }
        }
    }

    // ---- 弹层与剪贴板 ----------------------------------------------------------
    FileDialog {
        id: fileDialog
        title: qsTr("选择要批处理的图像")
        fileMode: FileDialog.OpenFiles
        nameFilters: [
            qsTr("图像文件 (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif)"),
            qsTr("所有文件 (*)")
        ]
        onAccepted: root.appendPaths(selectedFiles, false)
    }

    // 添加目录与选择输出目录是两个不同语义的对话框（前者入清单、后者只记录
    // 目标），不共用实例。
    FolderDialog {
        id: folderDialog
        title: qsTr("选择目录（递归扫描）")
        onAccepted: root.appendPaths([selectedFolder], true)
    }

    FolderDialog {
        id: outputDirDialog
        title: qsTr("选择输出目录")
        onAccepted: root.outputDir = root.urlToPath(selectedFolder)
    }

    AppToast {
        id: toast
    }

    TextArea {
        id: clipboardHelper
        visible: false
        width: 0
        height: 0
    }

    // ---- 链探针（Instantiator，非视觉委托）-------------------------------------
    // 快照 FilterService.chainModel 当前行，供 loadPreset 后还原（见文件头）。
    Instantiator {
        id: chainProbe
        model: FilterService.chainModel

        delegate: QtObject {
            required property string chainFilterKey
            required property var chainParams
            required property bool chainEnabled
        }
    }

    // ---- 服务接线 --------------------------------------------------------------
    Connections {
        target: BatchService

        function onBatchStarted(taskId) {
            // 受理落地：句柄换成真实 task_id。受理前已点的取消在这里补发，
            // 避免"取消竞态窗口内受理"导致批次照跑（batch_service.cpp:88-96
            // 的翻译只覆盖已受理情形）。
            root.batchRef = taskId;
            if (root.cancelRequested)
                BatchService.cancelBatch(taskId);
        }

        function onBatchFinished(taskId) {
            root.phase = AppBatchWizard.Phase.Settled;
            root.batchRef = "";
            root.cancelRequested = false;
            // 批内单文件失败不中断批次（协议 §3.5）；有失败用 warning，
            // 全部成功用 success。
            if (root.batchFailed > 0)
                root.showToast(qsTr("批处理完成：%1 项，其中失败 %2、跳过 %3")
                               .arg(root.batchTotal).arg(root.batchFailed)
                               .arg(root.batchSkipped), AppToast.Type.Warning);
            else
                root.showToast(qsTr("批处理完成：%1 项全部成功")
                               .arg(root.batchDone), AppToast.Type.Success);
        }

        function onBatchError(code, message) {
            if (root.phase === AppBatchWizard.Phase.Running) {
                if (code === "CANCELLED") {
                    // 残余行已由服务归 skipped；按取消收口而非错误。
                    root.phase = AppBatchWizard.Phase.Settled;
                    root.batchRef = "";
                    root.cancelRequested = false;
                    root.showToast(qsTr("批处理已取消（完成 %1 / %2）")
                                   .arg(root.batchDone).arg(root.batchTotal),
                                   AppToast.Type.Info);
                    return;
                }
                // 非 CANCELLED 失败：行保持最后已知状态
                // （batch_service.cpp onTaskEvent），如实呈现并允许重新开始。
                root.phase = AppBatchWizard.Phase.Interrupted;
                root.batchRef = "";
                root.cancelRequested = false;
            }
            root.showToast(code + " · " + message, AppToast.Type.Error);
        }
    }

    Connections {
        target: FilterService

        function onPresetLoaded(steps) {
            // 只认本向导发起的载入（编辑页签不与本页共存，Loader 互斥）。
            if (!root.chainLoadPending)
                return;
            root.chainLoadPending = false;
            root.chainSteps = steps;
            root.restoreChainSnapshot();
            root.showToast(qsTr("滤镜链已套用：%1（%2 步）")
                           .arg(root.selectedPreset).arg(steps.length),
                           AppToast.Type.Success);
        }

        function onFilterError(code, message) {
            // 预设载入失败（如 FILE_NOT_FOUND）：还原编辑器链后照常呈现。
            if (root.chainLoadPending) {
                root.chainLoadPending = false;
                root.restoreChainSnapshot();
            }
            root.showToast(code + " · " + message, AppToast.Type.Error);
        }

        function onPresetsChanged() {
            root.rebuildPresetModel();
        }
    }

    Connections {
        target: Application.backend

        function onErrorOccurred(code, message) {
            // Worker 进程层错误（启动失败/崩溃）：不会有任何 task.* 事件跟进，
            // 运行态必须如实解除（EditorPage.qml:902-912 同款纪律）。
            if (root.phase === AppBatchWizard.Phase.Running) {
                root.phase = AppBatchWizard.Phase.Interrupted;
                root.batchRef = "";
                root.cancelRequested = false;
            }
            root.showToast(code + " · " + message, AppToast.Type.Error);
        }

        function onRunningChanged() {
            // Worker 就绪后补拉预设缓存（编辑页未开过时本页是唯一拉取方）。
            if (Application.backend.running)
                FilterService.presetsList();
        }
    }

    // ---- 内联小构件 -------------------------------------------------------------
    component FieldCaption: Label {
        font.pixelSize: Theme.fontSizeSmall
        color: Theme.textSecondary
    }
}
