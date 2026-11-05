import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

// Editor workspace (Phase 2 prototype with Phase 4 componentization): open +
// display + zoom/pan. Processing, preview pipeline and history arrive via the
// Python Worker in Phase 3+; the inspector is intentionally absent until then.
//
// This page keeps its Phase 2 behavior — the Phase 4 pass only swaps the tool
// row onto the shared component set (AppButton / AppToolButton /
// AppTopToolbar.GroupRule / AppProgressIndicator / AppStatusBar). Backend
// launching lives on the settings page, not here.
Page {
    id: page

    property url pendingSource

    background: Rectangle { color: Theme.canvasBackdrop }

    function openFile(url) {
        errorLabel.text = ""
        canvas.source = url
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            color: Theme.surface

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacingMd
                anchors.rightMargin: Theme.spacingMd
                spacing: Theme.spacingSm

                AppButton {
                    kind: AppButton.Kind.Primary
                    text: qsTr("打开")
                    onClicked: fileDialog.open()
                }

                AppTopToolbar.GroupRule { Layout.alignment: Qt.AlignVCenter }

                AppToolButton {
                    display: AbstractButton.TextOnly
                    text: qsTr("−")
                    tooltipText: qsTr("缩小")
                    onClicked: canvas.zoomBy(1 / 1.25)
                }
                AppToolButton {
                    display: AbstractButton.TextOnly
                    text: qsTr("+")
                    tooltipText: qsTr("放大")
                    onClicked: canvas.zoomBy(1.25)
                }
                AppToolButton {
                    display: AbstractButton.TextOnly
                    text: qsTr("适配")
                    tooltipText: qsTr("适配窗口")
                    onClicked: canvas.fitToWindow()
                }
                AppToolButton {
                    display: AbstractButton.TextOnly
                    text: qsTr("100%")
                    tooltipText: qsTr("实际大小")
                    onClicked: canvas.setActualSize()
                }

                Label {
                    text: canvas.zoom >= 0.01
                          ? Math.round(canvas.zoom * 100) + "%"
                          : "—"
                    font.pixelSize: Theme.fontSizeNumeric
                    color: Theme.textPrimary
                }

                AppTopToolbar.GroupRule { Layout.alignment: Qt.AlignVCenter }

                Label {
                    id: errorLabel
                    Layout.fillWidth: true
                    text: ""
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.error
                    elide: Text.ElideRight
                }

                AppProgressIndicator {
                    form: AppProgressIndicator.Form.Inline
                    indeterminate: true
                    visible: canvas.busy
                    Layout.alignment: Qt.AlignVCenter
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Theme.border
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ImageCanvas {
                id: canvas
                anchors.fill: parent
                showCheckerboard: true

                onImageDropped: function (url) { page.openFile(url) }
                onLoadFailed: function (reason) {
                    errorLabel.text = qsTr("打开失败：%1").arg(reason)
                }
            }

            // Empty state: no document loaded. Double-click fit is implemented
            // inside ImageCanvas (mouseDoubleClickEvent → fitToWindow).
            ColumnLayout {
                anchors.centerIn: parent
                visible: !canvas.busy && canvas.imageSize.isEmpty
                spacing: Theme.spacingMd

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("拖放图像到此处，或点击\"打开\"")
                    font.pixelSize: Theme.fontSizeBody
                    color: Theme.textSecondary
                }

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("滚轮缩放 · 拖动平移 · 双击适配 · 图像处理随 Phase 3 接入")
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.textDisabled
                }
            }
        }

        // Bottom info bar (document size / mouse position) on the shared
        // status-bar component instead of a hand-rolled Rectangle.
        AppStatusBar {
            Layout.fillWidth: true
            leftText: {
                if (canvas.imageSize.isEmpty)
                    return qsTr("未打开图像")
                return canvas.imageSize.width + "×" + canvas.imageSize.height
                       + " · " + qsTr("鼠标") + " "
                       + Math.max(0, Math.floor(canvas.mousePosition.x)) + ","
                       + Math.max(0, Math.floor(canvas.mousePosition.y))
            }
        }
    }

    FileDialog {
        id: fileDialog
        title: qsTr("打开图像")
        nameFilters: [
            qsTr("图像文件 (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif)"),
            qsTr("所有文件 (*)")
        ]
        onAccepted: page.openFile(selectedFile)
    }
}
