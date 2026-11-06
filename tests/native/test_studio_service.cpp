// Phase 6C service tests: StudioService as the Texture Studio facade
// (docs/toolbox-2.0-project-plan.md §9.7).
//
// Simulation strategy — same as test_task_model.cpp / test_filter_service.cpp /
// test_batch_service.cpp (no Python Worker in native tests): the tests emit
// BackendManager's responseReady/taskEvent signals directly. The manager is
// never started, so sendAction only consumes its request_id counter slot
// (backend_manager.cpp:102-107, "req-<counter>"): each Q_INVOKABLE sends a
// known number of requests, so tests predict request ids by call order relative
// to a probe sendAction, and probe-before/after proves locally-rejected calls
// sent nothing. Action names on the wire must be locked by tests/test_worker_*.py
// when the Worker side lands.
//
// Protocol status note (honest scope): generate.list / generate.render are NOT
// yet in docs/ipc-protocol.md §3 nor in python_worker/dispatcher.py — the task
// list for this batch covers the native side only (native/models/generator_model.*,
// native/services/studio_service.*, CMake, tests). A real Worker today answers
// UNKNOWN_ACTION; the sync-rejection test below locks exactly that path, and the
// accepted/progress/completed/failed paths encode the §2.3/§7 lifecycle contract
// the Worker-side implementation has to satisfy (shapes declared in
// studio_service.h header comment).
//
// Singleton split matters here (same as test_filter_service.cpp): StudioService
// instances are fresh per test function, but exportToEditor delegates to the
// process-wide DocumentService::instance() (studio_service.cpp exportToEditor),
// so initTestCase binds that singleton once to the test-wide BackendManager
// member (never a stack Harness that would leave a dangling m_backend behind).
// The delegation test is declared LAST — the document state of the DocumentService
// singleton outlives a test function.
//
// Store isolation mirrors test_document_service.cpp / test_filter_service.cpp:
// SettingsService builds its QSettings with explicit IniFormat, so the
// QSettings::setPath redirect in initTestCase covers the addRecentFile side
// effect of the delegated openDocument.
#include <QtTest/QAbstractItemModelTester>
#include <QtTest/QtTest>

#include <QJsonArray>
#include <QJsonObject>
#include <QSettings>
#include <QSignalSpy>
#include <QTemporaryDir>

#include <memory>

#include "backend/backend_manager.h"
#include "backend/ipc_protocol.h"
#include "core/document_service.h"
#include "models/generator_model.h"
#include "models/task_model.h"
#include "services/settings_service.h"
#include "services/studio_service.h"

using toolbox::BackendManager;
using toolbox::DocumentService;
using toolbox::GeneratorModel;
using toolbox::SettingsService;
using toolbox::StudioService;
using toolbox::TaskModel;

namespace {

QString reqId(int n) {
    return QStringLiteral("req-%1").arg(n);
}

// Probe: consumes one request-id slot and returns its number, giving every test
// a stable offset regardless of execution order (same trace trick as
// test_filter_service.cpp / test_batch_service.cpp).
int probeSlot(BackendManager &backend) {
    return backend.sendAction(QStringLiteral("probe")).mid(4).toInt();
}

QJsonObject successResponse(const QString &requestId, const QJsonObject &result) {
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("request_id"), requestId},
        {QStringLiteral("success"), true},
        {QStringLiteral("result"), result},
    };
}

QJsonObject failedResponse(const QString &requestId, const QString &code, const QString &message) {
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("request_id"), requestId},
        {QStringLiteral("success"), false},
        {QStringLiteral("error"),
         QJsonObject{
             {QStringLiteral("code"), code},
             {QStringLiteral("message"), message},
             {QStringLiteral("details"), QJsonObject{}},
         }},
    };
}

// docs/ipc-protocol.md §3 image.open：sync，result 携带 document_id（
// exportToEditor 委托链的落点）。
QJsonObject openSuccessResponse(const QString &requestId, const QString &documentId) {
    return successResponse(requestId, QJsonObject{
                                          {QStringLiteral("document_id"), documentId},
                                          {QStringLiteral("width"), 512},
                                          {QStringLiteral("height"), 512},
                                          {QStringLiteral("format"), QStringLiteral("PNG")},
                                          {QStringLiteral("file_size"), 4096},
                                      });
}

