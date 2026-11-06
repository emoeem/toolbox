// Phase 5 service tests: FilterService as the filter-page facade (catalog fill,
// presets, preview/apply delegation).
//
// Simulation strategy — same as test_task_model.cpp / test_document_service.cpp
// (no Python Worker in native tests): the tests emit BackendManager's
// responseReady/taskEvent signals directly. The manager is never started, so
// sendAction only consumes its request_id counter slot
// (backend_manager.cpp:103-107, "req-<counter>"): each Q_INVOKABLE sends a
// known number of requests, so tests predict request ids by call order relative
// to a probe sendAction, and probe-before/after proves locally-rejected calls
// sent nothing. Action names on the wire are locked by tests/test_worker_*.py
// and test_ipc_protocol, not here.
//
// The singleton split matters here: FilterService instances are fresh per test
// function, but previewChain/applyChain delegate to the process-wide
// DocumentService::instance() (filter_service.cpp previewChain/applyChain), so
// initTestCase binds the singleton once to the test-wide BackendManager member
// (never a stack Harness that would leave a dangling m_backend behind). Tests
// that rely on "no document open" are declared BEFORE the one that opens one —
// the document state of the singleton outlives a test function.
//
// Store isolation mirrors test_document_service.cpp: SettingsService builds its
// QSettings with explicit IniFormat (settings_service.cpp:39), so the
// QSettings::setPath redirect in initTestCase covers the addRecentFile side
// effect of the openDocument in the delegation test.
#include <QtTest/QAbstractItemModelTester>
#include <QtTest/QtTest>

#include <QJsonArray>
#include <QJsonObject>
#include <QSettings>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QUrl>

#include <memory>

#include "backend/backend_manager.h"
#include "backend/ipc_protocol.h"
#include "core/document_service.h"
#include "models/filter_chain_model.h"
#include "models/filter_model.h"
#include "models/task_model.h"
#include "services/settings_service.h"

using toolbox::BackendManager;
using toolbox::DocumentService;
using toolbox::FilterChainModel;
using toolbox::FilterModel;
using toolbox::FilterService;
using toolbox::TaskModel;

namespace {

QString reqId(int n) {
    return QStringLiteral("req-%1").arg(n);
}

// Probe: consumes one request-id slot and returns its number, giving every test
// a stable offset regardless of execution order (same trace trick as the
// cancel tests in test_task_model.cpp).
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

// docs/ipc-protocol.md §3 image.open：sync，result 携带 document_id。
QJsonObject openSuccessResponse(const QString &requestId, const QString &documentId) {
    return successResponse(requestId, QJsonObject{
                                           {QStringLiteral("document_id"), documentId},
                                           {QStringLiteral("width"), 640},
                                           {QStringLiteral("height"), 480},
                                           {QStringLiteral("format"), QStringLiteral("PNG")},
                                           {QStringLiteral("file_size"), 4096},
                                       });
}

// docs/ipc-protocol.md §2.3：异步动作受理响应。
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

// docs/ipc-protocol.md §3 filter.list 的 result（元素形状对照
// python_worker/adapters/filter_adapter.py list_filters）。
QJsonObject filterListResult() {
    return QJsonObject{
        {QStringLiteral("filters"),
         QJsonArray{
             QJsonObject{
                 {QStringLiteral("key"), QStringLiteral("gaussian_blur")},
                 {QStringLiteral("name"), QStringLiteral("高斯模糊")},
                 {QStringLiteral("category"), QStringLiteral("blur")},
                 {QStringLiteral("category_label"), QStringLiteral("模糊")},
                 {QStringLiteral("description"), QStringLiteral("经典高斯核模糊")},
                 {QStringLiteral("available"), true},
                 {QStringLiteral("optional_deps"), QJsonArray{}},
                 {QStringLiteral("params"), QJsonArray{}},
             },
             QJsonObject{
                 {QStringLiteral("key"), QStringLiteral("gmic_relight")},
                 {QStringLiteral("name"), QStringLiteral("G'MIC 光影")},
                 {QStringLiteral("category"), QStringLiteral("lighting")},
                 {QStringLiteral("category_label"), QStringLiteral("光影")},
                 {QStringLiteral("description"), QStringLiteral("需要 G'MIC")},
                 {QStringLiteral("available"), false},
                 {QStringLiteral("optional_deps"), QJsonArray{QStringLiteral("gmic")}},
                 {QStringLiteral("params"), QJsonArray{}},
             },
         }},
    };
}

// docs/ipc-protocol.md §3.4 filter.presets.list 的 result：只暴露
// {name, step_count} 两个字段（文件路径/时间戳等存储细节不进协议）。
QJsonObject presetsResult(const QStringList &names) {
    QJsonArray presets;
    for (const auto &name : names) {
        presets.append(QJsonObject{
            {QStringLiteral("name"), name},
            {QStringLiteral("step_count"), 2},
        });
    }
    return QJsonObject{{QStringLiteral("presets"), presets}};
}

QJsonArray presetStepsResult() {
    return QJsonArray{
        QJsonObject{
            {QStringLiteral("filter_key"), QStringLiteral("sepia")},
            {QStringLiteral("params"), QJsonObject{{QStringLiteral("intensity"), 0.8}}},
            {QStringLiteral("enabled"), true},
        },
        QJsonObject{
            {QStringLiteral("filter_key"), QStringLiteral("vignette")},
            {QStringLiteral("params"), QJsonObject{}},
            {QStringLiteral("enabled"), false},
        },
    };
}

} // namespace

