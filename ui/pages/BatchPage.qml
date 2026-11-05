import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Batch workspace (Phase 1 nav target). Queue/file list/configuration are
// Phase 6 work (master plan Phase 6: Batch Processing); this page only proves
// routing and theming until then.
Page {
    background: Rectangle { color: Theme.background }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingSm

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("批量处理工作区")
            font.pixelSize: Theme.fontSizeTitle
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("计划状态：P1 · 随 Phase 6（滤镜与创作工作区）交付")
            font.pixelSize: Theme.fontSizeBody
            color: Theme.textSecondary
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("将包含：文件导入、任务队列、单项进度与取消、失败重试")
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.textDisabled
        }
    }
}
