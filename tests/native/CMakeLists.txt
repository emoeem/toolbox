# Native (C++) test suite. Runs under CTest on Linux CI and the target env.
# QML/visual tests are added in later phases (master plan §14.1).
find_package(Qt6 6.4 REQUIRED COMPONENTS Quick Test)

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
