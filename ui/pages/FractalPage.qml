import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Fractal Studio (Phase 1 nav target for the Create category). Parameter
// panel, preview canvas and preset management arrive in Phase 6.
Page {
    background: Rectangle { color: Theme.background }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingSm

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("Fractal Studio")
            font.pixelSize: Theme.fontSizeTitle
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("计划状态：P1 · 随 Phase 6 交付（公式、着色、缩放导航、渲染取消）")
            font.pixelSize: Theme.fontSizeBody
            color: Theme.textSecondary
        }
    }
}
