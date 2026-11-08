import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Right-hand inspector shell (ui-component-spec.md §2 InspectorPanel):
// - fixed width Theme.inspectorWidth; `collapsed` swaps to a slim expand
//   strip (28px chevron button + spacingSm gutters) with a motion.normal
//   width animation — persist `collapsed` at the call site
//   (layout/inspectorCollapsed), the component writes no settings;
// - `tabs` is a JS array of { id, title } objects (plain strings are also
//   accepted, id = title); currentIndex selects the tab, currentTabId reads
//   it back, ←/→ move the selection while the tab strip has focus;
// - the default slot is the tab body, placed inside a vertically scrollable
//   container (spec: 内部滚动); group content with AppSectionGroup.
Rectangle {
    id: root

    property var tabs: []
    property int currentIndex: 0
    property bool collapsed: false

    readonly property string currentTabId: root.tabId(root.currentIndex)
    readonly property int collapsedWidth: 28 + Theme.spacingSm * 2

    default property alias content: bodyColumn.data

    implicitWidth: root.collapsed ? root.collapsedWidth : Theme.inspectorWidth

    Behavior on width {
        NumberAnimation { duration: Theme.motionNormal; easing.type: Easing.OutCubic }
    }

    color: Theme.surface

    function tabTitle(index) {
        const item = root.tabs[index];
        if (item === undefined || item === null)
            return "";
        if (typeof item === "string")
            return item;
        return item.title !== undefined ? String(item.title) : "";
    }

    function tabId(index) {
        const item = root.tabs[index];
        if (item === undefined || item === null)
            return "";
        if (typeof item === "string")
            return item;
        return item.id !== undefined ? String(item.id) : "";
    }

    function selectTab(index) {
        if (root.tabs.length === 0)
            return;
        const clamped = Math.max(0, Math.min(root.tabs.length - 1, index));
        root.currentIndex = clamped;
        const target = tabRepeater.itemAt(clamped);
        if (target)
            target.forceActiveFocus();
    }

    onTabsChanged: {
        if (root.currentIndex >= root.tabs.length)
            root.currentIndex = root.tabs.length > 0 ? root.tabs.length - 1 : 0;
    }

    // Chevron icon button shared by the collapse control and the expand
    // strip; §4 states: hover/pressed fill, 2px accent keyboard focus ring,
    // 40% opacity when disabled, hover tooltip via AppTooltip.
    component InspectorIconButton: AbstractButton {
        id: iconButton

        property real glyphRotation: 0
        property string tooltipText: ""

        width: 28
        height: 28
        opacity: iconButton.enabled ? 1.0 : 0.4

        HoverHandler {
            id: tipHover
            cursorShape: Qt.PointingHandCursor
            onHoveredChanged: {
                if (hovered && iconButton.tooltipText !== "") {
                    tip.open(iconButton.tooltipText,
                             (iconButton.width - tip.implicitWidth) / 2,
                             iconButton.height + Theme.spacingXs);
                } else if (!hovered) {
                    tip.close();
                }
            }
        }

        Keys.onReturnPressed: (event) => {
            event.accepted = true;
            iconButton.clicked();
        }
        Keys.onEnterPressed: (event) => {
            event.accepted = true;
            iconButton.clicked();
        }

        AppTooltip { id: tip }

        background: Item {
            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusSm
                color: iconButton.pressed ? Qt.darker(Theme.surfaceElevated, 1.08)
                     : iconButton.hovered ? Theme.surfaceElevated : "transparent"

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
                visible: iconButton.visualFocus && iconButton.enabled
            }
        }

        contentItem: Item {
            Canvas {
                anchors.centerIn: parent
                width: 12
                height: 12
                rotation: iconButton.glyphRotation

                Behavior on rotation {
                    NumberAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
                }

                property color glyphColor: iconButton.hovered ? Theme.textPrimary : Theme.textSecondary
                onGlyphColorChanged: requestPaint()

                onPaint: {
                    const ctx = getContext("2d");
                    ctx.reset();
                    ctx.strokeStyle = glyphColor.toString();
                    ctx.lineWidth = 1.5;
                    ctx.lineCap = "round";
                    ctx.beginPath();
                    ctx.moveTo(4.5, 3);
                    ctx.lineTo(7.5, 6);
                    ctx.lineTo(4.5, 9);
                    ctx.stroke();
                }
            }
        }
    }

    Column {
        anchors.fill: parent
        spacing: 0

        Item {
            id: header
            width: parent.width
            height: 28 + Theme.spacingSm * 2
            visible: !root.collapsed

            Flickable {
                id: tabsScroll
                anchors.left: parent.left
                anchors.right: collapseButton.left
                anchors.leftMargin: Theme.spacingSm
                anchors.rightMargin: Theme.spacingSm
                anchors.verticalCenter: parent.verticalCenter
                height: 28
                contentWidth: tabsRow.width
                contentHeight: height
                clip: true
                interactive: contentWidth > width

                Row {
                    id: tabsRow
                    spacing: Theme.spacingXs

                    Repeater {
                        id: tabRepeater
                        model: root.tabs

                        delegate: AbstractButton {
                            id: tabButton

                            required property int index

                            readonly property bool isSelected: root.currentIndex === tabButton.index

                            width: tabLabel.implicitWidth + Theme.spacingMd * 2
                            height: 28
                            focusPolicy: Qt.StrongFocus

                            background: Rectangle {
                                radius: Theme.radiusMd
                                color: tabButton.isSelected ? Theme.accent
                                     : tabButton.pressed ? Qt.darker(Theme.surfaceElevated, 1.08)
                                     : tabButton.hovered ? Theme.surfaceElevated : "transparent"

                                Behavior on color {
                                    ColorAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
                                }
                            }

                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: -2
                                radius: Theme.radiusMd + 2
                                color: "transparent"
                                border.color: Theme.accent
                                border.width: 2
                                visible: tabButton.visualFocus
                            }

                            contentItem: Label {
                                id: tabLabel
                                text: root.tabTitle(tabButton.index)
                                font.pixelSize: Theme.fontSizeBody
                                elide: Text.ElideRight
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                color: tabButton.isSelected ? Theme.onAccent
                                     : tabButton.hovered ? Theme.textPrimary : Theme.textSecondary
                            }

                            onClicked: root.currentIndex = tabButton.index

                            Keys.onLeftPressed: (event) => {
                                event.accepted = true;
                                root.selectTab(tabButton.index - 1);
                            }
                            Keys.onRightPressed: (event) => {
                                event.accepted = true;
                                root.selectTab(tabButton.index + 1);
                            }
                        }
                    }
                }

                ScrollIndicator.horizontal: ScrollIndicator {}
            }

            InspectorIconButton {
                id: collapseButton
                anchors.right: parent.right
                anchors.rightMargin: Theme.spacingSm
                anchors.verticalCenter: parent.verticalCenter
                tooltipText: qsTr("折叠检查器")
                onClicked: root.collapsed = true
            }
        }

        Flickable {
            id: bodyScroll
            width: parent.width
            height: parent.height - header.height
            visible: !root.collapsed
            clip: true
            contentWidth: width
            contentHeight: bodyColumn.height + Theme.spacingMd * 2

            Column {
                id: bodyColumn
                x: Theme.spacingLg
                y: Theme.spacingMd
                width: bodyScroll.width - Theme.spacingLg * 2
                spacing: Theme.spacingMd
            }

            ScrollIndicator.vertical: ScrollIndicator {}
        }

        InspectorIconButton {
            id: expandStrip
            width: parent.width
            height: root.height
            visible: root.collapsed
            glyphRotation: 180

            background: Item {
                Rectangle {
                    anchors.fill: parent
                    color: expandStrip.pressed ? Qt.darker(Theme.surfaceElevated, 1.08)
                         : expandStrip.hovered ? Theme.surfaceElevated : "transparent"

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
                    visible: expandStrip.visualFocus && expandStrip.enabled
                }
            }

            onClicked: root.collapsed = false
        }
    }
}
