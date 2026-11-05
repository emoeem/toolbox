import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Shader Studio (Phase 1 nav target). GLSL editor + live GL preview arrive in
// Phase 6; real OpenGL session validation happens on the Linux target only.
Page {
    background: Rectangle { color: Theme.background }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingSm

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("Shader Studio")
            font.pixelSize: Theme.fontSizeTitle
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("计划状态：P1 · 随 Phase 6 交付（GLSL 编辑器、uniform 面板、GL 预览）")
            font.pixelSize: Theme.fontSizeBody
            color: Theme.textSecondary
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("真实图形会话验证在 Linux 目标环境执行（总纲 §13）")
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.textDisabled
        }
    }
}
