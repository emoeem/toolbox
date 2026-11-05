import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// History entry row (ui-component-spec.md §3 HistoryItem) — pure display:
// 操作名 + 时间, the current node highlighted (surfaceElevated fill + 2px
// accent bar + DemiBold primary text).
//
// Intentionally non-interactive: jump-to-node (continuous undo/redo walk)
// arrives with the Phase 5 history model, so this item exposes no clicked()
// signal and no hover/pressed/focus states — no fake affordances (总纲 §3.4).
// Feed it from HistoryModel when Phase 5 lands.
Rectangle {
    id: root

    property string title: ""
    property string timestamp: ""
    property bool isCurrent: false

    implicitWidth: 200
    implicitHeight: rowLayout.implicitHeight + Theme.spacingSm * 2

    radius: Theme.radiusSm
    color: root.isCurrent ? Theme.surfaceElevated : "transparent"

    Rectangle {  // current-node accent bar
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 2
        color: Theme.accent
        visible: root.isCurrent
    }

    RowLayout {
        id: rowLayout
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: Theme.spacingMd
        anchors.rightMargin: Theme.spacingMd
        spacing: Theme.spacingSm

        Label {
            Layout.fillWidth: true
            text: root.title
            font.pixelSize: Theme.fontSizeBody
            font.weight: root.isCurrent ? Font.DemiBold : Font.Normal
            color: root.isCurrent ? Theme.textPrimary : Theme.textSecondary
            elide: Text.ElideRight
        }

        Label {
            visible: root.timestamp !== ""
            text: root.timestamp
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.textSecondary
            Layout.alignment: Qt.AlignVCenter
        }
    }
}
