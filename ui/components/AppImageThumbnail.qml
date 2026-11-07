import QtQuick
import QtQuick.Controls

// Thumbnail (ui-component-spec.md §3 ImageThumbnail): asynchronous decode
// (asynchronous Image + sourceSize bound to the display size so only the
// thumbnail is decoded, never the full original on the UI thread), memory
// cached by the Image element. `status` mirrors the load state:
//   "idle"    — no source assigned
//   "loading" — indeterminate AppProgressIndicator placeholder
//   "ready"   — image shown, aspect-fit into the item
//   "error"   — drawn broken-image glyph (frame + mountain + slash)
//
// Callers must hand in Worker-generated thumbnail paths
// (ui-component-spec.md §3: 仅请求 Worker 生成的缩略图路径). Passive display
// item — no §4 interactive states.
Rectangle {
    id: root

    property url source: ""

    readonly property string status:
        root.source === "" ? "idle"
            : thumbImage.status === Image.Ready ? "ready"
            : thumbImage.status === Image.Error ? "error"
            : "loading"

    radius: Theme.radiusSm
    color: Theme.surfaceElevated
    clip: true

    Image {
        id: thumbImage
        anchors.fill: parent
        asynchronous: true
        cache: true
        fillMode: Image.PreserveAspectFit
        source: root.source
        sourceSize: Qt.size(Math.max(1, width), Math.max(1, height))
        visible: root.status === "ready"
    }

    AppProgressIndicator {
        anchors.centerIn: parent
        indeterminate: true
        visible: root.status === "loading"
    }

    Canvas {
        anchors.centerIn: parent
        width: 24
        height: 24
        visible: root.status === "error"

        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            ctx.strokeStyle = Theme.textDisabled.toString();
            ctx.lineWidth = 1.5;  // icon stroke width per design-system §5
            ctx.lineCap = "round";
            ctx.beginPath();
            ctx.moveTo(3, 4);
            ctx.lineTo(21, 4);
            ctx.lineTo(21, 20);
            ctx.lineTo(3, 20);
            ctx.closePath();
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(3, 16);
            ctx.lineTo(9, 11);
            ctx.lineTo(13, 14);
            ctx.lineTo(16, 12);
            ctx.lineTo(21, 16);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(20, 5);
            ctx.lineTo(4, 19);
            ctx.stroke();
        }
    }
}
