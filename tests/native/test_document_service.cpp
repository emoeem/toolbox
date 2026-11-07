// Phase 4 service tests: DocumentService as the document/edit facade over the
// Worker protocol, plus HistoryModel as its history consumer.
//
// Simulation strategy — same as test_task_model.cpp (no Python Worker in
// native tests): the tests emit BackendManager's responseReady/taskEvent
// signals directly, which is exactly the hand-off
// BackendManager::onWorkerResponse/onWorkerEvent performs for real Worker
// frames (backend_manager.cpp:123-158). The manager is never started, so
// sendAction only consumes its request_id counter slot
// (backend_manager.cpp:103-107, "req-<counter>"): each Q_INVOKABLE sends
// exactly once, so the tests predict request ids by call order, and
// probe-before/after sendAction calls prove that locally-rejected calls sent
// nothing (same trace trick as the cancel tests in test_task_model.cpp).
//
// Request-id sequencing also can't be spoofed by wire-shape mistakes: message
// shapes here mirror docs/ipc-protocol.md §2.2/§2.3/§3.1-§3.3, while the wire
// itself is locked by tests/test_worker_*.py (Python) and test_ipc_protocol.
//
// Store isolation for the addRecentFile side effect: SettingsService builds
// its QSettings with explicit IniFormat (settings_service.cpp:39), so the
// QSettings::setPath(IniFormat, UserScope, tmp) redirect in initTestCase is
// honored on every platform — no QSKIP needed here (the skip in
// test_settings_service.cpp predates that explicit-IniFormat fix). The
// singleton is pinned once for the whole binary run (SettingsService caches
// s_instance), so recent-file assertions are relative ("first entry is the
// path just opened") with unique paths per test function.
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
#include "models/history_model.h"
#include "models/task_model.h"
#include "services/settings_service.h"

using toolbox::BackendManager;
using toolbox::DocumentService;
using toolbox::HistoryModel;
using toolbox::SettingsService;
using toolbox::TaskModel;

namespace {

QString reqId(int n) {
    return QStringLiteral("req-%1").arg(n);
}

// docs/ipc-protocol.md §3 image.open：sync，result 携带 document_id/width/height。
QJsonObject openSuccessResponse(const QString &requestId, const QString &documentId, int width,
                                int height) {
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("request_id"), requestId},
        {QStringLiteral("success"), true},
        {QStringLiteral("result"),
         QJsonObject{
             {QStringLiteral("document_id"), documentId},
             {QStringLiteral("width"), width},
             {QStringLiteral("height"), height},
             {QStringLiteral("format"), QStringLiteral("PNG")},
             {QStringLiteral("file_size"), 4096},
         }},
    };
}

// docs/ipc-protocol.md §2.3：异步动作受理响应。
QJsonObject asyncAcceptedResponse(const QString &requestId, const QString &taskId) {
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("request_id"), requestId},
        {QStringLiteral("success"), true},
        {QStringLiteral("result"),
         QJsonObject{
             {QStringLiteral("task_id"), taskId},
             {QStringLiteral("status"), QStringLiteral("queued")},
         }},
    };
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

// docs/ipc-protocol.md §3.3 image.history 的 result 形状。
QJsonObject historyResult(int current, bool canUndo, bool canRedo) {
    QJsonArray entries;
    const QStringList names = {QStringLiteral("open"), QStringLiteral("image.adjust"),
                               QStringLiteral("image.transform")};
    for (int i = 0; i < names.size(); ++i)
        entries.append(
            QJsonObject{{QStringLiteral("index"), i}, {QStringLiteral("name"), names.at(i)}});
    return QJsonObject{
        {QStringLiteral("entries"), entries},
        {QStringLiteral("current"), current},
        {QStringLiteral("canUndo"), canUndo},
        {QStringLiteral("canRedo"), canRedo},
    };
}

// Owns manager + service in destruction-safe order (the service is destroyed
// first, so it never observes a half-dead backend).
struct Harness {
    BackendManager backend;
    DocumentService service;

    Harness() { service.bindBackend(&backend); }

    // Full sync handshake for one openDocument call (seq = predicted request
    // counter slot, starting at 1 in a fresh Harness).
    void openDoc(int seq, const QString &documentId, const QString &path, int width, int height) {
        service.openDocument(QUrl::fromLocalFile(path));
        emit backend.responseReady(reqId(seq),
                                   openSuccessResponse(reqId(seq), documentId, width, height));
    }

    // Async action accepted: success response carrying a task_id (§2.3).
    void acceptAsync(int seq, const QString &taskId) {
        emit backend.responseReady(reqId(seq), asyncAcceptedResponse(reqId(seq), taskId));
    }
};

} // namespace

class TestDocumentService : public QObject {
    Q_OBJECT

  private slots:
    void initTestCase();
    void cleanupTestCase();

    // DocumentService
    void defaultsBeforeAnyDocument();
    void untrackedFramesAreIgnored();
    void dispatchRegistersTaskModelRows();
    void openDocumentSucceedsTracksStateAndRecentFiles();
    void openDocumentFailureEmitsError();
    void openDocumentRejectsNonLocalUrlLocally();
    void completedUpdatesVersionAndModified();
    void filterApplyCompletedBumpsVersionWithoutPreview();
    void previewCompletedDoesNotTouchVersionOrModified();
    void resetCompletedCarriesVersionAndPreview();
    void saveCompletesAndClearsModified();
    void saveFailureSurfacesErrorAndKeepsModified();
    void failedTaskEmitsDocumentError();
    void noDocumentCallsStayLocal();
    void unboundBackendEmitsInternal();
    void asyncResponseWithoutTaskIdReportsProtocolBreach();
    void staleTaskResultsDroppedAfterReopen();

    // Phase 9：applyTransform / applyAnnotate
    void applyTransformAndAnnotateLocalRejections();
    void applyTransformDispatchAndCompletion();
    void applyAnnotateDispatchAndFailure();

    // HistoryModel（合并进同文件，任务清单允许）
    void historyReadyForwardsIntoHistoryModel();
    void historyModelRendersCoalescedAdjustEntries();
    void historyModelRoleNamesMatchImplementation();
    void historyModelRefreshParsesProtocolShape();
    void historyModelRefreshUpdatesFlags();
    void historyModelEmptyHistoryClearsState();

  private:
    std::unique_ptr<QTemporaryDir> m_storeDir;
};

void TestDocumentService::initTestCase() {
    // SettingsService 显式按 IniFormat 构造存储（settings_service.cpp:39），
    // 因此该重定向在所有平台生效；本测试类无需平台跳过。单例在此固定，
    // 整个测试二进制共享同一存储与 recentFiles 内存态。
    m_storeDir = std::make_unique<QTemporaryDir>();
    QVERIFY(m_storeDir->isValid());
    QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, m_storeDir->path());
    SettingsService::instance();
}

void TestDocumentService::cleanupTestCase() {
    m_storeDir.reset();
}

void TestDocumentService::defaultsBeforeAnyDocument() {
    Harness h;
    QCOMPARE(h.service.currentDocumentId(), QString());
    QCOMPARE(h.service.documentPath(), QString());
    QCOMPARE(h.service.currentVersion(), 0);
    QVERIFY(!h.service.documentModified());
}

