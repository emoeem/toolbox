import Toolbox
import QtQuick
import QtQuick.Controls

// Icon-only action button with an optional badge and an automatic hover
// tooltip (ui-component-spec.md §1 IconButton).
//
// icon.name renders through Qt's platform icon theme until the bundled
// Lucide set is wired up (ui-design-system.md §5) — with a theme that lacks
// the named icon the button shows no glyph but stays functional.
//
// Badge uses accent + onAccent: it marks attention (e.g. task counts), not
// error state.
AbstractButton {
    id: root

    readonly property alias badge: badgeData
    property string tooltipText: ""

    opacity: root.enabled ? 1.0 : 0.4  // design-system §4 Disabled
    display: AbstractButton.IconOnly

    palette.buttonText: root.hovered ? Theme.textPrimary : Theme.textSecondary
    palette.text: palette.buttonText

    implicitWidth: 32
    implicitHeight: 32
    leftPadding: 0
    rightPadding: 0
    topPadding: 0
    bottomPadding: 0

    HoverHandler {
        id: tooltipHover
        cursorShape: Qt.PointingHandCursor
        onHoveredChanged: {
            if (hovered && root.tooltipText !== "") {
                tip.open(root.tooltipText,
                         (root.width - tip.implicitWidth) / 2,
                         root.height + Theme.spacingXs);
            } else if (!hovered) {
                tip.close();
            }
        }
    }

    // design-system §4: Space activates natively (ButtonPressKeys);
    // Enter/Return are handled here so activation does not depend on the
    // platform theme. Accepted here (Keys.BeforeItem) → single activation.
    Keys.onReturnPressed: (event) => {
        event.accepted = true;
        root.clicked();
    }
    Keys.onEnterPressed: (event) => {
        event.accepted = true;
        root.clicked();
    }

    QtObject {
        id: badgeData
        property string text: ""
    }

    AppTooltip {
        id: tip
    }

    background: Item {
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusSm
            color: root.pressed ? Qt.darker(Theme.surfaceElevated, 1.08)
                 : root.hovered ? Theme.surfaceElevated : "transparent"

            Behavior on color {
                ColorAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
            }
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: Theme.radiusSm + 2
            color: "transparent"
            border.color: Theme.accent
            border.width: 2
            visible: root.visualFocus && root.enabled
        }
    }

    Rectangle {
        visible: badgeData.text !== ""
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.rightMargin: -Theme.spacingXs
        anchors.topMargin: -Theme.spacingXs
        width: badgeLabel.implicitWidth + Theme.spacingSm
        height: Theme.fontSizeSmall + Theme.spacingSm
        radius: Theme.radiusSm
        color: Theme.accent
        border.color: Theme.surface
        border.width: 1

        Label {
            id: badgeLabel
            anchors.centerIn: parent
            text: badgeData.text
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.onAccent
        }
    }
}
