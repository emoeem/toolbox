import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Texture Studio (Phase 1 nav target). Generator list, live parameters and
// tile preview arrive in Phase 6.
Page {
    background: Rectangle { color: Theme.background }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingSm

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("Texture Studio")
            font.pixelSize: Theme.fontSizeTitle
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("计划状态：P1 · 随 Phase 6 交付（生成器、参数、平铺预览、导出）")
            font.pixelSize: Theme.fontSizeBody
            color: Theme.textSecondary
        }
    }
}
