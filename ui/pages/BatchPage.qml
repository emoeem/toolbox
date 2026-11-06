import QtQuick
import QtQuick.Controls

// 批量处理工作区（product-information-architecture.md §1/§2：一级导航"批量"
// 的宿主页面，native/app/application.cpp navModel "batch" 路由至此；
// ui-page-spec.md §3）。总纲 §13 Phase 6 第 7 项（Batch Processing）起由
// AppBatchWizard 承载真实工作流：文件/目录导入、输出与滤镜链配置、任务表与
// 总进度，数据源为 BatchService/BatchModel（C++ 单例，页面不 sendAction）。
// 页面自身无状态——向导是自足组件（服务接线、非模态运行与 Toast 提示都在
// 组件内），便于复用与单独测试。
Page {
    background: Rectangle { color: Theme.background }

    AppBatchWizard {
        anchors.fill: parent
    }
}
