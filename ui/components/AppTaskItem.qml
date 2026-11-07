import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Task row (ui-component-spec.md §3 TaskItem) bound to the TaskModel roles —
// exact roleNames from TaskModel::roleNames (native/models/task_model.cpp),
// declared as
// required properties so ListView { model: Application.taskModel } wires the
// delegate automatically:
//   taskTaskId (string) / taskName (string) / taskStatus (string:
//   queued|running|completed|failed|cancelled|cancelling) /
//   taskProgress (int 0-100) / taskError (string).
//
// Status semantics follow docs/ipc-protocol.md §2.3/§7: queued/running/
// cancelling are active → progress bar + cancel button (disabled while
// cancelling: the request was already forwarded by TaskModel::cancelTask);
// completed/failed/cancelled are terminal → no cancel. Failed rows with an
// error message expand the detail text on click (失败行展开 error).
//
// taskModel defaults to the hosting ListView's model; assign it explicitly
// when the row is used outside a ListView.
AbstractButton {
    id: root

    required property string taskTaskId
    required property string taskName
    required property string taskStatus
    required property int taskProgress
    required property string taskError

    readonly property var taskModel: ListView.view ? ListView.view.model : null
    property bool errorExpanded: false

    readonly property bool isActive:
        root.taskStatus === "queued" || root.taskStatus === "running"
        || root.taskStatus === "cancelling"
    readonly property bool hasErrorDetail:
        root.taskStatus === "failed" && root.taskError !== ""

    implicitWidth: 240
    implicitHeight: rows.implicitHeight + topPadding + bottomPadding
    topPadding: Theme.spacingXs
    bottomPadding: Theme.spacingXs
    leftPadding: Theme.spacingSm
    rightPadding: Theme.spacingSm

    activeFocusOnTab: root.hasErrorDetail

    onClicked: {
        if (root.hasErrorDetail)
            root.errorExpanded = !root.errorExpanded;
    }

    Keys.onReturnPressed: (event) => {
        event.accepted = true;
        root.clicked();
    }
    Keys.onEnterPressed: (event) => {
        event.accepted = true;
        root.clicked();
    }

    HoverHandler {
        cursorShape: root.hasErrorDetail ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    background: Item {
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusSm
            color: root.hasErrorDetail && root.pressed ? Qt.darker(Theme.surfaceElevated, 1.08)
                 : root.hovered ? Theme.surfaceElevated : "transparent"

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
            visible: root.visualFocus && root.enabled
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: Theme.border
        }
    }

    contentItem: Column {
        id: rows
        spacing: Theme.spacingXs

        RowLayout {
            width: parent.width
            spacing: Theme.spacingSm

            Rectangle {  // status dot
                width: 8
                height: 8
                radius: Theme.radiusSm  // half of the 8px dot → circle
                color: root.statusColor()
                Layout.alignment: Qt.AlignVCenter
            }

            Label {
                Layout.fillWidth: true
                text: root.taskName
                font.pixelSize: Theme.fontSizeBody
                color: Theme.textPrimary
                elide: Text.ElideRight
            }

            AppProgressIndicator {
                form: AppProgressIndicator.Form.Bar
                from: 0
                to: 100
                value: root.taskProgress
                visible: root.isActive
                Layout.preferredWidth: 96
                Layout.alignment: Qt.AlignVCenter
            }

            Label {
                text: root.statusLabel()
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textSecondary
                Layout.alignment: Qt.AlignVCenter
            }

            AppButton {
                visible: root.isActive
                enabled: root.taskStatus !== "cancelling"
                kind: AppButton.Kind.Ghost
                size: AppButton.Size.Small
                text: qsTr("取消")
                onClicked: {
                    if (root.taskModel && root.taskModel.cancelTask !== undefined)
                        root.taskModel.cancelTask(root.taskTaskId);
                }
            }
        }

        Label {  // expanded error detail (failed rows)
            visible: root.hasErrorDetail && root.errorExpanded
            width: parent.width
            text: root.taskError
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.error
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
        }
    }

    // Unknown statuses fall back to the raw string / secondary color so a
    // new protocol state stays readable instead of rendering empty.
    function statusColor() {
        switch (root.taskStatus) {
        case "running": return Theme.accent;
        case "completed": return Theme.success;
        case "failed": return Theme.error;
        case "cancelled": return Theme.textDisabled;
        case "queued":
        case "cancelling":
        default: return Theme.textSecondary;
        }
    }

    function statusLabel() {
        switch (root.taskStatus) {
        case "queued": return qsTr("排队中");
        case "running": return qsTr("运行中 · %1%").arg(root.taskProgress);
        case "completed": return qsTr("已完成");
        case "failed": return qsTr("失败");
        case "cancelled": return qsTr("已取消");
        case "cancelling": return qsTr("取消中");
        default: return root.taskStatus;
        }
    }
}
