import QtQuick
import QtQuick.Controls

// Progress / loading indicator (ui-component-spec.md §1 ProgressIndicator).
// Two forms:
// - Inline: circular arc — indeterminate is a rotating arc, determinate an
//   arc filled proportionally to value.
// - Bar: horizontal bar — determinate fill / indeterminate sliding segment.
// Tokens: accent over surfaceElevated track (ui-design-system.md §2.1).
Control {
    id: root

    enum Form { Inline, Bar }

    property int form: AppProgressIndicator.Form.Inline
    property bool indeterminate: false

    // Determinate range; defaults mirror ProgressBar (0..1).
    property real value: 0
    property real from: 0
    property real to: 1

    readonly property real ratio:
        root.to > root.from
            ? Math.max(0, Math.min(1, (root.value - root.from) / (root.to - root.from)))
            : 0

    // Spinner revolution: functional loading timing, not a §2.5 transition.
    readonly property int spinPeriodMs: 1200

    implicitWidth: root.form === AppProgressIndicator.Form.Inline ? 20 : 120
    implicitHeight: root.form === AppProgressIndicator.Form.Inline ? 20 : Theme.spacingXs

    contentItem: Item {
        // ---- inline arc ----------------------------------------------------
        Canvas {
            id: arc
            visible: root.form === AppProgressIndicator.Form.Inline
            anchors.centerIn: parent
            width: 20
            height: 20
            transformOrigin: Item.Center

            onPaint: {
                const ctx = getContext("2d");
                ctx.reset();
                ctx.strokeStyle = Theme.accent.toString();
                ctx.lineWidth = 2;
                ctx.lineCap = "round";
                ctx.beginPath();
                if (root.indeterminate) {
                    ctx.arc(width / 2, height / 2, width / 2 - 2, 0, Math.PI / 2);
                } else {
                    const start = -Math.PI / 2;
                    ctx.arc(width / 2, height / 2, width / 2 - 2,
                            start, start + root.ratio * Math.PI * 2);
                }
                ctx.stroke();
            }

            RotationAnimation on rotation {
                running: root.visible && root.indeterminate
                         && root.form === AppProgressIndicator.Form.Inline
                from: 0
                to: 360
                duration: root.spinPeriodMs
                loops: Animation.Infinite
            }

            Connections {
                target: root
                function onRatioChanged() { arc.requestPaint() }
            }
            Connections {
                target: Theme
                function onDarkModeChanged() { arc.requestPaint() }
            }
        }

        // ---- horizontal bar --------------------------------------------------
        Item {
            visible: root.form === AppProgressIndicator.Form.Bar
            anchors.fill: parent

            Rectangle {
                id: track
                anchors.fill: parent
                radius: Theme.radiusSm  // equals the 4px bar height → pill
                color: Theme.surfaceElevated
            }

            Rectangle {
                id: fill
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height
                radius: Theme.radiusSm
                color: Theme.accent
                x: 0
                width: root.indeterminate ? parent.width * 0.35 : root.ratio * parent.width

                SequentialAnimation on x {
                    running: root.visible && root.indeterminate
                             && root.form === AppProgressIndicator.Form.Bar
                    loops: Animation.Infinite
                    NumberAnimation { from: -fill.width; to: track.width; duration: root.spinPeriodMs }
                    NumberAnimation { from: track.width; to: -fill.width; duration: root.spinPeriodMs }
                }

                // The sliding animation writes x imperatively; restore the
                // left-anchored determinate position when it stops.
                Connections {
                    target: root
                    function onIndeterminateChanged() {
                        if (!root.indeterminate)
                            fill.x = 0;
                    }
                }
            }
        }
    }
}
