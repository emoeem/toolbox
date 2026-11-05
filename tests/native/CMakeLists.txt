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
