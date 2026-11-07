import QtQuick
import QtQuick.Controls

// 原图/当前图滑块对比（Phase 9）：两幅 QQuickImage 叠加，分割线左侧露出
// 原图、右侧显示当前图；分割线可拖动。宿主（EditorPage）以 compareActive
// 控制显隐，进入时禁用其他交互（工具栏缩放/历史按钮与检查器），Esc 或再点
// 工具栏按钮退出（退出键在宿主：本组件不持有模式状态）。
//
// 源：originalSource = 打开时的本地文件 URL（openFile 记录，未编辑的源图）；
// currentSource = 画布当前 source（最近一次预览文件 URL）。两侧均为
// PreserveAspectFit 居中：若当前图与原图纵横比不同（裁剪/旋转后），两侧
// 内容不逐像素对位，按各自外接框居中对比——对比是辅助视图，取真值以画布
// 与文档状态为准（组件内不做任何像素级对位计算）。
Item {
    id: root

    property url originalSource: ""
    property url currentSource: ""
    property real position: 0.5   // 分割线位置（0..1，宽度占比）

    onPositionChanged: position = Math.max(0.02, Math.min(0.98, position))

    // ---- 当前图（底层，全幅）---------------------------------------------------
    Image {
        anchors.fill: parent
        source: root.currentSource
        fillMode: Image.PreserveAspectFit
        asynchronous: false
        cache: false
    }

    // ---- 原图（上层，按分割线宽度裁剪露左半）----------------------------------
    Item {
        x: 0
        y: 0
        width: root.position * root.width
        height: parent.height
        clip: true

        Image {
            // 尺寸锚定到整个覆盖层（而非裁剪窗），保证两侧同一外接框对齐。
            x: 0
            y: 0
            width: root.width
            height: root.height
            source: root.originalSource
            fillMode: Image.PreserveAspectFit
            asynchronous: false
            cache: false
        }
    }

    // ---- 分割线 + 手柄 + 拖拽 ---------------------------------------------------
    Rectangle {
        x: root.position * root.width - width / 2
        y: 0
        width: 2
        height: parent.height
        color: Theme.accent
    }

    Rectangle {
        x: root.position * root.width - width / 2
        y: parent.height / 2 - height / 2
        width: 28
        height: 28
        radius: height / 2  // 圆形手柄由自身尺寸导出
        color: Theme.surface
        border.color: Theme.accent
        border.width: 1

        Canvas {
            anchors.centerIn: parent
            width: 16
            height: 10

            onPaint: {
                const ctx = getContext("2d");
                ctx.reset();
                ctx.strokeStyle = Theme.textPrimary.toString();
                ctx.lineWidth = 1.5;  // design-system §5 icon stroke width
                ctx.lineCap = "round";
                ctx.beginPath();
                ctx.moveTo(6, 1); ctx.lineTo(1, 5); ctx.lineTo(6, 9);   // ◂
                ctx.moveTo(10, 1); ctx.lineTo(15, 5); ctx.lineTo(10, 9); // ▸
                ctx.stroke();
            }
        }
    }

    MouseArea {
        id: dragArea

        anchors.fill: parent
        hoverEnabled: false
        acceptedButtons: Qt.LeftButton
        cursorShape: Qt.SplitHCursor

        onPressed: function (mouse) { root.position = mouse.x / root.width; }
        onPositionChanged: function (mouse) {
            if (pressed)
                root.position = mouse.x / root.width;
        }
        onWheel: (wheel) => { wheel.accepted = true; }  // 对比中冻结缩放
    }

    // ---- 角标 -------------------------------------------------------------------
    Rectangle {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: Theme.spacingMd
        width: origLabel.implicitWidth + Theme.spacingSm * 2
        height: origLabel.implicitHeight + Theme.spacingXs * 2
        radius: Theme.radiusSm
        color: Theme.overlayScrim

        Label {
            id: origLabel
            anchors.centerIn: parent
            text: qsTr("原图")
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.textPrimary
        }
    }
    Rectangle {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: Theme.spacingMd
        width: curLabel.implicitWidth + Theme.spacingSm * 2
        height: curLabel.implicitHeight + Theme.spacingXs * 2
        radius: Theme.radiusSm
        color: Theme.overlayScrim

        Label {
            id: curLabel
            anchors.centerIn: parent
            text: qsTr("当前")
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.textPrimary
        }
    }
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.margins: Theme.spacingMd
        width: hintLabel.implicitWidth + Theme.spacingSm * 2
        height: hintLabel.implicitHeight + Theme.spacingXs * 2
        radius: Theme.radiusSm
        color: Theme.overlayScrim

        Label {
            id: hintLabel
            anchors.centerIn: parent
            text: qsTr("拖动分割线对比原图与当前图 · Esc 退出")
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.textPrimary
        }
    }
}
