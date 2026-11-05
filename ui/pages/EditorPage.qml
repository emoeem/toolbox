import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

// Editor workspace (Phase 2 prototype): open + display + zoom/pan.
// Processing, preview pipeline and history arrive via the Python Worker in
// Phase 3+; the inspector is intentionally absent until then.
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

                Button {
                    text: qsTr("打开")
                    onClicked: fileDialog.open()
                }

                ToolSeparator {}

                Button { text: qsTr("−"); onClicked: canvas.zoomBy(1 / 1.25) }
                Button { text: qsTr("+"); onClicked: canvas.zoomBy(1.25) }
                Button { text: qsTr("适配"); onClicked: canvas.fitToWindow() }
                Button { text: qsTr("100%"); onClicked: canvas.setActualSize() }

                Label {
                    text: canvas.zoom >= 0.01
                          ? Math.round(canvas.zoom * 100) + "%"
                          : "—"
                    font.pixelSize: Theme.fontSizeNumeric
                    color: Theme.textPrimary
                }

                ToolSeparator {}

                Label {
                    id: errorLabel
                    Layout.fillWidth: true
                    text: ""
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.error
                    elide: Text.ElideRight
                }

                BusyIndicator {
                    visible: canvas.busy
                    running: canvas.busy
                    width: 24
                    height: 24
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

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.statusBarHeight
            color: Theme.surface

            Label {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: Theme.spacingLg
                text: {
                    if (canvas.imageSize.isEmpty)
                        return qsTr("未打开图像")
                    return canvas.imageSize.width + "×" + canvas.imageSize.height
                           + " · " + qsTr("鼠标") + " "
                           + Math.max(0, Math.floor(canvas.mousePosition.x)) + ","
                           + Math.max(0, Math.floor(canvas.mousePosition.y))
                }
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textSecondary
            }

            Rectangle {
                anchors.top: parent.top
                width: parent.width
                height: 1
                color: Theme.border
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