void TestDocumentService::untrackedFramesAreIgnored() {
    Harness h;
    QSignalSpy opened(&h.service, &DocumentService::documentOpened);
    QSignalSpy versionChanged(&h.service, &DocumentService::documentVersionChanged);
    QSignalSpy modifiedChanged(&h.service, &DocumentService::documentModifiedChanged);
    QSignalSpy preview(&h.service, &DocumentService::previewReady);
    QSignalSpy errors(&h.service, &DocumentService::documentError);
    QSignalSpy history(&h.service, &DocumentService::historyReady);
    QSignalSpy saved(&h.service, &DocumentService::documentSaved);

    // 未跟踪的 request_id（worker.hello 由 BackendManager 消费；filter.* 归他方）。
    emit h.backend.responseReady(reqId(9),
                                 openSuccessResponse(reqId(9), QStringLiteral("doc-ghost"), 1, 1));
    // 未知 task_id 的事件（filter.apply 任务、本服务创建前已存在的任务）。
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-ghost"), QJsonObject{{QStringLiteral("version"), 42},
                                                                 {QStringLiteral("width"), 1},
                                                                 {QStringLiteral("height"), 1}}));
    emit h.backend.taskEvent(failedEvent(QStringLiteral("task-ghost"),
                                         QStringLiteral("ENGINE_ERROR"), QStringLiteral("x")));
    // 无 task_id 的事件帧。
    emit h.backend.taskEvent(QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.completed")},
    });

    QCOMPARE(opened.count(), 0);
    QCOMPARE(versionChanged.count(), 0);
    QCOMPARE(modifiedChanged.count(), 0);
    QCOMPARE(preview.count(), 0);
    QCOMPARE(errors.count(), 0);
    QCOMPARE(history.count(), 0);
    QCOMPARE(saved.count(), 0);
    QCOMPARE(h.service.currentDocumentId(), QString());
    QCOMPARE(h.service.currentVersion(), 0);
}

void TestDocumentService::dispatchRegistersTaskModelRows() {
    Harness h;
    TaskModel model;
    QAbstractItemModelTester tester(&model);
    model.setBackend(&h.backend);
    // 生产接线的镜像：QML 侧 EditorPage Component.onCompleted 调
    // DocumentService.bindTaskModel(Application.taskModel)（document_service.h）。
    h.service.bindTaskModel(&model);

    // image.open（sync）：无 task_id，永不建行。
    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/rows.png"), 640, 480);
    QCOMPARE(model.rowCount(), 0);

    // 全分辨率 adjust：受理响应回前无行，受理即建行（§2.3 queued），
    // completed 事件推进到终态——任务抽屉/摘要的可见性依赖这条链路。
    h.service.adjust(QJsonObject{{QStringLiteral("brightness"), 10}}, false, -1);
    QCOMPARE(model.rowCount(), 0);
    h.acceptAsync(2, QStringLiteral("task-1"));
    QCOMPARE(model.rowCount(), 1);
    QCOMPARE(model.index(0, 0).data(TaskModel::TaskIdRole).toString(), QStringLiteral("task-1"));
    QCOMPARE(model.index(0, 0).data(TaskModel::NameRole).toString(), QStringLiteral("应用调整"));
    QCOMPARE(model.index(0, 0).data(TaskModel::StatusRole).toString(), QStringLiteral("queued"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-1"), QJsonObject{{QStringLiteral("version"), 1},
                                                             {QStringLiteral("width"), 640},
                                                             {QStringLiteral("height"), 480}}));
    QCOMPARE(model.index(0, 0).data(TaskModel::StatusRole).toString(), QStringLiteral("completed"));

    // 预览任务同样入列（行内取消的唯一入口是任务行）。
    h.service.adjust(QJsonObject{{QStringLiteral("brightness"), 5}}, true, 512);
    h.acceptAsync(3, QStringLiteral("task-2"));
    QCOMPARE(model.rowCount(), 2);
    QCOMPARE(model.index(1, 0).data(TaskModel::NameRole).toString(), QStringLiteral("调整预览"));

    // 撤销各自成行；同步 image.history 不建行（无 task_id）。
    h.service.undo();
    h.acceptAsync(4, QStringLiteral("task-3"));
    QCOMPARE(model.rowCount(), 3);
    QCOMPARE(model.index(2, 0).data(TaskModel::NameRole).toString(), QStringLiteral("撤销"));
    h.service.requestHistory();
    emit h.backend.responseReady(reqId(5),
                                 successResponse(reqId(5), historyResult(0, false, false)));
    QCOMPARE(model.rowCount(), 3);
}

void TestDocumentService::openDocumentSucceedsTracksStateAndRecentFiles() {
    Harness h;
    QSignalSpy opened(&h.service, &DocumentService::documentOpened);
    QSignalSpy docChanged(&h.service, &DocumentService::currentDocumentChanged);
    QSignalSpy versionChanged(&h.service, &DocumentService::documentVersionChanged);
    QSignalSpy modifiedChanged(&h.service, &DocumentService::documentModifiedChanged);
    QSignalSpy recentChanged(SettingsService::instance(), &SettingsService::recentFilesChanged);

    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/first.png"), 1024, 768);
    // open 恰好消耗一个 request_id 槽位。
    QCOMPARE(h.backend.sendAction(QStringLiteral("probe")), reqId(2));

    QCOMPARE(h.service.currentDocumentId(), QStringLiteral("doc-a1"));
    QCOMPARE(h.service.documentPath(), QStringLiteral("/tmp/first.png"));
    QCOMPARE(h.service.currentVersion(), 0); // §3.1：image.open 时 version = 0
    QVERIFY(!h.service.documentModified());

    QCOMPARE(opened.count(), 1);
    QCOMPARE(opened.at(0).at(0).toString(), QStringLiteral("doc-a1"));
    QCOMPARE(opened.at(0).at(1).toString(), QStringLiteral("/tmp/first.png"));
    QCOMPARE(opened.at(0).at(2).toInt(), 1024);
    QCOMPARE(opened.at(0).at(3).toInt(), 768);
    QCOMPARE(docChanged.count(), 1);
    // 版本 0 → 0：值未变不发 NOTIFY（首开场景）。
    QCOMPARE(versionChanged.count(), 0);
    QCOMPARE(modifiedChanged.count(), 0);

    // 打开成功必须写入最近文件（SettingsService::instance()->addRecentFile）。
    QCOMPARE(recentChanged.count(), 1);
    QCOMPARE(SettingsService::instance()->recentFiles().first(), QStringLiteral("/tmp/first.png"));
}

