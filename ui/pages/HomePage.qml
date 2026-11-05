import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Home page (Phase 2): working entry into the editor + honest phase status.
// Recent files / tool search / backend summary become real in Phase 4.
Page {
    id: page

    background: Rectangle { color: Theme.background }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingXl
        spacing: Theme.spacingLg

        Label {
            text: qsTr("首页")
            font.pixelSize: Theme.fontSizeTitle
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        RowLayout {
            spacing: Theme.spacingMd

            Button {
                text: qsTr("打开图像（进入编辑工作区）")
                onClicked: Application.navigate("editor")
            }

            Label {
                text: qsTr("拖放到编辑器画布即可打开（Phase 2 支持本地文件）")
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textSecondary
            }
        }

        Label {
            text: qsTr("工具分类")
            font.pixelSize: Theme.fontSizeHeading
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        GridView {
            id: toolGrid

            readonly property int cardWidth: 200
            readonly property int cardHeight: 84

            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: Application.toolModel
            cellWidth: cardWidth + Theme.spacingMd
            cellHeight: cardHeight + Theme.spacingMd

            delegate: ItemDelegate {
                id: card

                width: toolGrid.cardWidth
                height: toolGrid.cardHeight
                enabled: model.available

                background: Rectangle {
                    radius: Theme.radiusMd
                    color: card.enabled ? (card.hovered ? Theme.surfaceElevated : Theme.surface)
                                        : Theme.surface
                    border.color: card.hovered && card.enabled ? Theme.borderStrong : Theme.border
                }

                contentItem: ColumnLayout {
                    spacing: Theme.spacingXs

                    Label {
                        Layout.fillWidth: true
                        text: model.title
                        font.pixelSize: Theme.fontSizeBody
                        font.weight: Font.DemiBold
                        color: card.enabled ? Theme.textPrimary : Theme.textDisabled
                        elide: Text.ElideRight
                    }

                    Label {
                        Layout.fillWidth: true
                        text: model.category + " · " + (model.available ? model.phase : qsTr("随 %1 提供").arg(model.phase))
                        font.pixelSize: Theme.fontSizeSmall
                        color: card.enabled ? Theme.textSecondary : Theme.textDisabled
                        elide: Text.ElideRight
                    }
                }

                onClicked: {
                    if (model.toolId === "tool.open-image")
                        Application.navigate("editor")
                    else if (model.toolId === "tool.fractal")
                        Application.navigate("create")
                    else if (model.toolId === "tool.batch")
                        Application.navigate("batch")
                    // 其余工具随 Phase 4+ 接入真实工作流后启用跳转
                }
            }

            ScrollIndicator.vertical: ScrollIndicator {}
        }
    }
}
