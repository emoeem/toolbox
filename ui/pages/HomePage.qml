import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Home page (Phase 4): working entry into the editor.
// - AppSearchField with debounced live search over Application.toolModel;
//   clicking an available result navigates to its workspace (unavailable
//   tools are disabled rows — no fake navigation);
// - tool catalog grid on AppToolCatalogItem (ToolModel roles);
// - recent files from SettingsService.recentFiles (read-only rows — opening
//   files is the Phase 5 file workflow, so rows are deliberately not
//   clickable); empty state is a dashed guide, no sample data (总纲 §3.4).
Page {
    id: page

    background: Rectangle { color: Theme.background }

    // Debounced search results (QVariantList of {id,title,category,available,phase,keywords}).
    property var searchResults: []
    property string searchQuery: ""

    // Catalog tool id → nav entry it belongs to. Unavailable tools and the
    // unmapped ones yield "" (no navigation — honest, per the Phase 2
    // mapping, extended with the editor tools that live in the editor page).
    function toolTargetPage(toolId) {
        switch (toolId) {
        case "tool.open-image":
        case "tool.adjust":
        case "tool.filter":
        case "tool.crop":
        case "tool.transform":
            return "editor";
        case "tool.fractal":
        case "tool.texture":
        case "tool.shader":
            return "create";
        case "tool.batch":
            return "batch";
        default:
            return "";
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingXl
        spacing: Theme.spacingLg

        Label {
            text: qsTr("首页")
            font.pixelSize: Theme.fontSizeTitle
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        AppSearchField {
            id: searchField

            Layout.fillWidth: true
            Layout.maximumWidth: 480
            placeholderText: qsTr("搜索工具（名称 / 分类 / 关键词）")

            onSearched: (query) => {
                page.searchQuery = query;
                page.searchResults = query === "" ? [] : Application.toolModel.search(query);
            }
        }

        // Live results for the current query. Unavailable tools render
        // disabled rows instead of pretending to navigate.
        ListView {
            id: resultList

            readonly property bool hasQuery: page.searchQuery !== ""

            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(contentHeight, 192)
            visible: hasQuery
            clip: true
            interactive: contentHeight > height
            model: page.searchResults

            Label {
                anchors.top: parent.top
                anchors.topMargin: Theme.spacingSm
                anchors.horizontalCenter: parent.horizontalCenter
                visible: resultList.hasQuery && resultList.count === 0
                text: qsTr("没有匹配的工具")
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textSecondary
            }

            delegate: ItemDelegate {
                id: resultRow

                required property var modelData

                width: resultList.width
                height: 36
                enabled: resultRow.modelData.available

                HoverHandler { cursorShape: Qt.PointingHandCursor }

                background: Item {
                    Rectangle {
                        anchors.fill: parent
                        radius: Theme.radiusSm
                        color: resultRow.pressed ? Qt.darker(Theme.surfaceElevated, 1.08)
                             : resultRow.hovered ? Theme.surfaceElevated : "transparent"
                    }

                    // §4 Focus — 2px accent ring outside the row, keyboard only.
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: -2
                        radius: Theme.radiusSm + 2
                        color: "transparent"
                        border.color: Theme.accent
                        border.width: 2
                        visible: resultRow.visualFocus
                    }
                }

                contentItem: RowLayout {
                    spacing: Theme.spacingSm

                    Label {
                        Layout.fillWidth: true
                        text: resultRow.modelData.title
                        font.pixelSize: Theme.fontSizeBody
                        color: resultRow.enabled ? Theme.textPrimary : Theme.textDisabled
                        elide: Text.ElideRight
                    }

                    Label {
                        text: resultRow.modelData.category + " · "
                              + (resultRow.modelData.available
                                 ? resultRow.modelData.phase
                                 : qsTr("随 %1 提供").arg(resultRow.modelData.phase))
                        font.pixelSize: Theme.fontSizeSmall
                        color: resultRow.enabled ? Theme.textSecondary : Theme.textDisabled
                        elide: Text.ElideRight
                    }
                }

                onClicked: {
                    const target = page.toolTargetPage(resultRow.modelData.id);
                    if (target !== "")
                        Application.navigate(target);
                }
            }

            ScrollIndicator.vertical: ScrollIndicator {}
        }

        // 快速开始 (kept from Phase 2): the one working entry into the editor.
        RowLayout {
            spacing: Theme.spacingMd

            AppButton {
                kind: AppButton.Kind.Primary
                text: qsTr("打开图像（进入编辑工作区）")
                onClicked: Application.navigate("editor")
            }

            Label {
                Layout.fillWidth: true
                text: qsTr("拖放到编辑器画布即可打开（Phase 2 支持本地文件）")
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textSecondary
                elide: Text.ElideRight
            }
        }

        // 最近文件 — SettingsService.recentFiles, most-recent-first. Rows are
        // display-only: opening a file is the Phase 5 file workflow.
        ColumnLayout {
            id: recentSection

            Layout.fillWidth: true
            spacing: Theme.spacingSm

            Label {
                text: qsTr("最近文件")
                font.pixelSize: Theme.fontSizeHeading
                font.weight: Font.DemiBold
                color: Theme.textPrimary
            }

            // Empty state: dashed guide, no sample data (spec §1 空状态).
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 96
                visible: SettingsService.recentFiles.length === 0

                Canvas {
                    id: dashedBorder
                    anchors.fill: parent

                    onPaint: {
                        const ctx = getContext("2d");
                        ctx.reset();
                        ctx.strokeStyle = Theme.border.toString();
                        ctx.lineWidth = 1.5;
                        ctx.setLineDash([4, 4]);
                        ctx.strokeRect(0.5, 0.5, width - 1, height - 1);
                    }
                }

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: Theme.spacingXs

                    Label {
                        Layout.alignment: Qt.AlignHCenter
                        text: qsTr("暂无最近文件")
                        font.pixelSize: Theme.fontSizeBody
                        color: Theme.textSecondary
                    }

                    Label {
                        Layout.alignment: Qt.AlignHCenter
                        text: qsTr("打开图像后，最近使用的文件会显示在这里（文件工作流随 Phase 5 提供）")
                        font.pixelSize: Theme.fontSizeSmall
                        color: Theme.textDisabled
                    }
                }
            }

            Repeater {
                model: SettingsService.recentFiles

                delegate: Item {
                    id: recentRow

                    required property string modelData
                    required property int index

                    width: recentSection.width
                    height: 32

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacingSm
                        anchors.rightMargin: Theme.spacingSm
                        spacing: Theme.spacingSm

                        Label {
                            text: {
                                const path = recentRow.modelData;
                                const cut = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
                                return cut >= 0 ? path.substring(cut + 1) : path;
                            }
                            font.pixelSize: Theme.fontSizeBody
                            color: Theme.textPrimary
                            elide: Text.ElideMiddle
                            Layout.preferredWidth: 220
                        }

                        Label {
                            Layout.fillWidth: true
                            text: recentRow.modelData
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textSecondary
                            elide: Text.ElideMiddle
                        }

                        Label {
                            text: recentRow.index === 0 ? qsTr("最近使用") : ""
                            visible: recentRow.index === 0
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textDisabled
                        }
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: 1
                        color: Theme.border
                    }
                }
            }
        }

        // 工具分类 — AppToolCatalogItem grid over ToolModel roles.
        Label {
            text: qsTr("工具分类")
            font.pixelSize: Theme.fontSizeHeading
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        GridView {
            id: toolGrid

            readonly property int cardWidth: 200
            readonly property int cardHeight: 84

            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: Application.toolModel
            cellWidth: cardWidth + Theme.spacingMd
            cellHeight: cardHeight + Theme.spacingMd

            delegate: AppToolCatalogItem {
                width: toolGrid.cardWidth
                height: toolGrid.cardHeight

                onClicked: (clickedToolId) => {
                    const target = page.toolTargetPage(clickedToolId);
                    if (target !== "")
                        Application.navigate(target);
                }
            }

            ScrollIndicator.vertical: ScrollIndicator {}
        }
    }
}