void TestDocumentService::openDocumentFailureEmitsError() {
    Harness h;
    QSignalSpy opened(&h.service, &DocumentService::documentOpened);
    QSignalSpy errors(&h.service, &DocumentService::documentError);
    QSignalSpy actionFailed(&h.service, &DocumentService::documentActionFailed);
    const int recentCount = SettingsService::instance()->recentFiles().size();

    h.service.openDocument(QUrl::fromLocalFile(QStringLiteral("/tmp/missing.png")));
    emit h.backend.responseReady(reqId(1),
                                 failedResponse(reqId(1), QStringLiteral("FILE_NOT_FOUND"),
                                                QStringLiteral("文件不存在: /tmp/missing.png")));

    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("FILE_NOT_FOUND"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("文件不存在: /tmp/missing.png"));
    // 同步拒绝属于未落定动作：documentActionFailed 携带提交上下文（open 尚无
    // 文档，documentId 为空串）。
    QCOMPARE(actionFailed.count(), 1);
    QCOMPARE(actionFailed.at(0).at(0).toString(), QString());
    QCOMPARE(actionFailed.at(0).at(1).toString(), QStringLiteral("image.open"));
    QCOMPARE(opened.count(), 0);
    QVERIFY(h.service.currentDocumentId().isEmpty());
    QCOMPARE(SettingsService::instance()->recentFiles().size(), recentCount);
}

void TestDocumentService::openDocumentRejectsNonLocalUrlLocally() {
    Harness h;
    QSignalSpy errors(&h.service, &DocumentService::documentError);

    QCOMPARE(h.backend.sendAction(QStringLiteral("probe.before")), reqId(1));
    h.service.openDocument(QUrl(QStringLiteral("https://example.com/a.png")));
    QCOMPARE(h.backend.sendAction(QStringLiteral("probe.after")), reqId(2)); // 未发送
    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
}

void TestDocumentService::completedUpdatesVersionAndModified() {
    Harness h;
    QSignalSpy versionChanged(&h.service, &DocumentService::documentVersionChanged);
    QSignalSpy modifiedChanged(&h.service, &DocumentService::documentModifiedChanged);
    QSignalSpy preview(&h.service, &DocumentService::previewReady);

    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/seq.png"), 1024, 768);

    // image.adjust（preview=false）→ version += 1（§3.1/§3.2）。
    h.service.adjust(QJsonObject{{QStringLiteral("brightness"), 20}}, false, -1);
    h.acceptAsync(2, QStringLiteral("task-1"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-1"), QJsonObject{{QStringLiteral("version"), 1},
                                                             {QStringLiteral("width"), 1024},
                                                             {QStringLiteral("height"), 768}}));
    QCOMPARE(h.service.currentVersion(), 1);
    QVERIFY(h.service.documentModified());
    QCOMPARE(versionChanged.count(), 1);
    QCOMPARE(versionChanged.at(0).at(0).toInt(), 1);
    QCOMPARE(modifiedChanged.count(), 1);
    QCOMPARE(preview.count(), 0); // 全分辨率不带画布刷新文件

    // image.transform（preview=false）→ version += 1；modified 已是 true 不重发。
    h.service.transform(QStringLiteral("rotate"), QJsonObject{{QStringLiteral("angle"), 90}}, false,
                        -1);
    h.acceptAsync(3, QStringLiteral("task-2"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-2"), QJsonObject{{QStringLiteral("version"), 2},
                                                             {QStringLiteral("width"), 768},
                                                             {QStringLiteral("height"), 1024}}));
    QCOMPARE(h.service.currentVersion(), 2);
    QCOMPARE(versionChanged.count(), 2);
    QCOMPARE(modifiedChanged.count(), 1);

    // image.undo → 同样递增（§3.1），并携带画布刷新文件（§3.3）。
    h.service.undo();
    h.acceptAsync(4, QStringLiteral("task-3"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-3"),
                       QJsonObject{{QStringLiteral("version"), 3},
                                   {QStringLiteral("width"), 1024},
                                   {QStringLiteral("height"), 768},
                                   {QStringLiteral("path"), QStringLiteral("/tmp/w/refresh.png")},
                                   {QStringLiteral("sha256"), QStringLiteral("aa")}}));
    QCOMPARE(h.service.currentVersion(), 3);
    QVERIFY(h.service.documentModified());
    QCOMPARE(versionChanged.count(), 3);
    QCOMPARE(versionChanged.at(2).at(0).toInt(), 3);
    QCOMPARE(preview.count(), 1);
    QCOMPARE(preview.at(0).at(0).value<QJsonObject>().value(QStringLiteral("path")).toString(),
             QStringLiteral("/tmp/w/refresh.png"));

    // 重开新文档：version 复位 0（§3.1）、modified 清除、path 换新。
    h.service.openDocument(QUrl::fromLocalFile(QStringLiteral("/tmp/second.png")));
    emit h.backend.responseReady(reqId(5),
                                 openSuccessResponse(reqId(5), QStringLiteral("doc-b2"), 640, 480));
    QCOMPARE(h.service.currentVersion(), 0);
    QCOMPARE(versionChanged.count(), 4);
    QCOMPARE(versionChanged.at(3).at(0).toInt(), 0);
    QVERIFY(!h.service.documentModified());
    QCOMPARE(modifiedChanged.count(), 2); // apply 时 true，重开清除
    QCOMPARE(h.service.documentPath(), QStringLiteral("/tmp/second.png"));
}

// filter.apply（全分辨率）完成路径：version += 1、modified=true、无画布刷新
// 文件；其 undo/redo 与 image.undo 走同一 PendingKind::Undo 通道（§3.3 同一
// completed result 形状——Worker 端历史条目参数化后协议面不变，此测试锁定
// 消费侧契约：参数化 undo 的完成事件仍携带画布刷新文件）。
void TestDocumentService::filterApplyCompletedBumpsVersionWithoutPreview() {
    Harness h;
    QSignalSpy versionChanged(&h.service, &DocumentService::documentVersionChanged);
    QSignalSpy modifiedChanged(&h.service, &DocumentService::documentModifiedChanged);
    QSignalSpy preview(&h.service, &DocumentService::previewReady);
    QSignalSpy actionFailed(&h.service, &DocumentService::documentActionFailed);

    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/chain.png"), 800, 600);

    const QJsonArray steps{
        QJsonObject{{QStringLiteral("filter_key"), QStringLiteral("grayscale_standard")},
                    {QStringLiteral("params"), QJsonObject{}},
                    {QStringLiteral("enabled"), true}}};
    h.service.applyFilters(steps, false, -1);
    QCOMPARE(h.backend.sendAction(QStringLiteral("probe")), reqId(3)); // filter.apply 消耗槽位 2
    h.acceptAsync(2, QStringLiteral("task-f1"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-f1"), QJsonObject{{QStringLiteral("version"), 1},
                                                              {QStringLiteral("width"), 800},
                                                              {QStringLiteral("height"), 600}}));
    QCOMPARE(h.service.currentVersion(), 1);
    QVERIFY(h.service.documentModified());
    QCOMPARE(versionChanged.count(), 1);
    QCOMPARE(modifiedChanged.count(), 1);
    QCOMPARE(preview.count(), 0); // filter.apply 全分辨率无像素文件（§3.1）
    QCOMPARE(actionFailed.count(), 0);

    // 链应用后的 undo：completed result 形状与 image.undo 一致（画布刷新文件）。
    // 槽位 4：:467 的探针 sendAction 已无条件消耗 req-3（backend_manager.cpp:103
    // 对任何 sendAction 都 ++m_requestCounter），undo 本身占 req-4。
    h.service.undo();
    h.acceptAsync(4, QStringLiteral("task-f2"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-f2"),
                       QJsonObject{{QStringLiteral("version"), 2},
                                   {QStringLiteral("width"), 800},
                                   {QStringLiteral("height"), 600},
                                   {QStringLiteral("path"), QStringLiteral("/tmp/w/undo.png")},
                                   {QStringLiteral("sha256"), QStringLiteral("bb")}}));
    QCOMPARE(h.service.currentVersion(), 2);
    QVERIFY(h.service.documentModified()); // undo 不清除 modified（§3.3）
    QCOMPARE(preview.count(), 1);
    QCOMPARE(preview.at(0).at(0).value<QJsonObject>().value(QStringLiteral("path")).toString(),
             QStringLiteral("/tmp/w/undo.png"));
}

