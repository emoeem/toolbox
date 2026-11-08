import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 透视校正画布层（Phase 9 变换页签 · 高级折叠区入口）。四角拖拽的简化手柄
// 交互（与 AppCropOverlay 同款：统一命中测试的 MouseArea + 视口坐标拖拽），
// 任一任务要求"复用 AppCropOverlay 手柄交互的简化版或独立 AppPerspective
// Overlay"——独立组件：四角自由拖动 + 四边形连线 + 界外暗化（Canvas even-odd
// 填充），不做比例锁定/整体拖动。
//
// 显示矩形推演与视图冻结假设同 AppCropOverlay 文件头（居中显示 + 本层吞掉
// 鼠标/滚轮 + 宿主 canvasModeActive 门控）。角点钳回显示矩形内。
//
// [应用] 把四角换算为文档像素（TL,TR,BR,BL 顺序 = 初始化顺序，拖拽不改写
// 身份），经 applyRequested({corners: [[x,y]×4]}) 交宿主
// DocumentService.applyTransform({perspective: …})；本层不触碰任何服务。
Item {
    id: root

    // ---- 宿主注入（与画布同源，组件内不自造状态）---------------------------
    required property real zoom
    required property int imageWidth            // 预览像素（canvas.imageSize）
    required property int imageHeight
    required property int documentWidth         // 当前文档尺寸（文档像素）
    required property int documentHeight

    signal applyRequested(variant transform)    // {corners: [[x,y]×4]}，文档像素
    signal cancelled()

    // ---- 显示矩形（视口坐标，居中假设同 AppCropOverlay）---------------------
    readonly property real dispX: (root.width - root.imageWidth * root.zoom) / 2
    readonly property real dispY: (root.height - root.imageHeight * root.zoom) / 2
    readonly property real dispW: root.imageWidth * root.zoom
    readonly property real dispH: root.imageHeight * root.zoom

    // 四角（视口坐标）：TL, TR, BR, BL。身份固定——拖拽只改坐标。
    property var corners: []

    readonly property int grabRadius: 16        // 角点命中半径（视口 px）

    onVisibleChanged: if (visible) root.resetCorners()
    onCornersChanged: quadCanvas.requestPaint()
    onWidthChanged: quadCanvas.requestPaint()
    onHeightChanged: quadCanvas.requestPaint()

    function resetCorners() {
        const inset = 0.1;
        const x0 = root.dispX + root.dispW * inset;
        const y0 = root.dispY + root.dispH * inset;
        const x1 = root.dispX + root.dispW * (1 - inset);
        const y1 = root.dispY + root.dispH * (1 - inset);
        root.corners = [
            { x: x0, y: y0 }, { x: x1, y: y0 },
            { x: x1, y: y1 }, { x: x0, y: y1 }
        ];
    }

    function cornerAt(index) {
        return (root.corners[index] !== undefined) ? root.corners[index] : { x: 0, y: 0 };
    }

    function setCorner(index, px, py) {
        const clamped = [
            Math.max(root.dispX, Math.min(px, root.dispX + root.dispW)),
            Math.max(root.dispY, Math.min(py, root.dispY + root.dispH))
        ];
        const next = root.corners.slice();
        next[index] = { x: clamped[0], y: clamped[1] };
        root.corners = next;
    }

    // ---- 视口 → 文档像素换算（口径同 AppCropOverlay.toDocumentPoint）--------
    function toDocumentPoint(px, py) {
        const kx = root.imageWidth > 0 ? root.documentWidth / root.imageWidth : 1;
        const ky = root.imageHeight > 0 ? root.documentHeight / root.imageHeight : kx;
        return { x: (px - root.dispX) / root.zoom * kx,
                 y: (py - root.dispY) / root.zoom * ky };
    }

    function emitApply() {
        if (root.corners.length !== 4)
            return;
        const docCorners = [];
        for (let i = 0; i < 4; ++i) {
            const p = root.toDocumentPoint(root.corners[i].x, root.corners[i].y);
            docCorners.push([Math.round(p.x), Math.round(p.y)]);
        }
        root.applyRequested({ corners: docCorners });
    }

    // ---- 交互层（视图冻结 + 角点拖拽；点击浮条由声明次序保证优先）------------
    MouseArea {
        id: dragArea

        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton

        property int dragCorner: -1

        onPressed: function (mouse) {
            dragArea.dragCorner = root.nearestCorner(mouse.x, mouse.y);
            dragArea.cursorShape = dragArea.dragCorner >= 0
                    ? Qt.SizeAllCursor : Qt.ArrowCursor;
        }
        onPositionChanged: function (mouse) {
            if (pressed && dragArea.dragCorner >= 0)
                root.setCorner(dragArea.dragCorner, mouse.x, mouse.y);
            else
                dragArea.cursorShape = root.nearestCorner(mouse.x, mouse.y) >= 0
                        ? Qt.SizeAllCursor : Qt.ArrowCursor;
        }
        onReleased: function () { dragArea.dragCorner = -1; }
        onWheel: (wheel) => { wheel.accepted = true; }  // 冻结缩放
    }

    function nearestCorner(px, py) {
        let best = -1;
        let bestDist = root.grabRadius;
        for (let i = 0; i < root.corners.length; ++i) {
            const dx = px - root.corners[i].x;
            const dy = py - root.corners[i].y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist <= bestDist) {
                bestDist = dist;
                best = i;
            }
        }
        return best;
    }

    // ---- 四边形 + 界外暗化 + 角点（Canvas 矢量绘制，无像素处理）--------------
    Canvas {
        id: quadCanvas

        anchors.fill: parent

        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            if (root.corners.length !== 4 || root.dispW <= 0 || root.dispH <= 0)
                return;

            // 界外暗化：外矩形 + 四边形 even-odd 填充（四边形内不被填充）。
            ctx.fillStyle = Theme.overlayScrim.toString();
            ctx.beginPath();
            ctx.moveTo(0, 0);
            ctx.lineTo(width, 0);
            ctx.lineTo(width, height);
            ctx.lineTo(0, height);
            ctx.closePath();
            ctx.moveTo(root.corners[0].x, root.corners[0].y);
            ctx.lineTo(root.corners[1].x, root.corners[1].y);
            ctx.lineTo(root.corners[2].x, root.corners[2].y);
            ctx.lineTo(root.corners[3].x, root.corners[3].y);
            ctx.closePath();
            ctx.fillRule = Qt.OddEvenFill;
            ctx.fill();

            // 四边形连线。
            ctx.strokeStyle = Theme.accent.toString();
            ctx.lineWidth = 1.5;  // design-system §5 icon stroke width
            ctx.beginPath();
            ctx.moveTo(root.corners[0].x, root.corners[0].y);
            ctx.lineTo(root.corners[1].x, root.corners[1].y);
            ctx.lineTo(root.corners[2].x, root.corners[2].y);
            ctx.lineTo(root.corners[3].x, root.corners[3].y);
            ctx.closePath();
            ctx.stroke();

            // 角点手柄（8px 实心方 + accent 描边）。
            ctx.fillStyle = Theme.surface.toString();
            for (let i = 0; i < root.corners.length; ++i) {
                ctx.beginPath();
                ctx.rect(root.corners[i].x - 5, root.corners[i].y - 5, 10, 10);
                ctx.fill();
                ctx.stroke();
            }
        }
    }

    // ---- 浮条：提示 + 应用/取消 ------------------------------------------------
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.spacingLg
        width: perspBarRow.implicitWidth + Theme.spacingMd * 2
        height: perspBarRow.implicitHeight + Theme.spacingSm * 2
        radius: Theme.radiusMd
        color: Theme.surface
        border.color: Theme.border
        border.width: 1

        RowLayout {
            id: perspBarRow
            anchors.centerIn: parent
            spacing: Theme.spacingMd

            Label {
                text: qsTr("拖动四个角点到文档边缘，[应用] 校正透视")
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textSecondary
            }

            AppButton {
                kind: AppButton.Kind.Primary
                text: qsTr("应用")
                onClicked: root.emitApply()
            }
            AppButton {
                text: qsTr("取消")
                onClicked: root.cancelled()
            }
        }
    }
}
