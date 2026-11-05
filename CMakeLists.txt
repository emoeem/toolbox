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

qt_add_executable(toolbox
    native/app/main.cpp
    native/app/application.h
    native/app/application.cpp
    native/models/tool_model.h
    native/models/tool_model.cpp
    native/models/task_model.h
    native/models/task_model.cpp
    # Phase 4: 设置/字体服务与 Worker 任务行模型
    native/services/settings_service.h
    native/services/settings_service.cpp
    native/services/font_service.h
    native/services/font_service.cpp
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

# 跨目录 C++ include 走 tests/native 的同一约定：以 native/ 为唯一 include 根，
# 源码里用路径限定写法（"models/tool_model.h"、"backend/ipc_protocol.h"）。
target_include_directories(toolbox PRIVATE ${CMAKE_SOURCE_DIR}/native)

# QML 模块登记：与 ui/ 下的实际文件一一对应（ui/components/ 28 个基础/布局/业务
# 组件 + Main + Theme 单例 + 8 个页面），qt_add_qml_module 按此清单编译进
# qrc:/Toolbox 模块；新增 .qml 必须同步登记，否则类型解析失败。
set(QML_FILES
    ui/Main.qml
    ui/themes/Theme.qml
    ui/components/AppButton.qml
    ui/components/AppColorField.qml
    ui/components/AppContextMenu.qml
    ui/components/AppDialog.qml
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
    add_subdirectory(tests/native)
endif()

install(TARGETS toolbox
    BUNDLE DESTINATION .
    RUNTIME DESTINATION bin
)
