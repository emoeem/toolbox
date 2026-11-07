# Native (C++) test suite. Runs under CTest on Linux CI and the target env.
find_package(Qt6 6.4 REQUIRED COMPONENTS Quick Test)

# QML 烟雾测试（v2.0.0-alpha.1 实机反馈催生，见 test_qml_smoke.cpp 头注释）：
# 与主程序相同的 C++ 源 + 同一份 ${QML_FILES}（根目录定义）重复声明
# qt_add_qml_module——测试二进制内嵌同一份 qrc:/Toolbox 与 C++ QML 单例，
# offscreen 真加载 Main.qml。构建成本翻倍（全量 TU 编两遍）换取
# "QML 运行时坏即 CI 红"的永久门禁；发布构建 BUILD_TESTING=OFF 不受影响。
qt_add_executable(test_qml_smoke test_qml_smoke.cpp)
target_link_libraries(test_qml_smoke PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Qml
    Qt6::Quick
    Qt6::QuickControls2
    Qt6::Test
)
# qt_add_qml_module 按“当前源目录”解析 QML_FILES 相对路径（CI 实证：ui/Main.qml
# 被找成 tests/native/ui/Main.qml）——这里必须转绝对路径。
set(QML_FILES_ABS)
foreach(_qml ${QML_FILES})
  list(APPEND QML_FILES_ABS "${CMAKE_SOURCE_DIR}/${_qml}")
endforeach()
qt_add_qml_module(test_qml_smoke
    URI Toolbox
    VERSION 1.0
    RESOURCE_PREFIX "/"
    SOURCES
        ${CMAKE_SOURCE_DIR}/native/app/application.h
        ${CMAKE_SOURCE_DIR}/native/app/application.cpp
        ${CMAKE_SOURCE_DIR}/native/models/tool_model.h
        ${CMAKE_SOURCE_DIR}/native/models/tool_model.cpp
        ${CMAKE_SOURCE_DIR}/native/models/task_model.h
        ${CMAKE_SOURCE_DIR}/native/models/task_model.cpp
        ${CMAKE_SOURCE_DIR}/native/models/filter_model.h
        ${CMAKE_SOURCE_DIR}/native/models/filter_model.cpp
        ${CMAKE_SOURCE_DIR}/native/models/filter_chain_model.h
        ${CMAKE_SOURCE_DIR}/native/models/filter_chain_model.cpp
        ${CMAKE_SOURCE_DIR}/native/models/batch_model.h
        ${CMAKE_SOURCE_DIR}/native/models/batch_model.cpp
        ${CMAKE_SOURCE_DIR}/native/models/generator_model.h
        ${CMAKE_SOURCE_DIR}/native/models/generator_model.cpp
        ${CMAKE_SOURCE_DIR}/native/models/assist_model.h
        ${CMAKE_SOURCE_DIR}/native/models/assist_model.cpp
        ${CMAKE_SOURCE_DIR}/native/models/history_model.h
        ${CMAKE_SOURCE_DIR}/native/models/history_model.cpp
        ${CMAKE_SOURCE_DIR}/native/services/settings_service.h
        ${CMAKE_SOURCE_DIR}/native/services/settings_service.cpp
        ${CMAKE_SOURCE_DIR}/native/services/font_service.h
        ${CMAKE_SOURCE_DIR}/native/services/font_service.cpp
        ${CMAKE_SOURCE_DIR}/native/services/filter_service.h
        ${CMAKE_SOURCE_DIR}/native/services/filter_service.cpp
        ${CMAKE_SOURCE_DIR}/native/services/batch_service.h
        ${CMAKE_SOURCE_DIR}/native/services/batch_service.cpp
        ${CMAKE_SOURCE_DIR}/native/services/studio_service.h
        ${CMAKE_SOURCE_DIR}/native/services/studio_service.cpp
        ${CMAKE_SOURCE_DIR}/native/services/assist_service.h
        ${CMAKE_SOURCE_DIR}/native/services/assist_service.cpp
        ${CMAKE_SOURCE_DIR}/native/core/document_service.h
        ${CMAKE_SOURCE_DIR}/native/core/document_service.cpp
        ${CMAKE_SOURCE_DIR}/native/graphics/image_canvas.h
        ${CMAKE_SOURCE_DIR}/native/graphics/image_canvas.cpp
        ${CMAKE_SOURCE_DIR}/native/backend/ipc_protocol.h
        ${CMAKE_SOURCE_DIR}/native/backend/ipc_protocol.cpp
        ${CMAKE_SOURCE_DIR}/native/backend/python_worker.h
        ${CMAKE_SOURCE_DIR}/native/backend/python_worker.cpp
        ${CMAKE_SOURCE_DIR}/native/backend/backend_manager.h
        ${CMAKE_SOURCE_DIR}/native/backend/backend_manager.cpp
    QML_FILES ${QML_FILES_ABS}
)
# 根目录对 Theme.qml 的 QT_QML_SINGLETON_TYPE 是目录作用域，子目录不继承。
set_source_files_properties(${CMAKE_SOURCE_DIR}/ui/themes/Theme.qml
    PROPERTIES QT_QML_SINGLETON_TYPE TRUE)
