import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Parameter slider (ui-component-spec.md §1 SliderField) — the primary
// control for filter/adjustment parameters.
//
// Layout: label row (label + numeric AppNumberField + suffix) over the
// slider track. value is two-way synced (imperatively, to keep drag
// bindings intact) between the slider and the number field.
//
// - defaultValue: double-click the label to reset.
// - dragging (readonly): true while the user drags the handle — drives the
//   two-level preview (lo-fi while dragging, hi-fi after release).
// - valueModified(): throttled while dragging (interval = motion.fast,
//   §2.5); flushed once on release together with dragFinished().
// - suffix: unit string ("°", "%") shown after the value field.
// 根用 ColumnLayout（非 Column 定位器）：本组件在 EditorPage 检查器
// ColumnLayout 与 BatchWizard 中使用——定位器根的 implicit 尺寸反馈环触发
// polish loop（CI 烟雾实证）；嵌套 Layout 是标准解。
ColumnLayout {
    id: root

    property string label: ""
    property real value: 0
    property real from: 0
    property real to: 100
    property real step: 1
    property real defaultValue: 0
    property string suffix: ""

    readonly property bool dragging: slider.pressed

    // Decimals for the value display, derived from step.
    readonly property int decimals: root.stepDecimals(root.step)

    signal valueModified()
    signal dragFinished()

    // Column 定位器 implicitWidth 只读（CI 烟雾实证，同 AppNumberField）且
    // 组件不自带宽度（Layout 上下文命令式 width 触发 polish loop）——全部
    // 使用点已在 Layout 中显式定宽（fillWidth/preferredWidth/width）。
    spacing: Theme.spacingSm
    opacity: root.enabled ? 1.0 : 0.4

    property bool movedWhilePressed: false

    Component.onCompleted: root.syncControls()

    onValueChanged: root.syncControls()
    onFromChanged: slider.from = root.from
    onToChanged: slider.to = root.to
    onStepChanged: slider.stepSize = root.step

    function syncControls() {
        valueField.value = root.value;
        slider.from = root.from;
        slider.to = root.to;
        slider.stepSize = root.step;
        slider.value = root.value;
    }

    function stepDecimals(s) {
        const abs = Math.abs(s);
        if (abs === 0)
            return 2;
        let d = 0;
        let v = abs;
        while (Math.abs(v - Math.round(v)) > 1e-9 && d < 6) {
            v *= 10;
            d += 1;
        }
        return d;
    }

    function bigStep() {
        const raw = Math.abs(root.to - root.from) / 10;
        return root.step > 0 ? Math.max(root.step, Math.ceil(raw / root.step) * root.step) : raw;
    }

    function reset() {
        root.value = root.defaultValue;
        root.valueModified();
    }

    // Trailing throttle for drag-time valueModified().
    Timer {
        id: valueThrottle
        interval: Theme.motionFast  // §2.5 motion.fast
        onTriggered: root.valueModified()
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: Theme.spacingSm

        Label {
            Layout.fillWidth: true
            text: root.label
            font.pixelSize: Theme.fontSizeSmall  // §2.4: labels use small
            color: root.enabled ? Theme.textSecondary : Theme.textDisabled
            elide: Text.ElideRight

            TapHandler {
                onDoubleTapped: root.reset()
            }
        }

        AppNumberField {
            id: valueField
            Layout.preferredWidth: 96
            from: root.from
            to: root.to
            step: root.step
            decimals: root.decimals
            onValueModified: root.value = valueField.value
        }

        Label {
            visible: root.suffix !== ""
            text: root.suffix
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.textSecondary
        }
    }

    Slider {
        id: slider
        Layout.fillWidth: true
        stepSize: root.step

        onMoved: {
            root.movedWhilePressed = true;
            root.value = slider.value;
            valueThrottle.restart();
        }

        onPressedChanged: {
            if (!pressed && root.movedWhilePressed) {
                root.movedWhilePressed = false;
                valueThrottle.stop();
                root.valueModified();
                root.dragFinished();
            }
        }

        // design-system §4: PgUp/PgDn take large steps (←/→ are native).
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_PageUp || event.key === Qt.Key_PageDown) {
                event.accepted = true;
                const delta = event.key === Qt.Key_PageUp ? root.bigStep() : -root.bigStep();
                slider.value = Math.max(root.from, Math.min(root.to, slider.value + delta));
                root.value = slider.value;
                root.valueModified();
            }
        }

        background: Item {
            implicitHeight: 24

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width
                height: Theme.spacingXs  // 4px track
                radius: Theme.radiusSm
                color: Theme.surfaceElevated
            }

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                height: Theme.spacingXs
                width: slider.visualPosition * parent.width
                radius: Theme.radiusSm
                color: Theme.accent
            }

            Rectangle {
                anchors.fill: parent
                anchors.margins: -2
                radius: Theme.radiusSm + 2
                color: "transparent"
                border.color: Theme.accent
                border.width: 2
                visible: slider.visualFocus && slider.enabled
            }
        }

        handle: Rectangle {
            x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
            y: slider.topPadding + slider.availableHeight / 2 - height / 2
            width: 16
            height: 16
            radius: 8  // circular handle derived from its own size
            color: slider.pressed ? Theme.accent : Theme.surface
            border.width: slider.pressed || slider.hovered ? 2 : 1
            border.color: slider.pressed ? Theme.accentPressed : Theme.accent
        }
    }
}
