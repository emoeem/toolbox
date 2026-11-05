import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Main window shell (Phase 2 prototype).
// Phase 2 scope: token-driven shell, navigation rail, page routing, theme
// switching. The editor toolbar, inspector and task panel arrive in Phase 4.
ApplicationWindow {
    id: window

    minimumWidth: Theme.minWindowWidth
    minimumHeight: Theme.minWindowHeight
    width: 1280
    height: 800
    visible: true
    title: qsTr("Toolbox 2.0 — 原型")
    color: Theme.background

    RowLayout {
        anchors.fill: parent
        spacing: 0

        AppSidebar {
            Layout.fillHeight: true
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Minimal header: identity + theme switch (real, functional).
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Theme.toolbarHeight
                color: Theme.surface

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingLg
                    anchors.rightMargin: Theme.spacingLg

                    Label {
                        text: qsTr("Toolbox 2.0")
                        font.pixelSize: Theme.fontSizeHeading
                        font.weight: Font.DemiBold
                        color: Theme.textPrimary
                    }

                    Item { Layout.fillWidth: true }

                    Label {
                        text: qsTr("Phase 2 技术原型 · 处理引擎未接入（Phase 3）")
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textSecondary
                    }

                    Button {
                        id: themeButton
                        text: Theme.darkMode ? qsTr("浅色主题") : qsTr("深色主题")
                        onClicked: Theme.darkMode = !Theme.darkMode
                    }
                }

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: Theme.border
                }
            }

            // Page router. Pages are same-module types; Loader keeps pages
            // independent so navigation stays decoupled from page internals.
            Loader {
                id: pageLoader
                Layout.fillWidth: true
                Layout.fillHeight: true
                source: Application.currentPage
            }

            // StatusBar placeholder uses real tokens; live data lands in Phase 4.
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Theme.statusBarHeight
                color: Theme.surface

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: Theme.spacingLg
                    text: qsTr("就绪 · 任务队列 Phase 3 接入")
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textSecondary
                }

                Rectangle {
                    anchors.top: parent.top
                    width: parent.width
                    height: 1
                    color: Theme.border
                }
            }
        }
    }
}