target_include_directories(test_qml_smoke PRIVATE
    ${CMAKE_SOURCE_DIR}/native
    ${CMAKE_SOURCE_DIR}/native/app
    ${CMAKE_SOURCE_DIR}/native/core
    ${CMAKE_SOURCE_DIR}/native/models
    ${CMAKE_SOURCE_DIR}/native/services
    ${CMAKE_SOURCE_DIR}/native/backend
    ${CMAKE_SOURCE_DIR}/native/graphics
)
add_test(NAME qml_smoke COMMAND test_qml_smoke)

qt_add_executable(test_native_models test_models.cpp)
target_link_libraries(test_native_models PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Qml
    Qt6::Quick
    Qt6::Test
)
add_test(NAME native_models COMMAND test_native_models)

qt_add_executable(test_ipc_protocol test_ipc_protocol.cpp)
target_link_libraries(test_ipc_protocol PRIVATE
    Qt6::Core
    Qt6::Test
)
add_test(NAME ipc_protocol COMMAND test_ipc_protocol)

# The two tests above need the Toolbox QML module types (ToolModel/NavModel
# live in the toolbox target). Link against the object/module by including
# the same sources — simplest robust approach for a prototype is compiling
# the model sources directly into the test target.
target_sources(test_native_models PRIVATE
    ${CMAKE_SOURCE_DIR}/native/models/tool_model.cpp
)
target_include_directories(test_native_models PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)
target_sources(test_ipc_protocol PRIVATE
    ${CMAKE_SOURCE_DIR}/native/backend/ipc_protocol.cpp
)
target_include_directories(test_ipc_protocol PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)

# Phase 4: 服务与任务队列模型单测。与上面两个目标同一模式：被测 .cpp 直接编入
# 测试目标，include 根统一为 native/（源码内路径限定写法保持一致）。

# TaskModel over a real BackendManager: the tests emit the manager's
# responseReady/taskEvent signals directly (no Worker process started), so the
# backend/ sources (BackendManager + its PythonWorker dependency + the protocol
# encoder) must be compiled in as well.
qt_add_executable(test_task_model test_task_model.cpp)
target_link_libraries(test_task_model PRIVATE
    Qt6::Core
    Qt6::Qml
    Qt6::Test
)
add_test(NAME task_model COMMAND test_task_model)
target_sources(test_task_model PRIVATE
    ${CMAKE_SOURCE_DIR}/native/models/task_model.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/backend_manager.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/python_worker.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/ipc_protocol.cpp
)
target_include_directories(test_task_model PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)

# SettingsService: settings_service.cpp includes QJSEngine/QQmlEngine for the
# QML singleton factory, hence Qt6::Qml. QSettings isolation (per-test
# QTemporaryDir) lives in the test itself.
qt_add_executable(test_settings_service test_settings_service.cpp)
target_link_libraries(test_settings_service PRIVATE
    Qt6::Core
    Qt6::Qml
    Qt6::Test
)
add_test(NAME settings_service COMMAND test_settings_service)
target_sources(test_settings_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native/services/settings_service.cpp
)
target_include_directories(test_settings_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)

# FontService: QRawFont/QFontDatabase/QGuiApplication need Qt6::Gui (QTEST_MAIN
# then provides a QGuiApplication); QJSEngine/QQmlEngine need Qt6::Qml.
qt_add_executable(test_font_service test_font_service.cpp)
target_link_libraries(test_font_service PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Qml
    Qt6::Test
)
add_test(NAME font_service COMMAND test_font_service)
target_sources(test_font_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native/services/font_service.cpp
)
target_include_directories(test_font_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)

