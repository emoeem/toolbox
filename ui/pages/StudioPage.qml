import QtQuick
import QtQuick.Controls

// Studio 工作区（product-information-architecture.md §1/§2：一级导航"创作"
// 的宿主页面，native/app/application.cpp navModel "create" 路由至此；
// ui-page-spec.md §5 Studio 页规格）。总纲 §13 Phase 6 第 8-11 项（各
// Studio 的生成器工作流）由 AppStudioPage 承载：生成器目录、参数面板
// （paramsJson 驱动）、预览画布与导出/另存，数据源为 StudioService
// （C++ 单例，组件不 sendAction）。页面自身无状态——组件自足（服务接线、
// 渲染防抖与 Toast 提示都在组件内），便于复用与单独测试（AppBatchWizard
// / BatchPage 同款分工）。
Page {
    background: Rectangle { color: Theme.background }

    AppStudioPage {
        anchors.fill: parent
    }
}
