import QtQuick
import QtQuick.Controls

// Themed tooltip popup (ui-component-spec.md §1 Tooltip):
// typography.small text, visible border in both themes, uniform 500ms show
// delay applied inside open().
//
// open(text, x, y) shadows Popup's no-arg open(): all arguments are optional
// — open() alone shows the current text at the current position after the
// delay. x/y are relative to the popup's parent item. close() (also shadowed)
// cancels a pending delayed show and hides immediately.
//
// The 500ms hover→show delay is centralized here so every hover user gets
// the spec'd uniform delay without per-call-site timers.
Popup {
    id: root

    property string text: ""

    // ui-component-spec.md §1: 统一延迟 500ms.
    readonly property int showDelayMs: 500

    closePolicy: Popup.NoAutoClose
    dim: false

    topPadding: Theme.spacingSm
    bottomPadding: Theme.spacingSm
    leftPadding: Theme.spacingMd
    rightPadding: Theme.spacingMd

    implicitWidth: Math.min(contentItem.implicitWidth + leftPadding + rightPadding, 320)
    implicitHeight: contentItem.implicitHeight + topPadding + bottomPadding

    background: Rectangle {
        color: Theme.surfaceElevated
        radius: Theme.radiusSm
        border.color: Theme.border
        border.width: 1
    }

    contentItem: Label {
        text: root.text
        font.pixelSize: Theme.fontSizeSmall
        color: Theme.textPrimary
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
    }

    Timer {
        id: showTimer
        interval: root.showDelayMs
        onTriggered: root.visible = true
    }

    function open(text, x, y) {
        if (text !== undefined)
            root.text = text;
        if (x !== undefined)
            root.x = x;
        if (y !== undefined)
            root.y = y;
        showTimer.restart();
    }

    function close() {
        showTimer.stop();
        root.visible = false;
    }
}
