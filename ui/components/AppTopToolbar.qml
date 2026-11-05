import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Top toolbar (ui-component-spec.md §2 TopToolbar):
// - fixed height Theme.toolbarHeight, surface background, bottom hairline;
// - three groups: contentLeft (document actions — also the default slot) /
//   contentCenter (history, horizontally centered) / contentRight (zoom +
//   workspace context actions);
// - adjacent non-empty groups are separated by a 1px Theme.border vertical
//   rule (spec: 分组间用 1px border 竖线).
//
// Slots are RowLayout containers with spacing spacingSm — declare one item
// per button (AppToolButton). For sub-groups inside one slot place an
// AppTopToolbar.GroupRule between the items (same 1px rule).
//
// The toolbar itself is a passive container: hover/pressed/focus/disabled
// states live in the slotted interactive controls (design-system §4).
Rectangle {
    id: root

    default property alias contentLeft: leftSlot.data
    property alias contentCenter: centerSlot.data
    property alias contentRight: rightSlot.data

    height: Theme.toolbarHeight
    implicitHeight: Theme.toolbarHeight
    color: Theme.surface

    // 1px vertical rule between groups; height keeps spacing.md gutters
    // inside the toolbarHeight row.
    component GroupRule: Rectangle {
        width: 1
        height: Theme.toolbarHeight - Theme.spacingMd * 2
        color: Theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingLg
        anchors.rightMargin: Theme.spacingLg
        spacing: Theme.spacingMd

        RowLayout {
            id: leftSlot
            Layout.alignment: Qt.AlignVCenter
            spacing: Theme.spacingSm
        }

        GroupRule {
            Layout.alignment: Qt.AlignVCenter
            visible: leftSlot.visibleChildren.length > 0
                     && centerSlot.visibleChildren.length > 0
        }

        Item { Layout.fillWidth: true }

        RowLayout {
            id: centerSlot
            Layout.alignment: Qt.AlignVCenter
            spacing: Theme.spacingSm
        }

        Item { Layout.fillWidth: true }

        GroupRule {
            Layout.alignment: Qt.AlignVCenter
            visible: centerSlot.visibleChildren.length > 0
                     && rightSlot.visibleChildren.length > 0
        }

        RowLayout {
            id: rightSlot
            Layout.alignment: Qt.AlignVCenter
            spacing: Theme.spacingSm
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
