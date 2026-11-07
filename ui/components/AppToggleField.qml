import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Toggle row (ui-component-spec.md §1 ToggleField): a switch + label where
// the whole row is clickable. Wraps ItemDelegate, so checked/toggled() and
// Space/Enter activation come from the base type.
//
// States (design-system §4): Default / Hover+Pressed (row fill) / Focus
// (ring around the switch, keyboard only) / Disabled (40% opacity +
// textDisabled label).
ItemDelegate {
    id: root

    checkable: true
    opacity: root.enabled ? 1.0 : 0.4

    implicitWidth: contentItem.implicitWidth + leftPadding + rightPadding
    implicitHeight: 36
    leftPadding: Theme.spacingMd
    rightPadding: Theme.spacingMd
    topPadding: 0
    bottomPadding: 0

    HoverHandler {
        cursorShape: Qt.PointingHandCursor
    }

    // design-system §4: Space toggles natively (ButtonPressKeys);
    // Enter/Return toggle here so activation does not depend on the platform
    // theme. Accepted here (Keys.BeforeItem) → single toggle.
    Keys.onReturnPressed: (event) => {
        event.accepted = true;
        root.checked = !root.checked;
        root.toggled();
        root.clicked();
    }
    Keys.onEnterPressed: (event) => {
        event.accepted = true;
        root.checked = !root.checked;
        root.toggled();
        root.clicked();
    }

    background: Rectangle {
        radius: Theme.radiusMd
        color: root.pressed ? Qt.darker(Theme.surfaceElevated, 1.08)
             : root.hovered ? Theme.surfaceElevated : "transparent"

        Behavior on color {
            ColorAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
        }
    }

    contentItem: RowLayout {
        spacing: Theme.spacingMd

        Label {
            Layout.fillWidth: true
            text: root.text
            font.pixelSize: Theme.fontSizeBody
            color: root.enabled ? Theme.textPrimary : Theme.textDisabled
            elide: Text.ElideRight
        }

        // Switch indicator. The track is a pill: radius derives from the
        // control height (geometric requirement, not a palette constant).
        Item {
            Layout.preferredWidth: 36
            Layout.preferredHeight: 20
            Layout.alignment: Qt.AlignVCenter

            Rectangle {
                anchors.fill: parent
                radius: height / 2
                color: root.checked ? Theme.accent : Theme.surfaceElevated
                border.width: root.checked ? 0 : 1
                border.color: Theme.border

                Behavior on color {
                    ColorAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
                }
            }

            Rectangle {
                id: handle
                width: 16
                height: 16
                radius: 8  // circular knob derived from its own size
                y: (parent.height - height) / 2
                x: root.checked ? parent.width - width - 2 : 2
                color: root.checked ? Theme.onAccent : Theme.surface

                Behavior on x {
                    NumberAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
                }
            }

            // Focus ring around the switch (the interactive affordance).
            Rectangle {
                anchors.fill: parent
                anchors.margins: -2
                radius: parent.height / 2 + 2
                color: "transparent"
                border.color: Theme.accent
                border.width: 2
                visible: root.visualFocus && root.enabled
            }
        }
    }
}
