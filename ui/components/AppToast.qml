import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Toast notification (ui-component-spec.md §1 Toast): type
// info/success/warning/error, 5s auto-close; error toasts carry a "copy
// details" action.
//
// closed() is the signal inherited from Popup — close() (the auto-close timer
// and the close button both call it) emits it. Do NOT redeclare
// `signal closed()` here: a same-named QML signal shadows the base-class one,
// so the static emission from close() would never reach consumers' onClosed.
//
// Positioning: with autoPosition (default) the toast docks to the
// bottom-right corner of its parent item — declare it directly under
// ApplicationWindow (or a full-area item). The spec's "最多同屏 3 条"
// stacking and the right-bottom stack layout are owned by the toast host:
// set autoPosition: false and provide x/y offsets to stack manually.
//
// As a Popup it renders in the window overlay layer — a sensible z without
// per-page management.
Popup {
    id: root

    enum Type { Info, Success, Warning, Error }

    property int type: AppToast.Type.Info
    property string text: ""
    property bool autoPosition: true

    // ui-component-spec.md §1: 5s 自动消失.
    readonly property int timeoutMs: 5000

    readonly property color typeColor:
        root.type === AppToast.Type.Error ? Theme.error
            : root.type === AppToast.Type.Warning ? Theme.warning
            : root.type === AppToast.Type.Success ? Theme.success
            : Theme.accent  // info has no dedicated token; accent is the app's informational color

    closePolicy: Popup.NoAutoClose
    dim: false
    padding: Theme.spacingMd

    implicitWidth: Math.min(contentItem.implicitWidth + leftPadding + rightPadding, 384)
    implicitHeight: contentItem.implicitHeight + topPadding + bottomPadding

    onAboutToShow: {
        autoClose.restart();
        if (root.autoPosition && root.parent) {
            root.x = root.parent.width - root.width - Theme.spacingLg;
            root.y = root.parent.height - root.height - Theme.spacingLg;
        }
    }

    onVisibleChanged: {
        if (!visible)
            autoClose.stop();
    }

    // No onClosed handler needed: Popup emits its inherited closed() from
    // close(), which is the consumers' signal (see file header).

    function copyDetails() {
        // Pure-QML clipboard write via a hidden TextArea selection copy.
        clipboardHelper.text = root.text;
        clipboardHelper.selectAll();
        clipboardHelper.copy();
    }

    background: Rectangle {
        color: Theme.surfaceElevated
        radius: Theme.radiusMd
        border.color: Theme.border
        border.width: 1

        // Hidden helper used by copyDetails(); kept inside the background
        // (not the RowLayout contentItem) so no layout manages it.
        TextArea {
            id: clipboardHelper
            visible: false
            width: 0
            height: 0
        }
    }

    contentItem: RowLayout {
        spacing: Theme.spacingSm

        Rectangle {
            Layout.preferredWidth: 8
            Layout.preferredHeight: 8
            Layout.alignment: Qt.AlignVCenter
            radius: Theme.radiusSm  // equals half of the 8px dot → circle
            color: root.typeColor
        }

        Label {
            Layout.fillWidth: true
            Layout.maximumWidth: 320
            text: root.text
            font.pixelSize: Theme.fontSizeBody
            color: Theme.textPrimary
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
        }

        AppButton {
            visible: root.type === AppToast.Type.Error
            kind: AppButton.Kind.Ghost
            size: AppButton.Size.Small
            text: qsTr("复制")
            onClicked: root.copyDetails()
        }

        Item {
            Layout.preferredWidth: 20
            Layout.preferredHeight: 20
            Layout.alignment: Qt.AlignVCenter

            MouseArea {
                id: closeArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.close()
            }

            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusSm
                color: closeArea.containsMouse ? Theme.surfaceElevated : "transparent"
            }

            Canvas {
                anchors.centerIn: parent
                width: 12
                height: 12
                property color glyphColor: closeArea.containsMouse ? Theme.textPrimary : Theme.textSecondary
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
    }

    Timer {
        id: autoClose
        interval: root.timeoutMs
        onTriggered: root.close()
    }
}
