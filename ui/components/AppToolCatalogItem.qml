import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Tool catalog card (ui-component-spec.md §3 ToolCatalogItem) bound to the
// ToolModel roles — exact roleNames from native/models/tool_model.cpp:73-83,
// declared as required properties so ListView/GridView { model:
// Application.toolModel } wires the card automatically:
//   toolId / title / category / available / phase.
//
// Emits clicked(clickedToolId) — only for available tools (§3: 进入对应工具流
// is the call site's job). Unavailable tools render grayed out (§4 Disabled:
// textDisabled, no hover/cursor feedback) and show a hover tooltip; the
// default reason text mirrors HomePage ("随 P2 提供", product IA §5).
//
// Category renders as a bordered badge, phase as a small trailing label.
// The icon slot is intentionally absent until the licensed Lucide set lands
// (ui-design-system.md §5) — no fake glyphs.
Rectangle {
    id: root

    required property string toolId
    required property string title
    required property string category
    required property bool available
    required property string phase

    property string unavailableText: qsTr("随 %1 提供").arg(root.phase)

    signal clicked(string clickedToolId)

    implicitWidth: 200
    implicitHeight: cardColumn.implicitHeight + Theme.spacingMd * 2

    radius: Theme.radiusMd
    color: root.available && cardHover.hovered ? Theme.surfaceElevated : Theme.surface
    border.width: 1
    border.color: root.available && cardHover.hovered ? Theme.borderStrong : Theme.border

    HoverHandler {
        id: cardHover
        cursorShape: root.available ? Qt.PointingHandCursor : Qt.ArrowCursor
        onHoveredChanged: {
            if (!root.available && hovered && root.unavailableText !== "") {
                cardTip.open(root.unavailableText, 0, root.height + Theme.spacingXs);
            } else if (!hovered) {
                cardTip.close();
            }
        }
    }

    TapHandler {
        onTapped: {
            if (root.available)
                root.clicked(root.toolId);
        }
    }

    // §4 Focus — keyboard activation for available tools; mouse taps do not
    // take focus, so the accent ring is keyboard-only.
    activeFocusOnTab: root.available

    Keys.onSpacePressed: (event) => {
        event.accepted = true;
        if (root.available)
            root.clicked(root.toolId);
    }
    Keys.onReturnPressed: (event) => {
        event.accepted = true;
        if (root.available)
            root.clicked(root.toolId);
    }
    Keys.onEnterPressed: (event) => {
        event.accepted = true;
        if (root.available)
            root.clicked(root.toolId);
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: -2
        radius: Theme.radiusMd + 2
        color: "transparent"
        border.color: Theme.accent
        border.width: 2
        visible: root.activeFocus && root.available
    }

    AppTooltip { id: cardTip }

    ColumnLayout {
        id: cardColumn
        anchors.fill: parent
        anchors.margins: Theme.spacingMd
        spacing: Theme.spacingXs

        Label {
            Layout.fillWidth: true
            text: root.title
            font.pixelSize: Theme.fontSizeBody
            font.weight: Font.DemiBold
            color: root.available ? Theme.textPrimary : Theme.textDisabled
            elide: Text.ElideRight
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingSm

            Rectangle {  // category badge
                visible: root.category !== ""
                width: badgeLabel.implicitWidth + Theme.spacingSm * 2
                height: badgeLabel.implicitHeight + Theme.spacingXs * 2
                radius: Theme.radiusSm
                color: "transparent"
                border.color: Theme.border
                border.width: 1

                Label {
                    id: badgeLabel
                    anchors.centerIn: parent
                    text: root.category
                    font.pixelSize: Theme.fontSizeSmall
                    color: root.available ? Theme.textSecondary : Theme.textDisabled
                }
            }

            Item { Layout.fillWidth: true }

            Label {
                visible: root.phase !== ""
                text: root.phase
                font.pixelSize: Theme.fontSizeSmall
                color: root.available ? Theme.textSecondary : Theme.textDisabled
                Layout.alignment: Qt.AlignVCenter
            }
        }
    }
}