# DocumentService + HistoryModel + TaskModel: the service consumes
# BackendManager signals (test emits them directly, no Worker process — same
# harness as test_task_model above), calls
# SettingsService::instance()->addRecentFile on open success and registers
# async actions with TaskModel::trackRequest (bindTaskModel), so the backend/,
# models/ and services/ sources are compiled in as well. Both service sources
# use the QML singleton factory, hence Qt6::Qml.
qt_add_executable(test_document_service test_document_service.cpp)
target_link_libraries(test_document_service PRIVATE
    Qt6::Core
    Qt6::Qml
    Qt6::Test
)
add_test(NAME document_service COMMAND test_document_service)
target_sources(test_document_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native/core/document_service.cpp
    ${CMAKE_SOURCE_DIR}/native/models/history_model.cpp
    ${CMAKE_SOURCE_DIR}/native/models/task_model.cpp
    ${CMAKE_SOURCE_DIR}/native/services/settings_service.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/backend_manager.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/python_worker.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/ipc_protocol.cpp
)
target_include_directories(test_document_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)

# FilterModel / FilterChainModel：纯数据模型（不连 BackendManager），填充经
# Q_INVOKABLE（reloadFrom / replaceFrom），测试直接构造即可；QAbstractItemModelTester
# 需 Qt6::Test，QML_ELEMENT 元类型需 Qt6::Qml。
qt_add_executable(test_filter_model test_filter_model.cpp)
target_link_libraries(test_filter_model PRIVATE
    Qt6::Core
    Qt6::Qml
    Qt6::Test
)
add_test(NAME filter_model COMMAND test_filter_model)
target_sources(test_filter_model PRIVATE
    ${CMAKE_SOURCE_DIR}/native/models/filter_model.cpp
)
target_include_directories(test_filter_model PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)

qt_add_executable(test_filter_chain_model test_filter_chain_model.cpp)
target_link_libraries(test_filter_chain_model PRIVATE
    Qt6::Core
    Qt6::Qml
    Qt6::Test
)
add_test(NAME filter_chain_model COMMAND test_filter_chain_model)
target_sources(test_filter_chain_model PRIVATE
    ${CMAKE_SOURCE_DIR}/native/models/filter_chain_model.cpp
)
target_include_directories(test_filter_chain_model PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)

# FilterService：消费 BackendManager 信号（测试直接发射，同 test_task_model
# 模式），previewChain/applyChain 委托 DocumentService::instance()（其 applyFilters
# 走 tracked dispatch 并登记 TaskModel 行、openDocument 写 SettingsService 最近
# 文件），故 core/、models/（filter 两模型 + task_model）、services/ 与 backend/
# 源一并编入。两处服务源码均用 QML 单例工厂，故需 Qt6::Qml。
qt_add_executable(test_filter_service test_filter_service.cpp)
target_link_libraries(test_filter_service PRIVATE
    Qt6::Core
    Qt6::Qml
    Qt6::Test
)
add_test(NAME filter_service COMMAND test_filter_service)
target_sources(test_filter_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native/services/filter_service.cpp
    ${CMAKE_SOURCE_DIR}/native/core/document_service.cpp
    ${CMAKE_SOURCE_DIR}/native/models/filter_model.cpp
    ${CMAKE_SOURCE_DIR}/native/models/filter_chain_model.cpp
    ${CMAKE_SOURCE_DIR}/native/models/task_model.cpp
    ${CMAKE_SOURCE_DIR}/native/services/settings_service.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/backend_manager.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/python_worker.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/ipc_protocol.cpp
)
target_include_directories(test_filter_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)

# BatchModel：纯数据模型（不连 BackendManager），填充经 Q_INVOKABLE
#（resetFrom / updateFrom / clear），测试直接构造即可；同 test_filter_model
# 模式。QAbstractItemModelTester 需 Qt6::Test，QML_ELEMENT 元类型需 Qt6::Qml。
qt_add_executable(test_batch_model test_batch_model.cpp)
target_link_libraries(test_batch_model PRIVATE
    Qt6::Core
    Qt6::Qml
    Qt6::Test
)
add_test(NAME batch_model COMMAND test_batch_model)
target_sources(test_batch_model PRIVATE
    ${CMAKE_SOURCE_DIR}/native/models/batch_model.cpp
)
target_include_directories(test_batch_model PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)

