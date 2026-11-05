import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Modal dialog shell wrapping Dialog (ui-component-spec.md §1 Dialog).
// API per the ask: title / content (Component) / accepted / rejected.
//
// - The modal scrim uses Theme.overlayScrim.
// - Esc rejects (Dialog native); the scrim does NOT close the dialog —
//   decisions that must be explicit are not dismissible by a stray click.
// - Buttons: add a `footer` with a DialogButtonBox of AppButtons (primary
//   action on the right per spec). DialogButtonBox wires Enter to the
//   default button and Esc to rejection.
//
// As a Popup, the dialog renders in the window overlay layer, above page
// content — no per-page z management needed.
Dialog {
    id: root

    property Component content: null

    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.NoAutoClose

    implicitWidth: 480  // shell default; callers may override
    padding: Theme.spacingLg

    Overlay.modal: Rectangle {
        color: Theme.overlayScrim
    }

    background: Rectangle {
        color: Theme.surface
        radius: Theme.radiusLg
        border.color: Theme.border
        border.width: 1
    }

    header: ColumnLayout {
        spacing: Theme.spacingSm

        Label {
            visible: root.title !== ""
            Layout.fillWidth: true
            text: root.title
            font.pixelSize: Theme.fontSizeHeading
            font.weight: Font.DemiBold
            color: Theme.textPrimary
            elide: Text.ElideRight
        }

        Rectangle {
            visible: root.title !== ""
            Layout.fillWidth: true
            height: 1
            color: Theme.border
        }
    }

    contentItem: Loader {
        sourceComponent: root.content
    }
}
