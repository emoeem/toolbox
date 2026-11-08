import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Main window shell (Phase 4): AppWorkspaceLayout as the workspace skeleton,
// AppTopToolbar (identity + theme), AppStatusBar (live backend state + task
// drawer trigger) and the AppTaskQueuePanel drawer above the status bar.
// Page routing stays the Phase 2 Loader + Application.currentPage so pages
// remain decoupled from shell internals.
ApplicationWindow {
    id: window

    minimumWidth: Theme.minWindowWidth
    minimumHeight: Theme.minWindowHeight
    width: 1280
    height: 800
    visible: true
    title: qsTr("Toolbox 2.0")
    color: Theme.background

    // 全局退出快捷键（phase4-acceptance §3 验收项；applicationWindow 自带
    // 关闭流程会触发真实窗口关闭，不绕过未保存文档检查）。
    Shortcut {
        sequence: "Ctrl+Q"
        onActivated: window.close()
    }

    // Theme index of the persisted mode: dark=0 / light=1 / system=2.
    function themeIndex() {
        const mode = SettingsService.themeMode;
        if (mode === "light")
            return 1;
        if (mode === "system")
            return 2;
        return 0;
    }

    // Theme.darkMode mirrors the persisted mode. The system branch is
    // resolved to dark for now — following the OS palette needs a platform
    // theme observer which is not wired yet (noted in the settings page too).
    function applyTheme() {
        Theme.darkMode = SettingsService.themeMode !== "light";
        themeSelector.currentIndex = themeIndex();
    }

    Component.onCompleted: applyTheme()

    Connections {
        target: SettingsService
        function onThemeModeChanged() { window.applyTheme() }
    }

    AppTopToolbar {
        id: topBar

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right

        Label {
            text: qsTr("Toolbox 2.0")
            font.pixelSize: Theme.fontSizeHeading
            font.weight: Font.DemiBold
            color: Theme.textPrimary
            Layout.alignment: Qt.AlignVCenter
        }

        contentRight: [
            AppSegmentedControl {
                id: themeSelector

                model: [qsTr("深色"), qsTr("浅色"), qsTr("系统")]
                Layout.alignment: Qt.AlignVCenter

                onActivated: (index) => {
                    const mode = index === 1 ? "light" : index === 2 ? "system" : "dark";
                    SettingsService.themeMode = mode;  // normalized + persisted by the service
                    window.applyTheme();
                }
            }
        ]
    }

    // Workspace skeleton: Ready state hosts the routed page; the four generic
    // states belong to the pages themselves (ui-page-spec.md §6).
    AppWorkspaceLayout {
        id: workspace

        anchors.top: topBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: statusBar.top

        Loader {
            id: pageLoader
            objectName: "pageLoader"
            anchors.fill: parent
            source: Application.currentPage
        }
    }

    // Live worker state (BackendManager::state string) on the left; the task
    // drawer trigger on the right (ui-component-spec.md §2 StatusBar).
    AppStatusBar {
        id: statusBar

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        leftText: qsTr("后端 %1").arg(backendStateLabel())

        function backendStateLabel() {
            switch (Application.backend.state) {
            case "idle": return qsTr("未启动");
            case "starting": return qsTr("启动中");
            case "handshaking": return qsTr("握手中");
            case "ready": return qsTr("就绪");
            case "crashed": return qsTr("已崩溃");
            case "stopped": return qsTr("已停止");
            default: return Application.backend.state;
            }
        }

        AppButton {
            kind: AppButton.Kind.Ghost
            size: AppButton.Size.Small
            text: taskPanel.count > 0 ? qsTr("任务 · %1").arg(taskPanel.count) : qsTr("任务")
            onClicked: taskPanel.expanded = !taskPanel.expanded
        }
    }

    // Bottom task drawer, revealed by the status-bar 任务 button. Hidden
    // entirely while collapsed — the drawer's own chevron collapses it back
    // to invisible; the status bar button reopens it.
    AppTaskQueuePanel {
        id: taskPanel

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: statusBar.top
        z: 1
        visible: expanded
        model: Application.taskModel
    }
}
