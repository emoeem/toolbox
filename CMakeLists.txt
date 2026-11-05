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

set(QML_FILES
    ui/Main.qml
    ui/themes/Theme.qml
    ui/components/AppSidebar.qml
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
