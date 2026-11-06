// Phase 6 service tests: BatchService as the batch-workspace facade
// (docs/toolbox-2.0-project-plan.md §9.4).
//
// Simulation strategy — same as test_task_model.cpp / test_filter_service.cpp
// (no Python Worker in native tests): the tests emit BackendManager's
// responseReady/taskEvent signals directly. The manager is never started, so
// sendAction only consumes its request_id counter slot
// (backend_manager.cpp:103-105, "req-<counter>"): tests predict request ids by
// call order relative to a probe sendAction, and probe-before/after proves
// locally-rejected or no-op calls sent nothing. Wire payloads are not
// observable in this state (PythonWorker::sendLine drops lines while the
// process is stopped, python_worker.cpp:104-107), so the batch.start params
// shape (paths/output_dir/format/quality?/naming/pattern/steps) is locked here
// only indirectly via the acceptance round-trip and must be pinned by
// tests/test_worker_batch.py when the Worker side lands.
//
// Protocol status note (honest scope): batch.start is NOT yet in
// docs/ipc-protocol.md §3 nor in python_worker/dispatcher.py — the task list
// for this batch covers the native side only (native/models/batch_model.*,
// native/services/batch_service.*, CMake, tests). A real Worker today answers
// UNKNOWN_ACTION; the sync-rejection test below locks exactly that path, and
// the accepted/progress/completed/failed paths encode the §2.3/§7 lifecycle
// contract the Worker-side implementation has to satisfy.
#include <QtTest/QAbstractItemModelTester>
#include <QtTest/QtTest>

#include <QJsonArray>
#include <QJsonObject>
#include <QSignalSpy>

#include "backend/backend_manager.h"
#include "backend/ipc_protocol.h"
#include "models/batch_model.h"
#include "services/batch_service.h"

using toolbox::BackendManager;
using toolbox::BatchModel;
using toolbox::BatchService;

namespace {

QString reqId(int n) {
    return QStringLiteral("req-%1").arg(n);
}

// Probe: consumes one request-id slot and returns its number, giving every test
// a stable offset regardless of execution order (same trace trick as
// test_filter_service.cpp / the cancel tests in test_task_model.cpp).
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

// docs/ipc-protocol.md §2.3：异步动作受理响应。
QJsonObject acceptedResponse(const QString &requestId, const QString &taskId) {
    return successResponse(requestId, QJsonObject{
                                          {QStringLiteral("task_id"), taskId},
                                          {QStringLiteral("status"), QStringLiteral("queued")},
                                      });
}

QJsonObject progressEvent(const QString &taskId, const QString &file, const QString &state,
                          int progress) {
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.progress")},
        {QStringLiteral("task_id"), taskId},
        {QStringLiteral("file"), file},
        {QStringLiteral("state"), state},
        {QStringLiteral("progress"), progress},
    };
}

// 无 file 字段的纯整体进度帧（BatchService 忽略，行数据不做第二真相源）。
QJsonObject overallProgressEvent(const QString &taskId, int progress) {
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.progress")},
        {QStringLiteral("task_id"), taskId},
        {QStringLiteral("progress"), progress},
    };
}

QJsonObject completedEvent(const QString &taskId, const QJsonArray &items) {
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.completed")},
        {QStringLiteral("task_id"), taskId},
        {QStringLiteral("result"),
         QJsonObject{
             {QStringLiteral("total"), items.size()},
             {QStringLiteral("items"), items},
         }},
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

QJsonObject item(const QString &file, const QString &state, const QString &error = {},
                 const QString &outputPath = {}) {
    QJsonObject object{
        {QStringLiteral("file"), file},
        {QStringLiteral("state"), state},
    };
    if (!error.isEmpty())
        object.insert(QStringLiteral("error"), error);
    if (!outputPath.isEmpty())
        object.insert(QStringLiteral("output_path"), outputPath);
    return object;
}

QStringList threePaths() {
    return {QStringLiteral("/tmp/src/a.png"), QStringLiteral("/tmp/src/b.png"),
            QStringLiteral("/tmp/src/c.png")};
}

} // namespace

