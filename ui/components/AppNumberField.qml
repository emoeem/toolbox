import Toolbox
import QtQuick
import QtQuick.Controls

// Numeric field wrapping SpinBox (ui-component-spec.md §1 NumberField):
// value/from/to/decimals/step, ↑/↓ fine-tuning, wheel stepping, and an error
// state (error stroke + errorText, typography.small) while the edited text is
// invalid.
//
// Implementation notes (verified against Qt sources):
// - SpinBox stores integers scaled by 10^decimals; textFromValue /
//   valueFromText convert through the same factor (required for decimals).
// - The public increase()/decrease() do NOT emit valueModified, so stepping
//   (↑/↓ keys, wheel) goes through nudge(): root.value is written directly
//   and valueModified() emitted once. Programmatic value writes never emit
//   valueModified (ValueStatus::Unmodified), which keeps the two-way sync
//   loop-free.
// - The contentItem TextField mirrors spinBox.displayText (Basic style
//   pattern); commit happens natively on Enter or focus loss.
//
// Deliberate deviation from the spec table: ←/→ keep their standard caret
// movement inside the editable field instead of stepping the value; ↑/↓ and
// the wheel cover stepping.
//
// Typography: fontSizeNumeric (§2.4); the font family itself is applied
// application-wide by FontService (Phase 4 task 4).
Column {
    id: root

    property real value: 0
    property real from: 0
    property real to: 99
    property int decimals: 2
    property real step: 1
    property bool editable: true

    property string errorText: qsTr("无效数值")

    // True while the focused text is invalid (unparseable or out of bounds).
    readonly property bool error:
        valueField.activeFocus && valueField.text.length > 0 && !valueField.acceptableInput

    signal valueModified()

    // SpinBox stores integers scaled by 10^decimals.
    readonly property real factor: Math.pow(10, root.decimals)

    // Column 定位器的 implicitWidth/Height 由子项自动计算（只读，CI 烟雾
    // 实证 Invalid property assignment）——显式宽度用 width，调用方经
    // Layout.fillWidth/width 覆盖仍可拉伸。
    width: 140

    // design-system §4 Disabled: the field-wide 40% opacity on top of the
    // textDisabled/glyph colors, same as AppSliderField/AppSelectField.
    opacity: root.enabled ? 1.0 : 0.4

    Component.onCompleted: root.syncSpin()

    onValueChanged: {
        spinBox.value = Math.round(root.value * root.factor);
        // Imperative re-sync (in addition to the displayText binding) keeps
        // the field text correct even if the user broke the binding by
        // editing; displayText is updated synchronously by SpinBox.
        valueField.text = spinBox.displayText;
    }
    onFromChanged: spinBox.from = Math.round(root.from * root.factor)
    onToChanged: spinBox.to = Math.round(root.to * root.factor)
    onStepChanged: spinBox.stepSize = Math.max(1, Math.round(root.step * root.factor))
    onDecimalsChanged: {
        spinBox.decimals = root.decimals;
        root.syncSpin();
    }

    function syncSpin() {
        spinBox.from = Math.round(root.from * root.factor);
        spinBox.to = Math.round(root.to * root.factor);
        spinBox.stepSize = Math.max(1, Math.round(root.step * root.factor));
        spinBox.value = Math.round(root.value * root.factor);
        valueField.text = spinBox.displayText;
    }

    // One step in direction (+1/-1), clamped and rounded to decimals
    // precision. Emits valueModified exactly once (user-driven).
    function nudge(direction) {
        if (!root.enabled)
            return;
        const next = Math.round((root.value + direction * root.step) * root.factor) / root.factor;
        root.value = Math.max(root.from, Math.min(root.to, next));
        root.valueModified();
    }

    SpinBox {
        id: spinBox
        width: parent.width
        height: 32
        editable: root.editable
        decimals: root.decimals
        rightPadding: 28  // reserves the up/down indicator column

        textFromValue: function(value, locale) {
            return Number(value / root.factor).toLocaleString(locale, "f", root.decimals);
        }
        valueFromText: function(text, locale) {
            return Math.round(Number.fromLocaleString(locale, text) * root.factor);
        }

        onValueModified: {
            root.value = spinBox.value / root.factor;
            root.valueModified();
        }

        contentItem: TextField {
            id: valueField
            readOnly: !spinBox.editable
            text: spinBox.displayText
            font.pixelSize: Theme.fontSizeNumeric
            color: root.enabled ? Theme.textPrimary : Theme.textDisabled
            selectionColor: Theme.accent
            selectedTextColor: Theme.onAccent
            verticalAlignment: TextInput.AlignVCenter
            leftPadding: Theme.spacingSm
            rightPadding: Theme.spacingSm
            background: null

            validator: DoubleValidator {
                bottom: Math.min(root.from, root.to)
                top: Math.max(root.from, root.to)
                decimals: root.decimals
                notation: DoubleValidator.StandardNotation
                locale: spinBox.locale.name
            }

            Keys.onUpPressed: (event) => {
                event.accepted = true;
                root.nudge(1);
            }
            Keys.onDownPressed: (event) => {
                event.accepted = true;
                root.nudge(-1);
            }
        }

        up.indicator: Item {
            x: spinBox.width - width
            y: 0
            implicitWidth: 24
            implicitHeight: spinBox.height / 2

            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusSm
                visible: spinBox.up.enabled && (spinBox.up.hovered || spinBox.up.pressed)
                color: spinBox.up.pressed ? Qt.darker(Theme.surfaceElevated, 1.15)
                                          : Qt.darker(Theme.surfaceElevated, 1.08)
            }

            Canvas {
                id: upGlyph
                anchors.centerIn: parent
                width: 12
                height: 8
                property color glyphColor:
                    spinBox.up.pressed ? Theme.accentPressed
                        : spinBox.up.enabled ? (spinBox.up.hovered ? Theme.textPrimary : Theme.textSecondary)
                        : Theme.textDisabled
                onGlyphColorChanged: requestPaint()
                onPaint: {
                    const ctx = getContext("2d");
                    ctx.reset();
                    ctx.strokeStyle = glyphColor.toString();
                    ctx.lineWidth = 1.5;  // icon stroke width per design-system §5
                    ctx.lineCap = "round";
                    ctx.beginPath();
                    ctx.moveTo(2, 6);
                    ctx.lineTo(6, 2);
                    ctx.lineTo(10, 6);
                    ctx.stroke();
                }
            }
        }

        down.indicator: Item {
            x: spinBox.width - width
            y: parent.height / 2
            implicitWidth: 24
            implicitHeight: spinBox.height / 2

            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusSm
                visible: spinBox.down.enabled && (spinBox.down.hovered || spinBox.down.pressed)
                color: spinBox.down.pressed ? Qt.darker(Theme.surfaceElevated, 1.15)
                                            : Qt.darker(Theme.surfaceElevated, 1.08)
            }

            Canvas {
                id: downGlyph
                anchors.centerIn: parent
                width: 12
                height: 8
                property color glyphColor:
                    spinBox.down.pressed ? Theme.accentPressed
                        : spinBox.down.enabled ? (spinBox.down.hovered ? Theme.textPrimary : Theme.textSecondary)
                        : Theme.textDisabled
                onGlyphColorChanged: requestPaint()
                onPaint: {
                    const ctx = getContext("2d");
                    ctx.reset();
                    ctx.strokeStyle = glyphColor.toString();
                    ctx.lineWidth = 1.5;  // icon stroke width per design-system §5
                    ctx.lineCap = "round";
                    ctx.beginPath();
                    ctx.moveTo(2, 2);
                    ctx.lineTo(6, 6);
                    ctx.lineTo(10, 2);
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
                border.color: spinBox.visualFocus ? Theme.accent : Theme.borderStrong

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
                visible: spinBox.visualFocus && spinBox.enabled
            }
        }
    }

    // Wheel stepping overlay: NoButton keeps click pass-through, and
    // hoverEnabled stays false so the SpinBox's own up/down hover indicators
    // still receive hover (评审修正：MouseArea 悬停会阻断下层 item 的 hover);
    // wheel delivery does not depend on hoverEnabled. Steps via nudge()
    // because SpinBox.increase() would not emit valueModified.
    MouseArea {
        anchors.fill: spinBox
        acceptedButtons: Qt.NoButton
        hoverEnabled: false
        onWheel: (wheel) => {
            if (!spinBox.enabled)
                return;
            if (wheel.angleDelta.y === 0)
                return;
            root.nudge(wheel.angleDelta.y > 0 ? 1 : -1);
            wheel.accepted = true;
        }
    }

    Label {
        visible: root.error
        width: parent.width
        text: root.errorText
        font.pixelSize: Theme.fontSizeSmall
        color: Theme.error
        elide: Text.ElideRight
    }
}
