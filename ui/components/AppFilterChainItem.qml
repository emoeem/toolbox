import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 滤镜链步骤行（ui-component-spec.md §3 AppFilterChainItem）：启用开关、
// 滤镜名、参数摘要、上移/下移/删除。
//
// 数据即 FilterChainModel 的角色（native/models/filter_chain_model.cpp
// roleNames：chainFilterKey/chainParams/chainEnabled/chainIndex）——required
// 属性与角色同名，直接作 ListView { model: FilterService.chainModel } 的委托
// 自动接线（AppTaskItem 同款模式）。行数据与协议 filter.preview/apply 的
// steps 元素一一对应：{filter_key, params, enabled}（docs/ipc-protocol.md §3）。
//
// 行为双通道（与 AppTaskItem 的 taskModel 直调同款惯例）：
// - 若宿主 ListView 的 model 具备 FilterChainModel 的 Q_INVOKABLE 编辑入口，
//   行内直接调用 setEnabled/moveUp/moveDown/removeRow（越界行号在模型侧静默
//   忽略）；行自身不做协议动作（filter.* 组包在 FilterService，禁止 QML
//   sendAction）。
// - 同时发射 clickedRow(row, action, value)：action ∈ "toggle"/"moveUp"/
//   "moveDown"/"remove"，value 仅 toggle 携带目标启用态——宿主可据此做
//   额外联动（如触发链预览），与直接调用解耦。
//
// displayName：链模型只存 filter_key，不存显示名；由宿主传 key → 显示名
// （AppFilterInspector 从 FilterModel 建立），未传时如实显示 filter_key。
Rectangle {
    id: root

    required property int chainIndex
    required property string chainFilterKey
    required property var chainParams
    required property bool chainEnabled

    property string displayName: ""
    readonly property var chainModel: ListView.view ? ListView.view.model : null

    signal clickedRow(int row, string action, bool value)

    implicitWidth: 240
    implicitHeight: rows.implicitHeight + Theme.spacingSm

    color: "transparent"

    Column {
        id: rows
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: 0

        // 启用 ToggleField：滤镜名作行文本（AppToggleField 整行可点，开关
        // 在行尾）。checked 与模型双向：初始按 chainEnabled 接线；用户点击
        // 会打破绑定，故由下方 onChainEnabledChanged 补偿式同步（同值写入
        // 无害）。
        AppToggleField {
            id: enableToggle
            width: parent.width
            text: root.displayName !== "" ? root.displayName : root.chainFilterKey
            checked: root.chainEnabled
            onToggled: {
                if (root.chainModel && root.chainModel.setEnabled !== undefined)
                    root.chainModel.setEnabled(root.chainIndex, enableToggle.checked);
                root.clickedRow(root.chainIndex, "toggle", enableToggle.checked);
            }
        }

        Item {
            width: parent.width
            height: summaryRow.implicitHeight

            RowLayout {
                id: summaryRow
                anchors.left: parent.left
                anchors.right: parent.right
                spacing: Theme.spacingXs

                Label {
                    Layout.fillWidth: true
                    text: root.paramsSummary(root.chainParams)
                    font.pixelSize: Theme.fontSizeSmall
                    color: root.chainEnabled ? Theme.textSecondary : Theme.textDisabled
                    elide: Text.ElideRight
                }

                AppIconButton {
                    display: AbstractButton.TextOnly
                    text: "↑"
                    tooltipText: qsTr("上移")
                    enabled: root.chainModel !== null && root.chainIndex > 0
                    onClicked: {
                        if (root.chainModel && root.chainModel.moveUp !== undefined)
                            root.chainModel.moveUp(root.chainIndex);
                        root.clickedRow(root.chainIndex, "moveUp", false);
                    }
                }

                AppIconButton {
                    display: AbstractButton.TextOnly
                    text: "↓"
                    tooltipText: qsTr("下移")
                    enabled: root.chainModel !== null && root.chainIndex >= 0
                             && root.chainIndex < root.rowCountOf() - 1
                    onClicked: {
                        if (root.chainModel && root.chainModel.moveDown !== undefined)
                            root.chainModel.moveDown(root.chainIndex);
                        root.clickedRow(root.chainIndex, "moveDown", false);
                    }
                }

                AppIconButton {
                    display: AbstractButton.TextOnly
                    text: "✕"
                    tooltipText: qsTr("删除")
                    enabled: root.chainModel !== null
                    onClicked: {
                        if (root.chainModel && root.chainModel.removeRow !== undefined)
                            root.chainModel.removeRow(root.chainIndex);
                        root.clickedRow(root.chainIndex, "remove", false);
                    }
                }
            }
        }
    }

    // 底部 1px 分隔线（AppTaskItem 同款行样式）。
    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: Theme.border
    }

    // 模型侧 setEnabled 之后的视觉回写（用户点击已打破 checked 绑定；
    // 外部 setEnabled/preset 载入的重置靠这里）。同值写入不触发视觉变化。
    onChainEnabledChanged: enableToggle.checked = root.chainEnabled

    // 行数供"下移"边界判定；无模型时按 0 处理（按钮禁用）。
    function rowCountOf() {
        return root.chainModel && root.chainModel.stepCount !== undefined
                ? root.chainModel.stepCount : 0;
    }

    // 参数摘要 "k=v · k=v"（params 为协议原样对象，链内不校验）。
    // 空 params 显示"默认参数"——语义为 Worker 端按 FilterDef 默认值合并。
    function paramsSummary(params) {
        if (!params || typeof params !== "object")
            return qsTr("默认参数");
        const parts = [];
        for (const key in params) {
            const v = params[key];
            parts.push(key + "=" + (v !== null && typeof v === "object"
                                    ? JSON.stringify(v) : String(v)));
        }
        return parts.length > 0 ? parts.join(" · ") : qsTr("默认参数");
    }
}
