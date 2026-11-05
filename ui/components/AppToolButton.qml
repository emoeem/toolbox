import QtQuick
import QtQuick.Controls

// Toolbar button wrapping ToolButton (ui-component-spec.md §1 ToolButton).
// checkable/checked/autoExclusive come from the base type; the checked state
// uses an accent fill with onAccent content. Automatic hover tooltip with
// the uniform 500ms delay via AppTooltip.
//
// icon.name renders through Qt's platform icon theme until the bundled
// Lucide set is wired up (ui-design-system.md §5).
ToolButton {
    id: root

    property string tooltipText: ""

    opacity: root.enabled ? 1.0 : 0.4  // design-system §4 Disabled
    display: AbstractButton.IconOnly

    palette.buttonText: root.checked ? Theme.onAccent : Theme.textPrimary
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

    AppTooltip {
        id: tip
    }

    background: Item {
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusSm
            // Pressed stays visible inside the checked state too: the accent
            // fill deepens to accentPressed (the pressed-accent token used by
            // AppButton's primary) instead of short-circuiting the ternary.
            color: root.checked ? (root.pressed ? Theme.accentPressed : Theme.accent)
                 : root.pressed ? Qt.darker(Theme.surfaceElevated, 1.08)
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
}