void TestDocumentService::previewCompletedDoesNotTouchVersionOrModified() {
    Harness h;
    QSignalSpy versionChanged(&h.service, &DocumentService::documentVersionChanged);
    QSignalSpy modifiedChanged(&h.service, &DocumentService::documentModifiedChanged);
    QSignalSpy preview(&h.service, &DocumentService::previewReady);

    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/preview-src.png"), 1024, 768);

    // image.adjust（preview=true）→ 只 emit previewReady；result.version 为
    // 提交时版本，不改 version / modified（§3.2）。
    h.service.adjust(QJsonObject{{QStringLiteral("brightness"), 5}}, true, 512);
    h.acceptAsync(2, QStringLiteral("task-1"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-1"),
                       QJsonObject{{QStringLiteral("version"), 0},
                                   {QStringLiteral("width"), 512},
                                   {QStringLiteral("height"), 341},
                                   {QStringLiteral("path"), QStringLiteral("/tmp/w/prev.png")},
                                   {QStringLiteral("sha256"), QStringLiteral("bb")}}));

    QCOMPARE(preview.count(), 1);
    QCOMPARE(preview.at(0).at(0).value<QJsonObject>().value(QStringLiteral("path")).toString(),
             QStringLiteral("/tmp/w/prev.png"));
    QCOMPARE(preview.at(0).at(0).value<QJsonObject>().value(QStringLiteral("sha256")).toString(),
             QStringLiteral("bb"));
    QCOMPARE(h.service.currentVersion(), 0);
    QVERIFY(!h.service.documentModified());
    QCOMPARE(versionChanged.count(), 0);
    QCOMPARE(modifiedChanged.count(), 0);
}

void TestDocumentService::resetCompletedCarriesVersionAndPreview() {
    Harness h;
    QSignalSpy versionChanged(&h.service, &DocumentService::documentVersionChanged);
    QSignalSpy modifiedChanged(&h.service, &DocumentService::documentModifiedChanged);
    QSignalSpy preview(&h.service, &DocumentService::previewReady);

    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/reset.png"), 800, 600);

    // 先制造一次未保存修改（modified=true），reset 必须把它清掉：
    // 像素回到源图即无未保存修改（Worker 端 image_adapter.py reset 置
    // modified=False），UI 真值（● / 保存按钮）必须与 image.metadata 一致。
    h.service.adjust(QJsonObject{{QStringLiteral("brightness"), 10}}, false, -1);
    h.acceptAsync(2, QStringLiteral("task-1"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-1"), QJsonObject{{QStringLiteral("version"), 1},
                                                             {QStringLiteral("width"), 800},
                                                             {QStringLiteral("height"), 600}}));
    QVERIFY(h.service.documentModified());
    QCOMPARE(modifiedChanged.count(), 1); // adjust 置脏

    h.service.reset();
    h.acceptAsync(3, QStringLiteral("task-2"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-2"),
                       QJsonObject{{QStringLiteral("version"), 2},
                                   {QStringLiteral("width"), 800},
                                   {QStringLiteral("height"), 600},
                                   {QStringLiteral("path"), QStringLiteral("/tmp/w/r.png")},
                                   {QStringLiteral("sha256"), QStringLiteral("cc")}}));

    // reset 同样 version += 1（§3.1），但 modified 清回 false 而非置脏（§3.3）。
    QCOMPARE(h.service.currentVersion(), 2);
    QVERIFY(!h.service.documentModified());
    QCOMPARE(versionChanged.count(), 2);
    QCOMPARE(modifiedChanged.count(), 2); // true → false 恰好一次
    QCOMPARE(preview.count(), 1);         // 画布刷新文件照常携带

    // 未编辑文档的 reset：modified 保持 false，不再发 NOTIFY（无 true→false 抖动）。
    h.service.reset();
    h.acceptAsync(4, QStringLiteral("task-3"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-3"),
                       QJsonObject{{QStringLiteral("version"), 3},
                                   {QStringLiteral("width"), 800},
                                   {QStringLiteral("height"), 600},
                                   {QStringLiteral("path"), QStringLiteral("/tmp/w/r.png")},
                                   {QStringLiteral("sha256"), QStringLiteral("cc")}}));
    QCOMPARE(h.service.currentVersion(), 3);
    QVERIFY(!h.service.documentModified());
    QCOMPARE(versionChanged.count(), 3);
    QCOMPARE(modifiedChanged.count(), 2); // 值未变不重发
    QCOMPARE(preview.count(), 2);
}

void TestDocumentService::saveCompletesAndClearsModified() {
    Harness h;
    QSignalSpy saved(&h.service, &DocumentService::documentSaved);
    QSignalSpy versionChanged(&h.service, &DocumentService::documentVersionChanged);
    QSignalSpy modifiedChanged(&h.service, &DocumentService::documentModifiedChanged);

    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/save-src.png"), 640, 480);
    h.service.adjust(QJsonObject{{QStringLiteral("brightness"), 10}}, false, -1);
    h.acceptAsync(2, QStringLiteral("task-1"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-1"), QJsonObject{{QStringLiteral("version"), 1},
                                                             {QStringLiteral("width"), 640},
                                                             {QStringLiteral("height"), 480}}));
    QVERIFY(h.service.documentModified());

    h.service.saveDocument(QStringLiteral("/tmp/out.png"), 85);
    h.acceptAsync(3, QStringLiteral("task-2"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-2"),
                       QJsonObject{{QStringLiteral("saved"), true},
                                   {QStringLiteral("path"), QStringLiteral("/tmp/out.png")},
                                   {QStringLiteral("file_size"), 4096}}));

    QCOMPARE(saved.count(), 1);
    QCOMPARE(saved.at(0).at(0).toString(), QStringLiteral("/tmp/out.png"));
    QVERIFY(!h.service.documentModified());
    QCOMPARE(modifiedChanged.count(), 2);    // apply 时 true，save 后 false
    QCOMPARE(h.service.currentVersion(), 1); // §3.1：save 不改 version
    QCOMPARE(versionChanged.count(), 1);
}

