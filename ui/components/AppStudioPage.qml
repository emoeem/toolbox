import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

// 统一 Studio 工作区（总纲 §13 Phase 6 第 8-11 项：各 Studio 的生成器工作
// 流，product-information-architecture.md §1/§2 "创作=生成器工作区" 的落
// 地；ui-page-spec.md §5 Studio 页规格）。宿主是 ui/pages/StudioPage.qml
// （一级导航"创作"入口，application.cpp navModel "create" 路由至此）；
// 本组件自足：直接读写 StudioService 单例与 Application（navigate/backend/
// taskModel），页面无需转发（AppBatchWizard/BatchPage 同款分工）。
//
// 数据源与 C++ 契约（native/services/studio_service.h，QML 层不 sendAction，
// 全部经服务 Q_INVOKABLE/信号）：
// - StudioService.generatorModel：GeneratorModel 角色 generatorKey/
//   generatorName/categoryLabel/paramsJson/available/optionalDeps（与
//   generator_model.cpp roleNames 逐一核对）——目录卡片复用 AppFilterCard
//   （同名语义：名称/分类/可用性置灰+依赖 Tooltip），GeneratorModel 角色名
//   与 AppFilterCard 必需属性不同名，经包装委托逐角色接线（FilterModel.search
//   结果的 AppFilterInspector 同款手法）。
// - StudioService.bindBackend / bindTaskModel（QML 侧接线，幂等——EditorPage
//   对 DocumentService 的同款纪律）；bindTaskModel 让渲染任务进任务抽屉，
//   本组件的行探针也依赖任务行存在。
// - StudioService.loadGenerators()：目录拉取（sync 动作）。页面打开时一次 +
//   Worker 就绪时 rowCount===0 且非在途兜底一次（EditorPage.qml:914-921
//   同款幂等口径）；loadingGenerators 驱动 Loading 态。
// - StudioService.render(generatorKey, paramsJson, width, height)：参数面板
//   （复用 AppFilterParameterGroup，paramsJson 驱动，见该组件头注的整表发送
//   /Worker 兜底纪律）与尺寸选择（512/1024/2048）的任何变化 → 300ms 防抖 →
//   单飞提交：在途时新请求只置 renderQueued，解除后补发一次最新参数。
//   返回值是提交关联号 request_id（空 = 本地拒绝，未上送）；§2.3 受理异步，
//   真实 task_id 经 renderAccepted(taskId) 交付。服务端允许并发渲染（各自
//   按 task_id 关联），本组件仍串行化——notifyPreviewReady 不携带 task 关联，
//   并发渲染的迟到预览会按到达序覆盖画布，串行化保证显示顺序与参数一致。
// - StudioService.notifyPreviewReady(imagePath)：渲染完成交付预览源——文件
//   路径（?v= 递增进位防同路径不刷新，EditorPage.qml:846-852 同款）或内联
//   data: 文本（§4 内联兜底，直接作 Image source；内联无落盘文件，导出/
//   另存如实禁用）。
// - StudioService.exportToEditor(imagePath)：[导出到编辑器]——委托
//   DocumentService::openDocument（studio_service.cpp:130-140），随后本组件
//   跳转 editor 页（IA §2：创作产物发送到编辑器继续处理）。文档交接的时序
//   契约在 C++/EditorPage 侧，见组件 risks 记录。
// - StudioService.studioError(code, message)：错误呈现通道（含 task.failed
//   转发，studio_service.cpp:200-210）——失败 Toast 归这里，本组件不重复。
// - StudioService.savePreviewAs(sourcePath, targetPath)：[另存为] 的文件复
//   制一步（跨端契约新增项，评审已批：mkpath + 覆盖语义、同步 bool 返回；
//   studio_service.h 当前落地版本尚未包含，typeof 探测 + 如实提示，由修复
//   轮在 C++ 侧补齐，QML 调用形状不变）。
//
// 纪律（总纲 §9：UI 主线程零像素计算；AppFilterInspector 同款组件边界）：
// - studio.* 的组包/提交全部在 StudioService；本组件只传 generatorKey/
//   paramsJson 文本/尺寸，绝不 sendAction、不直接触碰 DocumentService。
// - 画布显示 Worker 交付的预览源（ImageCanvas 复用编辑器画布组件）；状态栏
//   的宽高/缩放比是度量显示（EditorPage 状态栏同款口径），非像素运算。
// - 失败呈现统一走 studioError（含 task.failed 转发）；单飞在途门的解除路径：
//   notifyPreviewReady（成功交付）、任务行终态（TaskModel 行探针，
//   EditorPage.qml:709-743 taskProbe 同款手法，completed/failed/cancelled
//   都只解门不弹 Toast——防与 studioError 双重呈现）、后端层 errorOccurred
//   （进程崩溃不会有任何 task 事件跟进，§6.4）、120s 看门狗（若服务未登记
//   任务行，探针惰性失效，看门狗是唯一自愈路径——如实报"超时未返回"并恢复
//   可渲染）。
Item {
    id: root

    // ---- 状态 -----------------------------------------------------------------
    readonly property bool backendReady: Application.backend.running

    // 选中生成器快照（目录委托点击/认领时复制）。GeneratorModel 契约只有角色
    // 通道（无 get()），目录 modelReset 时统一清空、由重建的委托重新认领。
    // 依赖列表不进快照：置灰原因的 Tooltip 由目录卡片按行自身角色呈现。
    property string selectedKey: ""
    property string selectedName: ""
    property string selectedParamsJson: ""
    property bool selectedAvailable: false

    // 渲染配置与在途状态。
    property int renderSize: 512
    readonly property var sizeChoices: [512, 1024, 2048]
    property bool renderInFlight: false
    property bool renderQueued: false
    property string activeTaskId: ""   // 在途渲染的 task_id（renderAccepted 交付；行探针匹配用）
    property int previewSeq: 0         // ?v= 递增：同路径预览强制重载
    property string previewPath: ""    // 最近一次 notifyPreviewReady 的本地文件路径

    readonly property bool hasPreview: root.previewPath !== ""

    Component.onCompleted: {
        // 服务接线（EditorPage.qml:83-90 同款纪律）：bindBackend 接 Worker 帧，
        // bindTaskModel 把渲染任务注入任务抽屉/任务行（本组件的行探针依赖任务
        // 行存在）。两个绑定都幂等。
        StudioService.bindBackend(Application.backend)
        StudioService.bindTaskModel(Application.taskModel)
        if (root.backendReady)
            StudioService.loadGenerators()
    }

    // ---- helpers --------------------------------------------------------------
    // 本地路径 → file:// URL（EditorPage.qml:109-115 同款纯函数，逐段
    // encodeURIComponent；QUrl::toLocalFile 解码还原。工具函数的跨页抽取是
    // EditorPage 的重构，不在本批文件清单内，先就地复制并注明出处）。
    function toFileUrl(path) {
        const segments = String(path).replace(/\\/g, "/").split("/");
        let encoded = "";
        for (let i = 0; i < segments.length; ++i)
            encoded += (i > 0 ? "/" : "") + encodeURIComponent(segments[i]);
        return encoded.charAt(0) === "/" ? "file://" + encoded : "file:///" + encoded;
    }

    // file:// URL → 本地路径（另存为目标路径；EditorPage.qml:118-132 同款）。
    function urlToPath(fileUrl) {
        const text = String(fileUrl);
        if (text.indexOf("file://") !== 0)
            return text;  // 非本地 URL：原样交给服务端校验
        let path = text.substring("file://".length);
        try {
            path = decodeURIComponent(path);
        } catch (e) {
            // 畸形百分号序列：保留原样，由 savePreviewAs 报错
        }
        if (path.length > 2 && path.charAt(0) === "/" && path.charAt(2) === ":")
            path = path.substring(1);
        return path;
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

    // 另存为默认文件名：<generator>-<timestamp>.png（评审口径）；生成器名中
    // 的文件名非法字符替换为 "-"，时间戳精确到秒。
    function defaultSaveName() {
        const base = root.selectedName !== "" ? root.selectedName : "preview";
        const safe = base.replace(/[\\/:*?"<>|]/g, "-");
        return safe + "-" + Qt.formatDateTime(new Date(), "yyyyMMdd-HHmmss") + ".png";
    }

    // ---- 选择 -----------------------------------------------------------------
    function selectGenerator(key, name, paramsJson, available) {
        if (root.selectedKey === key)
            return;  // 重复点击同一卡片不重渲染
        root.selectedKey = key;
        root.selectedName = name;
        root.selectedParamsJson = paramsJson;
        root.selectedAvailable = available;
        // 换生成器与改参数共用同一防抖出口：参数面板随 selectedParamsJson
        // 重建（AppFilterParameterGroup.rebuild 不发 paramsChanged），渲染由
        // 这里显式触发。
        renderDebounce.restart();
    }

    // 目录委托创建/可用性变化时的认领：无选中时首个可用项自动入选（模型序）。
    // 委托创建即认领而不是 itemAtIndex 扫描——Ready 态之外委托可能尚未创建，
    // 认领时机会随可见性自动补齐（转到 Ready 态时委托创建 → onCompleted）。
    function claimSelection(row) {
        if (root.selectedKey !== "" || !row.available)
            return;
        root.selectGenerator(row.generatorKey, row.generatorName, row.paramsJson,
                             row.available);
    }

    // ---- 渲染 -----------------------------------------------------------------
    // 防抖出口（参数面板 paramsChanged / 尺寸切换 / 生成器切换共用）。
    function requestRender() {
        if (!root.backendReady || root.selectedKey === "" || !root.selectedAvailable)
            return;  // 未就绪/未选中静默跳过——自动防抖出口弹错误 Toast 纯属噪音
        if (root.renderInFlight) {
            root.renderQueued = true;
            return;
        }
        // 组包（params 整表 JSON 文本）在此完成，提交只经 StudioService.render。
        // 返回值是提交关联号 request_id；空 = 本地拒绝（INVALID_PARAMS/未绑定，
        // studioError 已呈现）——不置在途、不伪装成功。真实 task_id 异步经
        // renderAccepted 交付（§2.3），在途门先按提交立起、行探针在受理后才有
        // 可匹配的 task_id。
        const requestId = StudioService.render(root.selectedKey,
                                               JSON.stringify(paramGroup.currentParams()),
                                               root.renderSize, root.renderSize);
        if (requestId === "")
            return;
        root.renderInFlight = true;
        root.renderQueued = false;
        renderWatchdog.restart();
    }

    // 单飞门解除（notifyPreviewReady / 任务行终态 / 后端崩溃 / 看门狗共用）。
    // 解除后补发一次在途期间积压的最新请求（renderQueued）。
    function finishRender() {
        renderWatchdog.stop();
        root.renderInFlight = false;
        root.activeTaskId = "";
        if (root.renderQueued) {
            root.renderQueued = false;
            root.requestRender();
        }
    }

    // 预览源交付（§4 两种形状）：文件路径 → toFileUrl + ?v=（同路径强制重载）；
    // 内联 data: 文本 → 直接作 source（每次交付都是新字符串，无缓存问题）。
    // 内联交付没有落盘文件：previewPath 保持空，导出/另存如实禁用（它们的
    // C++ 契约是本地文件路径，QUrl::fromLocalFile 对 data: 无意义）。
    function showPreview(imageSource) {
        if (String(imageSource).indexOf("data:") === 0) {
            canvas.source = imageSource;
            root.previewPath = "";
            return;
        }
        root.previewPath = String(imageSource);
        root.previewSeq += 1;
        canvas.source = root.toFileUrl(imageSource) + "?v=" + root.previewSeq;
    }

    // ---- 导出 -----------------------------------------------------------------
    function exportToEditor() {
        if (!root.hasPreview)
            return;
        // 提交即跳转（IA §2 产物进编辑器）。Toast 不发：页面随即卸载，看不到；
        // 编辑器内的呈现由 C++ 交接通道负责。
        StudioService.exportToEditor(root.previewPath);
        Application.navigate("editor");
    }

    function openSaveDialog() {
        if (!root.hasPreview)
            return;
        // 预选默认文件名（FileDialog.selectedFile 可在 open 前预设，EditorPage
        // openSaveDialog 同款）。
        saveDialog.selectedFile = root.toFileUrl(root.defaultSaveName());
        saveDialog.open();
    }

    // ---- 布局骨架 --------------------------------------------------------------
    // 通用页面状态（ui-page-spec §6）归 AppWorkspaceLayout：无 Worker 一票
    // 否决（目录与渲染都来自 Worker），目录为空是 Empty。
    AppWorkspaceLayout {
        id: shell

        anchors.fill: parent

        viewState: !root.backendReady
                   ? AppWorkspaceLayout.ViewState.BackendDown
                   : (catalogList.count === 0
                      ? (StudioService.loadingGenerators
                         ? AppWorkspaceLayout.ViewState.Loading
                         : AppWorkspaceLayout.ViewState.Empty)
                      : AppWorkspaceLayout.ViewState.Ready)
        emptyText: qsTr("暂无可用生成器（生成器目录为空）")
        backendDownText: qsTr("处理引擎未连接（%1）——请到设置页启动 Worker")
                         .arg(Application.backend.state)

        RowLayout {
            anchors.fill: parent
            spacing: 0

            // ---- 左：生成器目录（列表；置灰+依赖 Tooltip 由 AppFilterCard）----
            Rectangle {
                Layout.preferredWidth: 220
                Layout.fillHeight: true
                color: Theme.surface

                Column {
                    anchors.fill: parent
                    spacing: 0

                    AppPanelHeader {
                        id: catalogHeader

                        width: parent.width
                        title: qsTr("生成器")
                    }

                    ListView {
                        id: catalogList

                        width: parent.width
                        height: parent.height - catalogHeader.height
                        clip: true
                        spacing: Theme.spacingXs
                        boundsBehavior: Flickable.StopAtBounds
                        model: StudioService.generatorModel

                        ScrollIndicator.vertical: ScrollIndicator {}

                        delegate: Item {
                            id: genRow

                            required property int index
                            required property string generatorKey
                            required property string generatorName
                            required property string categoryLabel
                            required property string paramsJson
                            required property bool available
                            required property var optionalDeps

                            width: ListView.view ? ListView.view.width : 0
                            height: genCard.implicitHeight

                            Component.onCompleted: root.claimSelection(genRow)
                            onAvailableChanged: root.claimSelection(genRow)

                            AppFilterCard {
                                id: genCard

                                anchors.fill: parent
                                filterKey: genRow.generatorKey
                                filterName: genRow.generatorName
                                categoryLabel: genRow.categoryLabel
                                available: genRow.available
                                optionalDeps: genRow.optionalDeps
                                selected: root.selectedKey === genRow.generatorKey
                                onClicked: root.selectGenerator(
                                               genRow.generatorKey, genRow.generatorName,
                                               genRow.paramsJson, genRow.available)
                            }
                        }
                    }
                }
            }

            // ---- 中：预览画布 + 顶部条（尺寸/状态/缩放）------------------------
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
                            text: qsTr("尺寸")
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textSecondary
                            Layout.alignment: Qt.AlignVCenter
                        }

                        AppSegmentedControl {
                            id: sizeSelector

                            model: ["512", "1024", "2048"]
                            currentIndex: root.sizeChoices.indexOf(root.renderSize)
                            Layout.alignment: Qt.AlignVCenter

                            onActivated: (index) => {
                                if (index < 0 || index >= root.sizeChoices.length)
                                    return;
                                if (root.renderSize === root.sizeChoices[index])
                                    return;
                                root.renderSize = root.sizeChoices[index];
                                root.renderDebounce.restart();
                            }
                        }

                        AppProgressIndicator {
                            form: AppProgressIndicator.Form.Inline
                            indeterminate: true
                            visible: root.renderInFlight || canvas.busy
                            Layout.alignment: Qt.AlignVCenter
                        }

                        Item { Layout.fillWidth: true }

                        AppToolButton {
                            display: AbstractButton.TextOnly
                            text: qsTr("−")
                            tooltipText: qsTr("缩小")
                            enabled: root.hasPreview
                            onClicked: canvas.zoomBy(1 / 1.25)
                        }
                        AppToolButton {
                            display: AbstractButton.TextOnly
                            text: qsTr("适配")
                            tooltipText: qsTr("适配窗口")
                            enabled: root.hasPreview
                            onClicked: canvas.fitToWindow()
                        }
                        AppToolButton {
                            display: AbstractButton.TextOnly
                            text: qsTr("+")
                            tooltipText: qsTr("放大")
                            enabled: root.hasPreview
                            onClicked: canvas.zoomBy(1.25)
                        }
                        AppToolButton {
                            display: AbstractButton.TextOnly
                            text: qsTr("100%")
                            tooltipText: qsTr("实际大小")
                            enabled: root.hasPreview
                            onClicked: canvas.setActualSize()
                        }
                        Label {
                            // 度量显示（EditorPage 状态栏/缩放标签同款口径）。
                            text: canvas.imageSize.isEmpty
                                  ? "—"
                                  : canvas.imageSize.width + "×" + canvas.imageSize.height
                            font.pixelSize: Theme.fontSizeNumeric
                            color: Theme.textPrimary
                            Layout.alignment: Qt.AlignVCenter
                        }
                    }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    ImageCanvas {
                        id: canvas
                        anchors.fill: parent
                        showCheckerboard: true

                        // 拖放打开是编辑器职责，Studio 画布不接 imageDropped。
                        onLoadFailed: function (reason) {
                            if (canvas.source.toString() !== "")
                                root.showToast(qsTr("预览加载失败：%1").arg(reason),
                                               AppToast.Type.Error)
                        }
                    }

                    // 未选中：引导空态（Ready 态下的组件内空态，画布置后）。
                    ColumnLayout {
                        anchors.centerIn: parent
                        visible: root.selectedKey === ""
                        spacing: Theme.spacingSm

                        Label {
                            Layout.alignment: Qt.AlignHCenter
                            text: qsTr("在左侧选择生成器开始创作")
                            font.pixelSize: Theme.fontSizeBody
                            color: Theme.textSecondary
                        }

                        Label {
                            Layout.alignment: Qt.AlignHCenter
                            text: qsTr("参数与尺寸变化后会自动渲染预览（防抖 300ms）")
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textDisabled
                        }
                    }

                    // 已选中但画布无图：如实说，不摆假画布（画布显示状态以
                    // ImageCanvas 的实际解码结果为准，内联/文件交付都覆盖）。
                    Label {
                        anchors.centerIn: parent
                        visible: root.selectedKey !== "" && canvas.imageSize.isEmpty
                        text: root.renderInFlight
                              ? qsTr("正在渲染 %1 × %2 预览…").arg(root.renderSize).arg(root.renderSize)
                              : qsTr("预览尚未生成（参数变化后会自动渲染）")
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textDisabled
                    }
                }
            }

            // ---- 右：参数面板 + 导出（AppInspectorPanel，ui-page-spec §5）------
            AppInspectorPanel {
                id: inspector

                Layout.fillHeight: true
                tabs: [{ id: "params", title: qsTr("参数") }]
                currentIndex: 0

                // 未选中提示（AppFilterParameterGroup 的 paramsJson 为空 →
                // 面板本身为空列，引导行负责说明）。
                Label {
                    visible: root.selectedKey === ""
                    width: parent.width
                    text: qsTr("选择生成器后，参数与导出会显示在这里")
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textDisabled
                    wrapMode: Text.WordWrap
                }

                // 参数面板：paramsJson 驱动（FilterDef 形状，AppFilterParameterGroup
                // 头注的类型映射/整表发送纪律原样适用；生成器不支持的类型按该
                // 组件的"暂不支持"行如实呈现并以默认值提交）。
                AppFilterParameterGroup {
                    id: paramGroup

                    visible: root.selectedKey !== ""
                    width: parent.width
                    paramsJson: root.selectedParamsJson

                    onParamsChanged: renderDebounce.restart()
                }

                AppButton {
                    visible: root.selectedKey !== ""
                    width: parent.width
                    text: qsTr("重置参数")
                    enabled: paramGroup.hasParameters
                    onClicked: paramGroup.reset()   // reset → paramsChanged → 防抖渲染
                }

                AppSectionGroup {
                    title: qsTr("导出")
                    visible: root.selectedKey !== ""
                    width: parent.width

                    AppButton {
                        width: parent.width
                        kind: AppButton.Kind.Primary
                        text: qsTr("导出到编辑器")
                        enabled: root.hasPreview
                        onClicked: root.exportToEditor()
                    }

                    AppButton {
                        width: parent.width
                        text: qsTr("另存为")
                        enabled: root.hasPreview
                        onClicked: root.openSaveDialog()
                    }

                    Label {
                        width: parent.width
                        text: {
                            if (root.hasPreview)
                                return qsTr("当前预览：%1").arg(root.fileNameOf(root.previewPath));
                            if (!canvas.imageSize.isEmpty)
                                return qsTr("当前预览为内联数据（未落盘），暂不支持导出/另存");
                            return qsTr("尚未渲染，导出可用后显示文件名");
                        }
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textSecondary
                        elide: Text.ElideMiddle
                    }
                }
            }
        }
    }

    // ---- Toast ------------------------------------------------------------------
    AppToast {
        id: toast
    }

    // ---- 任务行探针（单飞门的兜底解除路径）----------------------------------------
    // notifyPreviewReady 不携带 task 关联（契约如此）；渲染失败时不会有
    // notifyPreviewReady——用 TaskModel 行状态兜底解除（EditorPage.qml:709-743
    // taskProbe 同款手法）。行存在的前提是 StudioService 登记了任务行（bindTaskModel
    // 已接）；若未登记，探针惰性失效，单飞门由 notifyPreviewReady/看门狗/后端
    // 错误解除。
    Item {
        id: taskProbe
        visible: false

        Repeater {
            model: Application.taskModel

            delegate: Item {
                required property string taskTaskId
                required property string taskStatus
                required property string taskError

                onTaskStatusChanged: root.watchTask(taskTaskId, taskStatus, taskError)
                Component.onCompleted: root.watchTask(taskTaskId, taskStatus, taskError)
            }
        }
    }

    // 终态行判定（queued|running|cancelling 之外全是终态，task_model.h:29-30）。
    // 只解除在途门、不弹 Toast：failed 的呈现由 StudioService 统一转发
    // studioError（studio_service.cpp:200-210），这里再报就是双重 Toast。
    function watchTask(taskId, status, error) {
        if (taskId === "" || taskId !== root.activeTaskId)
            return;
        if (status !== "completed" && status !== "failed" && status !== "cancelled")
            return;
        root.finishRender();
        // completed：显示归 notifyPreviewReady（先到先行），此处只解除在途门。
        // failed/cancelled：错误/静默呈现归 studioError，这里只恢复可渲染。
    }

    // ---- 服务/后端接线 ------------------------------------------------------------
    Connections {
        target: StudioService

        // 受理响应落地：真实 task_id（render 返回的 request_id 不可与任务行
        // 匹配，§2.3）。单飞在途期间到达的受理必属本次提交；看门狗已放行后的
        // 迟到受理按陈旧丢弃（不把 activeTaskId 指向已放弃的渲染）。
        function onRenderAccepted(taskId) {
            if (!root.renderInFlight)
                return;
            root.activeTaskId = String(taskId);
        }

        function onNotifyPreviewReady(imagePath) {
            const source = String(imagePath);
            // 服务端契约：path/data 皆缺不发射本信号（studio_service.cpp:216-221），
            // 空串防御性兜底仅解在途门、不显示。
            if (source === "") {
                root.finishRender();
                return;
            }
            root.showPreview(source);
            root.finishRender();
        }

        function onStudioError(code, message) {
            root.showToast(code + " · " + message, AppToast.Type.Error);
        }
    }

    Connections {
        target: StudioService.generatorModel

        function onModelReset() {
            // 目录重拉后统一重选：清空快照，重建的委托按模型序认领首个可用项
            // （claimSelection），避免指向已消失生成器的幽灵选中。
            root.selectedKey = "";
            root.selectedName = "";
            root.selectedParamsJson = "";
            root.selectedAvailable = false;
        }
    }

    // Worker 进程层错误（启动失败 / 握手超时 / 崩溃）：在途渲染不会有任何
    // task 事件或 notifyPreviewReady 跟进——在途门必须按真实状态恢复
    // （EditorPage onErrorOccurred 同款，§6.4）。
    Connections {
        target: Application.backend

        function onErrorOccurred(code, message) {
            renderWatchdog.stop();
            root.renderInFlight = false;
            root.renderQueued = false;
            root.activeTaskId = "";
            root.showToast(code + " · " + message, AppToast.Type.Error);
        }

        function onRunningChanged() {
            // 就绪兜底拉取目录（页面打开时未就绪 → 首轮被跳过）；在途/已加载
            // 不重发（幂等，EditorPage.qml:914-921 同款条件）。
            if (Application.backend.running && !StudioService.loadingGenerators
                    && StudioService.generatorModel.rowCount() === 0)
                StudioService.loadGenerators();
        }
    }

    // ---- 对话框 -------------------------------------------------------------------
    FileDialog {
        id: saveDialog
        title: qsTr("另存预览图")
        fileMode: FileDialog.SaveFile
        nameFilters: [
            qsTr("图像文件 (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)"),
            qsTr("所有文件 (*)")
        ]
        onAccepted: {
            const target = root.urlToPath(selectedFile);
            if (target === "")
                return;
            // 跨端契约新增：StudioService.savePreviewAs(sourcePath, targetPath)
            // ——同步 bool（mkpath + 覆盖语义，评审已批口径）。studio_service.h
            // 当前落地版本尚未包含该 Q_INVOKABLE：typeof 探测，缺失时如实提示
            // （绝不静默无操作），由修复轮在 C++ 侧补齐，调用形状不变。
            if (typeof StudioService.savePreviewAs !== "function") {
                root.showToast(qsTr("另存为暂不可用：savePreviewAs 尚未在 StudioService 实现"),
                               AppToast.Type.Warning);
                return;
            }
            const ok = StudioService.savePreviewAs(root.previewPath, target);
            if (ok)
                root.showToast(qsTr("已保存：%1").arg(target), AppToast.Type.Success);
            else
                root.showToast(qsTr("保存失败：%1").arg(target), AppToast.Type.Error);
        }
    }

    // ---- 渲染防抖 -------------------------------------------------------------------
    // 任一渲染触发源（参数/尺寸/生成器）→ 300ms 防抖 → 单飞提交。EditorPage
    // previewDebounce 同款 interval。
    Timer {
        id: renderDebounce
        interval: 300
        onTriggered: root.requestRender()
    }

    // ---- 在途看门狗（契约缺口的自愈路径）------------------------------------------
    // 契约的信号面没有独立的"渲染失败已解门"事件；若任务行未登记（bindTaskModel
    // 之外的服务实例），failed 终态探针匹配不上，renderInFlight 会永久卡死、
    // 后续渲染只入队不提交。120s 静默即如实报"超时未返回"并恢复（代价：极慢
    // 的真渲染若超过 120s 会被提前放行，可能多提交一次——宁可重复渲染，不可
    // 无信号焊死；notifyPreviewReady 的迟到响应同样没有 id 可甄别，该风险记录
    // 在 notes）。
    Timer {
        id: renderWatchdog
        interval: 120000
        onTriggered: {
            if (!root.renderInFlight)
                return;
            root.showToast(qsTr("渲染超时未返回（120s），已恢复可再次渲染"),
                           AppToast.Type.Warning);
            root.finishRender();
        }
    }
}
