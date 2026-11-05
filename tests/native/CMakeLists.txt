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