// generate.render 受理响应（§2.3 异步动作受理形态，与 filter.apply/batch.start
// 的受理回执同构）。
QJsonObject asyncAcceptedResponse(const QString &requestId, const QString &taskId) {
    return successResponse(requestId, QJsonObject{
                                          {QStringLiteral("task_id"), taskId},
                                          {QStringLiteral("status"), QStringLiteral("queued")},
                                      });
}

QJsonObject completedEvent(const QString &taskId, const QJsonObject &result) {
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.completed")},
        {QStringLiteral("task_id"), taskId},
        {QStringLiteral("result"), result},
    };
}

QJsonObject failedEvent(const QString &taskId, const QString &code, const QString &message) {
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.failed")},
        {QStringLiteral("task_id"), taskId},
        {QStringLiteral("error"),
         QJsonObject{
             {QStringLiteral("code"), code},
             {QStringLiteral("message"), message},
             {QStringLiteral("details"), QJsonObject{}},
         }},
    };
}

// generate.list 的 result（{generators: [...]}，形状契约见 studio_service.h
// 头注释）：可用生成器 + G'MIC 依赖置灰生成器。
QJsonObject generatorListResult() {
    return QJsonObject{
        {QStringLiteral("generators"),
         QJsonArray{
             QJsonObject{
                 {QStringLiteral("key"), QStringLiteral("perlin_noise")},
                 {QStringLiteral("name"), QStringLiteral("柏林噪声")},
                 {QStringLiteral("category"), QStringLiteral("noise")},
                 {QStringLiteral("category_label"), QStringLiteral("噪声")},
                 {QStringLiteral("available"), true},
                 {QStringLiteral("optional_deps"), QJsonArray{}},
                 {QStringLiteral("params"), QJsonArray{}},
             },
             QJsonObject{
                 {QStringLiteral("key"), QStringLiteral("gmic_texture")},
                 {QStringLiteral("name"), QStringLiteral("G'MIC 纹理")},
                 {QStringLiteral("category"), QStringLiteral("texture")},
                 {QStringLiteral("category_label"), QStringLiteral("纹理")},
                 {QStringLiteral("available"), false},
                 {QStringLiteral("optional_deps"), QJsonArray{QStringLiteral("gmic")}},
                 {QStringLiteral("params"), QJsonArray{}},
             },
         }},
    };
}

} // namespace

class TestStudioService : public QObject {
    Q_OBJECT

  private slots:
    void initTestCase();
    void cleanupTestCase();

    // 服务默认态 + 未绑定后端（每个 Q_INVOKABLE 如实报错、不上送）。
    void defaultsAndUnboundBackend();
    // generate.list 填充 generatorModel + loadingGenerators 生命周期。
    void loadGeneratorsFillsModel();
    // generate.list 失败：收在途标志、报错、目录保持旧数据。
    void loadGeneratorsFailureKeepsCatalog();
    // 同步拒绝（现实 Worker 尚无 generate.* → UNKNOWN_ACTION，§5）。
    void generateListSyncRejection();
    // render 本地拒绝：空 key / 非正尺寸 / paramsJson 非对象（零上送）。
    void renderLocalRejections();
    // 协议违约：受理成功响应缺 task_id（generate.render 必为异步受理，§2.3）。
    void missingTaskIdIsProtocolViolation();
    // 受理交付 task_id（renderAccepted + 任务行"生成渲染"）→ 完成事件经
    // notifyPreviewReady 交付 path / data 两种形状；缺预览图为协议违约；
    // 未知任务帧忽略。
    void renderAcceptanceAndCompletion();
    // §7：task.failed（含 CANCELLED）→ studioError，不发射预览信号。
    void renderFailureEvents();
    // 委托链路：exportToEditor → DocumentService.openDocument（声明在最后，
    // 文档单例状态跨测试函数存续）。
    void exportToEditorDelegates();

  private:
    std::unique_ptr<QTemporaryDir> m_storeDir;
    BackendManager m_backend;
};