class TestFilterService : public QObject {
    Q_OBJECT

  private slots:
    void initTestCase();
    void cleanupTestCase();

    // 服务默认态 + 未绑定后端（每个 Q_INVOKABLE 如实报错、不上送）。
    void defaultsAndUnboundBackend();
    // filter.list 填充 filterModel + loadingFilters 生命周期。
    void filterListFillsModel();
    void filterListFailureResetsLoading();
    // 预设本地拒绝（空名称）。
    void presetLocalRejections();
    // 预设往返（list → save → load → delete + 自动刷新）。
    void presetsRoundTrip();
    // 委托拒绝：空链 / 无文档（DocumentService::instance() 此时尚无文档）。
    void chainDelegationRejectedBeforeSend();
    // 委托链路：previewChain/applyChain → DocumentService.applyFilters →
    // 任务行"滤镜链" → 完成事件按 §3.1 落版本（声明顺序在最后一个测试开文档）。
    void previewAndApplyChainDelegate();

  private:
    std::unique_ptr<QTemporaryDir> m_storeDir;
    BackendManager m_backend;
};

void TestFilterService::initTestCase() {
    m_storeDir = std::make_unique<QTemporaryDir>();
    QVERIFY(m_storeDir->isValid());
    QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, m_storeDir->path());
    SettingsService::instance();
    // 委托目标 DocumentService::instance() 是进程级单例：整个二进制只绑定一次
    // 到测试级 m_backend（成员——不会被某个测试函数的栈回收藏断）。
    DocumentService::instance()->bindBackend(&m_backend);
}

void TestFilterService::cleanupTestCase() {
    m_storeDir.reset();
}