void TestDocumentService::saveFailureSurfacesErrorAndKeepsModified() {
    Harness h;
    QSignalSpy errors(&h.service, &DocumentService::documentError);
    QSignalSpy actionFailed(&h.service, &DocumentService::documentActionFailed);
    QSignalSpy saved(&h.service, &DocumentService::documentSaved);
    QSignalSpy modifiedChanged(&h.service, &DocumentService::documentModifiedChanged);

    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/save-fail.png"), 640, 480);
    // 先制造一次未保存修改：本用例的核心契约是"保存失败不得丢脏标记"，
    // modified 从未置 true 的平凡通过覆盖不了它。
    h.service.adjust(QJsonObject{{QStringLiteral("brightness"), 10}}, false, -1);
    h.acceptAsync(2, QStringLiteral("task-1"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-1"), QJsonObject{{QStringLiteral("version"), 1},
                                                             {QStringLiteral("width"), 640},
                                                             {QStringLiteral("height"), 480}}));
    QVERIFY(h.service.documentModified());
    QCOMPARE(modifiedChanged.count(), 1);
    QCOMPARE(actionFailed.count(), 0); // 成功路径不发 documentActionFailed

    h.service.saveDocument(QStringLiteral("/tmp/out.png"), -1);
    h.acceptAsync(3, QStringLiteral("task-2"));
    emit h.backend.taskEvent(failedEvent(QStringLiteral("task-2"), QStringLiteral("ENGINE_ERROR"),
                                         QStringLiteral("编码器异常")));

    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("ENGINE_ERROR"));
    // task.failed 属未落定动作：documentActionFailed 携带提交上下文，
    // QML 在途门控据此区分在途提交失败与无关任务失败。
    QCOMPARE(actionFailed.count(), 1);
    QCOMPARE(actionFailed.at(0).at(0).toString(), QStringLiteral("doc-a1"));
    QCOMPARE(actionFailed.at(0).at(1).toString(), QStringLiteral("image.save"));
    QCOMPARE(saved.count(), 0);
    QVERIFY(h.service.documentModified()); // 失败后脏标记保持 true
    QCOMPARE(modifiedChanged.count(), 1);  // 且未再发射（无先清后置的抖动）
}

void TestDocumentService::failedTaskEmitsDocumentError() {
    Harness h;
    QSignalSpy errors(&h.service, &DocumentService::documentError);
    QSignalSpy actionFailed(&h.service, &DocumentService::documentActionFailed);
    QSignalSpy versionChanged(&h.service, &DocumentService::documentVersionChanged);
    QSignalSpy modifiedChanged(&h.service, &DocumentService::documentModifiedChanged);

    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/cancel-src.png"), 640, 480);
    h.service.adjust(QJsonObject{{QStringLiteral("brightness"), 10}}, false, -1);
    h.acceptAsync(2, QStringLiteral("task-1"));
    emit h.backend.taskEvent(failedEvent(QStringLiteral("task-1"), QStringLiteral("CANCELLED"),
                                         QStringLiteral("任务已取消")));

    // §7：取消以 task.failed + CANCELLED 呈现，服务侧归一为 documentError；
    // 未落定动作另发 documentActionFailed（全分辨率无 -preview 后缀，QML
    // 在途门控据此解锁）。
    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("CANCELLED"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("任务已取消"));
    QCOMPARE(actionFailed.count(), 1);
    QCOMPARE(actionFailed.at(0).at(0).toString(), QStringLiteral("doc-a1"));
    QCOMPARE(actionFailed.at(0).at(1).toString(), QStringLiteral("image.adjust"));
    QCOMPARE(h.service.currentVersion(), 0);
    QVERIFY(!h.service.documentModified());
    QCOMPARE(versionChanged.count(), 0);
    QCOMPARE(modifiedChanged.count(), 0);

    // 同文档的预览任务失败：action 带 "-preview" 后缀——QML 门控不得因此
    // 解锁在途的全分辨率提交（无关错误提前解锁会重开历史栈竞态窗口）。
    h.service.adjust(QJsonObject{{QStringLiteral("brightness"), 5}}, true, 512);
    h.acceptAsync(3, QStringLiteral("task-2"));
    emit h.backend.taskEvent(failedEvent(QStringLiteral("task-2"), QStringLiteral("ENGINE_ERROR"),
                                         QStringLiteral("预览计算异常")));
    QCOMPARE(errors.count(), 2);
    QCOMPARE(actionFailed.count(), 2);
    QCOMPARE(actionFailed.at(1).at(0).toString(), QStringLiteral("doc-a1"));
    QCOMPARE(actionFailed.at(1).at(1).toString(), QStringLiteral("image.adjust-preview"));
    QCOMPARE(h.service.currentVersion(), 0);
}

void TestDocumentService::noDocumentCallsStayLocal() {
    Harness h;
    QSignalSpy errors(&h.service, &DocumentService::documentError);

    QCOMPARE(h.backend.sendAction(QStringLiteral("probe.before")), reqId(1));
    h.service.saveDocument(QStringLiteral("/tmp/x.png"), -1);
    h.service.adjust(QJsonObject{{QStringLiteral("brightness"), 1}}, false, -1);
    h.service.transform(QStringLiteral("rotate"), QJsonObject{{QStringLiteral("angle"), 90}}, false,
                        -1);
    h.service.undo();
    h.service.redo();
    h.service.reset();
    h.service.requestHistory();
    // 七次调用全部本地拒绝，未消耗任何槽位。
    QCOMPARE(h.backend.sendAction(QStringLiteral("probe.after")), reqId(2));
    QCOMPARE(errors.count(), 7);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("UNKNOWN_DOCUMENT"));
}

void TestDocumentService::unboundBackendEmitsInternal() {
    DocumentService standalone;
    QSignalSpy errors(&standalone, &DocumentService::documentError);
    QSignalSpy actionFailed(&standalone, &DocumentService::documentActionFailed);

    standalone.openDocument(QUrl::fromLocalFile(QStringLiteral("/tmp/a.png")));
    standalone.undo();
    QCOMPARE(errors.count(), 2);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INTERNAL"));
    // 未绑定后端时调用方可能已置在途标志：按未落定上报（documentId 为空、
    // action 指向各自动作）。
    QCOMPARE(actionFailed.count(), 2);
    QCOMPARE(actionFailed.at(0).at(0).toString(), QString());
    QCOMPARE(actionFailed.at(0).at(1).toString(), QStringLiteral("image.open"));
    QCOMPARE(actionFailed.at(1).at(0).toString(), QString());
    QCOMPARE(actionFailed.at(1).at(1).toString(), QStringLiteral("image.undo"));
    QVERIFY(standalone.currentDocumentId().isEmpty());
}

void TestDocumentService::asyncResponseWithoutTaskIdReportsProtocolBreach() {
    Harness h;
    QSignalSpy errors(&h.service, &DocumentService::documentError);
    QSignalSpy actionFailed(&h.service, &DocumentService::documentActionFailed);
    QSignalSpy saved(&h.service, &DocumentService::documentSaved);

    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/breach.png"), 640, 480);
    h.service.saveDocument(QStringLiteral("/tmp/out.png"), -1);
    // §2.3：异步动作的成功响应必带 task_id；缺失不得伪造受理状态。该动作
    // 永远不会有事件跟进，必须按未落定上报（否则在途标志失去解除路径）。
    emit h.backend.responseReady(reqId(2), successResponse(reqId(2), QJsonObject{}));

    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INTERNAL"));
    QCOMPARE(actionFailed.count(), 1);
    QCOMPARE(actionFailed.at(0).at(0).toString(), QStringLiteral("doc-a1"));
    QCOMPARE(actionFailed.at(0).at(1).toString(), QStringLiteral("image.save"));
    QCOMPARE(saved.count(), 0);
}

// ---- Phase 9：applyTransform / applyAnnotate --------------------------------

