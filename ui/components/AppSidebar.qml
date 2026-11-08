import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Navigation rail (Phase 2: text-only entries; icons arrive with the licensed
// icon set in Phase 4 — see ui-design-system.md §5).
//
// Highlight is derived from Application.currentPage directly (no
// ListView.currentIndex round-trip), so navigation state has one owner.
Rectangle {
    id: sidebar

    width: Theme.navRailWidthExpanded
    color: Theme.surface

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ListView {
            id: navList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: Application.navModel
            clip: true

            delegate: ItemDelegate {
                id: navItem

                readonly property bool isCurrent: model.page === Application.currentPage

                width: ListView.view.width
                height: 40
                enabled: model.available

                background: Rectangle {
                    radius: Theme.radiusMd
                    color: {
                        if (navItem.isCurrent)
                            return Theme.accent
                        if (navItem.enabled && navItem.hovered)
                            return Theme.surfaceElevated
                        return "transparent"
                    }
                }

                contentItem: RowLayout {
                    spacing: Theme.spacingSm

                    Label {
                        Layout.fillWidth: true
                        text: model.title
                        font.pixelSize: Theme.fontSizeBody
                        elide: Text.ElideRight
                        color: {
                            if (navItem.isCurrent)
                                return Theme.onAccent
                            if (!model.available)
                                return Theme.textDisabled
                            return Theme.textPrimary
                        }
                    }

                    Label {
                        text: model.phase
                        font.pixelSize: Theme.fontSizeSmall
                        color: navItem.isCurrent ? Theme.onAccent : Theme.textSecondary
                    }
                }

                onClicked: Application.navigate(model.navId)
            }

            ScrollIndicator.vertical: ScrollIndicator {}
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
        }

        Label {
            Layout.margins: Theme.spacingMd
            text: qsTr("P2 项随 Phase 7 提供")
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.textDisabled
        }
    }

    Rectangle {
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: 1
        color: Theme.border
    }
}