void TestStudioService::initTestCase() {
    m_storeDir = std::make_unique<QTemporaryDir>();
    QVERIFY(m_storeDir->isValid());
    QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, m_storeDir->path());
    SettingsService::instance();
    // 委托目标 DocumentService::instance() 是进程级单例：整个二进制只绑定一次
    // 到测试级 m_backend（成员——不会被某个测试函数的栈回收藏断）。
    DocumentService::instance()->bindBackend(&m_backend);
}

void TestStudioService::cleanupTestCase() {
    m_storeDir.reset();
}

void TestStudioService::defaultsAndUnboundBackend() {
    // 不 bindBackend 的裸服务：默认态干净，未绑定的调用一律 studioError(INTERNAL)
    // 且不上送（探针证明 request_id 计数器没被消费）。
    StudioService service;
    QAbstractItemModelTester modelTester(service.generatorModel());
    QSignalSpy errors(&service, &StudioService::studioError);

    QVERIFY(!service.loadingGenerators());
    QCOMPARE(service.generatorModel()->rowCount(), 0);

    const int n = probeSlot(m_backend);
    service.loadGenerators();
    QCOMPARE(service.render(QStringLiteral("gen"), QStringLiteral("{}"), 512, 512), QString());
    service.exportToEditor(QString()); // 空路径：本地拒绝在委托之前
    QCOMPARE(errors.count(), 3);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INTERNAL"));
    QCOMPARE(errors.at(1).at(0).toString(), QStringLiteral("INTERNAL"));
    QCOMPARE(errors.at(2).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(probeSlot(m_backend), n + 1); // 三次调用零上送
    QVERIFY(!service.loadingGenerators()); // 未发出不进入在途状态
}

void TestStudioService::loadGeneratorsFillsModel() {
    StudioService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.generatorModel());
    QSignalSpy loading(&service, &StudioService::loadingGeneratorsChanged);
    QSignalSpy errors(&service, &StudioService::studioError);

    const int n = probeSlot(m_backend);
    service.loadGenerators();
    QCOMPARE(service.loadingGenerators(), true);
    QCOMPARE(loading.count(), 1); // false → true

    emit m_backend.responseReady(reqId(n + 1),
                                 successResponse(reqId(n + 1), generatorListResult()));

    QCOMPARE(service.loadingGenerators(), false);
    QCOMPARE(loading.count(), 2); // true → false
    QCOMPARE(errors.count(), 0);
    QCOMPARE(service.generatorModel()->rowCount(), 2);
    QCOMPARE(service.generatorModel()
                 ->index(0, 0)
                 .data(GeneratorModel::GeneratorKeyRole)
                 .toString(),
             QStringLiteral("perlin_noise"));
    QCOMPARE(service.generatorModel()->index(0, 0).data(GeneratorModel::AvailableRole).toBool(),
             true);
    QCOMPARE(service.generatorModel()->index(1, 0).data(GeneratorModel::AvailableRole).toBool(),
             false);
    QCOMPARE(service.generatorModel()->index(1, 0).data(GeneratorModel::OptionalDepsRole)
                 .toStringList(),
             QStringList{QStringLiteral("gmic")});

    // 未跟踪帧不落 generatorModel：generate.render 的异步受理（task_id 响应）
    // 与未知 request_id 一律被 StudioService 忽略（studio_service.cpp 关联注释）。
    emit m_backend.responseReady(reqId(n + 7),
                                 asyncAcceptedResponse(reqId(n + 7), QStringLiteral("task-ghost")));
    QCOMPARE(service.generatorModel()->rowCount(), 2);
    QCOMPARE(errors.count(), 0);
    QCOMPARE(service.loadingGenerators(), false);
}