// 本地拒绝契约（applyFilters 空链同款）：无文档、空参数/空 ops 一律不上送
// （探针证明未消耗槽位），每次调用恰好一次 documentError + 一次
// documentActionFailed——后者是 QML 在途门控的唯一解除路径，多半个都会
// 卡死或提前解锁门控。
void TestDocumentService::applyTransformAndAnnotateLocalRejections() {
    Harness h;
    QSignalSpy errors(&h.service, &DocumentService::documentError);
    QSignalSpy actionFailed(&h.service, &DocumentService::documentActionFailed);

    QCOMPARE(h.backend.sendAction(QStringLiteral("probe.before")), reqId(1));
    // 无文档：全分辨率与预览两种形态都本地拒绝（action 各自带/不带 -preview
    // 后缀，QML 门控据此区分在途提交与预览提交的失败）。
    h.service.applyTransform(QJsonObject{
        {QStringLiteral("crop"),
         QJsonObject{{QStringLiteral("x"), 10}, {QStringLiteral("y"), 10},
                     {QStringLiteral("width"), 800}, {QStringLiteral("height"), 600}}}},
        false, -1);
    h.service.applyTransform(
        QJsonObject{{QStringLiteral("rotate_free"),
                     QJsonObject{{QStringLiteral("angle"), 15}, {QStringLiteral("expand"), true}}}},
        true, 512);
    h.service.applyAnnotate(QJsonArray{QJsonObject{
        {QStringLiteral("type"), QStringLiteral("pen")},
        {QStringLiteral("points"), QJsonArray{QJsonArray{1, 2}, QJsonArray{3, 4}}},
        {QStringLiteral("color"), QStringLiteral("#ff0000")},
        {QStringLiteral("width"), 4}}});
    // 空参数/空 ops：与无文档无关，同样本地拒绝（先于无文档判定，
    // applyFilters 空链先例）。
    h.service.applyTransform(QJsonObject{}, false, -1);
    h.service.applyAnnotate(QJsonArray{});
    // 五次调用全部本地拒绝，未消耗任何槽位。
    QCOMPARE(h.backend.sendAction(QStringLiteral("probe.after")), reqId(2));

    QCOMPARE(errors.count(), 5);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("UNKNOWN_DOCUMENT"));
    QCOMPARE(errors.at(1).at(0).toString(), QStringLiteral("UNKNOWN_DOCUMENT"));
    QCOMPARE(errors.at(2).at(0).toString(), QStringLiteral("UNKNOWN_DOCUMENT"));
    QCOMPARE(errors.at(3).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(errors.at(4).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(actionFailed.count(), 5);
    // 恰好一次、动作标识各就各位（空串 documentId：提交时尚无文档）。
    QCOMPARE(actionFailed.at(0).at(0).toString(), QString());
    QCOMPARE(actionFailed.at(0).at(1).toString(), QStringLiteral("image.transform"));
    QCOMPARE(actionFailed.at(1).at(1).toString(), QStringLiteral("image.transform-preview"));
    QCOMPARE(actionFailed.at(2).at(1).toString(), QStringLiteral("image.annotate"));
    QCOMPARE(actionFailed.at(3).at(1).toString(), QStringLiteral("image.transform"));
    QCOMPARE(actionFailed.at(4).at(1).toString(), QStringLiteral("image.annotate"));
}

// PendingKind::ApplyTransform 分发：组合对象原样透传的线形由 Python 侧
// （tests/test_worker_transform.py）锁定；此处锁定消费侧契约——受理建
// TaskModel 行（行名与旧 transform 统一）、全分辨率完成递增 version/置
// modified 且无像素文件、预览完成只发 previewReady 不触碰 version/modified
// （§3.1/§3.2，与 adjust/transform 预览语义一致）。
void TestDocumentService::applyTransformDispatchAndCompletion() {
    Harness h;
    TaskModel model;
    QAbstractItemModelTester tester(&model);
    model.setBackend(&h.backend);
    h.service.bindTaskModel(&model);
    QSignalSpy versionChanged(&h.service, &DocumentService::documentVersionChanged);
    QSignalSpy modifiedChanged(&h.service, &DocumentService::documentModifiedChanged);
    QSignalSpy preview(&h.service, &DocumentService::previewReady);
    QSignalSpy actionFailed(&h.service, &DocumentService::documentActionFailed);

    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/xform.png"), 1024, 768);

    // 全分辨率组合变换（crop + rotate_free 组合，Phase 9 执行顺序归 Worker）。
    const QJsonObject combo{
        {QStringLiteral("crop"),
         QJsonObject{{QStringLiteral("x"), 10}, {QStringLiteral("y"), 10},
                     {QStringLiteral("width"), 800}, {QStringLiteral("height"), 600}}},
        {QStringLiteral("rotate_free"),
         QJsonObject{{QStringLiteral("angle"), 15}, {QStringLiteral("expand"), true}}},
    };
    h.service.applyTransform(combo, false, -1);
    QCOMPARE(h.backend.sendAction(QStringLiteral("probe")), reqId(3)); // 消耗槽位 2
    h.acceptAsync(2, QStringLiteral("task-t1"));
    QCOMPARE(model.rowCount(), 1);
    QCOMPARE(model.index(0, 0).data(TaskModel::NameRole).toString(), QStringLiteral("应用变换"));
    QCOMPARE(model.index(0, 0).data(TaskModel::StatusRole).toString(), QStringLiteral("queued"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-t1"), QJsonObject{{QStringLiteral("version"), 1},
                                                             {QStringLiteral("width"), 800},
                                                             {QStringLiteral("height"), 600}}));
    QCOMPARE(h.service.currentVersion(), 1);
    QVERIFY(h.service.documentModified());
    QCOMPARE(versionChanged.count(), 1);
    QCOMPARE(modifiedChanged.count(), 1);
    QCOMPARE(preview.count(), 0); // 全分辨率完成无像素文件（同 adjust/transform）
    QCOMPARE(actionFailed.count(), 0);

    // 预览形态：result.version 为执行时版本——不递增、不置脏，只发 previewReady。
    h.service.applyTransform(
        QJsonObject{{QStringLiteral("rotate_free"), QJsonObject{{QStringLiteral("angle"), 30}}}},
        true, 512);
    h.acceptAsync(4, QStringLiteral("task-t2")); // 探针已消耗槽位 3
    QCOMPARE(model.rowCount(), 2);
    QCOMPARE(model.index(1, 0).data(TaskModel::NameRole).toString(), QStringLiteral("变换预览"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-t2"),
                       QJsonObject{{QStringLiteral("version"), 1},
                                   {QStringLiteral("width"), 512},
                                   {QStringLiteral("height"), 384},
                                   {QStringLiteral("path"), QStringLiteral("/tmp/w/tf.png")},
                                   {QStringLiteral("sha256"), QStringLiteral("dd")}}));
    QCOMPARE(preview.count(), 1);
    QCOMPARE(preview.at(0).at(0).value<QJsonObject>().value(QStringLiteral("path")).toString(),
             QStringLiteral("/tmp/w/tf.png"));
    QCOMPARE(h.service.currentVersion(), 1); // 预览不递增（§3.1）
    QCOMPARE(versionChanged.count(), 1);     // 无新发射
    QVERIFY(h.service.documentModified());   // 不置脏也不清除
    QCOMPARE(modifiedChanged.count(), 1);    // 无新发射
}

