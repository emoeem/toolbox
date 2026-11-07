import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Shared landing page for P2 categories (analyze / ai / files).
// Renders an honest "planned" state only — no placeholder forms, no fake
// buttons (master plan §3.4 / §9.8). These categories become real pages in
// Phase 7 and their entries are listed in docs/ui-migration-matrix.md.
Page {
    property string plannedTitle: qsTr("该分类")
    property string plannedPhase: qsTr("Phase 7")

    background: Rectangle { color: Theme.background }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingSm

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: plannedTitle
            font.pixelSize: Theme.fontSizeTitle
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("计划状态：%1 · 功能清单见 docs/ui-migration-matrix.md").arg(plannedPhase)
            font.pixelSize: Theme.fontSizeBody
            color: Theme.textSecondary
        }
    }
}
