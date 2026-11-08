import Toolbox
import QtQuick
import QtQuick.Controls

// 滤镜卡片（ui-component-spec.md §3 AppFilterCard）：滤镜名/分类/可用性。
//
// 数据即 FilterModel 的角色（native/models/filter_model.cpp roleNames：
// filterKey/filterName/categoryLabel/paramsJson/available/optionalDeps/
// description）——required 属性与角色同名，可直接作
// ListView/GridView { model: FilterService.filterModel } 的委托自动接线
// （AppTaskItem 同款模式）。搜索结果（FilterModel.search 返回的 QVariantMap
// 列表，键为 key/name/categoryLabel/...）形状不同，由调用方包一层委托把
// modelData.* 映射到这些属性（AppFilterInspector.qml 即此用法）。
//
// 状态（design-system §4）：
// - available=false：置灰（40% 口径）+ Tooltip 原因（optional_deps，如
//   "需要 G'MIC"——Worker 端 filter.list 的 available/optional_deps，
//   docs/ipc-protocol.md §3）；不发射 clicked，键盘激活同样无效。
// - available=true 且有 description：Tooltip 展示描述。
// - selected：accent 描边（检查器右侧参数面板的数据源标识）。
// - 键盘：Tab 进入焦点，Space/Enter/Return 激活；焦点环同全局 2px accent。
//
// clicked(filterKey)：filterKey 即 filter.preview/apply 的 filter_key
// （docs/ipc-protocol.md §3）。基类有意选 Item 而非 AbstractButton——
// AbstractButton 自带无参 clicked()，重声明带参会遮蔽基类信号（qmllint
// G_QML_SIGNAL_SHADOWED），Item 上干净地声明唯一 clicked(string)。
Item {
    id: root

    required property string filterKey
    required property string filterName
    required property string categoryLabel
    required property bool available
    required property var optionalDeps
    property string description: ""
    property bool selected: false

    signal clicked(string filterKey)

    implicitWidth: 128
    implicitHeight: nameLabel.implicitHeight + categoryLabel.implicitHeight
                    + Theme.spacingSm * 3
    opacity: root.available ? 1.0 : 0.4  // design-system §4 Disabled
    activeFocusOnTab: true

    HoverHandler {
        id: cardHover
        // 悬停文案由 onHoveredChanged 决定：不可用 → 原因，可用 → 描述（若有）。
        cursorShape: root.available ? Qt.PointingHandCursor : Qt.ForbiddenCursor
        onHoveredChanged: {
            if (!hovered) {
                tip.close();
                return;
            }
            const reason = root.available ? root.description : root.unavailableReason();
            if (reason === "")
                return;
            tip.open(reason,
                     (root.width - tip.implicitWidth) / 2,
                     root.height + Theme.spacingXs);
        }
    }

    // 点击与按压态同一个 handler：点击发射 clicked(filterKey)（不可用卡片
    // 不发射），按压态供背景取色。
    TapHandler {
        id: cardTap
        enabled: root.available
        onTapped: root.clicked(root.filterKey)
    }

    // design-system §4：Space/Enter/Return 激活（基类是 Item，无 AbstractButton
    // 的 ButtonPressKeys，三个键都在此显式处理，不依赖平台主题）。
    Keys.onSpacePressed: (event) => {
        event.accepted = true;
        root.activateIfAvailable();
    }
    Keys.onReturnPressed: (event) => {
        event.accepted = true;
        root.activateIfAvailable();
    }
    Keys.onEnterPressed: (event) => {
        event.accepted = true;
        root.activateIfAvailable();
    }

    AppTooltip {
        id: tip
    }

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusMd
        // 按压/悬停填充只对可用卡片成立：不可用卡片不响应任何交互。
        color: !root.available ? "transparent"
             : cardTap.pressed ? Qt.darker(Theme.surfaceElevated, 1.08)
             : cardHover.hovered ? Theme.surfaceElevated
             : "transparent"

        Behavior on color {
            ColorAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
        }
    }

    // 选中态 accent 描边（spec：选中卡片 accent 描边）。
    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusMd
        color: "transparent"
        border.color: Theme.accent
        border.width: 1
        visible: root.selected
    }

    // 键盘焦点环（同全局 2px accent，keyboard only）。
    Rectangle {
        anchors.fill: parent
        anchors.margins: -2
        radius: Theme.radiusMd + 2
        color: "transparent"
        border.color: Theme.accent
        border.width: 2
        visible: root.activeFocus && root.available
    }

    Column {
        anchors.fill: parent
        anchors.margins: Theme.spacingSm

        Label {
            id: nameLabel
            width: parent.width
            text: root.filterName
            font.pixelSize: Theme.fontSizeBody
            color: root.available ? Theme.textPrimary : Theme.textDisabled
            elide: Text.ElideRight
        }

        Label {
            id: categoryLabel
            width: parent.width
            text: root.categoryLabel
            font.pixelSize: Theme.fontSizeSmall
            color: root.available ? Theme.textSecondary : Theme.textDisabled
            elide: Text.ElideRight
        }
    }

    function activateIfAvailable() {
        if (root.available)
            root.clicked(root.filterKey);
    }

    // 置灰原因（Tooltip 文案）：optional_deps 来自 Worker filter.list；
    // 缺失依赖的兜底文案不点名具体依赖（宁可含糊，不谎报依赖名）。
    function unavailableReason() {
        const deps = root.optionalDeps;
        if (deps !== undefined && deps !== null && deps.length > 0)
            return qsTr("缺少可选依赖：%1").arg(deps.join(", "));
        return qsTr("当前环境不可用");
    }
}