class TestBatchService : public QObject {
    Q_OBJECT

  private slots:
    // 服务默认态 + 未绑定后端（startBatch 如实报错、cancelBatch 零上送）。
    void defaultsAndUnboundBackend();
    // 绑定后的本地拒绝：空 paths / 空 outputDir（错误 + 不上送）。
    void localRejectionsWhileBound();
    // 受理响应整表重建全 pending 行 + batchStarted 交付 task_id。
    void acceptanceBuildsPendingRows();
    // 同步拒绝（现实 Worker 尚无 batch.start → UNKNOWN_ACTION）：不造行。
    void syncRejectionKeepsModelUntouched();
    // 协议违约：成功响应缺 task_id（batch.start 必为异步受理，§2.3）。
    void missingTaskIdIsProtocolViolation();
    // 逐文件进度映射 + 无 file 帧/未知批次帧忽略。
    void perFileProgressUpdatesRows();
    // 完成：result.items 整表补登（含 output_path/error）+ batchFinished。
    void completedItemsRefreshRows();
    // §7：task.failed CANCELLED → 残余 pending/running 行收尾 skipped。
    void cancelledFailureSweepsToSkipped();
    // 非 CANCELLED 失败：行保持最后已知状态。
    void nonCancelledFailureKeepsRows();
    // 单活动批次：新受理覆盖旧跟踪，旧批次迟到事件被忽略。
    void singleActiveBatchSemantics();
    // cancelBatch 转发与本地 no-op 边界（探针计数证明）。
    void cancelBatchForwarding();

  private:
    BackendManager m_backend;
};

