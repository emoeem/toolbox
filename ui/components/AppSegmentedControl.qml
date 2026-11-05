import QtQuick
import QtQuick.Controls

// Exclusive segmented control (ui-component-spec.md §1 SegmentedControl,
// e.g. theme 深色/浅色/系统).
//
// API: model (JS array of strings, or objects with a textRole field),
// currentIndex, activated(index). The selected segment uses accent +
// onAccent (design-system §4); unselected segments use textSecondary.
//
// Keyboard: the control takes one Tab stop; ←/→ move the selection (each
// move emits activated), Space/Enter re-emit activated(currentIndex).
Control {
    id: root

    property var model: []
    property string textRole: "text"
    property int currentIndex: 0

    signal activated(int index)

    padding: Theme.spacingXs
    opacity: root.enabled ? 1.0 : 0.4
    // StrongFocus: clicking a segment also takes keyboard focus so ←/→ work
    // immediately after a click; visualFocus stays false for mouse focus.
    focusPolicy: Qt.StrongFocus

    implicitWidth: contentItem.implicitWidth + leftPadding + rightPadding
    implicitHeight: contentItem.implicitHeight + topPadding + bottomPadding

    function textAt(index) {
        const item = root.model[index];
        if (item === undefined || item === null)
            return "";
        if (typeof item === "string")
            return item;
        const roleValue = item[root.textRole];
        return roleValue !== undefined ? String(roleValue) : "";
    }

    function select(index) {
        if (root.model.length === 0)
            return;
        const i = Math.max(0, Math.min(root.model.length - 1, index));
        if (i !== root.currentIndex) {
            root.currentIndex = i;
            root.activated(i);
        }
    }

    Keys.onLeftPressed: (event) => {
        event.accepted = true;
        root.select(root.currentIndex - 1);
    }
    Keys.onRightPressed: (event) => {
        event.accepted = true;
        root.select(root.currentIndex + 1);
    }
    // Single generic handler so every key fires exactly once (specific
    // Keys signals could double-fire alongside `pressed`).
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Left) {
            event.accepted = true;
            root.select(root.currentIndex - 1);
        } else if (event.key === Qt.Key_Right) {
            event.accepted = true;
            root.select(root.currentIndex + 1);
        } else if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            event.accepted = true;
            if (root.currentIndex >= 0 && root.currentIndex < root.model.length)
                root.activated(root.currentIndex);
        }
    }

    background: Item {
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusMd
            color: Theme.surfaceElevated
            border.width: 1
            border.color: Theme.border
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: Theme.radiusMd + 2
            color: "transparent"
            border.color: Theme.accent
            border.width: 2
            visible: root.visualFocus && root.enabled
        }
    }

    contentItem: Row {
        spacing: Theme.spacingXs

        Repeater {
            model: root.model

            delegate: Item {
                id: segment
                required property int index

                width: segmentLabel.implicitWidth + Theme.spacingMd * 2
                height: 28

                readonly property bool isSelected: root.currentIndex === index
                readonly property bool isHovered: segmentHover.hovered && root.enabled

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusMd
                    color: segment.isSelected ? Theme.accent
                         : segment.isHovered ? Qt.darker(Theme.surfaceElevated, 1.12)
                         : "transparent"

                    Behavior on color {
                        ColorAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
                    }
                }

                Label {
                    id: segmentLabel
                    anchors.centerIn: parent
                    text: root.textAt(segment.index)
                    font.pixelSize: Theme.fontSizeBody
                    color: segment.isSelected ? Theme.onAccent
                         : segment.isHovered ? Theme.textPrimary : Theme.textSecondary
                }

                HoverHandler {
                    id: segmentHover
                }

                TapHandler {
                    onTapped: root.select(segment.index)
                }
            }
        }
    }
}
