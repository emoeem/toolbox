import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Color field (ui-component-spec.md §1 ColorField): a swatch button opening
// a picker with hex input, R/G/B inputs and a preset palette built from
// Theme tokens. value keeps any alpha; hex/RGB editing covers RGB only
// (spec: hex/RGB 输入).
AbstractButton {
    id: root

    property color value: Theme.accent

    signal valueModified()

    implicitWidth: 140  // default; callers stretch via width/Layout.fillWidth
    implicitHeight: 32
    opacity: root.enabled ? 1.0 : 0.4

    property bool ready: false

    Component.onCompleted: {
        root.ready = true;
        root.syncInputs();
    }

    onValueChanged: {
        if (root.ready)
            root.syncInputs();
    }

    HoverHandler {
        cursorShape: Qt.PointingHandCursor
    }

    // design-system §4: Space activates natively (ButtonPressKeys);
    // Enter/Return open the picker so activation does not depend on the
    // platform theme. Accepted here (Keys.BeforeItem) → single activation.
    Keys.onReturnPressed: (event) => {
        event.accepted = true;
        root.clicked();
    }
    Keys.onEnterPressed: (event) => {
        event.accepted = true;
        root.clicked();
    }

    // Opens/closes the picker popup declared below. AbstractButton has no
    // `popup` property (that is ComboBox's), so the Popup is a plain child
    // object and this handler is its only entry point.
    onClicked: colorPopup.opened ? colorPopup.close() : colorPopup.open()

    function hexString(c) {
        const hex2 = (v) => Math.round(v * 255).toString(16).padStart(2, "0");
        return "#" + hex2(c.r) + hex2(c.g) + hex2(c.b);
    }

    function syncInputs() {
        hexField.text = root.hexString(root.value);
        rField.value = Math.round(root.value.r * 255);
        gField.value = Math.round(root.value.g * 255);
        bField.value = Math.round(root.value.b * 255);
    }

    function revertHexIfInvalid() {
        const t = hexField.text.trim();
        const body = t.startsWith("#") ? t.substring(1) : t;
        if (!/^[0-9a-fA-F]{6}$/.test(body))
            hexField.text = root.hexString(root.value);
    }

    function applyHex() {
        const t = hexField.text.trim();
        const body = t.startsWith("#") ? t.substring(1) : t;
        if (!/^[0-9a-fA-F]{6}$/.test(body)) {
            hexField.text = root.hexString(root.value);
            return;
        }
        root.value = Qt.rgba(
                    parseInt(body.substring(0, 2), 16) / 255,
                    parseInt(body.substring(2, 4), 16) / 255,
                    parseInt(body.substring(4, 6), 16) / 255,
                    root.value.a);
        root.valueModified();
    }

    function applyRgb() {
        root.value = Qt.rgba(rField.value / 255, gField.value / 255, bField.value / 255, root.value.a);
        root.valueModified();
    }

    function setValue(c) {
        root.value = c;
        root.valueModified();
    }

    contentItem: Item {
        implicitWidth: swatchRect.width + Theme.spacingSm + hexLabel.implicitWidth
                       + Theme.spacingSm + chevron.width
        implicitHeight: 20

        Rectangle {
            id: swatchRect
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: 16
            height: 16
            radius: Theme.radiusSm
            color: root.value
            border.width: 1
            border.color: Theme.border
        }

        Label {
            id: hexLabel
            anchors.left: swatchRect.right
            anchors.leftMargin: Theme.spacingSm
            anchors.verticalCenter: parent.verticalCenter
            text: root.hexString(root.value)
            font.pixelSize: Theme.fontSizeNumeric
            color: root.enabled ? Theme.textPrimary : Theme.textDisabled
        }

        Canvas {
            id: chevron
            anchors.right: parent.right
            anchors.rightMargin: Theme.spacingSm
            anchors.verticalCenter: parent.verticalCenter
            width: 12
            height: 8
            property color glyphColor: root.enabled
                                       ? (root.hovered ? Theme.textPrimary : Theme.textSecondary)
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
            visible: root.visualFocus && root.enabled
        }
    }

    // Picker popup as a plain child Popup instance (parented to this button so
    // the y offset below is relative to it). Declaring it as `popup:` would
    // fail to load: AbstractButton has no such property.
    Popup {
        id: colorPopup
        parent: root
        y: root.height + Theme.spacingXs
        width: 248
        padding: Theme.spacingMd

        background: Rectangle {
            color: Theme.surfaceElevated
            radius: Theme.radiusLg
            border.color: Theme.border
            border.width: 1
        }

        contentItem: ColumnLayout {
            spacing: Theme.spacingMd

            RowLayout {
                spacing: Theme.spacingSm

                Label {
                    text: qsTr("HEX")
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textSecondary
                }

                AppTextField {
                    id: hexField
                    Layout.fillWidth: true
                    font.pixelSize: Theme.fontSizeNumeric
                    validator: RegExpValidator {
                        regularExpression: /^#?[0-9a-fA-F]{6}$/
                    }
                    onEditingFinished: root.applyHex()
                    onActiveFocusChanged: {
                        if (!activeFocus)
                            root.revertHexIfInvalid();
                    }
                }
            }

            RowLayout {
                spacing: Theme.spacingSm

                ColumnLayout {
                    spacing: Theme.spacingXs
                    Layout.fillWidth: true
                    Label {
                        text: qsTr("R")
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textSecondary
                    }
                    AppNumberField {
                        id: rField
                        Layout.fillWidth: true
                        implicitWidth: 0
                        from: 0; to: 255; step: 1; decimals: 0
                        onValueModified: root.applyRgb()
                    }
                }

                ColumnLayout {
                    spacing: Theme.spacingXs
                    Layout.fillWidth: true
                    Label {
                        text: qsTr("G")
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textSecondary
                    }
                    AppNumberField {
                        id: gField
                        Layout.fillWidth: true
                        implicitWidth: 0
                        from: 0; to: 255; step: 1; decimals: 0
                        onValueModified: root.applyRgb()
                    }
                }

                ColumnLayout {
                    spacing: Theme.spacingXs
                    Layout.fillWidth: true
                    Label {
                        text: qsTr("B")
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textSecondary
                    }
                    AppNumberField {
                        id: bField
                        Layout.fillWidth: true
                        implicitWidth: 0
                        from: 0; to: 255; step: 1; decimals: 0
                        onValueModified: root.applyRgb()
                    }
                }
            }

            Flow {
                Layout.fillWidth: true
                spacing: Theme.spacingSm

                // Preset swatches are Theme tokens themselves.
                Repeater {
                    model: [
                        Theme.accent, Theme.success, Theme.warning, Theme.error,
                        Theme.background, Theme.surface, Theme.surfaceElevated,
                        Theme.border, Theme.textPrimary, Theme.canvasBackdrop
                    ]

                    delegate: Rectangle {
                        required property int index
                        required property color modelData
                        width: 20
                        height: 20
                        radius: Theme.radiusSm
                        color: modelData
                        border.width: 1
                        border.color: Theme.border

                        TapHandler {
                            onTapped: root.setValue(modelData)
                        }
                    }
                }
            }
        }
    }
}