void TestFilterService::defaultsAndUnboundBackend() {
    // 不 bindBackend 的裸服务：默认态干净，未绑定的调用一律 filterError(INTERNAL)
    // 且不上送（探针证明 request_id 计数器没被消费）。
    FilterService service;
    QAbstractItemModelTester filterTester(service.filterModel());
    QAbstractItemModelTester chainTester(service.chainModel());
    QSignalSpy errors(&service, &FilterService::filterError);

    QVERIFY(!service.loadingFilters());
    QCOMPARE(service.filterModel()->rowCount(), 0);
    QCOMPARE(service.chainModel()->stepCount(), 0);

    const int n = probeSlot(m_backend);
    QVERIFY(service.presetsList().isEmpty()); // 未绑定：无缓存亦无刷新（错误 #1）
    service.loadFilters();
    service.savePreset(QStringLiteral("任意"));
    service.loadPreset(QStringLiteral("任意"));
    service.deletePreset(QStringLiteral("任意"));
    QCOMPARE(errors.count(), 5); // presetsList + loadFilters + 3 个预设调用
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INTERNAL"));
    QCOMPARE(probeSlot(m_backend), n + 1); // 五次调用零上送

    // 空名称同样本地拒绝（在绑定后端的服务上验证，见 presetLocalRejections）。
    QVERIFY(!service.loadingFilters());
}

void TestFilterService::filterListFillsModel() {
    FilterService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.filterModel());
    QSignalSpy loading(&service, &FilterService::loadingFiltersChanged);
    QSignalSpy errors(&service, &FilterService::filterError);

    const int n = probeSlot(m_backend);
    service.loadFilters();
    QCOMPARE(service.loadingFilters(), true);
    QCOMPARE(loading.count(), 1); // false → true

    emit m_backend.responseReady(reqId(n + 1), successResponse(reqId(n + 1), filterListResult()));

    QCOMPARE(service.loadingFilters(), false);
    QCOMPARE(loading.count(), 2); // true → false
    QCOMPARE(errors.count(), 0);
    QCOMPARE(service.filterModel()->rowCount(), 2);
    QCOMPARE(service.filterModel()->index(0, 0).data(FilterModel::FilterKeyRole).toString(),
             QStringLiteral("gaussian_blur"));
    QCOMPARE(service.filterModel()->index(1, 0).data(FilterModel::AvailableRole).toBool(), false);

    // 未跟踪帧不落 filterModel：DocumentService 的异步受理（task_id 响应）与
    // 未知 request_id 一律被 FilterService 忽略（filter_service.cpp 关联注释）。
    emit m_backend.responseReady(reqId(n + 7),
                                 asyncAcceptedResponse(reqId(n + 7), QStringLiteral("task-ghost")));
    QCOMPARE(service.filterModel()->rowCount(), 2);
    QCOMPARE(errors.count(), 0);
    QCOMPARE(service.loadingFilters(), false);
}

void TestFilterService::filterListFailureResetsLoading() {
    FilterService service;
    service.bindBackend(&m_backend);
    QSignalSpy loading(&service, &FilterService::loadingFiltersChanged);
    QSignalSpy errors(&service, &FilterService::filterError);

    const int n = probeSlot(m_backend);
    service.loadFilters();
    emit m_backend.responseReady(reqId(n + 1),
                                 failedResponse(reqId(n + 1), QStringLiteral("INTERNAL"),
                                                QStringLiteral("worker 异常")));

    // 失败响应同样收在途标志（否则 loadingFilters 永真，页面卡加载态）。
    QCOMPARE(service.loadingFilters(), false);
    QCOMPARE(loading.count(), 2);
    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INTERNAL"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("worker 异常"));
    QCOMPARE(service.filterModel()->rowCount(), 0); // 失败不填模型、不清旧数据
}

void TestFilterService::presetLocalRejections() {
    FilterService service;
    service.bindBackend(&m_backend);
    QSignalSpy errors(&service, &FilterService::filterError);
    QSignalSpy saved(&service, &FilterService::presetSaved);
    QSignalSpy loaded(&service, &FilterService::presetLoaded);
    QSignalSpy deleted(&service, &FilterService::presetDeleted);

    const int n = probeSlot(m_backend);
    service.savePreset(QString());
    service.savePreset(QStringLiteral("   "));
    service.loadPreset(QString());
    service.deletePreset(QStringLiteral("  "));
    QCOMPARE(errors.count(), 4);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("预设名称不能为空"));
    QCOMPARE(probeSlot(m_backend), n + 1); // 四次拒绝零上送
    QCOMPARE(saved.count(), 0);
    QCOMPARE(loaded.count(), 0);
    QCOMPARE(deleted.count(), 0);
}

