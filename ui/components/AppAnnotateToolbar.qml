import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 标注模式浮条（Phase 9 标注画布模式的参数面板）：工具选择（画笔/文字/矩形/
// 椭圆/箭头/局部模糊/像素化/橡皮）+ 参数（AppColorField 颜色、AppSliderField
// 粗细/字号/强度/块大小）+ [撤销上一笔][清空][完成标注][取消]。
//
// 职责边界（AppFilterInspector 同款纪律）：本组件只持有工具与参数的本地状态
// 并发信号——ops 数组、坐标采集与 Canvas 预览归 AppAnnotateOverlay，
// applyAnnotate(ops) 提交与在途门控归宿主 EditorPage（[完成标注] 只发
// finishRequested()）。组件不发 sendAction、不触碰 DocumentService。
//
// "撤销上一笔"只弹回**待提交** ops 的栈顶（纯本地状态）；已提交（完成标注
// 之后）的撤销走编辑器既有 undo（Worker 参数化 replay，协议 §3.3）。
Column {
    id: root

    // 工具词汇（op type 与协议 §3.9 image.annotate 同名，AppAnnotateOverlay
    // 按此分发采集）：pen/text/rect/ellipse/arrow/blur_rect/pixelate_rect/
    // eraser。
    readonly property var tools: [
        { key: "pen", label: qsTr("画笔") },
        { key: "text", label: qsTr("文字") },
        { key: "rect", label: qsTr("矩形") },
        { key: "ellipse", label: qsTr("椭圆") },
        { key: "arrow", label: qsTr("箭头") },
        { key: "blur_rect", label: qsTr("局部模糊") },
        { key: "pixelate_rect", label: qsTr("像素化") },
        { key: "eraser", label: qsTr("橡皮") }
    ]

    property string tool: "pen"
    property color color: Theme.error
    property real strokeWidth: 4        // 画笔/橡皮/箭头线宽与矩形/椭圆描边（1..40）
    property real textSize: 24          // 文字字号 → op.font_size（协议 1..512）
    property real strength: 10          // blur_rect 模糊半径（协议 0<r≤100）
    property real blockSize: 16         // pixelate_rect 块尺寸（协议 ≥2）

    // 待提交 op 数（宿主绑定 AppAnnotateOverlay.ops.length），驱动撤销/清空。
    property int opCount: 0

    readonly property bool usesColor: root.tool === "pen" || root.tool === "text"
                                      || root.tool === "rect" || root.tool === "ellipse"
                                      || root.tool === "arrow"
    readonly property bool usesWidth: root.tool !== "text"
                                      && root.tool !== "blur_rect"
                                      && root.tool !== "pixelate_rect"

    // 信号名用 finishRequested（不用 completed：与 Component.onCompleted 的
    // 处理器名空间相邻，易混淆且不可靠）。
    signal finishRequested()
    signal cancelled()
    signal undoLastRequested()
    signal clearRequested()

    spacing: Theme.spacingSm

    Rectangle {
        width: toolRow.implicitWidth + Theme.spacingMd * 2
        height: toolRow.implicitHeight + Theme.spacingSm * 2
        radius: Theme.radiusMd
        color: Theme.surface
        border.color: Theme.border
        border.width: 1

        RowLayout {
            id: toolRow
            anchors.centerIn: parent
            spacing: Theme.spacingSm

            Repeater {
                model: root.tools

                delegate: AppToolButton {
                    id: toolButton

                    required property var modelData

                    display: AbstractButton.TextOnly
                    text: modelData.label
                    tooltipText: modelData.label
                    checkable: true
                    autoExclusive: true
                    checked: root.tool === modelData.key
                    onClicked: root.tool = modelData.key
                }
            }

            Rectangle {  // 分组竖线（AppTopToolbar.GroupRule 同款 1px border）
                width: 1
                height: 20
                color: Theme.border
                Layout.alignment: Qt.AlignVCenter
            }

            AppColorField {
                visible: root.usesColor
                value: root.color
                onValueModified: root.color = value
            }

            AppSliderField {
                // 粗细：画笔/橡皮/箭头线宽与矩形/椭圆描边（文字与两个区域工具隐藏）。
                visible: root.usesWidth
                label: qsTr("粗细")
                from: 1; to: 40; step: 1; defaultValue: 4
                value: root.strokeWidth
                onValueModified: root.strokeWidth = value
            }

            AppSliderField {
                // 字号（文字工具）。
                visible: root.tool === "text"
                label: qsTr("字号")
                from: 8; to: 96; step: 1; defaultValue: 24
                value: root.textSize
                onValueModified: root.textSize = value
            }

            AppSliderField {
                // 强度 = blur_rect 的高斯模糊半径（协议 0<r≤100，image_adapter）。
                visible: root.tool === "blur_rect"
                label: qsTr("强度")
                from: 1; to: 100; step: 1; defaultValue: 10
                value: root.strength
                onValueModified: root.strength = value
            }

            AppSliderField {
                // 块尺寸 = pixelate_rect 的马赛克块（协议 ≥2 整数）。
                visible: root.tool === "pixelate_rect"
                label: qsTr("块大小")
                from: 2; to: 64; step: 1; defaultValue: 16
                value: root.blockSize
                onValueModified: root.blockSize = value
            }

            Rectangle {
                width: 1
                height: 20
                color: Theme.border
                Layout.alignment: Qt.AlignVCenter
            }

            AppButton {
                size: AppButton.Size.Small
                text: qsTr("撤销上一笔")
                enabled: root.opCount > 0
                onClicked: root.undoLastRequested()
            }
            AppButton {
                size: AppButton.Size.Small
                text: qsTr("清空")
                enabled: root.opCount > 0
                onClicked: root.clearRequested()
            }
            AppButton {
                kind: AppButton.Kind.Primary
                size: AppButton.Size.Small
                text: qsTr("完成标注")
                enabled: root.opCount > 0
                onClicked: root.finishRequested()
            }
            AppButton {
                size: AppButton.Size.Small
                text: qsTr("取消")
                onClicked: root.cancelled()
            }
        }
    }
}