// PendingKind::ApplyAnnotate 分发：全分辨率完成递增 version/置 modified、
// 无像素文件（同 filter.apply 全分辨率路径）；task.failed 时 documentError
// 照常呈现且 documentActionFailed 恰好一次（action = image.annotate）。
void TestDocumentService::applyAnnotateDispatchAndFailure() {
    Harness h;
    TaskModel model;
    QAbstractItemModelTester tester(&model);
    model.setBackend(&h.backend);
    h.service.bindTaskModel(&model);
    QSignalSpy versionChanged(&h.service, &DocumentService::documentVersionChanged);
    QSignalSpy modifiedChanged(&h.service, &DocumentService::documentModifiedChanged);
    QSignalSpy preview(&h.service, &DocumentService::previewReady);
    QSignalSpy errors(&h.service, &DocumentService::documentError);
    QSignalSpy actionFailed(&h.service, &DocumentService::documentActionFailed);

    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/annotate.png"), 800, 600);

    const QJsonArray ops{
        QJsonObject{{QStringLiteral("type"), QStringLiteral("pen")},
                    {QStringLiteral("points"), QJsonArray{QJsonArray{1, 2}, QJsonArray{3, 4}}},
                    {QStringLiteral("color"), QStringLiteral("#ff0000")},
                    {QStringLiteral("width"), 4}},
        QJsonObject{{QStringLiteral("type"), QStringLiteral("blur_rect")},
                    {QStringLiteral("x"), 10},
                    {QStringLiteral("y"), 10},
                    {QStringLiteral("width"), 50},
                    {QStringLiteral("height"), 50},
                    {QStringLiteral("strength"), 8}},
    };
    h.service.applyAnnotate(ops);
    QCOMPARE(h.backend.sendAction(QStringLiteral("probe")), reqId(3)); // 消耗槽位 2
    h.acceptAsync(2, QStringLiteral("task-an1"));
    QCOMPARE(model.rowCount(), 1);
    QCOMPARE(model.index(0, 0).data(TaskModel::NameRole).toString(), QStringLiteral("应用标注"));
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-an1"), QJsonObject{{QStringLiteral("version"), 1},
                                                              {QStringLiteral("width"), 800},
                                                              {QStringLiteral("height"), 600}}));
    QCOMPARE(h.service.currentVersion(), 1);
    QVERIFY(h.service.documentModified());
    QCOMPARE(versionChanged.count(), 1);
    QCOMPARE(modifiedChanged.count(), 1);
    QCOMPARE(preview.count(), 0); // 全分辨率无像素文件，不发 previewReady
    QCOMPARE(actionFailed.count(), 0);

    // 失败路径：未落定动作按提交上下文上报恰好一次（QML 在途门控据此解锁）。
    h.service.applyAnnotate(ops);
    h.acceptAsync(4, QStringLiteral("task-an2")); // 探针已消耗槽位 3
    emit h.backend.taskEvent(failedEvent(QStringLiteral("task-an2"),
                                         QStringLiteral("ENGINE_ERROR"),
                                         QStringLiteral("标注渲染失败")));
    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("ENGINE_ERROR"));
    QCOMPARE(actionFailed.count(), 1);
    QCOMPARE(actionFailed.at(0).at(0).toString(), QStringLiteral("doc-a1"));
    QCOMPARE(actionFailed.at(0).at(1).toString(), QStringLiteral("image.annotate"));
    // 失败只上报不改状态：版本与脏标记保持完成时的值。
    QCOMPARE(h.service.currentVersion(), 1);
    QVERIFY(h.service.documentModified());
    QCOMPARE(versionChanged.count(), 1);
    QCOMPARE(modifiedChanged.count(), 1);
}

void TestDocumentService::staleTaskResultsDroppedAfterReopen() {
    Harness h;
    QSignalSpy versionChanged(&h.service, &DocumentService::documentVersionChanged);
    QSignalSpy modifiedChanged(&h.service, &DocumentService::documentModifiedChanged);
    QSignalSpy preview(&h.service, &DocumentService::previewReady);
    QSignalSpy errors(&h.service, &DocumentService::documentError);
    QSignalSpy actionFailed(&h.service, &DocumentService::documentActionFailed);

    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/stale-a.png"), 640, 480);
    h.service.adjust(QJsonObject{{QStringLiteral("brightness"), 1}}, false, -1);
    h.acceptAsync(2, QStringLiteral("task-1"));
    h.service.adjust(QJsonObject{{QStringLiteral("contrast"), 2}}, false, -1);
    h.acceptAsync(3, QStringLiteral("task-2"));

    // 切换到 doc-b2：旧文档的两个在途任务从此全部陈旧。
    h.openDoc(4, QStringLiteral("doc-b2"), QStringLiteral("/tmp/stale-b.png"), 320, 240);
    QCOMPARE(h.service.currentDocumentId(), QStringLiteral("doc-b2"));
    QCOMPARE(h.service.currentVersion(), 0);

    // 陈旧任务的 completed：version/modified/previewReady 一律不触碰
    // （§3.1：version 是旧任务结果丢弃的依据）。
    emit h.backend.taskEvent(
        completedEvent(QStringLiteral("task-1"), QJsonObject{{QStringLiteral("version"), 2},
                                                             {QStringLiteral("width"), 640},
                                                             {QStringLiteral("height"), 480}}));
    QCOMPARE(versionChanged.count(), 0);
    QCOMPARE(modifiedChanged.count(), 0);
    QCOMPARE(preview.count(), 0);
    QCOMPARE(h.service.currentVersion(), 0);
    QVERIFY(!h.service.documentModified());

    // 陈旧任务的 failed：错误是文档状态之外的提示，仍然如实呈现；
    // documentActionFailed 携带提交时的旧 documentId——QML 门控据此忽略
    // 旧文档失败，不解除新文档的在途提交。
    emit h.backend.taskEvent(failedEvent(QStringLiteral("task-2"), QStringLiteral("ENGINE_ERROR"),
                                         QStringLiteral("处理器执行异常")));
    QCOMPARE(errors.count(), 1);
    QCOMPARE(actionFailed.count(), 1);
    QCOMPARE(actionFailed.at(0).at(0).toString(), QStringLiteral("doc-a1"));
    QCOMPARE(actionFailed.at(0).at(1).toString(), QStringLiteral("image.adjust"));
    QCOMPARE(h.service.currentDocumentId(), QStringLiteral("doc-b2"));
}