void TestFilterService::presetsRoundTrip() {
    FilterService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester chainTester(service.chainModel());
    QSignalSpy presetsChanged(&service, &FilterService::presetsChanged);
    QSignalSpy errors(&service, &FilterService::filterError);

    // 1) presetsList：调用即刷新（fire-and-forget），先回缓存，响应后更新缓存。
    const int n = probeSlot(m_backend);
    QVERIFY(service.presetsList().isEmpty());
    emit m_backend.responseReady(
        reqId(n + 1), successResponse(reqId(n + 1), presetsResult({QStringLiteral("链A")})));
    QCOMPARE(presetsChanged.count(), 1);
    QCOMPARE(errors.count(), 0);

    const auto cached = service.presetsList(); // 再次调用又上送一次（n+2）
    QCOMPARE(cached.size(), 1);
    QCOMPARE(cached.at(0).toMap().value(QStringLiteral("name")).toString(), QStringLiteral("链A"));
    QCOMPARE(cached.at(0).toMap().value(QStringLiteral("step_count")).toInt(), 2);
    emit m_backend.responseReady(
        reqId(n + 2), successResponse(reqId(n + 2), presetsResult({QStringLiteral("链A")})));
    QCOMPARE(presetsChanged.count(), 2);

    // 2) savePreset：chainModel 当前链上送（序列化在 sendAction 参数里，线上
    // 形状由 tests/test_worker_presets.py 锁定）；成功响应 {saved, name}
    // （§3.4）→ 信号 + 自动刷新缓存。
    QSignalSpy saved(&service, &FilterService::presetSaved);
    service.chainModel()->addStep(QStringLiteral("gaussian_blur"),
                                  QJsonObject{{QStringLiteral("radius"), 3}});
    service.chainModel()->addStep(QStringLiteral("vignette"));
    service.savePreset(QStringLiteral("链A"));
    emit m_backend.responseReady(reqId(n + 3),
                                 successResponse(reqId(n + 3), QJsonObject{
                                                                    {QStringLiteral("saved"), true},
                                                                    {QStringLiteral("name"),
                                                                     QStringLiteral("链A")},
                                                                }));
    QCOMPARE(saved.count(), 1);
    QCOMPARE(saved.at(0).at(0).toString(), QStringLiteral("链A"));
    emit m_backend.responseReady(reqId(n + 4),
                                 successResponse(reqId(n + 4),
                                                 presetsResult({QStringLiteral("链A"),
                                                                QStringLiteral("链B")})));
    QCOMPARE(presetsChanged.count(), 3); // save 成功后的自动刷新

    // 3) loadPreset：响应 {name, steps}（§3.4）写入 chainModel 并经
    // presetLoaded 交付（fire-and-forget 下这是 steps 的唯一同步可观察路径）。
    QSignalSpy loaded(&service, &FilterService::presetLoaded);
    service.loadPreset(QStringLiteral("链A"));
    emit m_backend.responseReady(reqId(n + 5), successResponse(reqId(n + 5),
                                                               QJsonObject{{QStringLiteral("name"),
                                                                            QStringLiteral("链A")},
                                                                           {QStringLiteral("steps"),
                                                                            presetStepsResult()}}));
    QCOMPARE(loaded.count(), 1);
    QCOMPARE(loaded.at(0).at(0).value<QVariantList>().size(), 2);
    QCOMPARE(service.chainModel()->stepCount(), 2);
    QCOMPARE(service.chainModel()->index(0, 0).data(FilterChainModel::ChainFilterKeyRole).toString(),
             QStringLiteral("sepia"));
    QCOMPARE(service.chainModel()->index(0, 0).data(FilterChainModel::ChainParamsRole)
                 .value<QJsonObject>()
                 .value(QStringLiteral("intensity"))
                 .toDouble(),
             0.8);
    QCOMPARE(service.chainModel()->index(1, 0).data(FilterChainModel::ChainEnabledRole).toBool(),
             false);

    // 4) deletePreset：成功信号 + 自动刷新缓存。
    QSignalSpy deleted(&service, &FilterService::presetDeleted);
    service.deletePreset(QStringLiteral("链A"));
    emit m_backend.responseReady(reqId(n + 6), successResponse(
                                                   reqId(n + 6),
                                                   QJsonObject{{QStringLiteral("deleted"), true}}));
    QCOMPARE(deleted.count(), 1);
    QCOMPARE(deleted.at(0).at(0).toString(), QStringLiteral("链A"));
    emit m_backend.responseReady(
        reqId(n + 7), successResponse(reqId(n + 7), presetsResult({QStringLiteral("链B")})));
    QCOMPARE(presetsChanged.count(), 4);
    QCOMPARE(errors.count(), 0);
}

