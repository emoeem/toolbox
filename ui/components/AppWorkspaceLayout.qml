import Toolbox
import QtQuick
import QtQuick.Controls

// Page workspace skeleton (ui-component-spec.md §2 WorkspaceLayout +
// ui-page-spec.md §6): canvasBackdrop background (design-system §6: 画布预览
// 区域永远使用 canvasBackdrop), one main content slot and the four generic
// page states, selected with viewState:
//   Ready       — `content` (default slot) is shown
//   Empty       — centered `emptyText` in textSecondary
//   Loading     — the `loading` Component, or an indeterminate
//                 AppProgressIndicator default
//   Error       — centered `errorText` in Theme.error
//   BackendDown — the `backendDown` Component, or a centered warning note
//                 with `backendDownText` (default 处理引擎未连接)
//
// topLeft/topRight are corner overlay slots (zoom HUD, view toggles). They
// stay instantiated and visible in every state — gate their children at the
// call site if a state should hide them.
//
// The shell is passive; §4 interactive states belong to the slotted content.
Rectangle {
    id: root

    enum ViewState { Ready, Empty, Loading, Error, BackendDown }

    property int viewState: AppWorkspaceLayout.ViewState.Ready

    property string emptyText: ""
    property string errorText: ""
    property string backendDownText: qsTr("处理引擎未连接")

    property Component loading: null
    property Component backendDown: null

    default property alias content: contentArea.data
    property alias topLeft: topLeftSlot.data
    property alias topRight: topRightSlot.data

    color: Theme.canvasBackdrop

    // ---- main content area -------------------------------------------------
    Item {
        id: contentArea
        anchors.fill: parent
        visible: root.viewState === AppWorkspaceLayout.ViewState.Ready
    }

    // ---- corner overlays (declared after contentArea → drawn on top) ------
    Item {
        id: topLeftSlot
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: Theme.spacingMd
    }

    Item {
        id: topRightSlot
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: Theme.spacingMd
    }

    // ---- generic page states (ui-page-spec.md §6) --------------------------
    Item {
        anchors.fill: parent
        visible: root.viewState === AppWorkspaceLayout.ViewState.Empty

        Label {
            anchors.centerIn: parent
            width: parent.width - Theme.spacingXl * 2
            visible: root.emptyText !== ""
            text: root.emptyText
            font.pixelSize: Theme.fontSizeBody
            color: Theme.textSecondary
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Item {
        anchors.fill: parent
        visible: root.viewState === AppWorkspaceLayout.ViewState.Loading

        Loader {
            anchors.centerIn: parent
            sourceComponent: root.loading
            visible: root.loading !== null
        }

        AppProgressIndicator {
            anchors.centerIn: parent
            indeterminate: true
            visible: root.loading === null
        }
    }

    Item {
        anchors.fill: parent
        visible: root.viewState === AppWorkspaceLayout.ViewState.Error

        Label {
            anchors.centerIn: parent
            width: parent.width - Theme.spacingXl * 2
            visible: root.errorText !== ""
            text: root.errorText
            font.pixelSize: Theme.fontSizeBody
            color: Theme.error
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Item {
        anchors.fill: parent
        visible: root.viewState === AppWorkspaceLayout.ViewState.BackendDown

        Loader {
            anchors.centerIn: parent
            sourceComponent: root.backendDown
            visible: root.backendDown !== null
        }

        Label {
            anchors.centerIn: parent
            width: parent.width - Theme.spacingXl * 2
            visible: root.backendDown === null
            text: root.backendDownText
            font.pixelSize: Theme.fontSizeBody
            color: Theme.warning
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