void TestDocumentService::historyReadyForwardsIntoHistoryModel() {
    Harness h;
    HistoryModel model;
    QAbstractItemModelTester tester(&model);
    // 生产接线的转发：DocumentService.historyReady → HistoryModel.refreshFrom。
    QObject::connect(&h.service, &DocumentService::historyReady, &model,
                     &HistoryModel::refreshFrom);
    QSignalSpy historyReady(&h.service, &DocumentService::historyReady);
    QSignalSpy undoChanged(&model, &HistoryModel::canUndoChanged);
    QSignalSpy redoChanged(&model, &HistoryModel::canRedoChanged);

    QCOMPARE(model.rowCount(), 0);
    QVERIFY(!model.canUndo());
    QVERIFY(!model.canRedo());

    h.openDoc(1, QStringLiteral("doc-a1"), QStringLiteral("/tmp/hist.png"), 640, 480);
    h.service.requestHistory();
    QCOMPARE(h.backend.sendAction(QStringLiteral("probe")), reqId(3)); // history 消耗槽位 2
    emit h.backend.responseReady(reqId(2), successResponse(reqId(2), historyResult(1, true, true)));

    QCOMPARE(historyReady.count(), 1);
    QCOMPARE(model.rowCount(), 3);
    QVERIFY(model.canUndo());
    QVERIFY(model.canRedo());
    QCOMPARE(undoChanged.count(), 1);
    QCOMPARE(redoChanged.count(), 1);

    // 行数据：index/name/histCurrent 与 §3.3 result 一一对应。
    QCOMPARE(model.index(0, 0).data(HistoryModel::HistIndexRole).toInt(), 0);
    QCOMPARE(model.index(0, 0).data(HistoryModel::HistNameRole).toString(), QStringLiteral("open"));
    QVERIFY(!model.index(0, 0).data(HistoryModel::HistCurrentRole).toBool());
    QCOMPARE(model.index(1, 0).data(HistoryModel::HistIndexRole).toInt(), 1);
    QCOMPARE(model.index(1, 0).data(HistoryModel::HistNameRole).toString(),
             QStringLiteral("image.adjust"));
    QVERIFY(model.index(1, 0).data(HistoryModel::HistCurrentRole).toBool());
    QCOMPARE(model.index(2, 0).data(HistoryModel::HistIndexRole).toInt(), 2);
    QCOMPARE(model.index(2, 0).data(HistoryModel::HistNameRole).toString(),
             QStringLiteral("image.transform"));
    QVERIFY(!model.index(2, 0).data(HistoryModel::HistCurrentRole).toBool());
}

// 滑杆命令合并（coalescing）后的 history 形状：Worker 端把连续的全分辨率
// image.adjust 并作单条（name 仍为 image.adjust），两次应用只呈现一行。
// HistoryModel 是纯消费者——本测试锁定合并后的条目数/行数据/旗标渲染。
void TestDocumentService::historyModelRendersCoalescedAdjustEntries() {
    HistoryModel model;
    QAbstractItemModelTester tester(&model);
    QSignalSpy undoChanged(&model, &HistoryModel::canUndoChanged);
    QSignalSpy redoChanged(&model, &HistoryModel::canRedoChanged);

    const QJsonArray entries{
        QJsonObject{{QStringLiteral("index"), 0}, {QStringLiteral("name"), QStringLiteral("open")}},
        QJsonObject{{QStringLiteral("index"), 1},
                    {QStringLiteral("name"), QStringLiteral("image.adjust")}},
    };
    model.refreshFrom(QJsonObject{{QStringLiteral("entries"), entries},
                                  {QStringLiteral("current"), 1},
                                  {QStringLiteral("canUndo"), true},
                                  {QStringLiteral("canRedo"), false}});

    QCOMPARE(model.rowCount(), 2); // 合并生效：两次应用仅一行（另加 open）
    QVERIFY(model.canUndo());
    QVERIFY(!model.canRedo());
    QCOMPARE(undoChanged.count(), 1);
    QCOMPARE(redoChanged.count(), 0); // false → false 不重发（实现锁定）
    QCOMPARE(model.index(1, 0).data(HistoryModel::HistIndexRole).toInt(), 1);
    QCOMPARE(model.index(1, 0).data(HistoryModel::HistNameRole).toString(),
             QStringLiteral("image.adjust"));
    QVERIFY(model.index(1, 0).data(HistoryModel::HistCurrentRole).toBool());
}

void TestDocumentService::historyModelRoleNamesMatchImplementation() {
    HistoryModel model;
    QAbstractItemModelTester tester(&model);

    const auto roles = model.roleNames();
    QCOMPARE(roles.size(), 3);
    QCOMPARE(roles.value(HistoryModel::HistIndexRole), QByteArray("histIndex"));
    QCOMPARE(roles.value(HistoryModel::HistNameRole), QByteArray("histName"));
    QCOMPARE(roles.value(HistoryModel::HistCurrentRole), QByteArray("histCurrent"));

    // 空模型的平面表契约。
    QCOMPARE(model.rowCount(), 0);
    QVERIFY(!model.index(0, 0).isValid());
    QVERIFY(!model.data(QModelIndex(), HistoryModel::HistNameRole).isValid());
}

void TestDocumentService::historyModelRefreshParsesProtocolShape() {
    HistoryModel model;
    QAbstractItemModelTester tester(&model);

    model.refreshFrom(historyResult(1, true, true));
    QCOMPARE(model.rowCount(), 3);
    QVERIFY(model.canUndo());
    QVERIFY(model.canRedo());

    // current 缺失（畸形结果）：全部行不是当前态，canUndo/canRedo 兜底 false。
    model.refreshFrom(QJsonObject{
        {
            QStringLiteral("entries"),
            QJsonArray{QJsonObject{{QStringLiteral("index"), 0},
                                   {QStringLiteral("name"), QStringLiteral("open")}}},
        },
    });
    QCOMPARE(model.rowCount(), 1);
    QVERIFY(!model.index(0, 0).data(HistoryModel::HistCurrentRole).toBool());
    QVERIFY(!model.canUndo());
    QVERIFY(!model.canRedo());
}

void TestDocumentService::historyModelRefreshUpdatesFlags() {
    HistoryModel model;
    QAbstractItemModelTester tester(&model);
    QSignalSpy undoChanged(&model, &HistoryModel::canUndoChanged);
    QSignalSpy redoChanged(&model, &HistoryModel::canRedoChanged);

    model.refreshFrom(historyResult(1, true, true));
    QCOMPARE(undoChanged.count(), 1);
    QCOMPARE(redoChanged.count(), 1);

    // undo 后 current 回到 0：canUndo 翻转，canRedo 不变（值不变不通知）。
    model.refreshFrom(historyResult(0, false, true));
    QCOMPARE(model.rowCount(), 3);
    QVERIFY(!model.canUndo());
    QVERIFY(model.canRedo());
    QCOMPARE(undoChanged.count(), 2);
    QCOMPARE(redoChanged.count(), 1);
    QVERIFY(model.index(0, 0).data(HistoryModel::HistCurrentRole).toBool());
    QVERIFY(!model.index(1, 0).data(HistoryModel::HistCurrentRole).toBool());
}

void TestDocumentService::historyModelEmptyHistoryClearsState() {
    HistoryModel model;
    QAbstractItemModelTester tester(&model);
    QSignalSpy undoChanged(&model, &HistoryModel::canUndoChanged);

    model.refreshFrom(historyResult(1, true, false));
    QCOMPARE(model.rowCount(), 3);
    QVERIFY(model.canUndo());

    model.refreshFrom(QJsonObject{});
    QCOMPARE(model.rowCount(), 0);
    QVERIFY(!model.canUndo());
    QVERIFY(!model.canRedo());
    QCOMPARE(undoChanged.count(), 2);
}

QTEST_MAIN(TestDocumentService)
#include "test_document_service.moc"
