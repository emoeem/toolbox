import Toolbox
import QtQuick
import QtQuick.Controls

// 工具页宿主（product-information-architecture.md §1/§2 一级导航"文件工具
// Files"入口，native/app/application.cpp navModel "files" 路由至此；总纲
// §9.9 统一工具页模板：PDF / OCR / EXIF / 水印 / 条码 / 压缩 / 归档 / 加密 /
// Base64 等低频能力的统一承载）。页面自身无状态——工作流（工具目录网格 /
// 参数面板 / 结果展示）在 ui/components/AppToolsPage.qml（AppBatchWizard/
// BatchPage、AppStudioPage/StudioPage 同款分工），数据源为 AssistService
// （C++ 单例，组件不 sendAction）。
Page {
    background: Rectangle { color: Theme.background }

    AppToolsPage {
        anchors.fill: parent
    }
}
