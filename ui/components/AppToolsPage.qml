import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 统一工具页工作流（总纲 §9.9 统一工具页模板：OCR / PDF / 条码 / 媒体 /
// EXIF / 水印 / 归档 / 加密 / Base64 / 校验和 / AI 等低频能力的统一承载；
// IA §1/§2 "文件工具 Files" 一级导航入口）。宿主是 ui/pages/ToolsPage.qml
// （application.cpp navModel "files" 路由至此）；本组件自足：直接读写
// AssistService 单例与 Application（navigate/backend/taskModel），页面无需
// 转发（AppStudioPage/AppBatchWizard 同款分工）。
//
// 数据源与实际 C++ 契约（native/services/assist_service.h、native/models/
// assist_model.cpp roleNames；QML 层不 sendAction，全部经服务 Q_INVOKABLE/
// 信号，FilterService/StudioService 同款纪律）：
// - AssistService.bindBackend(Application.backend) / bindTaskModel(
//   Application.taskModel)：QML 侧接线，幂等（AppStudioPage.qml:91-92 同款
//   纪律）——bindTaskModel 让 async 工具任务进任务抽屉（行名=目录显示名，
//   assist_service.cpp:106-113），行内取消因此可见。
// - AssistService.assistModel：AssistModel 角色 toolKey/toolName/
//   categoryLabel/available/optionalDeps（assist_model.cpp:63-71 逐一核对）
//   ——目录网格委托的 required 属性按此接线；置灰+依赖 Tooltip 复用
//   AppFilterCard（AppStudioPage 对生成器目录的同一手法）。
// - AssistService.loadTools()：目录拉取（assist.list，sync）。页面打开时
//   一次 + Worker 就绪时 rowCount===0 且非在途兜底一次（AppStudioPage.qml:
//   87-95/648-654 同款幂等口径）；loadingTools 属性驱动 Loading 态
//   （FilterService.loadingFilters 同款——本组件不自造加载记账）。
// - AssistService.runTool(toolKey, paramsJson)：运行工具（动作名 = 条目
//   key，assist_service.h 类头协议注记）。paramsJson 为参数"值"对象的 JSON
//   文本，空/纯空白按 {} 上送（无参工具合法）；解析失败/非对象在 C++ 本地
//   拒绝（assistError(INVALID_PARAMS) + 返回空串，不上送）。返回值为提交
//   关联号 request_id（空 = 本地拒绝未上送——assistError 已呈现，本组件
//   只解真实在途，不伪装成功；StudioService.render 同款口径）。
// - AssistService.notifyToolResult(toolKey, resultJson)：结果交付（sync
//   工具响应到达时 / async 工具 task.completed 到达时各一次，resultJson =
//   result 对象紧凑 JSON 文本，工具自有形状原样透传）。
// - AssistService.assistError(code, message)：统一失败呈现通道（未绑定
//   后端、本地/提交前拒绝、sync 拒绝、async task.failed 含 CANCELLED，
//   assist_service.cpp:138-146/186-193）——失败 Toast 归这里，本组件不
//   重复；它同时是单飞在途门的失败解除路径。
//
// 任务书契约差异（如实记录）：任务书写的信号名 toolResult 在落地实现中是
// notifyToolResult；落地契约还提供 bindBackend/bindTaskModel/assistError/
// toolAccepted/loadingTools（比任务书面宽）。本组件按落地实现接线。
//
// resultJson 的消费契约（QML 侧按 assist_adapter.py 的实际 result 形状
// 解析，未知形状落通用 JSON，不猜）：
//   1) {"text": "<字符串>"} → 文本结果（ocr.run assist_adapter.py:467、
//      pdf.extract_text :565、ascii.render :711——ASCII 的 rows/cols 附加键
//      随 text 呈现，不另列）：只读可选中 + [复制文本]；
//   2) {"files": ["<路径>",…]} → 文件/图像列表结果（pdf.split :503、
//      pdf.to_images :629、media.extract_frames :807）：异步缩略图 + 逐张
//      [导出到编辑器]（编辑器可读格式才启用，见 isImagePath——拆分 PDF 的
//      单页 .pdf 与抽帧图共用 files 键，按扩展名如实区分）；
//   3) {"path","width","height","sha256"}（§4 临时 PNG 通道，_deliver_image
//      assist_adapter.py:445-450 → filter_adapter.write_preview :86-104）→
//      单张图像结果：同上呈现与导出；
//   4) 其余（pdf.merge 的 {"path"}、checksum/exif/histogram/barcode.decode/
//      compare/ai.models.list 等）→ 通用 JSON：pretty print + [复制 JSON]。
//      单 path 无 width/height 的结果（watermark/exif.strip/pdf.merge 等）
//      无法按形状区分图像与文档文件，不猜——呈现为通用 JSON。
//   data: 内联结果协议上不存在（§4 禁 Base64 大图，Worker 也不发送），仅作
//   显示层防御支持；其导出如实禁用。
//
// 参数面板（任务书"按工具定义的 paramsJson"的落地现状）：assist.list 条目
// 与 AssistModel 角色面均不含参数定义（assist_adapter.py list_tools :327-346
// 的条目形状为证），工具参数校验权在 Worker 各动作（提交前 INVALID_PARAMS
// 带 key 级消息）。因此参数面板为通用 JSON 编辑器（合法 JSON 对象才提交，
// 本地内联报错、不上送、不弹 Toast——与 assistError 呈现通道不重复）；
// 按工具定义驱动 AppFilterParameterGroup（float/int/bool/enum/color/string
// 自动控件）的形态待参数定义进目录协议后即插即用。
//
// 导出到编辑器：复用既有 StudioService.exportToEditor（studio_service.h:107
// → DocumentService::openDocument），随后跳转 editor 页（IA §2：产物发送到
// 编辑器继续处理）。工具页不自建第二导出通道、不直接触碰 DocumentService
// （AppStudioPage 同款纪律）；非图像文件导出被文档层拒绝时经其自有错误通道
// 呈现。
//
// 在途门控（单飞 + 诚实自愈）：同一时刻至多一次在途运行（结果面板单一，
// 串行保证面板内容与最近一次提交一致）。解除路径：notifyToolResult（sync
// 直答 / async completed）、assistError（task.failed 含 CANCELLED）、后端层
// errorOccurred（进程崩溃不会有任何帧跟进，§6.4）与 120s 看门狗（契约无
// "在途取消/超时"专用事件，帧丢失时唯一自愈路径——宁可重复运行，不可无
// 信号焊死；AppStudioPage renderWatchdog 同款）。加载目录的在途标志由服务
// 持有（loadingTools）；Worker 崩溃可能把它留在途且无响应可收——与
// loadingFilters 同一残余风险（AppFilterInspector.qml:198-202 头注口径），
// 此时 backendReady 已翻转、页面整体落 BackendDown 态。
Item {
    id: root

    enum ResultKind { None, Text, Images, Json }

    // ---- 状态 -----------------------------------------------------------------
    readonly property bool backendReady: Application.backend.running

    // 选中工具快照（目录委托点击/认领时复制）。AssistModel 契约只有角色
    // 通道（无 get()），目录 modelReset 时统一清空、由重建的委托重新认领
    // （AppStudioPage 生成器快照同款）。
    property string selectedKey: ""
    property string selectedName: ""
    property string selectedCategory: ""
    property bool selectedAvailable: false

    // 参数 JSON 文本（工具"值"对象；换工具时清空——不同工具参数形状不同，
    // 不跨工具携带陈旧参数）。写入方向单一：paramsEditor.onTextChanged →
    // paramsText；清空经 clearParams() 写回编辑器（不双向绑定，防绑定环）。
    property string paramsText: ""

    // 参数编辑器的本地 JSON 校验：合法 JSON 对象才可运行（内联报错、不弹
    // Toast——提交后的拒绝呈现归 assistError，本地不再重复一份）。空/纯
    // 空白按无参提交（runTool 按 {} 上送，assist_service.cpp:92-93）。
    readonly property bool paramsValid: {
        const text = root.paramsText.trim();
        if (text === "")
            return true;
        try {
            const parsed = JSON.parse(text);
            return parsed !== null && typeof parsed === "object" && !Array.isArray(parsed);
        } catch (e) {
            return false;
        }
    }

    // 运行在途（单飞）与结果状态。
    property bool runInFlight: false
    property string activeRunToolKey: ""
    property string resultToolKey: ""
    property string resultName: ""     // 展示名：当前选中工具的结果用其名，其余用 key
    property int resultKind: AppToolsPage.ResultKind.None
    property string resultText: ""     // 文本结果 / 通用 JSON 的展示文本
    property var resultImages: []      // 图像/文件结果路径数组（string）
    property int resultSeq: 0          // ?v= 递增：同路径结果文件强制重载

    Component.onCompleted: {
        // 服务接线（AppStudioPage.qml:91-92 同款纪律）：bindBackend 接 Worker
        // 帧，bindTaskModel 让 async 工具任务进任务抽屉。两个绑定都幂等。
        AssistService.bindBackend(Application.backend)
        AssistService.bindTaskModel(Application.taskModel)
        if (root.backendReady)
            root.loadCatalog()
    }

    // ---- helpers --------------------------------------------------------------
    // 本地路径 → file:// URL（AppStudioPage.qml:101-107 同款纯函数，逐段
    // encodeURIComponent；工具函数的跨页抽取是重构，不在本批文件清单内，
    // 先就地复制并注明出处）。
    function toFileUrl(path) {
        const segments = String(path).replace(/\\/g, "/").split("/");
        let encoded = "";
        for (let i = 0; i < segments.length; ++i)
            encoded += (i > 0 ? "/" : "") + encodeURIComponent(segments[i]);
        return encoded.charAt(0) === "/" ? "file://" + encoded : "file:///" + encoded;
    }

    function fileNameOf(path) {
        const normalized = String(path).replace(/\\/g, "/");
        return normalized.substring(normalized.lastIndexOf("/") + 1);
    }

    function showToast(message, toastType) {
        toast.type = toastType;
        toast.text = message;
        if (toast.visible)
            toast.close();
        toast.open();
    }

    // 纯 QML 剪贴板写入（AppToast.qml:64-67 / AppBatchWizard.qml:179-181
    // 同款隐藏 TextArea 手法——QML 无 Clipboard API）。
    function copyText(text) {
        clipboardHelper.text = String(text);
        clipboardHelper.selectAll();
        clipboardHelper.copy();
    }

    // 编辑器可读图像格式（EditorPage 保存对话框 nameFilters 的读取集合口径）。
    // files 键的结果混含拆分 PDF 的 .pdf 与抽帧图——按扩展名如实区分，
    // 非图像的导出按钮禁用，不发起注定失败的文档打开。
    function isImagePath(path) {
        const name = root.fileNameOf(path).toLowerCase();
        return /\.(png|jpe?g|webp|bmp|tiff?)$/.test(name);
    }

    function isInlineSource(path) {
        return String(path).indexOf("data:") === 0;
    }

    // 等宽字体族解析（SettingsPage.qml:102-103 同款调用；JSON 展示用）。
    function monoFamily() {
        return FontService.resolveFamily(SettingsService.monoFontFamily,
                                         FontService.monoCandidates());
    }

    // ---- 目录 -----------------------------------------------------------------
    function loadCatalog() {
        if (!root.backendReady || AssistService.loadingTools)
            return;
        AssistService.loadTools();
    }

    // ---- 选择 -----------------------------------------------------------------
    // 清空参数编辑器（写入经编辑器 → onTextChanged → paramsText，单向）。
    function clearParams() {
        paramsEditor.text = "";
    }

    function selectTool(key, name, category, available) {
        if (root.selectedKey === key)
            return;  // 重复点击同一卡片不重置面板
        root.selectedKey = key;
        root.selectedName = name;
        root.selectedCategory = category;
        root.selectedAvailable = available;
        root.clearParams();
    }

    // 目录委托创建/可用性变化时的认领：无选中时首个可用项自动入选（模型序，
    // AppStudioPage.claimSelection 同款——Ready 态之外委托可能尚未创建，
    // 认领时机随可见性自动补齐）。
    function claimSelection(row) {
        if (root.selectedKey !== "" || !row.available)
            return;
        root.selectTool(row.toolKey, row.toolName, row.categoryLabel, row.available);
    }

    // ---- 运行 -----------------------------------------------------------------
    function runSelected() {
        if (!root.backendReady || root.selectedKey === "" || !root.selectedAvailable)
            return;
        if (root.runInFlight || !root.paramsValid)
            return;  // 单飞：运行按钮在途/参数非法时已禁用，函数级双保险
        // 提交只经 AssistService.runTool。返回空串 = 本地拒绝未上送：
        // assistError 已呈现（assist_service.cpp:88-103），这里如实不置在途。
        const requestId = AssistService.runTool(root.selectedKey, root.paramsText.trim());
        if (requestId === "")
            return;
        root.runInFlight = true;
        root.activeRunToolKey = root.selectedKey;
        runWatchdog.restart();
    }

    function finishRun() {
        runWatchdog.stop();
        root.runInFlight = false;
        root.activeRunToolKey = "";
    }

    // ---- 结果解析（头注的消费契约）---------------------------------------------
    function applyToolResult(toolKey, resultJson) {
        root.resultToolKey = String(toolKey);
        // 展示名：与当前选中一致时用选中名，其余如实显示 key（无 key→名
        // 反查通道，不伪造名称映射）。
        root.resultName = String(toolKey) === root.selectedKey
                ? root.selectedName : String(toolKey);
        root.resultSeq += 1;
        root.resultImages = [];

        let parsed;
        try {
            parsed = JSON.parse(String(resultJson));
        } catch (e) {
            parsed = undefined;
        }
        if (parsed !== undefined && parsed !== null && typeof parsed === "object"
                && !Array.isArray(parsed)) {
            // 1) 文本结果（OCR / 提取文本 / ASCII）。
            if (typeof parsed.text === "string") {
                root.resultKind = AppToolsPage.ResultKind.Text;
                root.resultText = parsed.text;
                return;
            }
            // 2) 文件/图像列表结果（files 键）。
            const files = root.stringArrayOf(parsed.files);
            if (files.length > 0) {
                root.resultKind = AppToolsPage.ResultKind.Images;
                root.resultImages = files;
                root.resultText = "";
                return;
            }
            // 3) 单张图像结果（§4 临时 PNG 通道：path + width/height/sha256）。
            if (typeof parsed.path === "string" && parsed.path !== ""
                    && typeof parsed.width === "number"
                    && typeof parsed.height === "number") {
                root.resultKind = AppToolsPage.ResultKind.Images;
                root.resultImages = [parsed.path];
                root.resultText = "";
                return;
            }
            // 4) 通用 JSON。
            root.resultKind = AppToolsPage.ResultKind.Json;
            root.resultText = root.prettyJson(parsed);
            return;
        }

        // JSON 解析失败/非对象（协议上不出现——resultJson 是 result 对象的
        // 紧凑序列化；防御性原样呈现，不谎称已格式化）。
        root.resultKind = AppToolsPage.ResultKind.Json;
        root.resultText = parsed === undefined ? String(resultJson) : root.prettyJson(parsed);
    }

    function prettyJson(value) {
        try {
            return JSON.stringify(value, null, 2);
        } catch (e) {
            return String(value);
        }
    }

    function stringArrayOf(value) {
        if (!Array.isArray(value))
            return [];
        for (let i = 0; i < value.length; ++i) {
            if (typeof value[i] !== "string" || value[i] === "")
                return [];
        }
        return value;
    }

    // ---- 导出 -----------------------------------------------------------------
    function exportImageToEditor(path) {
        const target = String(path);
        if (target === "" || root.isInlineSource(target) || !root.isImagePath(target))
            return;  // 内联/非图像：按钮已禁用（防御）
        // 提交即跳转（IA §2 产物进编辑器）。Toast 不发：页面随即卸载；
        // 编辑器内的呈现由 C++ 交接通道负责（AppStudioPage 同款）。
        StudioService.exportToEditor(target);
        Application.navigate("editor");
    }

    // ---- 布局骨架 --------------------------------------------------------------
    // 通用页面状态（ui-page-spec §6）归 AppWorkspaceLayout：无 Worker 一票
    // 否决（目录与运行都来自 Worker）；目录为空：服务在途记 Loading，否则
    // Empty。
    AppWorkspaceLayout {
        id: shell

        anchors.fill: parent

        viewState: !root.backendReady
                   ? AppWorkspaceLayout.ViewState.BackendDown
                   : (toolGrid.count === 0
                      ? (AssistService.loadingTools
                         ? AppWorkspaceLayout.ViewState.Loading
                         : AppWorkspaceLayout.ViewState.Empty)
                      : AppWorkspaceLayout.ViewState.Ready)
        emptyText: qsTr("暂无可用工具（Worker 未返回工具目录；请到设置页检查后端与外部依赖）")
        backendDownText: qsTr("处理引擎未连接（%1）——请到设置页启动 Worker")
                         .arg(Application.backend.state)

        RowLayout {
            anchors.fill: parent
            spacing: 0

            // ---- 左：工具目录（网格；置灰+依赖 Tooltip 由 AppFilterCard）----
            Rectangle {
                Layout.preferredWidth: 280
                Layout.fillHeight: true
                color: Theme.surface

                Column {
                    anchors.fill: parent
                    spacing: 0

                    AppPanelHeader {
                        id: catalogHeader

                        width: parent.width
                        title: qsTr("工具目录")
                    }

                    GridView {
                        id: toolGrid

                        width: parent.width
                        height: parent.height - catalogHeader.height
                        clip: true
                        cellWidth: width / 2
                        cellHeight: 68
                        boundsBehavior: Flickable.StopAtBounds
                        model: AssistService.assistModel

                        ScrollIndicator.vertical: ScrollIndicator {}

                        delegate: Item {
                            id: toolCell

                            // required 属性与 AssistModel 契约角色同名自动接线
                            // （toolKey/toolName/categoryLabel/available/
                            // optionalDeps，assist_model.cpp:63-71 roleNames，
                            // AppFilterCard 对 FilterModel 的同款模式）。
                            required property int index
                            required property string toolKey
                            required property string toolName
                            required property string categoryLabel
                            required property bool available
                            required property var optionalDeps

                            width: toolGrid.cellWidth
                            height: toolGrid.cellHeight

                            Component.onCompleted: root.claimSelection(toolCell)
                            onAvailableChanged: root.claimSelection(toolCell)

                            AppFilterCard {
                                anchors.fill: parent
                                anchors.margins: Theme.spacingXs

                                filterKey: toolCell.toolKey
                                filterName: toolCell.toolName
                                categoryLabel: toolCell.categoryLabel
                                available: toolCell.available
                                optionalDeps: toolCell.optionalDeps
                                selected: root.selectedKey === toolCell.toolKey
                                onClicked: root.selectTool(
                                               toolCell.toolKey, toolCell.toolName,
                                               toolCell.categoryLabel, toolCell.available)
                            }
                        }
                    }
                }
            }

            // ---- 中：结果展示（文本可复制 / 图像可导出 / 通用 JSON）----------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Theme.toolbarHeight
                    color: Theme.surface

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacingLg
                        anchors.rightMargin: Theme.spacingLg
                        spacing: Theme.spacingMd

                        Label {
                            text: root.selectedName !== ""
                                  ? root.selectedName
                                  : qsTr("未选择工具")
                            font.pixelSize: Theme.fontSizeHeading
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                            elide: Text.ElideRight
                            Layout.alignment: Qt.AlignVCenter
                        }

                        Label {
                            visible: root.selectedCategory !== ""
                            text: root.selectedCategory
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textSecondary
                            elide: Text.ElideRight
                            Layout.alignment: Qt.AlignVCenter
                        }

                        AppProgressIndicator {
                            form: AppProgressIndicator.Form.Inline
                            indeterminate: true
                            visible: root.runInFlight
                            Layout.alignment: Qt.AlignVCenter
                        }

                        Item { Layout.fillWidth: true }

                        Label {
                            text: root.runInFlight
                                  ? qsTr("正在运行…")
                                  : (root.resultToolKey !== ""
                                     ? qsTr("结果 · %1").arg(root.resultName)
                                     : qsTr("尚无结果"))
                            font.pixelSize: Theme.fontSizeSmall
                            color: root.runInFlight ? Theme.textSecondary : Theme.textDisabled
                            elide: Text.ElideMiddle
                            Layout.alignment: Qt.AlignVCenter
                        }
                    }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    // 未选择：引导空态（Ready 态下的组件内空态）。
                    ColumnLayout {
                        anchors.centerIn: parent
                        visible: root.selectedKey === ""
                        spacing: Theme.spacingSm

                        Label {
                            Layout.alignment: Qt.AlignHCenter
                            text: qsTr("在左侧选择工具开始使用")
                            font.pixelSize: Theme.fontSizeBody
                            color: Theme.textSecondary
                        }

                        Label {
                            Layout.alignment: Qt.AlignHCenter
                            text: qsTr("参数在右侧配置，点击 [运行工具] 后结果显示在这里")
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textDisabled
                        }
                    }

                    // 已选择、尚无结果：如实说，不摆假结果。
                    Label {
                        anchors.centerIn: parent
                        visible: root.selectedKey !== ""
                                 && root.resultKind === AppToolsPage.ResultKind.None
                        text: root.runInFlight
                              ? qsTr("正在运行 %1 …").arg(root.selectedName)
                              : qsTr("尚无结果（配置参数后点击 [运行工具]）")
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textDisabled
                    }

                    // ---- 文本结果（OCR / 提取文本 / ASCII）：可选中 + 复制 --
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingLg
                        visible: root.resultKind === AppToolsPage.ResultKind.Text
                        spacing: Theme.spacingSm

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacingSm

                            Label {
                                text: qsTr("文本结果（可选中复制）")
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textSecondary
                                Layout.fillWidth: true
                            }

                            AppButton {
                                size: AppButton.Size.Small
                                text: qsTr("复制文本")
                                enabled: root.resultText !== ""
                                onClicked: root.copyText(root.resultText)
                            }
                        }

                        TextArea {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            readOnly: true
                            wrapMode: TextArea.Wrap
                            text: root.resultText
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeBody
                            selectionColor: Theme.accent
                            persistentSelection: false

                            background: Rectangle {
                                radius: Theme.radiusMd
                                color: Theme.surface
                                border.color: Theme.border
                                border.width: 1
                            }
                        }
                    }

                    // ---- 文件/图像结果（PDF 转图 / 抽帧 / 临时 PNG 通道）----
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingLg
                        visible: root.resultKind === AppToolsPage.ResultKind.Images
                        spacing: Theme.spacingSm

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacingSm

                            Label {
                                text: qsTr("结果文件 · %1 项").arg(root.resultImages.length)
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textSecondary
                                Layout.fillWidth: true
                            }
                        }

                        ListView {
                            id: imageList

                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: Theme.spacingSm
                            boundsBehavior: Flickable.StopAtBounds
                            model: root.resultImages

                            ScrollIndicator.vertical: ScrollIndicator {}

                            delegate: Rectangle {
                                id: imageRow

                                required property int index
                                required property var modelData

                                readonly property string imagePath: String(modelData)
                                readonly property bool inlineData: root.isInlineSource(imagePath)
                                readonly property bool exportable: !inlineData
                                                                   && root.isImagePath(imagePath)
                                readonly property string imageSource: inlineData
                                        ? imagePath
                                        : root.toFileUrl(imagePath) + "?v=" + root.resultSeq

                                width: imageList.width
                                height: 96
                                radius: Theme.radiusSm
                                color: Theme.surface
                                border.color: Theme.border
                                border.width: 1

                                AppImageThumbnail {
                                    id: thumb

                                    x: Theme.spacingSm
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 80
                                    height: 80
                                    source: imageRow.imageSource
                                }

                                ColumnLayout {
                                    anchors.left: thumb.right
                                    anchors.right: exportButton.left
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.leftMargin: Theme.spacingMd
                                    anchors.rightMargin: Theme.spacingMd
                                    spacing: Theme.spacingXs

                                    Label {
                                        text: imageRow.inlineData
                                              ? qsTr("内联数据（#%1）").arg(imageRow.index + 1)
                                              : root.fileNameOf(imageRow.imagePath)
                                        font.pixelSize: Theme.fontSizeBody
                                        color: Theme.textPrimary
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }

                                    Label {
                                        text: imageRow.inlineData
                                              ? qsTr("未落盘，不支持导出到编辑器")
                                              : (imageRow.exportable
                                                 ? imageRow.imagePath
                                                 : qsTr("非图像文件（%1），不支持导出到编辑器")
                                                   .arg(imageRow.imagePath))
                                        font.pixelSize: Theme.fontSizeSmall
                                        color: Theme.textDisabled
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }
                                }

                                AppButton {
                                    id: exportButton

                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.rightMargin: Theme.spacingMd
                                    size: AppButton.Size.Small
                                    text: qsTr("导出到编辑器")
                                    enabled: imageRow.exportable
                                    onClicked: root.exportImageToEditor(imageRow.imagePath)
                                }
                            }
                        }
                    }

                    // ---- 通用 JSON：pretty print + [复制 JSON] ---------------
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingLg
                        visible: root.resultKind === AppToolsPage.ResultKind.Json
                        spacing: Theme.spacingSm

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacingSm

                            Label {
                                text: qsTr("结果 JSON")
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textSecondary
                                Layout.fillWidth: true
                            }

                            AppButton {
                                size: AppButton.Size.Small
                                text: qsTr("复制 JSON")
                                enabled: root.resultText !== ""
                                onClicked: root.copyText(root.resultText)
                            }
                        }

                        TextArea {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            readOnly: true
                            wrapMode: TextArea.NoWrap
                            text: root.resultText
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeMonospace
                            font.family: root.monoFamily()
                            selectionColor: Theme.accent
                            persistentSelection: false

                            background: Rectangle {
                                radius: Theme.radiusMd
                                color: Theme.surface
                                border.color: Theme.border
                                border.width: 1
                            }
                        }
                    }
                }
            }

            // ---- 右：参数面板 + 运行（AppInspectorPanel，AppStudioPage 同款）--
            AppInspectorPanel {
                id: inspector

                Layout.fillHeight: true
                tabs: [{ id: "params", title: qsTr("参数") }]
                currentIndex: 0

                // 未选中提示。
                Label {
                    visible: root.selectedKey === ""
                    width: parent.width
                    text: qsTr("选择工具后，参数与运行会显示在这里")
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textDisabled
                    wrapMode: Text.WordWrap
                }

                // 参数面板：工具参数以 JSON"值"对象提交（工具目录未含参数定义，
                // 见文件头注）。合法 JSON 对象才可运行；空 = 无参提交。
                Label {
                    visible: root.selectedKey !== ""
                    width: parent.width
                    text: qsTr("参数（JSON 对象，空 = 无参提交）")
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textSecondary
                    wrapMode: Text.WordWrap
                }

                TextArea {
                    id: paramsEditor

                    visible: root.selectedKey !== ""
                    width: parent.width
                    height: Math.max(implicitHeight, 96)
                    wrapMode: TextArea.Wrap
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMonospace
                    font.family: root.monoFamily()
                    selectionColor: Theme.accent
                    placeholderText: qsTr('{"path": "/images/a.png", …}')

                    background: Rectangle {
                        radius: Theme.radiusMd
                        color: Theme.surface
                        border.color: root.paramsValid ? Theme.border : Theme.error
                        border.width: 1
                    }

                    // 单向写入（paramsText 不回绑 text，clearParams 经编辑器
                    // 写回——防绑定环，见 paramsText 属性注释）。
                    onTextChanged: root.paramsText = paramsEditor.text
                }

                Label {
                    visible: root.selectedKey !== "" && !root.paramsValid
                    width: parent.width
                    text: qsTr("参数不是合法的 JSON 对象（数组/标量也不接受）——修正后才能运行")
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.error
                    wrapMode: Text.WordWrap
                }

                AppButton {
                    visible: root.selectedKey !== ""
                    width: parent.width
                    text: qsTr("清空参数")
                    enabled: root.paramsText !== ""
                    onClicked: root.clearParams()
                }

                AppButton {
                    visible: root.selectedKey !== ""
                    width: parent.width
                    kind: AppButton.Kind.Primary
                    text: qsTr("运行工具")
                    // AppButton 装载态禁用自身；enabled 显式带上 !runInFlight
                    // （AppFilterInspector.qml:411-416 注释约定：实例化处的
                    // enabled 绑定会覆盖组件内的 enabled: !loading）。
                    enabled: root.backendReady && root.selectedAvailable
                             && !root.runInFlight && root.paramsValid
                    loading: root.runInFlight
                    onClicked: root.runSelected()
                }

                Label {
                    visible: root.selectedKey !== "" && !root.selectedAvailable
                    width: parent.width
                    text: qsTr("该工具在当前环境不可用，无法运行")
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textDisabled
                    wrapMode: Text.WordWrap
                }
            }
        }
    }

    // ---- Toast ------------------------------------------------------------------
    AppToast {
        id: toast
    }

    // ---- 剪贴板辅助（AppToast.qml:79 同款隐藏 TextArea）--------------------------
    TextArea {
        id: clipboardHelper
        visible: false
        width: 0
        height: 0
    }

    // ---- 服务接线 ----------------------------------------------------------------
    Connections {
        target: AssistService

        // 结果交付（契约的结果通道；sync 直答与 async completed 共用）：
        // 呈现归本组件；单飞门只在结果属于当前在途提交时解除——不属于（如
        // 看门狗放行后的迟到结果）仅覆盖呈现。
        function onNotifyToolResult(toolKey, resultJson) {
            root.applyToolResult(toolKey, resultJson);
            if (root.runInFlight && String(toolKey) === root.activeRunToolKey)
                root.finishRun();
        }

        // 统一失败呈现（本地/提交前拒绝、sync 拒绝、async task.failed 含
        // CANCELLED）：Toast 归此一处；它同时是单飞在途门的失败解除路径
        // （失败必有本信号，assist_service.cpp:138-146/186-193）。
        function onAssistError(code, message) {
            if (root.runInFlight)
                root.finishRun();
            root.showToast(code + " · " + message, AppToast.Type.Error);
        }
    }

    Connections {
        target: AssistService.assistModel

        function onModelReset() {
            // 目录重拉后统一重选：清空快照，重建的委托按模型序认领首个可用项
            // （AppStudioPage 对 generatorModel 同款，避免幽灵选中）。
            root.selectedKey = "";
            root.selectedName = "";
            root.selectedCategory = "";
            root.selectedAvailable = false;
            root.clearParams();
        }
    }

    Connections {
        target: Application.backend

        // Worker 进程层错误（启动失败 / 握手超时 / 崩溃）：在途运行不会有任何
        // toolResult/assistError 跟进——在途门按真实状态恢复（§6.4，
        // AppStudioPage 同款）。
        function onErrorOccurred(code, message) {
            runWatchdog.stop();
            root.runInFlight = false;
            root.activeRunToolKey = "";
            root.showToast(code + " · " + message, AppToast.Type.Error);
        }

        // 就绪兜底拉取目录（页面打开时未就绪 → 首轮被跳过）；在途/已加载不重发
        // （幂等，AppStudioPage.qml:648-654 同款条件——但注意 BackendManager 的
        // running 属性 NOTIFY 是 stateChanged（backend_manager.h:18-19），没有
        // runningChanged 信号，处理器须挂 onStateChanged 才会触发）。
        function onStateChanged() {
            if (Application.backend.running && !AssistService.loadingTools
                    && AssistService.assistModel.rowCount() === 0)
                root.loadCatalog();
        }
    }

    // ---- 运行看门狗（帧丢失时的自愈路径）------------------------------------------
    // 正常路径下 notifyToolResult（成功）与 assistError（失败含取消）总会到
    // 其一；若 Worker 存活但帧丢失（协议层异常），120s 静默即如实报"超时未
    // 返回"并恢复可再次运行（AppStudioPage renderWatchdog 同款口径：宁可
    // 重复运行，不可无信号焊死）。
    Timer {
        id: runWatchdog
        interval: 120000
        onTriggered: {
            if (!root.runInFlight)
                return;
            root.showToast(qsTr("工具运行超时未返回（120s），已恢复可再次运行"),
                           AppToast.Type.Warning);
            root.finishRun();
        }
    }
}
