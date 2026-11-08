import Toolbox
import QtQuick
import QtQuick.Controls

// Themed single-line text input (ui-component-spec.md §1 TextField).
// States (ui-design-system.md §4):
// - Default: surfaceElevated fill + borderStrong stroke (§2.1: pre-focus
//   high-contrast stroke for inputs)
// - Focus: 2px accent ring, keyboard only (visualFocus — a mouse click
//   focuses without the ring)
// - Disabled: 40% opacity over textDisabled palette
TextField {
    id: root

    opacity: root.enabled ? 1.0 : 0.4
    color: Theme.textPrimary
    placeholderTextColor: Theme.textSecondary
    selectionColor: Theme.accent
    selectedTextColor: Theme.onAccent
    font.pixelSize: Theme.fontSizeBody

    background: Item {
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusSm
            color: Theme.surfaceElevated
            border.width: 1
            border.color: root.visualFocus ? Theme.accent : Theme.borderStrong

            Behavior on border.color {
                ColorAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
            }
        }

        // 2px accent focus ring — concentric geometry outside the fill.
        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: Theme.radiusSm + 2
            color: "transparent"
            border.color: Theme.accent
            border.width: 2
            visible: root.activeFocus
        }
    }
}