void TestStudioService::loadGeneratorsFailureKeepsCatalog() {
    StudioService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.generatorModel());
    QSignalSpy loading(&service, &StudioService::loadingGeneratorsChanged);
    QSignalSpy errors(&service, &StudioService::studioError);

    // 先成功填一次目录。
    const int n = probeSlot(m_backend);
    service.loadGenerators();
    emit m_backend.responseReady(reqId(n + 1),
                                 successResponse(reqId(n + 1), generatorListResult()));
    QCOMPARE(service.generatorModel()->rowCount(), 2);

    // 第二次刷新被拒：收在途标志 + 报错；目录保持旧数据（不填新、不清旧）。
    service.loadGenerators();
    QCOMPARE(service.loadingGenerators(), true);
    emit m_backend.responseReady(
        reqId(n + 2),
        failedResponse(reqId(n + 2), QStringLiteral("INTERNAL"), QStringLiteral("worker 异常")));
    QCOMPARE(service.loadingGenerators(), false);
    QCOMPARE(loading.count(), 4); // true→false→true→false
    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INTERNAL"));
    QCOMPARE(service.generatorModel()->rowCount(), 2); // 旧目录仍在
}

void TestStudioService::generateListSyncRejection() {
    StudioService service;
    service.bindBackend(&m_backend);
    QSignalSpy errors(&service, &StudioService::studioError);

    // 当前 Worker 无 generate.list → UNKNOWN_ACTION（§5）：在途标志收掉、错误
    // 如实上报（Studio 页的错误态），模型不动。
    const int n = probeSlot(m_backend);
    service.loadGenerators();
    emit m_backend.responseReady(
        reqId(n + 1),
        failedResponse(reqId(n + 1), QStringLiteral("UNKNOWN_ACTION"),
                       QStringLiteral("未知动作: generate.list")));
    QCOMPARE(service.loadingGenerators(), false);
    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("UNKNOWN_ACTION"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("未知动作: generate.list"));
}

