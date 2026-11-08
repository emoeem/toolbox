import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Themed context menu wrapping Menu (ui-component-spec.md §1 ContextMenu):
// 28px item height, right-aligned shortcut labels, accent highlight for
// keyboard navigation.
//
// Theming applies to the `delegate`, i.e. items created via addAction() /
// addItem() / the menu model. Items declared inline as children of the menu
// are real objects and keep the base style — build menus dynamically (or
// with Actions) to get the themed look. Right-aligned shortcut labels come
// from each item's bound Action (`action.shortcut`).
Menu {
    id: root

    padding: Theme.spacingXs

    background: Rectangle {
        implicitWidth: 200
        color: Theme.surfaceElevated
        radius: Theme.radiusMd
        border.color: Theme.border
        border.width: 1
    }

    delegate: MenuItem {
        id: menuItem

        height: 28  // spec §1: 菜单项统一高度 28px
        font.pixelSize: Theme.fontSizeBody

        // Shortcut display: MenuItem itself has no `shortcut` property; for
        // action-driven items (addAction) the label comes from the bound
        // Action's keysequence shortcut. Non-string variant values degrade
        // to a hidden label instead of guessing a rendering.
        readonly property string shortcutLabel: {
            const sc = menuItem.action ? menuItem.action.shortcut : null;
            if (sc === undefined || sc === null || sc === "")
                return "";
            if (typeof sc === "string")
                return sc;
            try {
                const s = sc.toString();
                if (s && s !== "[object Object]")
                    return s;
            } catch (e) {
            }
            return "";
        }

        contentItem: RowLayout {
            spacing: Theme.spacingMd

            Label {
                Layout.fillWidth: true
                text: menuItem.text
                font: menuItem.font
                color: menuItem.highlighted ? Theme.onAccent
                     : menuItem.enabled ? Theme.textPrimary : Theme.textDisabled
                elide: Text.ElideRight
            }

            Label {
                visible: menuItem.shortcutLabel !== ""
                text: menuItem.shortcutLabel
                font.pixelSize: Theme.fontSizeSmall
                color: menuItem.highlighted ? Theme.onAccent : Theme.textSecondary
                horizontalAlignment: Text.AlignRight
            }
        }

        background: Rectangle {
            radius: Theme.radiusSm
            color: menuItem.highlighted ? Theme.accent
                 : menuItem.hovered && menuItem.enabled ? Theme.surfaceElevated
                 : "transparent"

            Behavior on color {
                ColorAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
            }
        }
    }
}
