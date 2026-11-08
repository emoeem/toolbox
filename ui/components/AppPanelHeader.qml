import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Panel header (ui-component-spec.md §2 PanelHeader): heading title on the
// left, action icon buttons on the right (the default slot) — same header
// treatment as AppDialog (heading + bottom hairline).
//
// Height is content-driven: heading line + spacing.md gutters. The shell is
// passive; slotted action buttons own their §4 interactive states.
Rectangle {
    id: root

    property string title: ""
    default property alias actions: actionsRow.data

    implicitWidth: 200
    implicitHeight: headerRow.implicitHeight + Theme.spacingMd * 2
    color: Theme.surface

    RowLayout {
        id: headerRow
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: Theme.spacingLg
        anchors.rightMargin: Theme.spacingLg
        spacing: Theme.spacingSm

        Label {
            visible: root.title !== ""
            text: root.title
            font.pixelSize: Theme.fontSizeHeading
            font.weight: Font.DemiBold
            color: Theme.textPrimary
            elide: Text.ElideRight
            Layout.fillWidth: root.title !== ""
        }

        // Without a title the filler keeps the actions right-aligned.
        Item { Layout.fillWidth: root.title === "" }

        RowLayout {
            id: actionsRow
            spacing: Theme.spacingXs
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: Theme.border
    }
}