void TestStudioService::renderLocalRejections() {
    StudioService service;
    service.bindBackend(&m_backend);
    QSignalSpy accepted(&service, &StudioService::renderAccepted);
    QSignalSpy errors(&service, &StudioService::studioError);

    const int n = probeSlot(m_backend);
    // 空 generator_key。
    QCOMPARE(service.render(QString(), QStringLiteral("{}"), 512, 512), QString());
    // 非正尺寸。
    QCOMPARE(service.render(QStringLiteral("gen"), QStringLiteral("{}"), 0, 512), QString());
    QCOMPARE(service.render(QStringLiteral("gen"), QStringLiteral("{}"), 512, -1), QString());
    // paramsJson 解析失败 / 非对象。
    QCOMPARE(service.render(QStringLiteral("gen"), QStringLiteral("{not json"), 512, 512),
             QString());
    QCOMPARE(service.render(QStringLiteral("gen"), QStringLiteral("[1,2]"), 512, 512), QString());
    QCOMPARE(errors.count(), 5);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("生成器 key 为空"));
    QCOMPARE(errors.at(1).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(errors.at(1).at(1).toString(), QStringLiteral("渲染尺寸无效"));
    QCOMPARE(errors.at(3).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(errors.at(3).at(1).toString(), QStringLiteral("参数不是 JSON 对象"));
    QCOMPARE(probeSlot(m_backend), n + 1); // 五次拒绝零上送
    QCOMPARE(accepted.count(), 0);
}

void TestStudioService::missingTaskIdIsProtocolViolation() {
    StudioService service;
    service.bindBackend(&m_backend);
    QSignalSpy accepted(&service, &StudioService::renderAccepted);
    QSignalSpy errors(&service, &StudioService::studioError);

    const int n = probeSlot(m_backend);
    service.render(QStringLiteral("gen"), QStringLiteral("{}"), 512, 512);
    // 成功响应缺 task_id：generate.render 是异步动作（§2.3），缺失即协议违约，
    // 不伪造受理（该提交永远不会有事件跟进，test_batch_service.cpp:314-336 同款）。
    emit m_backend.responseReady(
        reqId(n + 1),
        successResponse(reqId(n + 1), QJsonObject{{QStringLiteral("accepted"), true}}));

    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INTERNAL"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("generate.render 响应缺少 task_id"));
    QCOMPARE(accepted.count(), 0);
}

void TestStudioService::renderAcceptanceAndCompletion() {
    StudioService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester modelTester(service.generatorModel());
    QSignalSpy accepted(&service, &StudioService::renderAccepted);
    QSignalSpy previewReady(&service, &StudioService::notifyPreviewReady);
    QSignalSpy errors(&service, &StudioService::studioError);

    // 任务行：渲染受理进 TaskModel（行名"生成渲染"），进度呈现归 TaskModel。
    TaskModel taskModel;
    QAbstractItemModelTester taskTester(&taskModel);
    taskModel.setBackend(&m_backend);
    service.bindTaskModel(&taskModel);

    // 1) 提交：返回提交关联号 request_id（§2.3：task_id 只随受理响应到达）；
    //    paramsJson 为参数值对象；响应前不造任务行（不伪造进度）。
    const int n = probeSlot(m_backend);
    const QString submitted =
        service.render(QStringLiteral("perlin_noise"), QStringLiteral("{\"seed\":42}"), 512, 512);
    QCOMPARE(submitted, reqId(n + 1));
    QCOMPARE(taskModel.rowCount(), 0);

    // 2) 受理：task_id 唯一交付路径 renderAccepted + 任务行建立。
    emit m_backend.responseReady(reqId(n + 1),
                                 asyncAcceptedResponse(reqId(n + 1), QStringLiteral("task-1")));
    QCOMPARE(accepted.count(), 1);
    QCOMPARE(accepted.at(0).at(0).toString(), QStringLiteral("task-1"));
    QCOMPARE(taskModel.rowCount(), 1);
    QCOMPARE(taskModel.index(0, 0).data(TaskModel::NameRole).toString(), QStringLiteral("生成渲染"));
    QCOMPARE(taskModel.index(0, 0).data(TaskModel::StatusRole).toString(),
             QStringLiteral("queued"));

    // 3) 进度事件：StudioService 不发预览（进度呈现归 TaskModel 行）。
    emit m_backend.taskEvent(QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.progress")},
        {QStringLiteral("task_id"), QStringLiteral("task-1")},
        {QStringLiteral("progress"), 40},
    });
    QCOMPARE(taskModel.index(0, 0).data(TaskModel::StatusRole).toString(),
             QStringLiteral("running"));
    QCOMPARE(previewReady.count(), 0);
    QCOMPARE(errors.count(), 0);

    // 4) 完成（§4 临时文件路径形状）：path 经 notifyPreviewReady 交付。
    emit m_backend.taskEvent(completedEvent(
        QStringLiteral("task-1"),
        QJsonObject{
            {QStringLiteral("path"), QStringLiteral("/tmp/toolbox-worker-1/tex.png")},
            {QStringLiteral("width"), 512},
            {QStringLiteral("height"), 512},
            {QStringLiteral("sha256"), QStringLiteral("abc")},
        }));
    QCOMPARE(previewReady.count(), 1);
    QCOMPARE(previewReady.at(0).at(0).toString(),
             QStringLiteral("/tmp/toolbox-worker-1/tex.png"));
    QCOMPARE(taskModel.index(0, 0).data(TaskModel::StatusRole).toString(),
             QStringLiteral("completed"));
    QCOMPARE(errors.count(), 0);

    // 5) 内联数据形状：无 path 时 data 原样交付（data-URL/base64 文本，QML
    //    Image 可直载）。
    const QString submitted2 = service.render(QStringLiteral("perlin_noise"), QString(), 256, 256);
    QCOMPARE(submitted2, reqId(n + 2)); // 空 paramsJson = 无参生成器，合法提交
    emit m_backend.responseReady(reqId(n + 2),
                                 asyncAcceptedResponse(reqId(n + 2), QStringLiteral("task-2")));
    QCOMPARE(accepted.count(), 2);
    emit m_backend.taskEvent(completedEvent(
        QStringLiteral("task-2"),
        QJsonObject{{QStringLiteral("data"), QStringLiteral("data:image/png;base64,AAAA")}}));
    QCOMPARE(previewReady.count(), 2);
    QCOMPARE(previewReady.at(1).at(0).toString(), QStringLiteral("data:image/png;base64,AAAA"));

    // 6) 协议违约：完成结果既无 path 也无 data——显式报错，不发射空路径的
    //    预览信号（QML 会把空串当真图源）。
    const QString submitted3 =
        service.render(QStringLiteral("perlin_noise"), QStringLiteral("{}"), 128, 128);
    QCOMPARE(submitted3, reqId(n + 3));
    emit m_backend.responseReady(reqId(n + 3),
                                 asyncAcceptedResponse(reqId(n + 3), QStringLiteral("task-3")));
    emit m_backend.taskEvent(completedEvent(QStringLiteral("task-3"),
                                            QJsonObject{{QStringLiteral("width"), 128}}));
    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INTERNAL"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("generate.render 完成结果缺少预览图"));
    QCOMPARE(previewReady.count(), 2);

    // 7) 未知任务的终态帧：忽略（image.* / filter.* 任务归各自服务）。
    emit m_backend.taskEvent(completedEvent(
        QStringLiteral("task-ghost"),
        QJsonObject{{QStringLiteral("path"), QStringLiteral("/tmp/ghost.png")}}));
    QCOMPARE(previewReady.count(), 2);
    QCOMPARE(errors.count(), 1);
}

