import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Settings page (Phase 4): left group list + right form per ui-page-spec.md §4.
// Groups in this ask: 外观 (theme + fonts wired to FontService/SettingsService,
// diagnose summary) / 工作区 (layout reset) / 后端 (worker paths + start) /
// 关于 (versions). Groups the page spec lists beyond this ask (性能/外部依赖/
// 存储) stay out — no fake controls (总纲 §3.4).
//
// Font semantics mirror app/fonts.py via FontService: every change re-resolves
// the family (resolveFamily) and applies it application-wide
// (applyToApplication). The mono family is persisted and diagnosable now; it
// takes visible effect once Phase 4 mono consumers exist — noted inline.
Page {
    id: page

    background: Rectangle { color: Theme.background }

    // ---- theme (same rules as Main.qml; system resolves to dark for now) --
    function themeIndex() {
        const mode = SettingsService.themeMode;
        if (mode === "light")
            return 1;
        if (mode === "system")
            return 2;
        return 0;
    }

    function applyTheme() {
        Theme.darkMode = SettingsService.themeMode !== "light";
        themeSelector.currentIndex = themeIndex();
    }

    // ---- fonts -------------------------------------------------------------
    // 系统默认 first, then the stored family when it is not part of the
    // service candidate chain, then the chain itself (mirrors the resolution
    // order in FontService::resolveFamily).
    function fontModel() {
        const candidates = FontService.sansCandidates();
        const model = [qsTr("系统默认")];
        const fam = SettingsService.uiFontFamily;
        if (fam !== "" && candidates.indexOf(fam) < 0)
            model.push(fam);
        return model.concat(candidates);
    }

    function monoModel() {
        const candidates = FontService.monoCandidates();
        const model = [qsTr("系统默认")];
        const fam = SettingsService.monoFontFamily;
        if (fam !== "" && candidates.indexOf(fam) < 0)
            model.push(fam);
        return model.concat(candidates);
    }

    function fontIndex() {
        const fam = SettingsService.uiFontFamily;
        if (fam === "")
            return 0;
        const i = fontModel().indexOf(fam);
        return i >= 0 ? i : 0;
    }

    function monoIndex() {
        const fam = SettingsService.monoFontFamily;
        if (fam === "")
            return 0;
        const i = monoModel().indexOf(fam);
        return i >= 0 ? i : 0;
    }

    // Resolve (FontService owns the candidate chains, app/fonts.py order) and
    // apply application-wide. The mono family passes through the same call —
    // QGuiApplication::setFont carries the UI family; mono takes effect in the
    // Phase 4 mono consumers (preview/worker diagnostics).
    function applyFonts() {
        const uiFamily = FontService.resolveFamily(
                    SettingsService.uiFontFamily, FontService.sansCandidates());
        FontService.applyToApplication(uiFamily, SettingsService.uiFontSize);
    }

    function restoreFontDefaults() {
        SettingsService.uiFontFamily = "";
        SettingsService.monoFontFamily = "";
        // SettingsService.kDefaultFontSize — app/fonts.py DEFAULT_SIZE (11).
        SettingsService.uiFontSize = 11;
        uiFontSelect.model = fontModel();
        uiFontSelect.currentIndex = fontIndex();
        monoFontSelect.model = monoModel();
        monoFontSelect.currentIndex = monoIndex();
        sizeField.value = SettingsService.uiFontSize;
        applyFonts();
    }

    function uiResolvedFamily() {
        return FontService.resolveFamily(
                    SettingsService.uiFontFamily, FontService.sansCandidates());
    }

    function monoResolvedFamily() {
        return FontService.resolveFamily(
                    SettingsService.monoFontFamily, FontService.monoCandidates());
    }

    // ---- diagnose ----------------------------------------------------------
    property var diagReport: null

    function refreshDiagnose() {
        diagReport = FontService.diagnose(SettingsService.uiFontFamily,
                                          SettingsService.monoFontFamily,
                                          SettingsService.uiFontSize);
    }

    // Read-only summary lines over the FontService.diagnose shape
    // (font_service.h): requested → resolved (QFontInfo), size, per-set
    // coverage and the fallback families of uncovered sets.
    property var diagLines: buildDiagLines()

    function buildDiagLines() {
        const lines = [];
        if (!diagReport)
            return lines;
        const setLabels = {
            latin: qsTr("西文"),
            digit: qsTr("数字"),
            cjk: qsTr("中文"),
            symbol: qsTr("符号"),
            emoji: qsTr("Emoji")
        };
        const sections = [
            { key: "ui", label: qsTr("界面字体") },
            { key: "mono", label: qsTr("等宽字体") }
        ];
        for (let s = 0; s < sections.length; ++s) {
            const entry = diagReport[sections[s].key];
            if (!entry)
                continue;
            const requested = entry.requested === "" ? qsTr("系统默认") : entry.requested;
            const cov = entry.coverage || {};
            const marks = [];
            for (const setId in setLabels) {
                marks.push(setLabels[setId]
                           + " " + (cov[setId] === true ? qsTr("✓") : qsTr("✗")));
            }
            lines.push(qsTr("%1：请求 %2 → 实际解析 %3 · %4 pt · 覆盖 %5")
                       .arg(sections[s].label).arg(requested)
                       .arg(entry.resolved).arg(entry.size)
                       .arg(marks.join(" · ")));
            const fallback = entry.fallback || {};
            for (const setId in fallback) {
                const families = fallback[setId];
                const detail = families.length > 0
                             ? families.join("、") : qsTr("无已安装候选族");
                lines.push(qsTr("%1：%2 字符缺失，回退族 %3")
                           .arg(sections[s].label).arg(setLabels[setId]).arg(detail));
            }
        }
        return lines;
    }

    function backendStateLabel() {
        switch (Application.backend.state) {
        case "idle": return qsTr("未启动");
        case "starting": return qsTr("启动中");
        case "handshaking": return qsTr("握手中");
        case "ready": return qsTr("就绪");
        case "crashed": return qsTr("已崩溃");
        case "stopped": return qsTr("已停止");
        default: return Application.backend.state;
        }
    }

    function backendStateColor() {
        switch (Application.backend.state) {
        case "ready": return Theme.success;
        case "crashed": return Theme.error;
        case "starting":
        case "handshaking": return Theme.warning;
        default: return Theme.textDisabled;
        }
    }

    Component.onCompleted: {
        applyTheme();
        uiFontSelect.model = fontModel();
        uiFontSelect.currentIndex = fontIndex();
        monoFontSelect.model = monoModel();
        monoFontSelect.currentIndex = monoIndex();
        refreshDiagnose();
    }

    Connections {
        target: SettingsService
        function onThemeModeChanged() { page.applyTheme() }
        function onUiFontFamilyChanged() { page.refreshDiagnose() }
        function onMonoFontFamilyChanged() { page.refreshDiagnose() }
        function onUiFontSizeChanged() { page.refreshDiagnose() }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingXl
        spacing: Theme.spacingLg

        ColumnLayout {
            Layout.fillHeight: true
            spacing: Theme.spacingSm

            Label {
                text: qsTr("设置")
                font.pixelSize: Theme.fontSizeTitle
                font.weight: Font.DemiBold
                color: Theme.textPrimary
            }

            ListView {
                id: groupList

                model: [qsTr("外观"), qsTr("工作区"), qsTr("后端"), qsTr("关于")]
                currentIndex: 0
                Layout.preferredWidth: Theme.navRailWidthExpanded
                Layout.fillHeight: true
                clip: true
                interactive: contentHeight > height

                delegate: ItemDelegate {
                    id: groupRow

                    required property string modelData
                    required property int index

                    width: groupList.width
                    height: 40
                    highlighted: groupList.currentIndex === groupRow.index

                    HoverHandler { cursorShape: Qt.PointingHandCursor }

                    background: Item {
                        Rectangle {
                            anchors.fill: parent
                            radius: Theme.radiusMd
                            color: groupRow.highlighted ? Theme.accent
                                 : groupRow.hovered ? Theme.surfaceElevated : "transparent"
                        }

                        // §4 Focus — 2px accent ring, keyboard only.
                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: -2
                            radius: Theme.radiusMd + 2
                            color: "transparent"
                            border.color: Theme.accent
                            border.width: 2
                            visible: groupRow.visualFocus
                        }
                    }

                    contentItem: Label {
                        text: groupRow.modelData
                        font.pixelSize: Theme.fontSizeBody
                        color: groupRow.highlighted ? Theme.onAccent : Theme.textPrimary
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: groupList.currentIndex = groupRow.index
                }

                ScrollIndicator.vertical: ScrollIndicator {}
            }
        }

        // Right form: one scrollable column per group.
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: groupList.currentIndex

            // ---- 外观 --------------------------------------------------------
            Flickable {
                id: appearanceScroll

                clip: true
                contentWidth: width
                contentHeight: appearanceColumn.implicitHeight
                ScrollIndicator.vertical: ScrollIndicator {}

                ColumnLayout {
                    id: appearanceColumn

                    width: appearanceScroll.width
                    spacing: Theme.spacingLg

                    RowLayout {
                        spacing: Theme.spacingMd

                        Label {
                            Layout.preferredWidth: 96
                            text: qsTr("主题")
                            font.pixelSize: Theme.fontSizeBody
                            color: Theme.textSecondary
                        }

                        AppSegmentedControl {
                            id: themeSelector

                            model: [qsTr("深色"), qsTr("浅色"), qsTr("系统")]

                            onActivated: (index) => {
                                const mode = index === 1 ? "light" : index === 2 ? "system" : "dark";
                                SettingsService.themeMode = mode;  // normalized + persisted
                                page.applyTheme();
                            }
                        }
                    }

                    RowLayout {
                        spacing: Theme.spacingMd

                        Label {
                            Layout.preferredWidth: 96
                            text: qsTr("UI 字体")
                            font.pixelSize: Theme.fontSizeBody
                            color: Theme.textSecondary
                        }

                        AppSelectField {
                            id: uiFontSelect

                            Layout.preferredWidth: 240

                            onActivated: (index) => {
                                SettingsService.uiFontFamily =
                                        index === 0 ? "" : uiFontSelect.textAt(index);
                                page.applyFonts();
                            }
                        }
                    }

                    RowLayout {
                        spacing: Theme.spacingMd

                        Label {
                            Layout.preferredWidth: 96
                            text: qsTr("字号")
                            font.pixelSize: Theme.fontSizeBody
                            color: Theme.textSecondary
                        }

                        AppNumberField {
                            id: sizeField

                            decimals: 0
                            step: 1
                            from: 8
                            to: 32
                            value: SettingsService.uiFontSize

                            onValueModified: {
                                SettingsService.uiFontSize = Math.round(sizeField.value);
                                page.applyFonts();
                            }
                        }
                    }

                    RowLayout {
                        spacing: Theme.spacingMd

                        Label {
                            Layout.preferredWidth: 96
                            text: qsTr("等宽字体")
                            font.pixelSize: Theme.fontSizeBody
                            color: Theme.textSecondary
                        }

                        AppSelectField {
                            id: monoFontSelect

                            Layout.preferredWidth: 240

                            onActivated: (index) => {
                                SettingsService.monoFontFamily =
                                        index === 0 ? "" : monoFontSelect.textAt(index);
                                page.applyFonts();
                            }
                        }
                    }

                    AppButton {
                        kind: AppButton.Kind.Secondary
                        text: qsTr("恢复默认")
                        onClicked: page.restoreFontDefaults()
                    }

                    // 预览样例文本框 — live sample of the resolved families.
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacingSm

                        Label {
                            text: qsTr("字体预览")
                            font.pixelSize: Theme.fontSizeHeading
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: previewColumn.implicitHeight
                                                    + Theme.spacingLg * 2
                            radius: Theme.radiusMd
                            color: Theme.surface
                            border.width: 1
                            border.color: Theme.border

                            ColumnLayout {
                                id: previewColumn

                                anchors.fill: parent
                                anchors.margins: Theme.spacingLg
                                spacing: Theme.spacingSm

                                Label {
                                    Layout.fillWidth: true
                                    text: qsTr("界面字体预览 Preview 0123 中文像素 Ag →€")
                                    font.family: page.uiResolvedFamily()
                                    font.pointSize: SettingsService.uiFontSize
                                    color: Theme.textPrimary
                                    elide: Text.ElideRight
                                }

                                Label {
                                    Layout.fillWidth: true
                                    text: qsTr("等宽字体预览 monospace 0O1lI 中文等宽 →€")
                                    font.family: page.monoResolvedFamily()
                                    font.pointSize: SettingsService.uiFontSize
                                    color: Theme.textSecondary
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }

                    // 诊断信息只读区 — FontService.diagnose summary.
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacingSm

                        Label {
                            text: qsTr("诊断信息")
                            font.pixelSize: Theme.fontSizeHeading
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                        }

                        Repeater {
                            model: page.diagLines

                            Label {
                                required property string modelData

                                Layout.fillWidth: true
                                text: modelData
                                font.pixelSize: Theme.fontSizeSmall
                                color: Theme.textSecondary
                                wrapMode: Text.WordWrap
                            }
                        }

                        Label {
                            Layout.fillWidth: true
                            text: qsTr("字体解析候选链与默认值镜像 app/fonts.py；完整诊断与 Worker 集成随 Phase 4 验收完善")
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textDisabled
                            wrapMode: Text.WordWrap
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            // ---- 工作区 --------------------------------------------------------
            Flickable {
                id: workspaceScroll

                clip: true
                contentWidth: width
                contentHeight: workspaceColumn.implicitHeight
                ScrollIndicator.vertical: ScrollIndicator {}

                ColumnLayout {
                    id: workspaceColumn

                    width: workspaceScroll.width
                    spacing: Theme.spacingLg

                    AppButton {
                        kind: AppButton.Kind.Secondary
                        text: qsTr("重置布局")
                        onClicked: SettingsService.resetLayout()
                    }

                    Label {
                        text: qsTr("当前：导航栏展开 %1 · 检查器折叠 %2")
                              .arg(SettingsService.navExpanded ? qsTr("是") : qsTr("否"))
                              .arg(SettingsService.inspectorCollapsed ? qsTr("是") : qsTr("否"))
                        font.pixelSize: Theme.fontSizeBody
                        color: Theme.textSecondary
                    }

                    Label {
                        Layout.fillWidth: true
                        text: qsTr("将导航栏展开态与检查器折叠态恢复为默认（layout/navExpanded=false、layout/inspectorCollapsed=false），由导航栏与检查器读取")
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textDisabled
                        wrapMode: Text.WordWrap
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            // ---- 后端 --------------------------------------------------------
            Flickable {
                id: backendScroll

                clip: true
                contentWidth: width
                contentHeight: backendColumn.implicitHeight
                ScrollIndicator.vertical: ScrollIndicator {}

                ColumnLayout {
                    id: backendColumn

                    width: backendScroll.width
                    spacing: Theme.spacingLg

                    RowLayout {
                        spacing: Theme.spacingMd

                        Label {
                            Layout.preferredWidth: 96
                            text: qsTr("Python 解释器")
                            font.pixelSize: Theme.fontSizeBody
                            color: Theme.textSecondary
                        }

                        AppTextField {
                            id: pythonField

                            Layout.preferredWidth: 360
                            text: SettingsService.backendPython
                            placeholderText: qsTr("python3 或解释器绝对路径")

                            onEditingFinished:
                                SettingsService.backendPython = pythonField.text
                        }
                    }

                    RowLayout {
                        spacing: Theme.spacingMd

                        Label {
                            Layout.preferredWidth: 96
                            text: qsTr("仓库根目录")
                            font.pixelSize: Theme.fontSizeBody
                            color: Theme.textSecondary
                        }

                        AppTextField {
                            id: repoRootField

                            Layout.preferredWidth: 360
                            text: SettingsService.backendRepoRoot
                            placeholderText: qsTr("仓库根目录绝对路径")

                            onEditingFinished:
                                SettingsService.backendRepoRoot = repoRootField.text
                        }
                    }

                    AppButton {
                        kind: AppButton.Kind.Primary
                        text: qsTr("启动后端")
                        onClicked: Application.startBackend()
                    }

                    RowLayout {
                        spacing: Theme.spacingSm

                        Rectangle {
                            width: 8
                            height: 8
                            radius: Theme.radiusSm  // half of the 8px dot → circle
                            color: page.backendStateColor()
                        }

                        Label {
                            text: qsTr("状态 %1").arg(page.backendStateLabel())
                            font.pixelSize: Theme.fontSizeBody
                            color: Theme.textPrimary
                        }

                        Label {
                            text: qsTr("Worker 进程%1")
                                  .arg(Application.backend.running ? qsTr("运行中") : qsTr("未运行"))
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textSecondary
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        text: qsTr("两个路径写入同一设置存储（backend/python、backend/repoRoot），改动即时持久化；任一路径为空时启动会报告 WORKER_START_FAILED")
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textDisabled
                        wrapMode: Text.WordWrap
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            // ---- 关于 --------------------------------------------------------
            Flickable {
                id: aboutScroll

                clip: true
                contentWidth: width
                contentHeight: aboutColumn.implicitHeight
                ScrollIndicator.vertical: ScrollIndicator {}

                ColumnLayout {
                    id: aboutColumn

                    width: aboutScroll.width
                    spacing: Theme.spacingMd

                    Label {
                        text: qsTr("Toolbox 版本 %1").arg(Application.version)
                        font.pixelSize: Theme.fontSizeBody
                        color: Theme.textPrimary
                    }

                    Label {
                        text: qsTr("Qt 版本 %1").arg(Application.qtVersion)
                        font.pixelSize: Theme.fontSizeBody
                        color: Theme.textPrimary
                    }

                    Label {
                        text: qsTr("UI：C++ / Qt Quick / QML · 协议版本 1")
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textSecondary
                    }

                    Item { Layout.fillHeight: true }
                }
            }
        }
    }
}