# BatchService：消费 BackendManager 信号（测试直接发射，同 test_task_model /
# test_filter_service 模式），batch_model 与 backend/（BackendManager +
# PythonWorker + 协议编码器）源一并编入；QML 单例工厂需 Qt6::Qml。
qt_add_executable(test_batch_service test_batch_service.cpp)
target_link_libraries(test_batch_service PRIVATE
    Qt6::Core
    Qt6::Qml
    Qt6::Test
)
add_test(NAME batch_service COMMAND test_batch_service)
target_sources(test_batch_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native/services/batch_service.cpp
    ${CMAKE_SOURCE_DIR}/native/models/batch_model.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/backend_manager.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/python_worker.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/ipc_protocol.cpp
)
target_include_directories(test_batch_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)

# GeneratorModel：纯数据模型（不连 BackendManager），填充经 Q_INVOKABLE
#（reloadFrom），测试直接构造即可；同 test_filter_model 模式。
# QAbstractItemModelTester 需 Qt6::Test，QML_ELEMENT 元类型需 Qt6::Qml。
qt_add_executable(test_generator_model test_generator_model.cpp)
target_link_libraries(test_generator_model PRIVATE
    Qt6::Core
    Qt6::Qml
    Qt6::Test
)
add_test(NAME generator_model COMMAND test_generator_model)
target_sources(test_generator_model PRIVATE
    ${CMAKE_SOURCE_DIR}/native/models/generator_model.cpp
)
target_include_directories(test_generator_model PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)

# StudioService：消费 BackendManager 信号（测试直接发射，同 test_batch_service
# 模式），exportToEditor 委托 DocumentService::instance()（openDocument 写
# SettingsService 最近文件、dispatch 登记 TaskModel 行），且 render 经
# bindTaskModel 登记任务行，故 core/、models/（generator + task）、services/
#（studio + settings）与 backend/ 源一并编入（test_filter_service 同款组合）。
# 两处服务源码均用 QML 单例工厂，故需 Qt6::Qml。
qt_add_executable(test_studio_service test_studio_service.cpp)
target_link_libraries(test_studio_service PRIVATE
    Qt6::Core
    Qt6::Qml
    Qt6::Test
)
add_test(NAME studio_service COMMAND test_studio_service)
target_sources(test_studio_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native/services/studio_service.cpp
    ${CMAKE_SOURCE_DIR}/native/models/generator_model.cpp
    ${CMAKE_SOURCE_DIR}/native/core/document_service.cpp
    ${CMAKE_SOURCE_DIR}/native/models/task_model.cpp
    ${CMAKE_SOURCE_DIR}/native/services/settings_service.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/backend_manager.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/python_worker.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/ipc_protocol.cpp
)
target_include_directories(test_studio_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)

# AssistModel：纯数据模型（不连 BackendManager），填充经 Q_INVOKABLE
#（reloadFrom），测试直接构造即可；同 test_generator_model 模式。
# QAbstractItemModelTester 需 Qt6::Test，QML_ELEMENT 元类型需 Qt6::Qml。
qt_add_executable(test_assist_model test_assist_model.cpp)
target_link_libraries(test_assist_model PRIVATE
    Qt6::Core
    Qt6::Qml
    Qt6::Test
)
add_test(NAME assist_model COMMAND test_assist_model)
target_sources(test_assist_model PRIVATE
    ${CMAKE_SOURCE_DIR}/native/models/assist_model.cpp
)
target_include_directories(test_assist_model PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)

# AssistService：消费 BackendManager 信号（测试直接发射，同 test_studio_service
# 模式），async 工具受理经 bindTaskModel 登记任务行，故 models/（assist +
# task）与 backend/（BackendManager + PythonWorker + 协议编码器）源一并编入。
# 无 DocumentService/SettingsService 委托（assist 不触碰文档与最近文件），
# 不需要 core/、services/settings 源。QML 单例工厂需 Qt6::Qml。
qt_add_executable(test_assist_service test_assist_service.cpp)
target_link_libraries(test_assist_service PRIVATE
    Qt6::Core
    Qt6::Qml
    Qt6::Test
)
add_test(NAME assist_service COMMAND test_assist_service)
target_sources(test_assist_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native/services/assist_service.cpp
    ${CMAKE_SOURCE_DIR}/native/models/assist_model.cpp
    ${CMAKE_SOURCE_DIR}/native/models/task_model.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/backend_manager.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/python_worker.cpp
    ${CMAKE_SOURCE_DIR}/native/backend/ipc_protocol.cpp
)
target_include_directories(test_assist_service PRIVATE
    ${CMAKE_SOURCE_DIR}/native
)
