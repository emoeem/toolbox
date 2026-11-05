pragma Singleton
import QtQuick

// Design token single source of truth for the QML side.
// Values MUST stay identical to docs/ui-design-system.md §2.
// Pages and components reference these tokens only — never local constants.
QtObject {
    id: root

    property bool darkMode: true

    // ---- color ------------------------------------------------------------
    readonly property color background: darkMode ? "#1e1e2e" : "#f7f7fb"
    readonly property color surface: darkMode ? "#181825" : "#ffffff"
    readonly property color surfaceElevated: darkMode ? "#313244" : "#eef0f6"
    readonly property color border: darkMode ? "#45475a" : "#d8dbe2"
    readonly property color borderStrong: darkMode ? "#585b70" : "#c2c6d1"
    readonly property color textPrimary: darkMode ? "#cdd6f4" : "#2b2d31"
    readonly property color textSecondary: darkMode ? "#a6adc8" : "#5c6370"
    readonly property color textDisabled: darkMode ? "#6c7086" : "#9aa0ad"
    readonly property color accent: darkMode ? "#cba6f7" : "#7c3aed"
    readonly property color accentHover: darkMode ? "#b4befe" : "#6d28d9"
    readonly property color accentPressed: darkMode ? "#a78bfa" : "#5b21b6"
    readonly property color onAccent: darkMode ? "#11111b" : "#ffffff"
    readonly property color success: darkMode ? "#a6e3a1" : "#1a7f37"
    readonly property color warning: darkMode ? "#f9e2af" : "#9a6700"
    readonly property color error: darkMode ? "#f38ba8" : "#cf222e"
    readonly property color canvasBackdrop: darkMode ? "#11111b" : "#e8e9ee"
    readonly property color checkerLight: darkMode ? "#3a3d52" : "#d4d6de"
    readonly property color checkerDark: darkMode ? "#2a2d42" : "#bfc2cc"
    readonly property color overlayScrim: darkMode ? "#b311111b" : "#662b2d31"

    // ---- spacing ------------------------------------------------------------
    readonly property int spacingXs: 4
    readonly property int spacingSm: 8
    readonly property int spacingMd: 12
    readonly property int spacingLg: 16
    readonly property int spacingXl: 24

    // ---- radius ------------------------------------------------------------
    readonly property int radiusSm: 4
    readonly property int radiusMd: 6
    readonly property int radiusLg: 10
    readonly property int radiusXl: 14

    // ---- typography (px sizes; line heights via implicit content height) ----
    readonly property int fontSizeTitle: 18
    readonly property int fontSizeHeading: 15
    readonly property int fontSizeBody: 13
    readonly property int fontSizeSmall: 11
    readonly property int fontSizeNumeric: 13
    readonly property int fontSizeMonospace: 12

    // ---- motion ------------------------------------------------------------
    readonly property int motionFast: 120
    readonly property int motionNormal: 200
    readonly property int motionSlow: 320

    // ---- layout ------------------------------------------------------------
    readonly property int navRailWidth: 56
    readonly property int navRailWidthExpanded: 200
    readonly property int inspectorWidth: 300
    readonly property int toolbarHeight: 44
    readonly property int statusBarHeight: 26
    readonly property int minWindowWidth: 960
    readonly property int minWindowHeight: 600
}