void TestStudioService::renderFailureEvents() {
    StudioService service;
    service.bindBackend(&m_backend);
    QSignalSpy previewReady(&service, &StudioService::notifyPreviewReady);
    QSignalSpy errors(&service, &StudioService::studioError);

    const int n = probeSlot(m_backend);
    service.render(QStringLiteral("gen"), QStringLiteral("{}"), 512, 512);
    emit m_backend.responseReady(reqId(n + 1),
                                 asyncAcceptedResponse(reqId(n + 1), QStringLiteral("task-1")));

    // §7：非取消失败（如引擎异常）→ studioError 透传 code/message。
    emit m_backend.taskEvent(failedEvent(QStringLiteral("task-1"), QStringLiteral("ENGINE_ERROR"),
                                         QStringLiteral("处理器执行异常")));
    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("ENGINE_ERROR"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("处理器执行异常"));
    QCOMPARE(previewReady.count(), 0);

    // §7：取消以 task.failed + CANCELLED 呈现——同一通道如实上报，不特判吞掉。
    service.render(QStringLiteral("gen"), QStringLiteral("{}"), 512, 512);
    emit m_backend.responseReady(reqId(n + 2),
                                 asyncAcceptedResponse(reqId(n + 2), QStringLiteral("task-2")));
    emit m_backend.taskEvent(failedEvent(QStringLiteral("task-2"), QStringLiteral("CANCELLED"),
                                         QStringLiteral("任务已取消")));
    QCOMPARE(errors.count(), 2);
    QCOMPARE(errors.at(1).at(0).toString(), QStringLiteral("CANCELLED"));
    QCOMPARE(previewReady.count(), 0);
}

void TestStudioService::exportToEditorDelegates() {
    StudioService service;
    service.bindBackend(&m_backend);
    QSignalSpy errors(&service, &StudioService::studioError);

    // 真实委托链路：exportToEditor → DocumentService::openDocument（image.open，
    // sync）——文档状态经 documentOpened 交付，不经 studioError/documentOpened
    // 之外的通道转述（studio_service.cpp exportToEditor 注释）。
    QSignalSpy docOpened(DocumentService::instance(), &DocumentService::documentOpened);
    QSignalSpy docErrors(DocumentService::instance(), &DocumentService::documentError);

    const int n = probeSlot(m_backend);
    service.exportToEditor(QStringLiteral("/tmp/tex.png"));
    QCOMPARE(errors.count(), 0); // 文档层错误不经 studioError（通道分离）
    emit m_backend.responseReady(reqId(n + 1),
                                 openSuccessResponse(reqId(n + 1), QStringLiteral("doc-tex")));
    QCOMPARE(docOpened.count(), 1);
    QCOMPARE(docOpened.at(0).at(1).toString(), QStringLiteral("/tmp/tex.png"));
    QCOMPARE(DocumentService::instance()->currentDocumentId(), QStringLiteral("doc-tex"));
    QCOMPARE(docErrors.count(), 0);
}

QTEST_MAIN(TestStudioService)
#include "test_studio_service.moc"