void TestFilterService::chainDelegationRejectedBeforeSend() {
    FilterService service;
    service.bindBackend(&m_backend);

    // DocumentService::instance() 此时尚无文档（本测试声明在打开文档的
    // previewAndApplyChainDelegate 之前）：空链与无文档都在本地拒绝，不上送。
    QSignalSpy docErrors(DocumentService::instance(), &DocumentService::documentError);
    QSignalSpy actionFailed(DocumentService::instance(), &DocumentService::documentActionFailed);
    QSignalSpy errors(&service, &FilterService::filterError);

    const int n = probeSlot(m_backend);
    service.applyChain(); // 空链 → INVALID_PARAMS（applyFilters 本地拒绝）
    service.previewChain(384);
    QCOMPARE(docErrors.count(), 2);
    QCOMPARE(docErrors.at(0).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(docErrors.at(0).at(1).toString(), QStringLiteral("滤镜链为空"));
    QCOMPARE(actionFailed.count(), 2);
    QCOMPARE(actionFailed.at(0).at(0).toString(), QString()); // 无文档：documentId 为空
    QCOMPARE(actionFailed.at(0).at(1).toString(), QStringLiteral("filter.apply"));
    QCOMPARE(actionFailed.at(1).at(1).toString(), QStringLiteral("filter.preview"));
    QCOMPARE(probeSlot(m_backend), n + 1); // 两次调用零上送

    // 非空链 + 无文档 → UNKNOWN_DOCUMENT，同样零上送、恰好一次失败上报。
    service.chainModel()->addStep(QStringLiteral("gaussian_blur"));
    docErrors.clear();
    actionFailed.clear();
    service.applyChain();
    QCOMPARE(docErrors.count(), 1);
    QCOMPARE(docErrors.at(0).at(0).toString(), QStringLiteral("UNKNOWN_DOCUMENT"));
    QCOMPARE(actionFailed.count(), 1);
    QCOMPARE(actionFailed.at(0).at(1).toString(), QStringLiteral("filter.apply"));
    QCOMPARE(probeSlot(m_backend), n + 2);
    QCOMPARE(errors.count(), 0); // 文档层错误不经 filterError（通道分离）
}

void TestFilterService::previewAndApplyChainDelegate() {
    FilterService service;
    service.bindBackend(&m_backend);
    QSignalSpy errors(&service, &FilterService::filterError);

    // 真实链路：DocumentService::instance() 经 applyFilters 提交 filter 链。
    QSignalSpy docOpened(DocumentService::instance(), &DocumentService::documentOpened);
    QSignalSpy previewReady(DocumentService::instance(), &DocumentService::previewReady);
    QSignalSpy versionChanged(DocumentService::instance(), &DocumentService::documentVersionChanged);
    QSignalSpy modifiedChanged(DocumentService::instance(), &DocumentService::documentModifiedChanged);
    QSignalSpy actionFailed(DocumentService::instance(), &DocumentService::documentActionFailed);

    // 任务行登记：异步 filter 链动作也进 TaskModel，任务名"滤镜链"（任务清单）。
    TaskModel taskModel;
    QAbstractItemModelTester taskTester(&taskModel);
    taskModel.setBackend(&m_backend);
    DocumentService::instance()->bindTaskModel(&taskModel);

    // 打开文档（image.open，sync）。
    const int n = probeSlot(m_backend);
    DocumentService::instance()->openDocument(QUrl::fromLocalFile(QStringLiteral("/tmp/chain.png")));
    emit m_backend.responseReady(reqId(n + 1), openSuccessResponse(reqId(n + 1),
                                                                   QStringLiteral("doc-fx")));
    QCOMPARE(docOpened.count(), 1);
    QCOMPARE(DocumentService::instance()->currentDocumentId(), QStringLiteral("doc-fx"));
    QCOMPARE(DocumentService::instance()->currentVersion(), 0);

    // 组链：两步，第二步禁用——装配应当原样保留 enabled=false。
    service.chainModel()->addStep(QStringLiteral("gaussian_blur"),
                                  QJsonObject{{QStringLiteral("radius"), 3}});
    service.chainModel()->addStep(QStringLiteral("vignette"));
    service.chainModel()->setEnabled(1, false);

    // previewChain(384)：filter.preview 任务（§3 预览不递增版本，§3.1）。
    service.previewChain(384);
    emit m_backend.responseReady(reqId(n + 2), asyncAcceptedResponse(reqId(n + 2),
                                                                     QStringLiteral("task-p")));
    QCOMPARE(taskModel.rowCount(), 1); // 受理即建行（§2.3，trackRequest"滤镜链"）
    QCOMPARE(taskModel.index(0, 0).data(TaskModel::NameRole).toString(), QStringLiteral("滤镜链"));
    emit m_backend.taskEvent(completedEvent(QStringLiteral("task-p"),
                                            QJsonObject{
                                                {QStringLiteral("path"),
                                                 QStringLiteral("/tmp/toolbox-worker-1/prev.png")},
                                                {QStringLiteral("width"), 384},
                                                {QStringLiteral("height"), 256},
                                                {QStringLiteral("sha256"), QStringLiteral("abc")},
                                                {QStringLiteral("preview_of"),
                                                 QStringLiteral("doc-fx")},
                                            }));
    QCOMPARE(previewReady.count(), 1);
    QCOMPARE(DocumentService::instance()->currentVersion(), 0); // 预览不递增
    QVERIFY(!DocumentService::instance()->documentModified());

    // applyChain()：filter.apply 全分辨率（§3.1：version += 1、modified=true；
    // result 无像素文件 → 不发 previewReady）。
    service.applyChain();
    emit m_backend.responseReady(reqId(n + 3), asyncAcceptedResponse(reqId(n + 3),
                                                                     QStringLiteral("task-a")));
    QCOMPARE(taskModel.rowCount(), 2); // 第二行：全分辨率滤镜链
    QCOMPARE(taskModel.index(1, 0).data(TaskModel::NameRole).toString(), QStringLiteral("滤镜链"));
    emit m_backend.taskEvent(completedEvent(QStringLiteral("task-a"),
                                            QJsonObject{
                                                {QStringLiteral("version"), 1},
                                                {QStringLiteral("width"), 640},
                                                {QStringLiteral("height"), 480},
                                            }));
    QCOMPARE(DocumentService::instance()->currentVersion(), 1);
    QCOMPARE(versionChanged.count(), 1);
    QCOMPARE(versionChanged.at(0).at(0).toInt(), 1);
    QCOMPARE(modifiedChanged.count(), 1);
    QVERIFY(DocumentService::instance()->documentModified());
    QCOMPARE(previewReady.count(), 1); // 全分辨率完成不借预览通道
    QCOMPARE(actionFailed.count(), 0);
    QCOMPARE(errors.count(), 0);
}

QTEST_MAIN(TestFilterService)
#include "test_filter_service.moc"