void TestBatchService::defaultsAndUnboundBackend() {
    // 不 bindBackend 的裸服务：默认态干净，未绑定的调用一律 batchError(INTERNAL)
    // 且不上送（探针证明 request_id 计数器没被消费）。
    BatchService service;
    QAbstractItemModelTester tester(service.batchModel());
    QSignalSpy started(&service, &BatchService::batchStarted);
    QSignalSpy errors(&service, &BatchService::batchError);

    QCOMPARE(service.batchModel()->rowCount(), 0);
    QCOMPARE(service.batchModel()->totalCount(), 0);

    const int n = probeSlot(m_backend);
    const QString submitted =
        service.startBatch(threePaths(), QStringLiteral("/tmp/out"), QStringLiteral("PNG"), 85,
                           QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    QCOMPARE(submitted, QString()); // 空返回值 = 未上送
    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INTERNAL"));
    QCOMPARE(service.batchModel()->rowCount(), 0); // 不受理不造行

    service.cancelBatch(QStringLiteral("task-1")); // 未绑定：本地 no-op
    QCOMPARE(started.count(), 0);
    QCOMPARE(probeSlot(m_backend), n + 1); // startBatch + cancelBatch 零上送
}

void TestBatchService::localRejectionsWhileBound() {
    BatchService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.batchModel());
    QSignalSpy errors(&service, &BatchService::batchError);

    const int n = probeSlot(m_backend);
    // 空文件列表（§9.4：文件与输出目录是批次的最小配置）。
    const QString noFiles =
        service.startBatch({}, QStringLiteral("/tmp/out"), QStringLiteral("PNG"), -1,
                           QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    QCOMPARE(noFiles, QString());
    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("批量文件列表为空"));

    // 空输出目录。
    const QString noDir =
        service.startBatch(threePaths(), QString(), QStringLiteral("PNG"), -1,
                           QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    QCOMPARE(noDir, QString());
    QCOMPARE(errors.count(), 2);
    QCOMPARE(errors.at(1).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(errors.at(1).at(1).toString(), QStringLiteral("输出目录为空"));

    // steps 允许为空（纯格式转换批次），不构成拒绝——提交号照常发出（响应
    // 全流程由 acceptanceBuildsPendingRows 锁定）。
    const QString submitted =
        service.startBatch(threePaths(), QStringLiteral("/tmp/out"), QStringLiteral("PNG"), -1,
                           QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    QCOMPARE(submitted, reqId(n + 1)); // 两次拒绝零上送，本次提交是第 1 个槽位
}

void TestBatchService::acceptanceBuildsPendingRows() {
    BatchService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.batchModel());
    QSignalSpy started(&service, &BatchService::batchStarted);
    QSignalSpy errors(&service, &BatchService::batchError);

    const int n = probeSlot(m_backend);
    const QString submitted =
        service.startBatch(threePaths(), QStringLiteral("/tmp/out"), QStringLiteral("JPEG"), 85,
                           QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    QCOMPARE(submitted, reqId(n + 1));             // 提交关联号 request_id
    QCOMPARE(service.batchModel()->rowCount(), 0); // 响应前不造行（不伪造进度）

    emit m_backend.responseReady(reqId(n + 1),
                                 acceptedResponse(reqId(n + 1), QStringLiteral("task-1")));

    QCOMPARE(started.count(), 1);
    QCOMPARE(started.at(0).at(0).toString(), QStringLiteral("task-1")); // task_id 唯一交付路径
    QCOMPARE(errors.count(), 0);
    QCOMPARE(service.batchModel()->rowCount(), 3);
    QCOMPARE(service.batchModel()->totalCount(), 3);
    QCOMPARE(service.batchModel()->doneCount(), 0);
    QCOMPARE(service.batchModel()->failedCount(), 0);
    // 行序 = 提交顺序，全部 pending 起点。
    const QStringList files = threePaths();
    for (int row = 0; row < 3; ++row) {
        const auto index = service.batchModel()->index(row, 0);
        QCOMPARE(index.data(BatchModel::BatchFileRole).toString(), files.at(row));
        QCOMPARE(index.data(BatchModel::BatchStateRole).toString(), QStringLiteral("pending"));
        QCOMPARE(index.data(BatchModel::BatchProgressRole).toInt(), 0);
    }
}

void TestBatchService::syncRejectionKeepsModelUntouched() {
    BatchService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.batchModel());
    QSignalSpy started(&service, &BatchService::batchStarted);
    QSignalSpy errors(&service, &BatchService::batchError);

    // 上一批次的行留在模型里（真实场景：上一批完成后再次提交被拒）。
    const int n = probeSlot(m_backend);
    service.startBatch(threePaths(), QStringLiteral("/tmp/out"), QStringLiteral("PNG"), -1,
                       QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    emit m_backend.responseReady(reqId(n + 1),
                                 acceptedResponse(reqId(n + 1), QStringLiteral("task-0")));
    QCOMPARE(service.batchModel()->rowCount(), 3);

    // 新批次被同步拒绝（当前 Worker 无 batch.start → UNKNOWN_ACTION，§5）。
    const QString submitted = service.startBatch(
        {QStringLiteral("/tmp/src/other.png")}, QStringLiteral("/tmp/out"), QStringLiteral("PNG"),
        -1, QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    QCOMPARE(submitted, reqId(n + 2));
    emit m_backend.responseReady(reqId(n + 2),
                                 failedResponse(reqId(n + 2), QStringLiteral("UNKNOWN_ACTION"),
                                                QStringLiteral("未知动作: batch.start")));

    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("UNKNOWN_ACTION"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("未知动作: batch.start"));
    QCOMPARE(started.count(), 1); // 只有 task-0 的受理
    // 模型保持 task-0 的现状——不受理不造行、也不清旧行。
    QCOMPARE(service.batchModel()->rowCount(), 3);
    QCOMPARE(service.batchModel()->index(0, 0).data(BatchModel::BatchFileRole).toString(),
             QStringLiteral("/tmp/src/a.png"));
}

void TestBatchService::missingTaskIdIsProtocolViolation() {
    BatchService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.batchModel());
    QSignalSpy started(&service, &BatchService::batchStarted);
    QSignalSpy errors(&service, &BatchService::batchError);

    const int n = probeSlot(m_backend);
    service.startBatch(threePaths(), QStringLiteral("/tmp/out"), QStringLiteral("PNG"), -1,
                       QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    // 成功响应缺 task_id：batch.start 是异步动作（§2.3），缺失即协议违约，
    // 不伪造受理（该提交永远不会有事件跟进）。
    emit m_backend.responseReady(
        reqId(n + 1),
        successResponse(reqId(n + 1), QJsonObject{{QStringLiteral("accepted"), true}}));

    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INTERNAL"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("batch.start 响应缺少 task_id"));
    QCOMPARE(started.count(), 0);
    QCOMPARE(service.batchModel()->rowCount(), 0);
}

void TestBatchService::perFileProgressUpdatesRows() {
    BatchService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.batchModel());
    QSignalSpy errors(&service, &BatchService::batchError);

    const int n = probeSlot(m_backend);
    service.startBatch(threePaths(), QStringLiteral("/tmp/out"), QStringLiteral("PNG"), -1,
                       QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    emit m_backend.responseReady(reqId(n + 1),
                                 acceptedResponse(reqId(n + 1), QStringLiteral("task-1")));

    // 逐文件进度：file 行键 + state/progress 原样映射进行（§9.4 单项进度）。
    emit m_backend.taskEvent(progressEvent(
        QStringLiteral("task-1"), QStringLiteral("/tmp/src/a.png"), QStringLiteral("running"), 30));
    emit m_backend.taskEvent(progressEvent(
        QStringLiteral("task-1"), QStringLiteral("/tmp/src/a.png"), QStringLiteral("done"), 100));
    emit m_backend.taskEvent(progressEvent(
        QStringLiteral("task-1"), QStringLiteral("/tmp/src/b.png"), QStringLiteral("failed"), 20));

    const auto model = service.batchModel();
    QCOMPARE(model->index(0, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("done"));
    QCOMPARE(model->index(0, 0).data(BatchModel::BatchProgressRole).toInt(), 100);
    QCOMPARE(model->index(1, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("failed"));
    QCOMPARE(model->index(1, 0).data(BatchModel::BatchProgressRole).toInt(), 20);
    QCOMPARE(model->doneCount(), 1);
    QCOMPARE(model->failedCount(), 1);
    QCOMPARE(errors.count(), 0);

    // 无 file 的纯整体进度帧：忽略（整体进度由计数推导）。
    emit m_backend.taskEvent(overallProgressEvent(QStringLiteral("task-1"), 55));
    QCOMPARE(model->index(2, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("pending"));
    QCOMPARE(model->index(2, 0).data(BatchModel::BatchProgressRole).toInt(), 0);

    // 未知/过期批次的事件：忽略。
    emit m_backend.taskEvent(progressEvent(QStringLiteral("task-ghost"),
                                           QStringLiteral("/tmp/src/c.png"), QStringLiteral("done"),
                                           100));
    QCOMPARE(model->index(2, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("pending"));
}

void TestBatchService::completedItemsRefreshRows() {
    BatchService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.batchModel());
    QSignalSpy finished(&service, &BatchService::batchFinished);
    QSignalSpy errors(&service, &BatchService::batchError);

    const int n = probeSlot(m_backend);
    service.startBatch(threePaths(), QStringLiteral("/tmp/out"), QStringLiteral("PNG"), -1,
                       QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    emit m_backend.responseReady(reqId(n + 1),
                                 acceptedResponse(reqId(n + 1), QStringLiteral("task-1")));

    // 完成事件的 result.items 全量补登（逐文件事件遗漏的终态与输出路径一次
    // 补齐；形状对照 processors/batch_filter_chain.py BatchItemResult 的 2.0
    // 词汇映射 succeeded→done）。
    emit m_backend.taskEvent(
        completedEvent(QStringLiteral("task-1"),
                       QJsonArray{
                           item(QStringLiteral("/tmp/src/a.png"), QStringLiteral("done"), {},
                                QStringLiteral("/tmp/out/a.png")),
                           item(QStringLiteral("/tmp/src/b.png"), QStringLiteral("failed"),
                                QStringLiteral("解码失败")),
                           item(QStringLiteral("/tmp/src/c.png"), QStringLiteral("skipped")),
                       }));

    QCOMPARE(finished.count(), 1);
    QCOMPARE(finished.at(0).at(0).toString(), QStringLiteral("task-1"));
    QCOMPARE(errors.count(), 0);
    const auto model = service.batchModel();
    QCOMPARE(model->rowCount(), 3);
    QCOMPARE(model->index(0, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("done"));
    QCOMPARE(model->index(0, 0).data(BatchModel::BatchOutputPathRole).toString(),
             QStringLiteral("/tmp/out/a.png"));
    QCOMPARE(model->index(1, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("failed"));
    QCOMPARE(model->index(1, 0).data(BatchModel::BatchErrorRole).toString(),
             QStringLiteral("解码失败"));
    QCOMPARE(model->index(2, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("skipped"));
    QCOMPARE(model->doneCount(), 1);
    QCOMPARE(model->failedCount(), 1);
}

void TestBatchService::cancelledFailureSweepsToSkipped() {
    BatchService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.batchModel());
    QSignalSpy errors(&service, &BatchService::batchError);

    const int n = probeSlot(m_backend);
    service.startBatch(threePaths(), QStringLiteral("/tmp/out"), QStringLiteral("PNG"), -1,
                       QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    emit m_backend.responseReady(reqId(n + 1),
                                 acceptedResponse(reqId(n + 1), QStringLiteral("task-1")));
    emit m_backend.taskEvent(progressEvent(
        QStringLiteral("task-1"), QStringLiteral("/tmp/src/a.png"), QStringLiteral("done"), 100));
    emit m_backend.taskEvent(progressEvent(
        QStringLiteral("task-1"), QStringLiteral("/tmp/src/b.png"), QStringLiteral("running"), 40));

    // §7：取消以 task.failed + CANCELLED 呈现；残余 pending/running 行收尾为
    // skipped（batch_filter_chain.py 取清扫掠的 2.0 词汇映射）。
    emit m_backend.taskEvent(failedEvent(QStringLiteral("task-1"), QStringLiteral("CANCELLED"),
                                         QStringLiteral("任务已取消")));

    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("CANCELLED"));
    const auto model = service.batchModel();
    QCOMPARE(model->index(0, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("done")); // 已终态行不动
    QCOMPARE(model->index(1, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("skipped")); // 运行中被中断
    QCOMPARE(model->index(1, 0).data(BatchModel::BatchProgressRole).toInt(), 40);
    QCOMPARE(model->index(2, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("skipped")); // 残余 pending
    QCOMPARE(model->doneCount(), 1);
    QCOMPARE(model->failedCount(), 0); // skipped 不计入 failed
}

void TestBatchService::nonCancelledFailureKeepsRows() {
    BatchService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.batchModel());
    QSignalSpy errors(&service, &BatchService::batchError);

    const int n = probeSlot(m_backend);
    service.startBatch(threePaths(), QStringLiteral("/tmp/out"), QStringLiteral("PNG"), -1,
                       QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    emit m_backend.responseReady(reqId(n + 1),
                                 acceptedResponse(reqId(n + 1), QStringLiteral("task-1")));
    emit m_backend.taskEvent(progressEvent(
        QStringLiteral("task-1"), QStringLiteral("/tmp/src/a.png"), QStringLiteral("running"), 25));

    // 非 CANCELLED 失败（如 Worker 崩溃恢复的 INTERNAL）：行保持最后已知状态。
    emit m_backend.taskEvent(failedEvent(QStringLiteral("task-1"), QStringLiteral("ENGINE_ERROR"),
                                         QStringLiteral("处理器执行异常")));

    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("ENGINE_ERROR"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("处理器执行异常"));
    const auto model = service.batchModel();
    QCOMPARE(model->index(0, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("running"));
    QCOMPARE(model->index(0, 0).data(BatchModel::BatchProgressRole).toInt(), 25);
    QCOMPARE(model->index(1, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("pending"));
    QCOMPARE(model->index(2, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("pending"));
}

void TestBatchService::singleActiveBatchSemantics() {
    BatchService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.batchModel());
    QSignalSpy started(&service, &BatchService::batchStarted);

    const int n = probeSlot(m_backend);
    service.startBatch(threePaths(), QStringLiteral("/tmp/out"), QStringLiteral("PNG"), -1,
                       QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    emit m_backend.responseReady(reqId(n + 1),
                                 acceptedResponse(reqId(n + 1), QStringLiteral("task-1")));
    QCOMPARE(service.batchModel()->rowCount(), 3);

    // 第二个批次受理：单活动批次语义——覆盖旧跟踪，模型整表重建为新清单。
    const QStringList next{QStringLiteral("/tmp/src/next.png")};
    service.startBatch(next, QStringLiteral("/tmp/out2"), QStringLiteral("PNG"), -1,
                       QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    emit m_backend.responseReady(reqId(n + 2),
                                 acceptedResponse(reqId(n + 2), QStringLiteral("task-2")));
    QCOMPARE(started.count(), 2);
    QCOMPARE(service.batchModel()->rowCount(), 1);
    QCOMPARE(service.batchModel()->index(0, 0).data(BatchModel::BatchFileRole).toString(),
             QStringLiteral("/tmp/src/next.png"));

    // 旧批次 task-1 的迟到事件：按 task_id 不匹配忽略，不触碰新批次行。
    emit m_backend.taskEvent(progressEvent(QStringLiteral("task-1"),
                                           QStringLiteral("/tmp/src/next.png"),
                                           QStringLiteral("failed"), 5));
    QCOMPARE(service.batchModel()->index(0, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("pending"));

    // 新批次的事件照常关联。
    emit m_backend.taskEvent(progressEvent(QStringLiteral("task-2"),
                                           QStringLiteral("/tmp/src/next.png"),
                                           QStringLiteral("running"), 10));
    QCOMPARE(service.batchModel()->index(0, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("running"));
}

void TestBatchService::cancelBatchForwarding() {
    BatchService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.batchModel());

    const int n = probeSlot(m_backend);
    service.startBatch(threePaths(), QStringLiteral("/tmp/out"), QStringLiteral("PNG"), -1,
                       QStringLiteral("pattern"), QStringLiteral("{name}_{i}"), QJsonArray{});
    emit m_backend.responseReady(reqId(n + 1),
                                 acceptedResponse(reqId(n + 1), QStringLiteral("task-1")));

    // 转发路径（BackendManager::cancelTask 与 sendAction 共用计数器，
    // backend_manager.cpp:103-108）：每次调用恰好消费一个槽位；空 id 零槽位。
    service.cancelBatch(QStringLiteral("task-1"));
    service.cancelBatch(reqId(n + 1)); // 提交号：受理后翻译成 task_id 再转发
    service.cancelBatch(QString());
    service.cancelBatch(QStringLiteral("task-unknown")); // 未知 id 原样转发
    QCOMPARE(probeSlot(m_backend), n + 5); // 提交(1) + 三次取消(2,3,4) + 探针(5)

    // 转发内容（task.cancel {task_id}）在停止态 Worker 上不可观测
    // （python_worker.cpp:104-107）——翻译正确性由代码审查与 Worker 侧测试锁定。
}

QTEST_MAIN(TestBatchService)
#include "test_batch_service.moc"
