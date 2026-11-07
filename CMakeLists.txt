cmake_minimum_required(VERSION 3.24)

project(Toolbox VERSION 0.2.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Qt 版本策略（总纲 §4.2）：
# - 构建下限 6.4：Ubuntu 24.04 CI runner 可用，且覆盖本工程用到的全部 API。
# - 产品目标版本：Arch/CachyOS 当前 Qt 6.8+（6.12 LTS 候选），在 Linux 验收时
#   记录实际锁定版本，见 docs/phase2-acceptance.md。
find_package(Qt6 6.4 REQUIRED COMPONENTS Core Gui Quick QuickControls2 Qml Test)

qt_standard_project_setup(REQUIRES 6.4)

set(TOOLBOX_SOURCES
    native/app/main.cpp
    native/app/application.h
    native/app/application.cpp
    native/models/tool_model.h
    native/models/tool_model.cpp
    native/models/task_model.h
    native/models/task_model.cpp
    # Phase 5: 滤镜目录与滤镜链模型
    native/models/filter_model.h
    native/models/filter_model.cpp
    native/models/filter_chain_model.h
    native/models/filter_chain_model.cpp
    # Phase 4: 设置/字体服务与 Worker 任务行模型
    native/services/settings_service.h
    native/services/settings_service.cpp
    native/services/font_service.h
    native/services/font_service.cpp
    # Phase 5: 滤镜页服务（目录/链/预设 facade）
    native/services/filter_service.h
    native/services/filter_service.cpp
    # Phase 6: 批量处理模型与服务（总纲 §9.4 批量工作区，BatchPage 数据源）
    native/models/batch_model.h
    native/models/batch_model.cpp
    native/services/batch_service.h
    native/services/batch_service.cpp
    # Phase 6C: 纹理生成器目录模型与 Studio 页服务（总纲 §9.7 Texture Studio）
    native/models/generator_model.h
    native/models/generator_model.cpp
    native/services/studio_service.h
    native/services/studio_service.cpp
    # Phase 7: 辅助工具目录模型与工具运行服务（总纲 §9.9 工具箱与辅助页面）
    native/models/assist_model.h
    native/models/assist_model.cpp
    native/services/assist_service.h
    native/services/assist_service.cpp
    # Phase 4: 文档服务（编辑器状态 facade）与撤销历史模型
    native/core/document_service.h
    native/core/document_service.cpp
    native/models/history_model.h
    native/models/history_model.cpp
    native/graphics/image_canvas.h
    native/graphics/image_canvas.cpp
    # Phase 3: Worker 进程管理与 IPC
    native/backend/ipc_protocol.h
    native/backend/ipc_protocol.cpp
    native/backend/python_worker.h
    native/backend/python_worker.cpp
    native/backend/backend_manager.h
    native/backend/backend_manager.cpp
)

qt_add_executable(toolbox ${TOOLBOX_SOURCES})

# 跨目录 C++ include 走 tests/native 的同一约定：以 native/ 为唯一 include 根，
# 源码里用路径限定写法（"models/tool_model.h"、"backend/ipc_protocol.h"）。
# 额外列出各头文件目录：qt_add_qml_module 生成的 qmltyperegistrations.cpp 以
# 裸文件名 include QML_ELEMENT 头（CI 实证），需要能直接解析到它们。
target_include_directories(toolbox PRIVATE
    ${CMAKE_SOURCE_DIR}/native
    ${CMAKE_SOURCE_DIR}/native/app
    ${CMAKE_SOURCE_DIR}/native/core
    ${CMAKE_SOURCE_DIR}/native/models
    ${CMAKE_SOURCE_DIR}/native/services
    ${CMAKE_SOURCE_DIR}/native/backend
    ${CMAKE_SOURCE_DIR}/native/graphics
)

# QML 模块登记：与 ui/ 下的实际文件一一对应（ui/components/ 29 个基础/布局/业务
# 组件 + Main + Theme 单例 + 8 个页面），qt_add_qml_module 按此清单编译进
# qrc:/Toolbox 模块；新增 .qml 必须同步登记，否则类型解析失败。
set(QML_FILES
    ui/Main.qml
    ui/themes/Theme.qml
    # Phase 6 第 7 项：批量处理向导（BatchPage 工作流组件）
    ui/components/AppBatchWizard.qml
    ui/components/AppButton.qml
    ui/components/AppColorField.qml
    ui/components/AppContextMenu.qml
    ui/components/AppDialog.qml
    # Phase 5 流程 2：滤镜页签业务组件
    ui/components/AppFilterCard.qml
    ui/components/AppFilterChainItem.qml
    ui/components/AppFilterInspector.qml
    ui/components/AppFilterParameterGroup.qml
    ui/components/AppHistoryItem.qml
    ui/components/AppIconButton.qml
    ui/components/AppImageThumbnail.qml
    ui/components/AppInspectorPanel.qml
    ui/components/AppNumberField.qml
    ui/components/AppPanelHeader.qml
    ui/components/AppProgressIndicator.qml
    ui/components/AppSearchField.qml
    ui/components/AppSectionGroup.qml
    ui/components/AppSegmentedControl.qml
    ui/components/AppSelectField.qml
    ui/components/AppSidebar.qml
    ui/components/AppSliderField.qml
    ui/components/AppStatusBar.qml
    # Phase 6 第 8-11 项：统一 Studio 工作区组件（StudioPage 宿主的工作流组件）
    ui/components/AppStudioPage.qml
    # Phase 7：统一工具页（文件工具入口的目录/参数/结果工作流组件）
    ui/components/AppToolsPage.qml
    ui/components/AppTaskItem.qml
    ui/components/AppTaskQueuePanel.qml
    ui/components/AppTextField.qml
    ui/components/AppToast.qml
    ui/components/AppToggleField.qml
    ui/components/AppToolButton.qml
    ui/components/AppToolCatalogItem.qml
    ui/components/AppTooltip.qml
    ui/components/AppTopToolbar.qml
    ui/components/AppWorkspaceLayout.qml
    ui/pages/HomePage.qml
    ui/pages/EditorPage.qml
    ui/pages/BatchPage.qml
    ui/pages/FractalPage.qml
    ui/pages/ShaderPage.qml
    ui/pages/TexturePage.qml
    ui/pages/SettingsPage.qml
    # Phase 6 第 8-11 项：创作（Studio）入口宿主页（application.cpp "create"）
    ui/pages/StudioPage.qml
    # Phase 7：文件工具入口宿主页（application.cpp "files"）
    ui/pages/ToolsPage.qml
    ui/pages/PlannedPage.qml
)

# Theme.qml 是 QML 单例（pragma Singleton），需显式标记。
set_source_files_properties(ui/themes/Theme.qml PROPERTIES QT_QML_SINGLETON_TYPE TRUE)

qt_add_qml_module(toolbox
    URI Toolbox
    VERSION 1.0
    RESOURCE_PREFIX "/"
    QML_FILES ${QML_FILES}
)

target_link_libraries(toolbox PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Qml
    Qt6::Quick
    Qt6::QuickControls2
)

include(CTest)
if(BUILD_TESTING)
    # QML 烟雾/截图测试（tests/native/test_qml_smoke.cpp）：必须在“本目录”
    # 声明模块——qt_add_qml_module 按 CMAKE_CURRENT_SOURCE_DIR 解析 QML 相对
    # 路径并决定 qrc 内嵌位置（tests/native 子目录声明会把 Main.qml 错位、
    # qrc:/Toolbox/ui/Main.qml 变 No such file or directory，CI 实证）。
    # 与主程序完全同源：同一批 C++ 源 + 同一批 QML，保证测的就是真实应用壳。
    qt_add_executable(test_qml_smoke tests/native/test_qml_smoke.cpp)
    target_include_directories(test_qml_smoke PRIVATE
        ${CMAKE_SOURCE_DIR}/native
        ${CMAKE_SOURCE_DIR}/native/app
        ${CMAKE_SOURCE_DIR}/native/core
        ${CMAKE_SOURCE_DIR}/native/models
        ${CMAKE_SOURCE_DIR}/native/services
        ${CMAKE_SOURCE_DIR}/native/backend
        ${CMAKE_SOURCE_DIR}/native/graphics
    )
    target_link_libraries(test_qml_smoke PRIVATE
        Qt6::Core
        Qt6::Gui
        Qt6::Qml
        Qt6::Quick
        Qt6::QuickControls2
        Qt6::Test
    )
    set(TOOLBOX_SMOKE_SOURCES ${TOOLBOX_SOURCES})
    list(REMOVE_ITEM TOOLBOX_SMOKE_SOURCES native/app/main.cpp)
    qt_add_qml_module(test_qml_smoke
        URI Toolbox
        VERSION 1.0
        RESOURCE_PREFIX "/"
        SOURCES ${TOOLBOX_SMOKE_SOURCES}
        QML_FILES ${QML_FILES}
    )
    add_subdirectory(tests/native)
endif()

install(TARGETS toolbox
    BUNDLE DESTINATION .
    RUNTIME DESTINATION bin
)
