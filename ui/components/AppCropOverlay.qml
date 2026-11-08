import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 画布裁剪交互层（Phase 9 变换页签的画布侧，docs/ui-component-spec.md §3 画布
// 交互层的 App* 组件化口径）。宿主（EditorPage）进入裁剪模式时显示本层，且
// 进入前先调 canvas.fitToWindow()：
//
// 显示矩形推演（native/graphics/image_canvas.cpp imageRect 同式）：画布把
// 预览文件按 zoom 居中显示（fitToWindow / setActualSize / zoomBy 都保持
// "图像中心 = 视口中心"，image_canvas.cpp:105-133），本层据此自行推算显示
// 矩形 dispRect = ((viewW - imgW*zoom)/2, (viewH - imgH*zoom)/2, ...)。激活
// 期间本层 MouseArea 吞掉全部鼠标与滚轮事件（画布无法拖动平移/缩放，
// panOffset 不漂移），居中假设因此始终成立；宿主另以 page.canvasModeActive
// 禁用工具栏缩放按钮与检查器作为第二道保险。
//
// 坐标换算（画布缩放 → 原图像素，任务口径）：拖拽都在视口坐标；应用时按
// dispRect → 预览像素 → 文档像素两级换算（预览与文档同比例，k =
// documentWidth / imageWidth）。documentWidth/Height 由宿主维护
// （documentOpened 种入，几何类全分辨率应用后按其确定性输出尺寸更新）。
//
// 交互：八向手柄（四角 + 四边）拖拽、矩形整体拖动、显示矩形内重新拉框、
// 暗区遮罩、三分线、比例锁定 AppSelectField（自由/1:1/4:3/3:4/16:9/9:16）。
// [应用] 组装 {x, y, width, height}（文档像素）经 applyRequested 交宿主
// DocumentService.applyTransform（全分辨率）；本层不触碰任何服务（QML 不发
// sendAction 的纪律同 AppFilterInspector 文件头）。
Item {
    id: root

    // ---- 宿主注入（与画布同源，组件内不自造状态）---------------------------
    required property real zoom                 // canvas.zoom
    required property int imageWidth            // canvas.imageSize.width（预览像素）
    required property int imageHeight
    required property int documentWidth         // 当前文档尺寸（文档像素）
    required property int documentHeight

    // 应用（crop 矩形，文档像素 {x,y,width,height}）/ 取消。
    signal applyRequested(variant crop)
    signal cancelled()

    // ---- 显示矩形（视口坐标，居中假设见文件头）------------------------------
    readonly property real dispX: (root.width - root.imageWidth * root.zoom) / 2
    readonly property real dispY: (root.height - root.imageHeight * root.zoom) / 2
    readonly property real dispW: root.imageWidth * root.zoom
    readonly property real dispH: root.imageHeight * root.zoom

    // ---- 选区（视口坐标）-----------------------------------------------------
    property real selX: 0
    property real selY: 0
    property real selW: 0
    property real selH: 0

    // 比例锁定：0 = 自由，否则 w/h 比值（AppSelectField 驱动）。
    property real ratioLock: 0

    readonly property int handleRadius: 12      // 手柄命中半径（视口 px）
    readonly property real minSelSize: 16       // 选区最小边（视口 px）

    // 选区的文档像素尺寸（浮条展示）。
    readonly property real selDocW:
        root.selW / root.zoom * (root.imageWidth > 0 ? root.documentWidth / root.imageWidth : 1)
    readonly property real selDocH:
        root.selH / root.zoom * (root.imageHeight > 0 ? root.documentHeight / root.imageHeight : 1)

    onVisibleChanged: if (visible) root.resetSelection()

    function resetSelection() {
        // 初始选区：显示矩形四边各内缩 1/8（留一圈可拖的手柄空隙）。
        const inset = 0.125;
        root.selX = root.dispX + root.dispW * inset;
        root.selY = root.dispY + root.dispH * inset;
        root.selW = root.dispW * (1 - inset * 2);
        root.selH = root.dispH * (1 - inset * 2);
        root.applyRatio();
    }

    // ---- 视口 → 文档像素换算 -------------------------------------------------
    function toDocumentPoint(px, py) {
        const kx = root.imageWidth > 0 ? root.documentWidth / root.imageWidth : 1;
        const ky = root.imageHeight > 0 ? root.documentHeight / root.imageHeight : kx;
        return { x: (px - root.dispX) / root.zoom * kx,
                 y: (py - root.dispY) / root.zoom * ky };
    }

    // ---- 选区几何运算 ---------------------------------------------------------
    function clampToDisplay(x, y, w, h) {
        // 位置与尺寸一并钳回显示矩形，保持最小边（minSelSize 视口 px）。
        w = Math.max(root.minSelSize, Math.min(w, root.dispW));
        h = Math.max(root.minSelSize, Math.min(h, root.dispH));
        x = Math.max(root.dispX, Math.min(x, root.dispX + root.dispW - w));
        y = Math.max(root.dispY, Math.min(y, root.dispY + root.dispH - h));
        return { x: x, y: y, w: w, h: h };
    }

    // 比例锁定落到当前选区：以宽定高（超界时以高定宽），居中补偿后整体钳回。
    function applyRatio() {
        if (root.ratioLock <= 0)
            return;
        let w = root.selW;
        let h = w / root.ratioLock;
        if (h > root.dispH) {
            h = root.dispH;
            w = h * root.ratioLock;
        }
        const cx = root.selX + root.selW / 2;
        const cy = root.selY + root.selH / 2;
        const clamped = root.clampToDisplay(cx - w / 2, cy - h / 2, w, h);
        root.selX = clamped.x; root.selY = clamped.y;
        root.selW = clamped.w; root.selH = clamped.h;
    }

    // ---- 手柄命中测试（返回拖拽模式）-----------------------------------------
    function hitTest(px, py) {
        const r = root.handleRadius;
        const left = root.selX, right = root.selX + root.selW;
        const top = root.selY, bottom = root.selY + root.selH;
        const nearL = Math.abs(px - left) <= r;
        const nearR = Math.abs(px - right) <= r;
        const nearT = Math.abs(py - top) <= r;
        const nearB = Math.abs(py - bottom) <= r;
        const inV = py >= top - r && py <= bottom + r;
        const inH = px >= left - r && px <= right + r;
        if (nearL && nearT && inH && inV) return "nw";
        if (nearR && nearT && inH && inV) return "ne";
        if (nearR && nearB && inH && inV) return "se";
        if (nearL && nearB && inH && inV) return "sw";
        if (nearT && inH) return "n";
        if (nearB && inH) return "s";
        if (nearL && inV) return "w";
        if (nearR && inV) return "e";
        if (px > left && px < right && py > top && py < bottom) return "move";
        return "new";
    }

    function cursorFor(mode) {
        switch (mode) {
        case "nw": case "se": return Qt.SizeFDiagCursor;
        case "ne": case "sw": return Qt.SizeBDiagCursor;
        case "n": case "s": return Qt.SizeVerCursor;
        case "e": case "w": return Qt.SizeHorCursor;
        case "move": return Qt.ArrowCursor;
        default: return Qt.CrossCursor;
        }
    }

    // 拖拽应用：mode + 按下时刻的锚点/选区快照 + 当前点 → 新选区（含比例与
    // 边界约束）。角手柄锚定对角；边手柄锚定对边；"new" 从按下点重新拉框。
    function dragSelection(mode, pressX, pressY, curX, curY) {
        const pr = dragArea.pressRect;
        let x = pr.x, y = pr.y, w = pr.width, h = pr.height;

        if (mode === "move") {
            const dx = curX - pressX, dy = curY - pressY;
            x = Math.max(root.dispX, Math.min(pr.x + dx, root.dispX + root.dispW - pr.width));
            y = Math.max(root.dispY, Math.min(pr.y + dy, root.dispY + root.dispH - pr.height));
        } else if (mode === "new") {
            x = Math.min(pressX, curX);
            y = Math.min(pressY, curY);
            w = Math.abs(curX - pressX);
            h = Math.abs(curY - pressY);
            if (root.ratioLock > 0) {
                h = w / root.ratioLock;
                if (curY < pressY) y = pressY - h;
            }
        } else {
            // 角/边手柄：按方向改写对应边。
            const east = mode.indexOf("e") >= 0, west = mode.indexOf("w") >= 0;
            const north = mode.indexOf("n") >= 0, south = mode.indexOf("s") >= 0;
            if (east) w = Math.max(root.minSelSize, curX - pr.x);
            if (west) { w = Math.max(root.minSelSize, pr.x + pr.width - curX); x = pr.x + pr.width - w; }
            if (south) h = Math.max(root.minSelSize, curY - pr.y);
            if (north) { h = Math.max(root.minSelSize, pr.y + pr.height - curY); y = pr.y + pr.height - h; }

            if (root.ratioLock > 0) {
                if (north || south) {
                    // 纵向边驱动：以高定宽，水平对中于原选区。
                    const cx = pr.x + pr.width / 2;
                    w = h * root.ratioLock;
                    x = cx - w / 2;
                } else if (east || west) {
                    // 横向边驱动：以宽定高，垂直对中于原选区。
                    const cy = pr.y + pr.height / 2;
                    h = w / root.ratioLock;
                    y = cy - h / 2;
                }
            }
        }

        const clamped = root.clampToDisplay(x, y, w, h);
        root.selX = clamped.x; root.selY = clamped.y;
        root.selW = clamped.w; root.selH = clamped.h;
    }

    // 应用：视口选区 → 文档像素矩形（取整、钳回文档边界），交宿主提交。
    function emitApply() {
        if (root.selW < root.minSelSize || root.selH < root.minSelSize)
            return;
        const tl = root.toDocumentPoint(root.selX, root.selY);
        const br = root.toDocumentPoint(root.selX + root.selW, root.selY + root.selH);
        const x = Math.max(0, Math.min(root.documentWidth - 1, Math.round(Math.min(tl.x, br.x))));
        const y = Math.max(0, Math.min(root.documentHeight - 1, Math.round(Math.min(tl.y, br.y))));
        const w = Math.max(1, Math.min(root.documentWidth - x, Math.round(Math.abs(br.x - tl.x))));
        const h = Math.max(1, Math.min(root.documentHeight - y, Math.round(Math.abs(br.y - tl.y))));
        root.applyRequested({ x: x, y: y, width: w, height: h });
    }

    // ---- 交互层：吞掉画布的鼠标与滚轮（激活期间视图冻结）--------------------
    // 绘制次序（同 z 按文档序）：遮罩 → 选区框/三分线 → 手柄 → 本 MouseArea
    // （透明、统一命中测试）→ 浮条（在 MouseArea 之后声明，点击优先达）。
    MouseArea {
        id: dragArea

        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton

        // 拖拽状态机：模式 + 按下锚点 + 按下时刻选区快照（锚定对边用）。
        property string dragMode: "none"
        property real pressX: 0
        property real pressY: 0
        property rect pressRect: Qt.rect(0, 0, 0, 0)

        onPressed: function (mouse) {
            dragArea.dragMode = root.hitTest(mouse.x, mouse.y);
            dragArea.pressX = mouse.x;
            dragArea.pressY = mouse.y;
            dragArea.pressRect = Qt.rect(root.selX, root.selY, root.selW, root.selH);
            dragArea.cursorShape = root.cursorFor(dragArea.dragMode);
        }
        onPositionChanged: function (mouse) {
            if (pressed) {
                root.dragSelection(dragArea.dragMode, dragArea.pressX, dragArea.pressY,
                                   mouse.x, mouse.y);
            } else {
                dragArea.cursorShape = root.cursorFor(root.hitTest(mouse.x, mouse.y));
            }
        }
        onReleased: function (mouse) {
            dragArea.dragMode = "none";
            // "new" 松手后过小的矩形弹回重置，避免误触残迹。
            if (root.selW < root.minSelSize || root.selH < root.minSelSize)
                root.resetSelection();
        }
        onWheel: (wheel) => { wheel.accepted = true; }  // 冻结缩放（见文件头）
    }

    // ---- 暗区遮罩（选区外的四条，先声明=先绘制）------------------------------
    Rectangle {
        x: root.dispX
        y: root.dispY
        width: root.dispW
        height: Math.max(0, root.selY - root.dispY)
        color: Theme.overlayScrim
    }
    Rectangle {
        x: root.dispX
        y: root.selY + root.selH
        width: root.dispW
        height: Math.max(0, root.dispY + root.dispH - root.selY - root.selH)
        color: Theme.overlayScrim
    }
    Rectangle {
        x: root.dispX
        y: root.selY
        width: Math.max(0, root.selX - root.dispX)
        height: root.selH
        color: Theme.overlayScrim
    }
    Rectangle {
        x: root.selX + root.selW
        y: root.selY
        width: Math.max(0, root.dispX + root.dispW - root.selX - root.selW)
        height: root.selH
        color: Theme.overlayScrim
    }

    // ---- 选区边框 + 三分线 ----------------------------------------------------
    Rectangle {
        x: root.selX
        y: root.selY
        width: root.selW
        height: root.selH
        color: "transparent"
        border.color: Theme.accent
        border.width: 1

        Rectangle {
            x: parent.width / 3 - 0.5
            y: 0
            width: 1
            height: parent.height
            color: Theme.overlayScrim
        }
        Rectangle {
            x: parent.width * 2 / 3 - 0.5
            y: 0
            width: 1
            height: parent.height
            color: Theme.overlayScrim
        }
        Rectangle {
            x: 0
            y: parent.height / 3 - 0.5
            width: parent.width
            height: 1
            color: Theme.overlayScrim
        }
        Rectangle {
            x: 0
            y: parent.height * 2 / 3 - 0.5
            width: parent.width
            height: 1
            color: Theme.overlayScrim
        }
    }

    // ---- 八向手柄（纯视觉；命中统一走 dragArea.hitTest）----------------------
    component CropHandle: Rectangle {
        color: Theme.surface
        border.color: Theme.accent
        border.width: 1
        radius: Theme.radiusSm
    }

    CropHandle {  // nw
        x: root.selX - width / 2; y: root.selY - height / 2
        width: 10; height: 10
    }
    CropHandle {  // ne
        x: root.selX + root.selW - width / 2; y: root.selY - height / 2
        width: 10; height: 10
    }
    CropHandle {  // se
        x: root.selX + root.selW - width / 2; y: root.selY + root.selH - height / 2
        width: 10; height: 10
    }
    CropHandle {  // sw
        x: root.selX - width / 2; y: root.selY + root.selH - height / 2
        width: 10; height: 10
    }
    CropHandle {  // n
        x: root.selX + root.selW / 2 - width / 2; y: root.selY - height / 2
        width: 14; height: 6
    }
    CropHandle {  // s
        x: root.selX + root.selW / 2 - width / 2; y: root.selY + root.selH - height / 2
        width: 14; height: 6
    }
    CropHandle {  // w
        x: root.selX - width / 2; y: root.selY + root.selH / 2 - height / 2
        width: 6; height: 14
    }
    CropHandle {  // e
        x: root.selX + root.selW - width / 2; y: root.selY + root.selH / 2 - height / 2
        width: 6; height: 14
    }

    // ---- 浮条：比例锁定 + 尺寸 + 应用/取消 -------------------------------------
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.spacingLg
        width: barRow.implicitWidth + Theme.spacingMd * 2
        height: barRow.implicitHeight + Theme.spacingSm * 2
        radius: Theme.radiusMd
        color: Theme.surface
        border.color: Theme.border
        border.width: 1

        RowLayout {
            id: barRow
            anchors.centerIn: parent
            spacing: Theme.spacingMd

            Label {
                text: qsTr("比例")
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textSecondary
            }

            AppSelectField {
                id: ratioSelect
                implicitWidth: 96
                model: [qsTr("自由"), "1:1", "4:3", "3:4", "16:9", "9:16"]
                currentIndex: 0
                onActivated: function (index) {
                    const ratios = [0, 1, 4 / 3, 3 / 4, 16 / 9, 9 / 16];
                    root.ratioLock = ratios[index];
                    root.applyRatio();
                }
            }

            Label {
                // 选区文档像素尺寸（换算口径见文件头）。
                text: Math.round(root.selDocW) + " × " + Math.round(root.selDocH)
                font.pixelSize: Theme.fontSizeNumeric
                color: Theme.textPrimary
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
