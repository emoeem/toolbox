import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Settings page (Phase 2 prototype).
// Working now: theme switch, version/protocol info. The full settings model
// (fonts via font.diagnose, performance, backend management) lands in Phase 4
// together with SettingsService — fake controls would violate the honesty rule.
Page {
    id: page

    background: Rectangle { color: Theme.background }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingXl
        spacing: Theme.spacingLg

        Label {
            text: qsTr("设置")
            font.pixelSize: Theme.fontSizeTitle
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        // 外观（可用的部分）
        ColumnLayout {
            spacing: Theme.spacingSm

            Label {
                text: qsTr("外观")
                font.pixelSize: Theme.fontSizeHeading
                font.weight: Font.DemiBold
                color: Theme.textPrimary
            }

            RowLayout {
                spacing: Theme.spacingMd

                Label {
                    text: qsTr("主题")
                    font.pixelSize: Theme.fontSizeBody
                    color: Theme.textSecondary
                }

                Button {
                    checked: Theme.darkMode
                    text: checked ? qsTr("深色") : qsTr("浅色")
                    onClicked: Theme.darkMode = !Theme.darkMode
                }
            }

            Label {
                text: qsTr("字体选择与字号随 Phase 4（字体服务）提供，沿用 Phase 0 已修复的字体解析体系")
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textDisabled
            }
        }

        // 后端
        ColumnLayout {
            spacing: Theme.spacingSm

            Label {
                text: qsTr("后端")
                font.pixelSize: Theme.fontSizeHeading
                font.weight: Font.DemiBold
                color: Theme.textPrimary
            }

            RowLayout {
                spacing: Theme.spacingMd

                Rectangle {
                    width: 10
                    height: 10
                    radius: 5
                    color: Theme.textDisabled
                }

                Label {
                    text: qsTr("Python Worker：未接入（随 Phase 3 提供，协议版本 1）")
                    font.pixelSize: Theme.fontSizeBody
                    color: Theme.textSecondary
                }
            }
        }

        // 关于
        ColumnLayout {
            spacing: Theme.spacingSm

            Label {
                text: qsTr("关于")
                font.pixelSize: Theme.fontSizeHeading
                font.weight: Font.DemiBold
                color: Theme.textPrimary
            }

            Label {
                text: qsTr("Toolbox %1 · Qt %2 · UI: C++ / Qt Quick / QML").arg(Application.version).arg(Application.qtVersion)
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textSecondary
            }
        }

        Item { Layout.fillHeight: true }
    }
}
