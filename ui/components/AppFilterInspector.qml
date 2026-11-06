import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 滤镜页签整体（ui-component-spec.md §3 / docs/user-flows.md 流程 2）：
// 搜索 + FilterCard 网格（FilterModel.search）→ 选中卡片 → 参数面板 →
// [加入链] → FilterChainModel 列表 → 预设行 → [预览][应用]。
//
// 职责边界（流程 2 的接线纪律）：
// - 本组件只读写 FilterService 的模型与预设 API（loadFilters 由页面在打开时
//   调用；preset save/load/delete 在此直调，都是协议同步动作）；filter.* 的
//   组包/提交全部经 FilterService（previewChain/applyChain），本组件不发
//   sendAction、不直接触碰 DocumentService。
// - [预览]/[应用] 只发 previewRequested()/applyRequested() 信号——防抖
//   （300ms）与在途状态机由宿主页面（EditorPage）持有，预览/应用的画布
//   刷新走页面既有的 previewReady/documentVersionChanged 路径。
// - 链的任何变化（加入/删除/排序/启停/载入预设）经 chainModel 的模型信号
//   汇成 chainChanged() 信号，宿主据此触发链预览。
//
// 预设缓存的防自激读法（FilterService.presetsList 文档约定）：presetsList()
// 调用即发送 filter.presets.list 并返回"最近一次缓存"；响应到达后服务端
// emit presetsChanged——若在 presetsChanged 里再调 presetsList() 会形成
// 请求→响应→presetsChanged→再请求 的自激环。故这里用一次性闸门：
// pullPresets() 置位闸门并发起请求；presetsChanged 消耗闸门后经 0ms Timer
// 延迟重读（不在槽内直接触发），重读返回的已是新缓存；其响应到达时闸门
// 已关闭，环终止。presetSaved/presetDeleted 后服务端会自动 refreshPresets，
// 处理器只重新置位闸门（保存动作持久化在先，随后到达的响应必然含新状态）。
Column {
    id: root

    // 宿主页面注入（与页面级在途门控同源，组件内不自造状态）。
    property bool backendReady: false
    property bool fullResInFlight: false
    property bool applyInFlight: false

    property string searchQuery: ""
    property var filterEntries: []        // FilterModel.search 的本地镜像
    property var filterNames: ({})        // key → 显示名（链行显示用）
    property var selectedEntry: null      // 选中的滤镜条目（search 结果的 map）

    // 预设缓存镜像 + 防自激闸门（见文件头注释）。
    property var presetEntries: []
    property bool presetRefreshQueued: false

    readonly property string selectedKey:
        root.selectedEntry !== null && root.selectedEntry !== undefined
        ? String(root.selectedEntry.key) : ""
    readonly property bool chainEmpty: FilterService.chainModel.stepCount === 0
    readonly property bool hasPresetSelection:
        presetSelect.currentIndex >= 0
        && presetSelect.currentIndex < root.presetEntries.length

    signal previewRequested()
    signal applyRequested()
    signal chainChanged()

    spacing: Theme.spacingMd

    Component.onCompleted: {
        // 目录镜像就地可算（search 不依赖后端）；预设的首次拉取由宿主页面在
        // bindBackend 之后调用 pullPresets()——本组件的 onCompleted 先于页面
        // 的（QML 子先父后），此刻 FilterService 尚未 bindBackend，直接拉只会
        // 发出 filterError(INTERNAL) 的无意义 Toast。
        root.refreshFilterEntries();
        root.rebuildFilterNames();
    }

    onBackendReadyChanged: {
        // Worker 就绪后补拉一次预设缓存（页面打开时未就绪 → 页面跳过了首次拉取）。
        if (root.backendReady)
            root.pullPresets();
    }

    // ---- 数据刷新 --------------------------------------------------------------
    function refreshFilterEntries() {
        // search("") 返回全部条目（FilterModel::search 文档约定）——浏览与
        // 搜索共用一条网格路径，排序沿用 Worker 端（category, name）。
        root.filterEntries = FilterService.filterModel.search(root.searchQuery);
    }

    function rebuildFilterNames() {
        const all = FilterService.filterModel.search("");
        const names = {};
        for (let i = 0; i < all.length; ++i)
            names[all[i].key] = all[i].name;
        root.filterNames = names;
    }

    function selectEntry(entry) {
        root.selectedEntry = entry;
    }

    function joinChain() {
        if (!root.selectedEntry || root.selectedEntry.available !== true)
            return;
        // 参数快照随步骤入链（协议 steps 元素的 params，FilterService 组包时
        // 原样上送）；面板回默认，为下一个滤镜腾出干净配置。
        FilterService.chainModel.addStep(String(root.selectedEntry.key),
                                         paramGroup.currentParams());
        paramGroup.reset();
    }

    function pullPresets() {
        root.presetRefreshQueued = true;
        root.presetEntries = FilterService.presetsList();  // 返回旧缓存；真实列表随响应送达
    }

    // 预设条目的显示文本（协议只暴露 name / step_count，docs/ipc-protocol.md §3.4）。
    function presetLabel(entry) {
        return String(entry.name) + " · " + qsTr("%1 步").arg(Number(entry.step_count));
    }

    // ---- FilterService / 模型信号 ----------------------------------------------
    Connections {
        target: FilterService.filterModel

        function onModelReset() {
            root.refreshFilterEntries();
            root.rebuildFilterNames();
        }
    }

    Connections {
        target: FilterService

        function onPresetsChanged() {
            if (!root.presetRefreshQueued)
                return;  // 未经闸门的响应（防御）：不触发重读，防自激
            root.presetRefreshQueued = false;
            presetSyncTimer.restart();
        }

        // 服务端保存/删除成功后自动 refreshPresets（filter_service.cpp）；此处
        // 只重新置位闸门接它的响应，不再额外发请求。
        function onPresetSaved(name) {
            root.presetRefreshQueued = true;
            presetNameField.clear();
        }

        function onPresetDeleted(name) {
            root.presetRefreshQueued = true;
        }
    }

    // 0ms 延迟重读：不在 presetsChanged 槽内直接调 presetsList()（防自激环，
    // 文件头注释）。重读返回新缓存；其引发的响应到达时闸门已关闭，环终止。
    Timer {
        id: presetSyncTimer
        interval: 0
        onTriggered: root.presetEntries = FilterService.presetsList()
    }

    // 链的任何变化 → chainChanged（宿主触发链预览）。replaceFrom（载入预设/
    // 应用后清链）走 modelReset；编辑入口走 insert/remove/move/dataChanged。
    Connections {
        target: FilterService.chainModel

        function onRowsInserted() { root.chainChanged() }
        function onRowsRemoved() { root.chainChanged() }
        function onRowsMoved() { root.chainChanged() }
        function onModelReset() { root.chainChanged() }
        function onDataChanged() { root.chainChanged() }
    }

    // ---- 搜索 ------------------------------------------------------------------
    AppSearchField {
        width: parent.width
        placeholderText: qsTr("搜索滤镜（名称 / 关键词 / 分类）")
        onSearched: (query) => {
            root.searchQuery = query;
            root.refreshFilterEntries();
        }
    }

    // ---- 滤镜库 ----------------------------------------------------------------
    RowLayout {
        width: parent.width
        spacing: Theme.spacingSm

        Label {
            text: qsTr("滤镜库")
            font.pixelSize: Theme.fontSizeHeading
            font.weight: Font.DemiBold
            color: Theme.textPrimary
            Layout.fillWidth: true
        }

        AppProgressIndicator {
            form: AppProgressIndicator.Form.Inline
            indeterminate: true
            visible: FilterService.loadingFilters
            Layout.alignment: Qt.AlignVCenter
        }
    }

    Label {
        width: parent.width
        text: {
            // 就绪状态优先于加载中：Worker 崩溃可能把 loadingFilters 留在途
            // （无响应可收），此时按真实状态报"未就绪"，不谎称仍在加载。
            if (!root.backendReady)
                return qsTr("Worker 未就绪，无法加载滤镜目录");
            if (FilterService.loadingFilters)
                return qsTr("正在加载滤镜目录…");
            if (FilterService.filterModel.rowCount() === 0)
                return qsTr("滤镜目录为空");
            return qsTr("没有匹配的滤镜");
        }
        font.pixelSize: Theme.fontSizeSmall
        color: Theme.textDisabled
        visible: root.filterEntries.length === 0
        horizontalAlignment: Text.AlignHCenter
        topPadding: Theme.spacingLg
        bottomPadding: Theme.spacingLg
    }

    GridView {
        id: filterGrid
        width: parent.width
        height: contentHeight
        interactive: false   // 与检查器外层滚动容器共用滚动，网格自身不吞滚轮
        clip: true
        cellWidth: width / 2
        cellHeight: 56
        model: root.filterEntries
        visible: root.filterEntries.length > 0

        delegate: Item {
            id: cardCell

            required property var modelData

            width: filterGrid.cellWidth
            height: filterGrid.cellHeight

            // 搜索结果的键（key/name/...）与卡片属性名对齐由这里显式映射
            // （AppFilterCard 的 required 属性面向 FilterModel 角色名）。
            AppFilterCard {
                anchors.fill: parent
                filterKey: String(cardCell.modelData.key)
                filterName: String(cardCell.modelData.name)
                categoryLabel: String(cardCell.modelData.categoryLabel)
                available: cardCell.modelData.available === true
                optionalDeps: cardCell.modelData.optionalDeps
                description: String(cardCell.modelData.description)
                selected: root.selectedKey === String(cardCell.modelData.key)
                onClicked: (key) => root.selectEntry(cardCell.modelData)
            }
        }
    }

    // ---- 选中滤镜的参数面板 ------------------------------------------------------
    AppSectionGroup {
        title: root.selectedEntry
               ? qsTr("参数 · %1").arg(String(root.selectedEntry.name))
               : qsTr("参数")
        defaultExpanded: true
        width: parent.width
        visible: root.selectedEntry !== null && root.selectedEntry !== undefined

        Label {
            width: parent.width
            text: root.selectedEntry ? String(root.selectedEntry.description) : ""
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.textSecondary
            wrapMode: Text.WordWrap
            visible: root.selectedEntry
                     && String(root.selectedEntry.description) !== ""
        }

        AppFilterParameterGroup {
            id: paramGroup
            width: parent.width
            paramsJson: root.selectedEntry ? String(root.selectedEntry.paramsJson) : ""
        }

        RowLayout {
            width: parent.width
            spacing: Theme.spacingSm

            AppButton {
                text: qsTr("重置参数")
                kind: AppButton.Kind.Ghost
                size: AppButton.Size.Small
                enabled: paramGroup.hasParameters
                onClicked: paramGroup.reset()
            }

            Item { Layout.fillWidth: true }

            AppButton {
                kind: AppButton.Kind.Primary
                size: AppButton.Size.Small
                text: qsTr("加入链")
                enabled: root.selectedEntry !== null && root.selectedEntry !== undefined
                         && root.selectedEntry.available === true
                onClicked: root.joinChain()
            }
        }
    }

    // ---- 滤镜链 ----------------------------------------------------------------
    AppSectionGroup {
        title: qsTr("滤镜链 · %1 步").arg(FilterService.chainModel.stepCount)
        defaultExpanded: true
        width: parent.width

        Label {
            width: parent.width
            text: qsTr("链为空：在上方选择滤镜并\"加入链\"；链顺序即应用顺序")
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.textDisabled
            wrapMode: Text.WordWrap
            visible: root.chainEmpty
            topPadding: Theme.spacingXs
            bottomPadding: Theme.spacingXs
        }

        ListView {
            id: chainList
            width: parent.width
            height: contentHeight
            interactive: false
            model: FilterService.chainModel
            visible: !root.chainEmpty

            delegate: AppFilterChainItem {
                width: chainList.width
                displayName: root.filterNames[chainFilterKey] !== undefined
                             ? root.filterNames[chainFilterKey] : ""
            }
        }
    }

    // ---- 预设（FilterService 预设 API，docs/ipc-protocol.md §3.4）--------------
    AppSectionGroup {
        title: qsTr("预设")
        defaultExpanded: true
        width: parent.width

        RowLayout {
            width: parent.width
            spacing: Theme.spacingSm

            AppTextField {
                id: presetNameField
                Layout.fillWidth: true
                placeholderText: qsTr("预设名称")
            }

            AppButton {
                text: qsTr("保存")
                size: AppButton.Size.Small
                enabled: presetNameField.text.trim() !== "" && !root.chainEmpty
                onClicked: FilterService.savePreset(presetNameField.text.trim())
            }
        }

        RowLayout {
            width: parent.width
            spacing: Theme.spacingSm

            AppSelectField {
                id: presetSelect
                Layout.fillWidth: true
                placeholderText: root.presetEntries.length === 0
                                 ? qsTr("暂无预设") : qsTr("选择预设")
                model: {
                    const labels = [];
                    for (let i = 0; i < root.presetEntries.length; ++i)
                        labels.push(root.presetLabel(root.presetEntries[i]));
                    return labels;
                }
            }

            AppButton {
                text: qsTr("加载")
                size: AppButton.Size.Small
                enabled: root.hasPresetSelection && !root.fullResInFlight
                onClicked: FilterService.loadPreset(
                               String(root.presetEntries[presetSelect.currentIndex].name))
            }

            AppButton {
                text: qsTr("删除")
                kind: AppButton.Kind.Danger
                size: AppButton.Size.Small
                enabled: root.hasPresetSelection
                onClicked: FilterService.deletePreset(
                               String(root.presetEntries[presetSelect.currentIndex].name))
            }
        }
    }

    // ---- 预览 / 应用 ------------------------------------------------------------
    // 按钮只发信号：防抖与在途门控在宿主页面（EditorPage）。
    RowLayout {
        width: parent.width
        spacing: Theme.spacingSm

        AppButton {
            Layout.fillWidth: true
            text: qsTr("预览")
            enabled: !root.chainEmpty && root.backendReady && !root.fullResInFlight
            onClicked: root.previewRequested()
        }

        AppButton {
            Layout.fillWidth: true
            kind: AppButton.Kind.Primary
            text: qsTr("应用")
            // AppButton 装载态禁用自身；enabled 显式带上 !applyInFlight（组件
            // 注释约定：实例化处的 enabled 绑定会覆盖组件内的 enabled: !loading）。
            enabled: !root.chainEmpty && root.backendReady
                     && !root.fullResInFlight && !root.applyInFlight
            loading: root.applyInFlight
            onClicked: root.applyRequested()
        }
    }
}
