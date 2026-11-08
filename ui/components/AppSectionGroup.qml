import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Collapsible parameter group (ui-component-spec.md §2 SectionGroup):
// chevron + 区块标题 (typography.heading per design-system §2.4) header row,
// default slot with the group content, revealed/collapsed with a
// motion.normal height animation (§2.5: 面板显隐).
//
// defaultExpanded seeds the initial state; persist the folded state at the
// call site if wanted — the component itself writes no settings.
//
// QML binding semantics, same caveat as AppButton.loading: an `expanded:`
// binding written at the instantiation site replaces the file's default
// `expanded: defaultExpanded` binding — include the seed there if needed
// (e.g. `expanded: settings.folded(id) === false && defaultExpanded`).
//
// §4 states live on the header row (hover/pressed/focus/disabled); the
// collapsed content is also disabled so hidden rows cannot take focus.
Column {
    id: root

    property string title: ""
    property bool defaultExpanded: true
    property bool expanded: defaultExpanded
    default property alias content: contentColumn.data

    spacing: 0

    AbstractButton {
        id: header
        width: root.width
        height: 32  // ui-component-spec.md §1 medium control height

        opacity: root.enabled ? 1.0 : 0.4  // design-system §4 Disabled
        leftPadding: Theme.spacingSm
        rightPadding: Theme.spacingSm

        HoverHandler { cursorShape: Qt.PointingHandCursor }

        Keys.onReturnPressed: (event) => {
            event.accepted = true;
            root.expanded = !root.expanded;
        }
        Keys.onEnterPressed: (event) => {
            event.accepted = true;
            root.expanded = !root.expanded;
        }

        background: Item {
            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusSm
                color: header.pressed ? Qt.darker(Theme.surfaceElevated, 1.08)
                     : header.hovered ? Theme.surfaceElevated : "transparent"

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
                visible: header.visualFocus && header.enabled
            }
        }

        contentItem: RowLayout {
            spacing: Theme.spacingSm

            Canvas {
                id: chevron
                width: 12
                height: 12
                Layout.alignment: Qt.AlignVCenter
                rotation: root.expanded ? 0 : -90

                Behavior on rotation {
                    NumberAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
                }

                property color glyphColor: header.hovered ? Theme.textPrimary : Theme.textSecondary
                onGlyphColorChanged: requestPaint()

                onPaint: {
                    const ctx = getContext("2d");
                    ctx.reset();
                    ctx.strokeStyle = glyphColor.toString();
                    ctx.lineWidth = 1.5;  // icon stroke width per design-system §5
                    ctx.lineCap = "round";
                    ctx.beginPath();
                    ctx.moveTo(3, 4.5);
                    ctx.lineTo(6, 7.5);
                    ctx.lineTo(9, 4.5);
                    ctx.stroke();
                }
            }

            Label {
                text: root.title
                font.pixelSize: Theme.fontSizeHeading
                font.weight: Font.DemiBold
                color: Theme.textPrimary
                elide: Text.ElideRight
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
            }
        }

        onClicked: root.expanded = !root.expanded
    }

    Item {
        id: reveal
        width: root.width
        height: root.expanded ? contentColumn.height : 0
        clip: true

        Behavior on height {
            NumberAnimation { duration: Theme.motionNormal; easing.type: Easing.OutCubic }
        }

        Column {
            id: contentColumn
            x: Theme.spacingLg
            width: root.width - Theme.spacingLg - Theme.spacingSm
            spacing: Theme.spacingMd
            enabled: root.expanded  // hidden rows are neither visible nor focusable
        }
    }
}
