import QtQuick
import QtQuick.Controls

// Themed select wrapping ComboBox (ui-component-spec.md §1 SelectField):
// model / textRole / currentIndex / count / displayText come from the base
// type. The popup uses surfaceElevated + radius.md per the spec; the
// highlighted item uses accent + onAccent (design-system §4).
ComboBox {
    id: root

    opacity: root.enabled ? 1.0 : 0.4  // design-system §4 Disabled

    implicitWidth: 160  // default; callers stretch via width/Layout.fillWidth
    implicitHeight: 32

    delegate: ItemDelegate {
        id: selectItem
        width: root.width
        height: 32
        highlighted: root.highlightedIndex === index

        contentItem: Label {
            text: selectItem.text
            font.pixelSize: Theme.fontSizeBody
            color: selectItem.highlighted ? Theme.onAccent
                 : selectItem.enabled ? Theme.textPrimary : Theme.textDisabled
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }

        background: Rectangle {
            radius: Theme.radiusSm
            color: selectItem.highlighted ? Theme.accent
                 : selectItem.hovered && selectItem.enabled ? Theme.surfaceElevated
                 : "transparent"

            Behavior on color {
                ColorAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
            }
        }
    }

    // Chevron drawn directly (no icon-theme dependency).
    indicator: Canvas {
        x: root.width - width - Theme.spacingMd
        y: (root.height - height) / 2
        width: 12
        height: 8
        property color glyphColor:
            root.enabled ? (root.hovered ? Theme.textPrimary : Theme.textSecondary)
                         : Theme.textDisabled
        onGlyphColorChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            ctx.strokeStyle = glyphColor.toString();
            ctx.lineWidth = 1.5;  // icon stroke width per design-system §5
            ctx.lineCap = "round";
            ctx.beginPath();
            ctx.moveTo(2, 2);
            ctx.lineTo(6, 6);
            ctx.lineTo(10, 2);
            ctx.stroke();
        }
    }

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

    contentItem: Item {
        implicitWidth: displayLabel.implicitWidth + 24
        implicitHeight: displayLabel.implicitHeight

        Label {
            id: displayLabel
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 24
            text: root.displayText
            font.pixelSize: Theme.fontSizeBody
            color: root.enabled ? Theme.textPrimary : Theme.textDisabled
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
    }

    popup: Popup {
        y: root.height + Theme.spacingXs
        width: root.width
        // Show at most 8 items before scrolling (item height 32 + padding).
        implicitHeight: Math.min(contentItem.implicitHeight + topPadding + bottomPadding,
                                 8 * 32 + 2 * Theme.spacingXs)

        background: Rectangle {
            color: Theme.surfaceElevated
            radius: Theme.radiusMd  // spec §1: 弹层用 surfaceElevated + radius.md
            border.color: Theme.border
            border.width: 1
        }

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: root.popup.visible ? root.delegateModel : null
            currentIndex: root.highlightedIndex

            ScrollIndicator.vertical: ScrollIndicator {}
        }
    }
}
