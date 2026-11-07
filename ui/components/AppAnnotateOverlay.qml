import QtQuick
import QtQuick.Controls

// 标注画布采集层（Phase 9 标注模式）：MouseArea 在画布上采集点序列/矩形，
// 松手生成**单个 op** 追加到待提交 ops 数组，并即时在本地 Canvas 预览层叠加
// 渲染。任务口径：预览层用 Canvas 矢量绘制已提交 op 的**近似**渲染，不做
// 任何 QML 像素计算（最终渲染由 Worker 端 applyAnnotate 全分辨率完成）。
//
// op 形状（文档像素坐标，与协议 docs/ipc-protocol.md §3.9 image.annotate
// 逐键一致）：
//   pen          {type, points: [[x,y]×n≥2], color, width}
//   eraser       {type, points: [[x,y]×n≥2], width}
//   rect         {type, x, y, width, height, color, stroke_width}
//   ellipse      {type, x, y, width, height, color, stroke_width}
//   arrow        {type, x1, y1, x2, y2, color, width}
//   text         {type, x, y, text, font_size, color}
//   blur_rect    {type, x, y, width, height, strength}   // strength=高斯半径 0<r≤100
//   pixelate_rect{type, x, y, width, height, block}      // block=马赛克块 ≥2
//
// 近似渲染与最终渲染的差异（如实声明）：
// - pen/rect/ellipse/arrow/text：矢量形状一致，线端/抗锯齿与 Worker（PIL）
//   实现有细微差别；
// - eraser：Worker 语义是把笔画覆盖的像素恢复为源图（open 态）基线；预览层
//   只能对本地已画 op 的预览像素做 destination-out 擦除——只能擦掉本会话
//   画上的标注，擦不掉文档里既有的内容差异，且与 Worker 对"几何变换后的
//   文档"的退化语义（等效恢复本动作应用前像素）不同；
// - blur_rect：预览只画半透明灰色块（QML 不做像素级模糊），Worker 才做真实
//   高斯模糊；
// - pixelate_rect：预览画半透明块 + 网格示意，Worker 才做真实块状量化；
// - 文字字体：预览用 QML 默认字体，Worker 端字体候选链（MiSans → Noto CJK →
//   DejaVu → PIL 内置）字形有差异（协议 §3.9 已声明像素结果不跨机锁定）。
//
// 显示矩形推演与视图冻结假设同 AppCropOverlay 文件头。ops 存文档像素，
// [完成标注] 由宿主经 DocumentService.applyAnnotate(ops) 全分辨率提交
// （本层不触碰服务）；[撤销]（已提交后）沿用编辑器 undo 参数化 replay。
Item {
    id: root

    // ---- 宿主注入（画布同源 + 工具栏参数绑定）-------------------------------
    required property real zoom
    required property int imageWidth            // 预览像素（canvas.imageSize）
    required property int imageHeight
    required property int documentWidth         // 当前文档尺寸（文档像素）
    required property int documentHeight
    property string tool: "pen"
    property color strokeColor: Theme.error
    property real strokeWidth: 4
    property real textSize: 24
    property real strength: 10          // blur_rect 高斯半径（协议 0<r≤100）
    property real blockSize: 16         // pixelate_rect 块尺寸（协议 ≥2）

    // 待提交 ops（文档像素）；undoLast()/clearOps() 供工具栏撤销/清空。
    // ops 的变更信号由 property var 自动派生（opsChanged），宿主按
    // ops.length 绑定工具栏按钮；任何变化都重绘预览层。
    property var ops: []
    onOpsChanged: drawCanvas.requestPaint()

    function undoLast() {
        if (root.ops.length === 0)
            return;
        const next = root.ops.slice(0, -1);
        root.ops = next;
    }

    function clearOps() {
        if (root.ops.length === 0)
            return;
        root.ops = [];
    }

    // 模式退出（宿主置 visible=false）时丢弃在画状态：文字输入框不落 op
    // （退出标注即放弃未提交编辑），拖拽半途状态一并复位。
    onVisibleChanged: {
        if (visible)
            return;
        textEditor.visible = false;
        root.drawing = false;
        root.livePoints = [];
        drawCanvas.requestPaint();
    }

    // ---- 显示矩形（视口坐标，居中假设同 AppCropOverlay）---------------------
    readonly property real dispX: (root.width - root.imageWidth * root.zoom) / 2
    readonly property real dispY: (root.height - root.imageHeight * root.zoom) / 2
    readonly property real dispW: root.imageWidth * root.zoom
    readonly property real dispH: root.imageHeight * root.zoom

    // ---- 视口 ↔ 文档像素换算（口径同 AppCropOverlay）------------------------
    function toDocumentPoint(px, py) {
        const kx = root.imageWidth > 0 ? root.documentWidth / root.imageWidth : 1;
        const ky = root.imageHeight > 0 ? root.documentHeight / root.imageHeight : kx;
        return { x: (px - root.dispX) / root.zoom * kx,
                 y: (py - root.dispY) / root.zoom * ky };
    }

    function toItemPoint(docX, docY) {
        const kx = root.documentWidth > 0 ? root.imageWidth / root.documentWidth : 1;
        const ky = root.documentHeight > 0 ? root.imageHeight / root.documentHeight : kx;
        return { x: root.dispX + docX * kx * root.zoom,
                 y: root.dispY + docY * ky * root.zoom };
    }

    readonly property real docScale:
        root.documentWidth > 0 ? root.imageWidth / root.documentWidth : 1

    function colorHex(c) {
        const hex2 = (v) => Math.round(v * 255).toString(16).padStart(2, "0");
        return "#" + hex2(c.r) + hex2(c.g) + hex2(c.b);
    }

    // ---- 采集状态机 -----------------------------------------------------------
    // drawing: 正在拖拽（pen/eraser 点序列或矩形类）；dragKind 复用 tool 词表。
    property bool drawing: false
    property var livePoints: []          // pen/eraser 在画点序列（视口坐标）
    property point dragStart             // 矩形类/箭头起点（视口坐标）
    property point dragCur               // 矩形类/箭头当前点（视口坐标）

    function commitOp(op) {
        const next = root.ops.slice();
        next.push(op);
        root.ops = next;
    }

    // ---- 交互层（视图冻结 + 采集；浮条与文字编辑器在其后声明）----------------
    MouseArea {
        id: captureArea

        anchors.fill: parent
        hoverEnabled: false
        acceptedButtons: Qt.LeftButton
        cursorShape: Qt.CrossCursor

        onPressed: function (mouse) {
            if (!root.isCanvasPoint(mouse.x, mouse.y))
                return;
            if (root.tool === "text") {
                root.openTextEditor(mouse.x, mouse.y);
                return;
            }
            root.drawing = true;
            root.dragStart = Qt.point(mouse.x, mouse.y);
            root.dragCur = root.dragStart;
            root.livePoints = [root.dragStart];
            drawCanvas.requestPaint();
        }
        onPositionChanged: function (mouse) {
            if (!root.drawing)
                return;
            root.dragCur = Qt.point(mouse.x, mouse.y);
            if (root.tool === "pen" || root.tool === "eraser") {
                // 点距 ≥ 2 视口 px 才记录（避免同点堆积）。
                const last = root.livePoints[root.livePoints.length - 1];
                const dx = mouse.x - last.x, dy = mouse.y - last.y;
                if (dx * dx + dy * dy >= 4)
                    root.livePoints.push(root.dragCur);
            }
            drawCanvas.requestPaint();
        }
        onReleased: function (mouse) {
            if (!root.drawing)
                return;
            root.drawing = false;
            root.dragCur = Qt.point(mouse.x, mouse.y);
            root.commitLive();
            drawCanvas.requestPaint();
        }
        onWheel: (wheel) => { wheel.accepted = true; }  // 冻结缩放
    }

    function isCanvasPoint(px, py) {
        return px >= root.dispX && px <= root.dispX + root.dispW
                && py >= root.dispY && py <= root.dispY + root.dispH;
    }

    // 松手：把在画形状固化为单个 op（文档像素）追加进 ops。
    function commitLive() {
        const color = root.colorHex(root.strokeColor);
        if (root.tool === "pen" || root.tool === "eraser") {
            if (root.livePoints.length < 2)
                return;  // 单点噪声不成笔
            const docPoints = [];
            for (let i = 0; i < root.livePoints.length; ++i) {
                const p = root.toDocumentPoint(root.livePoints[i].x, root.livePoints[i].y);
                docPoints.push([Math.round(p.x), Math.round(p.y)]);
            }
            const op = { type: root.tool, points: docPoints,
                         width: Math.max(1, Math.round(root.strokeWidth)) };
            if (root.tool === "pen")
                op.color = color;
            root.commitOp(op);
            root.livePoints = [];
            return;
        }

        const w = Math.abs(root.dragCur.x - root.dragStart.x);
        const h = Math.abs(root.dragCur.y - root.dragStart.y);
        if (root.tool === "arrow") {
            if (w * w + h * h < 9)
                return;  // 太短的箭头视为误触
            const a = root.toDocumentPoint(root.dragStart.x, root.dragStart.y);
            const b = root.toDocumentPoint(root.dragCur.x, root.dragCur.y);
            root.commitOp({ type: "arrow", x1: Math.round(a.x), y1: Math.round(a.y),
                            x2: Math.round(b.x), y2: Math.round(b.y), color: color,
                            width: Math.max(1, Math.round(root.strokeWidth)) });
            return;
        }

        // 矩形类（rect/ellipse/blur_rect/pixelate_rect）：太小视为误触。
        if (w < 3 || h < 3)
            return;
        const tl = root.toDocumentPoint(Math.min(root.dragStart.x, root.dragCur.x),
                                        Math.min(root.dragStart.y, root.dragCur.y));
        const dw = Math.round(w / root.zoom * (root.imageWidth > 0 ? root.documentWidth / root.imageWidth : 1));
        const dh = Math.round(h / root.zoom * (root.imageHeight > 0 ? root.documentHeight / root.imageHeight : 1));
        const base = { x: Math.round(tl.x), y: Math.round(tl.y), width: dw, height: dh };
        if (root.tool === "rect" || root.tool === "ellipse") {
            // 协议 §3.9：几何 width/height 与描边 stroke_width 异名（JSON 单键）。
            base.type = root.tool;
            base.color = color;
            base.stroke_width = Math.max(1, Math.round(root.strokeWidth));
        } else if (root.tool === "blur_rect") {
            base.type = "blur_rect";
            base.strength = Math.max(1, Math.round(root.strength));  // 0<r≤100
        } else {
            base.type = "pixelate_rect";
            base.block = Math.max(2, Math.round(root.blockSize));    // ≥2
        }
        root.commitOp(base);
    }

    // ---- 文字工具的内联输入框 --------------------------------------------------
    Rectangle {
        id: textEditor

        visible: false
        width: 220
        height: 36
        radius: Theme.radiusSm
        color: Theme.surface
        border.color: Theme.accent
        border.width: 1
        z: 2

        property point docPoint  // 提交锚点（文档像素）

        function commit() {
            const textValue = textField.text.trim();
            visible = false;
            // 标注模式已退出（宿主隐藏 overlay）时的焦点丢失不走提交。
            if (!root.visible)
                return;
            if (textValue === "")
                return;  // 空文本不成 op
            root.commitOp({ type: "text", x: Math.round(docPoint.x),
                            y: Math.round(docPoint.y), text: textValue,
                            font_size: Math.max(1, Math.round(root.textSize)),
                            color: root.colorHex(root.strokeColor) });
            textField.text = "";
        }

        AppTextField {
            id: textField
            anchors.fill: parent
            anchors.margins: Theme.spacingSm
            font.pixelSize: Theme.fontSizeBody
            placeholderText: qsTr("输入文字，Enter 提交")
            onAccepted: textEditor.commit()
            onActiveFocusChanged: if (!activeFocus && visible) textEditor.commit()
        }
    }

    function openTextEditor(px, py) {
        // 编辑框已开着时先提交上一段（复用同一实例，避免静默丢弃）。
        if (textEditor.visible)
            textEditor.commit();
        const doc = root.toDocumentPoint(px, py);
        textEditor.docPoint = Qt.point(doc.x, doc.y);
        // 输入框钳在视口内（右/下边界内缩一个框宽高）。
        textEditor.x = Math.min(px, root.width - textEditor.width - Theme.spacingSm);
        textEditor.y = Math.min(py, root.height - textEditor.height - Theme.spacingSm);
        textEditor.visible = true;
        textField.text = "";
        textField.forceActiveFocus();
    }

    // ---- 预览层：Canvas 矢量绘制（近似渲染，差异见文件头）---------------------
    Canvas {
        id: drawCanvas

        anchors.fill: parent

        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            if (root.dispW <= 0 || root.dispH <= 0)
                return;

            // 已提交 ops（文档像素 → 视口）逐个重放；eraser 用 destination-out
            // 按序擦除（重放次序即合成次序）。
            for (let i = 0; i < root.ops.length; ++i)
                root.paintOp(ctx, root.ops[i]);
            if (root.drawing)
                root.paintLive(ctx);
        }
    }

    function paintOp(ctx, op) {
        const s = root.docScale * root.zoom;  // 文档像素 → 视口
        ctx.lineWidth = Math.max(1, (op.width !== undefined ? op.width : 1) * s);
        ctx.strokeStyle = op.color !== undefined ? op.color : Theme.accent.toString();
        ctx.fillStyle = op.color !== undefined ? op.color : Theme.accent.toString();
        ctx.lineCap = "round";
        ctx.lineJoin = "round";

        if (op.type === "pen" || op.type === "eraser") {
            if (op.type === "eraser")
                ctx.globalCompositeOperation = "destination-out";
            ctx.beginPath();
            for (let i = 0; i < op.points.length; ++i) {
                const p = root.toItemPoint(op.points[i][0], op.points[i][1]);
                if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
            }
            ctx.stroke();
            ctx.globalCompositeOperation = "source-over";
            return;
        }
        if (op.type === "rect" || op.type === "ellipse" || op.type === "blur_rect"
                || op.type === "pixelate_rect") {
            const p = root.toItemPoint(op.x, op.y);
            const w = op.width * s, h = op.height * s;
            if (op.type === "rect" || op.type === "ellipse") {
                ctx.lineWidth = Math.max(1, (op.stroke_width !== undefined ? op.stroke_width : 1) * s);
            }
            if (op.type === "rect") {
                ctx.strokeRect(p.x, p.y, w, h);
                return;
            }
            if (op.type === "ellipse") {
                ctx.beginPath();
                ctx.ellipse(p.x + w / 2, p.y + h / 2, Math.abs(w / 2), Math.abs(h / 2),
                            0, 0, Math.PI * 2);
                ctx.stroke();
                return;
            }
            // blur_rect/pixelate_rect 近似：半透明灰块（+像素化网格示意），
            // 虚线框标范围。
            ctx.fillStyle = "rgba(128, 128, 128, 0.45)";
            ctx.fillRect(p.x, p.y, w, h);
            ctx.setLineDash([4, 3]);
            ctx.lineWidth = 1;
            ctx.strokeStyle = Theme.textSecondary.toString();
            ctx.strokeRect(p.x, p.y, w, h);
            ctx.setLineDash([]);
            if (op.type === "pixelate_rect") {
                const block = Math.max(3, (op.block !== undefined ? op.block : 16) * s);
                ctx.strokeStyle = "rgba(255, 255, 255, 0.35)";
                ctx.beginPath();
                for (let gx = p.x + block; gx < p.x + w; gx += block) {
                    ctx.moveTo(gx, p.y); ctx.lineTo(gx, p.y + h);
                }
                for (let gy = p.y + block; gy < p.y + h; gy += block) {
                    ctx.moveTo(p.x, gy); ctx.lineTo(p.x + w, gy);
                }
                ctx.stroke();
            }
            return;
        }
        if (op.type === "arrow") {
            const a = root.toItemPoint(op.x1, op.y1);
            const b = root.toItemPoint(op.x2, op.y2);
            root.drawArrowSegment(ctx, a.x, a.y, b.x, b.y, ctx.lineWidth);
            return;
        }
        if (op.type === "text") {
            const p = root.toItemPoint(op.x, op.y);
            ctx.font = Math.max(8, op.font_size * s) + "px sans-serif";
            ctx.textBaseline = "top";
            ctx.fillText(op.text, p.x, p.y);
            return;
        }
    }

    // 箭头线段 + 头部（等腰三角，头长随线宽）。paintOp 与 paintLive 共用。
    function drawArrowSegment(ctx, ax, ay, bx, by, lineWidth) {
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();
        const dx = bx - ax, dy = by - ay;
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len < 1)
            return;
        const ux = dx / len, uy = dy / len;
        const head = Math.max(8, lineWidth * 3);
        ctx.beginPath();
        ctx.moveTo(bx, by);
        ctx.lineTo(bx - ux * head + uy * head * 0.45,
                   by - uy * head - ux * head * 0.45);
        ctx.lineTo(bx - ux * head - uy * head * 0.45,
                   by - uy * head + ux * head * 0.45);
        ctx.closePath();
        ctx.fill();
    }

    // 在画形状（视口坐标直绘，松手时才换算为文档像素 op）。
    function paintLive(ctx) {
        ctx.strokeStyle = root.colorHex(root.strokeColor);
        ctx.fillStyle = root.colorHex(root.strokeColor);
        ctx.lineWidth = Math.max(1, root.strokeWidth * root.zoom);
        ctx.lineCap = "round";
        ctx.lineJoin = "round";

        if (root.tool === "pen" || root.tool === "eraser") {
            if (root.tool === "eraser")
                ctx.globalCompositeOperation = "destination-out";
            ctx.beginPath();
            for (let i = 0; i < root.livePoints.length; ++i) {
                if (i === 0) ctx.moveTo(root.livePoints[i].x, root.livePoints[i].y);
                else ctx.lineTo(root.livePoints[i].x, root.livePoints[i].y);
            }
            ctx.stroke();
            ctx.globalCompositeOperation = "source-over";
            return;
        }
        if (root.tool === "rect") {
            ctx.strokeRect(Math.min(root.dragStart.x, root.dragCur.x),
                           Math.min(root.dragStart.y, root.dragCur.y),
                           Math.abs(root.dragCur.x - root.dragStart.x),
                           Math.abs(root.dragCur.y - root.dragStart.y));
            return;
        }
        if (root.tool === "ellipse") {
            const x = Math.min(root.dragStart.x, root.dragCur.x);
            const y = Math.min(root.dragStart.y, root.dragCur.y);
            const w = Math.abs(root.dragCur.x - root.dragStart.x);
            const h = Math.abs(root.dragCur.y - root.dragStart.y);
            ctx.beginPath();
            ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2);
            ctx.stroke();
            return;
        }
        if (root.tool === "arrow") {
            root.drawArrowSegment(ctx, root.dragStart.x, root.dragStart.y,
                                  root.dragCur.x, root.dragCur.y, ctx.lineWidth);
            return;
        }
        if (root.tool === "blur_rect" || root.tool === "pixelate_rect") {
            // 在画期间的近似渲染（半透明灰块；松手后已提交 op 才带网格示意）。
            ctx.fillStyle = "rgba(128, 128, 128, 0.45)";
            ctx.fillRect(Math.min(root.dragStart.x, root.dragCur.x),
                         Math.min(root.dragStart.y, root.dragCur.y),
                         Math.abs(root.dragCur.x - root.dragStart.x),
                         Math.abs(root.dragCur.y - root.dragStart.y));
            return;
        }
    }
}
