import Toolbox
import QtQuick
import QtQuick.Controls

// Bottom task drawer (ui-component-spec.md §2 TaskQueuePanel, Phase 4 scope
// per the ask): always-visible header strip; `expanded` grows the drawer to
// show the task list with a motion.normal height animation. Persist
// `expanded`/`expandedHeight` at the call site — the component writes no
// settings.
//
// `model` binds a TaskModel directly (default Application.taskModel); rows
// render through AppTaskItem, which picks the TaskModel roles up as required
// properties. `count` exposes the row count for status-bar summaries.
//
// The header's 清空完成 button appears only when the bound model exposes a
// clearCompleted() entry point; TaskModel (task_model.h) does not have one
// yet, so with the default binding the button stays hidden instead of
// rendering an action that does nothing (总纲 §3.4 honesty rule).
Rectangle {
    id: root

    property bool expanded: false

    // Direct model binding; assign another TaskModel to override.
    property alias model: listView.model

    // Drawer height when expanded; default is 40% of the docked parent.
    property real expandedHeight: root.parent ? Math.round(root.parent.height * 0.4) : 0

    readonly property alias count: listView.count
    readonly property bool canClearCompleted:
        root.model !== null && root.model !== undefined
        && root.model.clearCompleted !== undefined

    readonly property int headerHeight: 28 + Theme.spacingSm * 2

    implicitHeight: root.expanded ? Math.max(root.headerHeight, root.expandedHeight)
                                  : root.headerHeight

    Behavior on height {
        NumberAnimation { duration: Theme.motionNormal; easing.type: Easing.OutCubic }
    }

    color: Theme.surface
    clip: true

    Item {
        id: header
        width: parent.width
        height: root.headerHeight

        Label {
            id: titleLabel
            anchors.left: parent.left
            anchors.leftMargin: Theme.spacingLg
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("任务队列")
            font.pixelSize: Theme.fontSizeHeading
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        Label {
            anchors.left: titleLabel.right
            anchors.leftMargin: Theme.spacingMd
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("%1 个任务").arg(root.count)
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.textSecondary
        }

        AppButton {
            id: clearButton
            anchors.right: toggleButton.left
            anchors.rightMargin: Theme.spacingSm
            anchors.verticalCenter: parent.verticalCenter
            visible: root.canClearCompleted
            kind: AppButton.Kind.Ghost
            size: AppButton.Size.Small
            text: qsTr("清空完成")
            onClicked: root.model.clearCompleted()
        }

        AbstractButton {
            id: toggleButton

            anchors.right: parent.right
            anchors.rightMargin: Theme.spacingSm
            anchors.verticalCenter: parent.verticalCenter
            width: 28
            height: 28
            opacity: enabled ? 1.0 : 0.4  // design-system §4 Disabled

            HoverHandler { cursorShape: Qt.PointingHandCursor }

            Keys.onReturnPressed: (event) => {
                event.accepted = true;
                root.expanded = !root.expanded;
            }
            Keys.onEnterPressed: (event) => {
                event.accepted = true;
                root.expanded = !root.expanded;
            }

            background: Item {
                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusSm
                    color: toggleButton.pressed ? Qt.darker(Theme.surfaceElevated, 1.08)
                         : toggleButton.hovered ? Theme.surfaceElevated : "transparent"

                    Behavior on color {
                        ColorAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: -2
                    radius: Theme.radiusSm + 2
                    color: "transparent"
                    border.color: Theme.accent
                    border.width: 2
                    visible: toggleButton.visualFocus && toggleButton.enabled
                }
            }

            contentItem: Item {
                Canvas {
                    anchors.centerIn: parent
                    width: 12
                    height: 12
                    rotation: root.expanded ? 180 : 0

                    Behavior on rotation {
                        NumberAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
                    }

                    property color glyphColor: toggleButton.hovered ? Theme.textPrimary : Theme.textSecondary
                    onGlyphColorChanged: requestPaint()

                    onPaint: {
                        const ctx = getContext("2d");
                        ctx.reset();
                        ctx.strokeStyle = glyphColor.toString();
                        ctx.lineWidth = 1.5;
                        ctx.lineCap = "round";
                        ctx.beginPath();
                        ctx.moveTo(3, 4.5);
                        ctx.lineTo(6, 7.5);
                        ctx.lineTo(9, 4.5);
                        ctx.stroke();
                    }
                }
            }

            onClicked: root.expanded = !root.expanded
        }
    }

    Rectangle {
        anchors.top: header.bottom
        width: parent.width
        height: 1
        color: Theme.border
    }

    ListView {
        id: listView
        anchors.top: header.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        visible: root.expanded
        clip: true
        model: Application.taskModel

        delegate: AppTaskItem {}

        ScrollIndicator.vertical: ScrollIndicator {}
    }

    // Empty state: a sibling of the ListView, not a child. ItemView re-parents
    // its declared children to the contentItem, where anchors.centerIn would
    // center on the content origin (y=0, clipped) instead of the visible area.
    Label {
        anchors.centerIn: listView
        visible: root.expanded && listView.count === 0
        text: qsTr("暂无任务")
        font.pixelSize: Theme.fontSizeSmall
        color: Theme.textSecondary
    }
}
