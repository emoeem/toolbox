import QtQuick
import QtQuick.Controls

// Search input (ui-component-spec.md §1 SearchField): placeholder, clear
// affordance (button + Esc) and a 300ms debounced searched(string).
// Return/Enter flushes the debounce and emits immediately.
// Global Ctrl+K focus arrives with the command palette phase — Main.qml has
// no such binding yet (spec deviation, see ui-component-spec.md §1).
TextField {
    id: root

    signal searched(string query)

    // ui-component-spec.md §1: 300ms 防抖.
    readonly property int debounceMs: 300

    opacity: root.enabled ? 1.0 : 0.4
    color: Theme.textPrimary
    placeholderTextColor: Theme.textSecondary
    selectionColor: Theme.accent
    selectedTextColor: Theme.onAccent
    font.pixelSize: Theme.fontSizeBody

    implicitHeight: 32
    leftPadding: Theme.spacingMd
    rightPadding: clearButton.visible ? 32 : Theme.spacingMd

    onTextEdited: debounce.restart()

    Keys.onEscapePressed: (event) => {
        event.accepted = true;
        root.clearQuery();
    }
    Keys.onReturnPressed: (event) => {
        event.accepted = true;
        debounce.stop();
        root.searched(root.text);
    }
    Keys.onEnterPressed: (event) => {
        event.accepted = true;
        debounce.stop();
        root.searched(root.text);
    }

    function clearQuery() {
        root.clear();
        debounce.stop();
        root.searched(root.text);
    }

    Timer {
        id: debounce
        interval: root.debounceMs
        onTriggered: root.searched(root.text)
    }

    // Clear affordance: the × is drawn directly (no icon-theme dependency).
    Item {
        id: clearButton
        visible: root.text.length > 0 && !root.readOnly && root.enabled
        anchors.right: parent.right
        anchors.rightMargin: Theme.spacingXs
        anchors.verticalCenter: parent.verticalCenter
        width: 20
        height: 20

        MouseArea {
            id: clearArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.clearQuery()
        }

        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusSm
            color: clearArea.containsMouse ? Theme.surfaceElevated : "transparent"
        }

        Canvas {
            anchors.centerIn: parent
            width: 12
            height: 12
            property color glyphColor: clearArea.containsMouse ? Theme.textPrimary : Theme.textSecondary
            onGlyphColorChanged: requestPaint()
            onPaint: {
                const ctx = getContext("2d");
                ctx.reset();
                ctx.strokeStyle = glyphColor.toString();
                ctx.lineWidth = 1.5;  // icon stroke width per design-system §5
                ctx.lineCap = "round";
                ctx.beginPath();
                ctx.moveTo(3, 3);
                ctx.lineTo(9, 9);
                ctx.moveTo(9, 3);
                ctx.lineTo(3, 9);
                ctx.stroke();
            }
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
            visible: root.visualFocus
        }
    }
}
