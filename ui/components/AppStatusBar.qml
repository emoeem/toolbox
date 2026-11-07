import QtQuick
import QtQuick.Controls

// Status bar (ui-component-spec.md §2 StatusBar): height
// Theme.statusBarHeight, surface background, top hairline.
//
// Left: `leftText` (typography.small, elided — 文档尺寸/缩放/坐标 live here).
// Right: the default slot — e.g. the task summary (色点 + N 项进行中) whose
// click opens AppTaskQueuePanel; that wiring belongs to the call site.
//
// Passive shell; slotted interactive controls own their §4 states.
Rectangle {
    id: root

    property string leftText: ""
    default property alias contentRight: rightRow.data

    height: Theme.statusBarHeight
    implicitHeight: Theme.statusBarHeight
    color: Theme.surface

    Label {
        anchors.left: parent.left
        anchors.leftMargin: Theme.spacingLg
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - Theme.spacingLg * 2 - rightRow.width - Theme.spacingMd
        visible: root.leftText !== ""
        text: root.leftText
        font.pixelSize: Theme.fontSizeSmall
        color: Theme.textSecondary
        elide: Text.ElideRight
    }

    Row {
        id: rightRow
        anchors.right: parent.right
        anchors.rightMargin: Theme.spacingLg
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.spacingMd
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 1
        color: Theme.border
    }
}
