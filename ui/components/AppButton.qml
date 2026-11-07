import QtQuick
import QtQuick.Controls

// Themed push button wrapping AbstractButton (ui-component-spec.md §1
// AppButton). clicked() / icon.name / text come from the base type.
//
// kind: Primary (accent, one primary action per page) / Secondary / Danger /
// Ghost. size: Small 28 / Medium 32 / Large 40 (spec §1 height rule).
//
// loading: overlays an indeterminate inline AppProgressIndicator on the
// content and disables the control (design-system §4 Loading). Note the QML
// semantics: an `enabled:` binding written at the instantiation site replaces
// this file's `enabled: !loading` binding — include `!loading` in such
// bindings (e.g. `enabled: backendReady && !loading`).
AbstractButton {
    id: root

    enum Kind { Primary, Secondary, Danger, Ghost }
    enum Size { Small, Medium, Large }

    property int kind: AppButton.Kind.Secondary
    property int size: AppButton.Size.Medium
    property bool loading: false

    enabled: !root.loading
    opacity: root.enabled ? 1.0 : 0.4  // design-system §4 Disabled

    font.pixelSize: Theme.fontSizeBody
    spacing: Theme.spacingSm
    display: AbstractButton.TextBesideIcon

    // Primary/Danger carry light-on-accent text; the rest use primary text.
    palette.buttonText:
        (root.kind === AppButton.Kind.Primary || root.kind === AppButton.Kind.Danger)
            ? Theme.onAccent : Theme.textPrimary
    palette.text: palette.buttonText

    implicitHeight:
        root.size === AppButton.Size.Small ? 28
            : root.size === AppButton.Size.Large ? 40 : 32
    leftPadding: Theme.spacingMd
    rightPadding: Theme.spacingMd
    topPadding: 0
    bottomPadding: 0

    HoverHandler {
        cursorShape: Qt.PointingHandCursor
    }

    // design-system §4: Space activates natively (ButtonPressKeys);
    // Enter/Return are handled here so activation does not depend on the
    // platform theme. Accepted here (Keys.BeforeItem) → single activation.
    Keys.onReturnPressed: (event) => {
        event.accepted = true;
        root.clicked();
    }
    Keys.onEnterPressed: (event) => {
        event.accepted = true;
        root.clicked();
    }

    background: Item {
        Rectangle {
            id: fill
            anchors.fill: parent
            radius: Theme.radiusMd
            color: root.fillColor()
            border.width: root.kind === AppButton.Kind.Secondary ? 1 : 0
            border.color: root.pressed ? Theme.borderStrong : Theme.border

            Behavior on color {
                ColorAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic }
            }
        }

        // Loading covers the label with the same fill so the spinner reads
        // alone (§4 Loading: "替换/覆盖内容").
        Rectangle {
            anchors.fill: parent
            radius: fill.radius
            color: fill.color
            visible: root.loading
        }

        // 2px accent focus ring — keyboard only (visualFocus), concentric
        // geometry outside the fill.
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

    AppProgressIndicator {
        anchors.centerIn: parent
        width: 16
        height: 16
        form: AppProgressIndicator.Form.Inline
        indeterminate: true
        visible: root.loading
    }

    // State colors derived from tokens (design-system §4: 状态样式由令牌派生);
    // pressed shades are deterministic token derivations, not new palette
    // constants.
    function fillColor() {
        if (root.kind === AppButton.Kind.Primary)
            return root.pressed ? Theme.accentPressed
                 : root.hovered ? Theme.accentHover : Theme.accent;
        if (root.kind === AppButton.Kind.Danger)
            return root.pressed ? Qt.darker(Theme.error, 1.25)
                 : root.hovered ? (Theme.darkMode ? Qt.lighter(Theme.error, 1.12)
                                                  : Qt.darker(Theme.error, 1.08))
                 : Theme.error;
        // Secondary / Ghost share the neutral ramp: hover → surfaceElevated,
        // pressed → one shade deeper.
        return root.pressed ? Qt.darker(Theme.surfaceElevated, 1.08)
             : root.hovered ? Theme.surfaceElevated : "transparent";
    }
}
