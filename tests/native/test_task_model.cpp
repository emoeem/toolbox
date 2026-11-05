// Phase 4 model tests: TaskModel as the Worker-driven task queue frontend.
//
// Simulation strategy (no Python Worker in native tests): the tests emit
// BackendManager's responseReady/taskEvent signals directly. That is exactly
// the hand-off BackendManager::onWorkerResponse/onWorkerEvent perform for real
// Worker frames (backend_manager.cpp:129-166), so the model observes the same
// signal shapes as in production. The manager itself is never started; its
// cancelTask() then only encodes a task.cancel request into a stopped worker,
// which PythonWorker::sendLine drops (python_worker.cpp:104-109). The single
// externally visible trace of BackendManager::cancelTask in that state is the
// request_id counter slot it consumes (shared with sendAction,
// backend_manager.cpp:108/113-118) — the cancel tests use a sendAction probe
// before/after to prove the forward really happened.
//
// Role-name assertions lock the QML contract consumed by AppTaskItem.qml
// (required properties taskTaskId/taskName/taskStatus/taskProgress/taskError).
// Message shapes mirror docs/ipc-protocol.md §2.2/§2.3/§7.
#include <QtTest/QAbstractItemModelTester>
#include <QtTest/QtTest>

#include <QJsonObject>
#include <QSignalSpy>

#include "backend/backend_manager.h"
#include "backend/ipc_protocol.h"
#include "models/task_model.h"

using toolbox::BackendManager;
using toolbox::TaskModel;

namespace {

QJsonObject successResponse(const QString &requestId, const QString &taskId)
{
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("request_id"), requestId},
        {QStringLiteral("success"), true},
        {QStringLiteral("result"), QJsonObject{
             {QStringLiteral("task_id"), taskId},
             {QStringLiteral("status"), QStringLiteral("queued")},
         }},
    };
}

QJsonObject syncResponse(const QString &requestId)
{
    // A tracked-but-synchronous action: success without a task_id.
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("request_id"), requestId},
        {QStringLiteral("success"), true},
        {QStringLiteral("result"), QJsonObject{
             {QStringLiteral("filter_count"), 153},
         }},
    };
}

QJsonObject failedResponse(const QString &requestId, const QString &code)
{
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("request_id"), requestId},
        {QStringLiteral("success"), false},
        {QStringLiteral("error"), QJsonObject{
             {QStringLiteral("code"), code},
             {QStringLiteral("message"), QStringLiteral("处理失败")},
             {QStringLiteral("details"), QJsonObject{}},
         }},
    };
}

QJsonObject progressEvent(const QString &taskId, int progress)
{
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.progress")},
        {QStringLiteral("task_id"), taskId},
        {QStringLiteral("progress"), progress},
    };
}

QJsonObject completedEvent(const QString &taskId)
{
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.completed")},
        {QStringLiteral("task_id"), taskId},
        {QStringLiteral("result"), QJsonObject{
             {QStringLiteral("path"), QStringLiteral("/tmp/toolbox-worker-1/prev.png")},
         }},
    };
}

QJsonObject failedEvent(const QString &taskId, const QString &code, const QString &message)
{
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.failed")},
        {QStringLiteral("task_id"), taskId},
        {QStringLiteral("error"), QJsonObject{
             {QStringLiteral("code"), code},
             {QStringLiteral("message"), message},
             {QStringLiteral("details"), QJsonObject{}},
         }},
    };
}

// Owns manager + model in destruction-safe order (the model is destroyed
// first, so it never observes a half-dead backend).
struct Harness
{
    BackendManager backend;
    TaskModel model;

    Harness() { model.setBackend(&backend); }

    // Simulates an async action: the UI registers the request and the manager
    // forwards its success response carrying a task_id (docs/ipc-protocol.md §2.3).
    void spawn(const QString &requestId, const QString &taskId, const QString &name)
    {
        model.trackRequest(requestId, name);
        emit backend.responseReady(requestId, successResponse(requestId, taskId));
    }
};

} // namespace

class TestTaskModel : public QObject
{
    Q_OBJECT

private slots:
    void roleNamesMatchImplementation();
    void trackedResponseCreatesRow();
    void untrackedFailedAndSyncResponsesCreateNoRow();
    void progressEventsUpdateRow();
    void completedEventIsTerminal();
    void failedEventCarriesError();
    void cancelledCodeMapsToCancelled();
    void cancelTaskFlipsActiveRowAndForwards();
    void cancelTaskRejectsTerminalRows();
    void terminalRowsCappedAtSixtyFour();
    void activeRowsSurviveTrimming();

private:
    static int rowOfTaskId(const QAbstractItemModel &model, const QString &taskId);
};

int TestTaskModel::rowOfTaskId(const QAbstractItemModel &model, const QString &taskId)
{
    for (int row = 0; row < model.rowCount(); ++row) {
        if (model.index(row, 0).data(TaskModel::TaskIdRole).toString() == taskId)
            return row;
    }
    return -1;
}

void TestTaskModel::roleNamesMatchImplementation()
{
    Harness h;
    QAbstractItemModelTester tester(&h.model);

    const auto roles = h.model.roleNames();
    QCOMPARE(roles.size(), 5);
    // QML consumes these names via required properties (AppTaskItem.qml).
    QCOMPARE(roles.value(TaskModel::TaskIdRole), QByteArray("taskTaskId"));
    QCOMPARE(roles.value(TaskModel::NameRole), QByteArray("taskName"));
    QCOMPARE(roles.value(TaskModel::StatusRole), QByteArray("taskStatus"));
    QCOMPARE(roles.value(TaskModel::ProgressRole), QByteArray("taskProgress"));
    QCOMPARE(roles.value(TaskModel::ErrorRole), QByteArray("taskError"));
}

void TestTaskModel::trackedResponseCreatesRow()
{
    Harness h;
    QAbstractItemModelTester tester(&h.model);
    QSignalSpy rowsInserted(&h.model, &QAbstractItemModel::rowsInserted);

    h.spawn(QStringLiteral("req-1"), QStringLiteral("task-1"), QStringLiteral("滤镜预览"));

    QCOMPARE(rowsInserted.count(), 1);
    QCOMPARE(h.model.rowCount(), 1);

    const auto index = h.model.index(0, 0);
    QCOMPARE(index.data(TaskModel::TaskIdRole).toString(), QStringLiteral("task-1"));
    QCOMPARE(index.data(TaskModel::NameRole).toString(), QStringLiteral("滤镜预览"));
    QCOMPARE(index.data(TaskModel::StatusRole).toString(), QStringLiteral("queued"));
    QCOMPARE(index.data(TaskModel::ProgressRole).toInt(), 0);
    QVERIFY(index.data(TaskModel::ErrorRole).toString().isEmpty());

    // Flat table contract: no children, no out-of-range rows, invalid queries
    // answer invalid instead of crashing.
    QCOMPARE(h.model.rowCount(index), 0);
    QVERIFY(!h.model.index(1, 0).isValid());
    QVERIFY(!h.model.index(0, 0, index).isValid());
    QVERIFY(!h.model.data(QModelIndex(), TaskModel::StatusRole).isValid());
}

void TestTaskModel::untrackedFailedAndSyncResponsesCreateNoRow()
{
    Harness h;
    QAbstractItemModelTester tester(&h.model);

    // Untracked request (worker.hello / task.cancel / sync actions): no row.
    emit h.backend.responseReady(QStringLiteral("req-a"),
                                 successResponse(QStringLiteral("req-a"),
                                                 QStringLiteral("task-ghost")));
    QCOMPARE(h.model.rowCount(), 0);

    // Failure response for a tracked request: it will never produce a task.
    h.model.trackRequest(QStringLiteral("req-b"), QStringLiteral("图像保存"));
    emit h.backend.responseReady(QStringLiteral("req-b"),
                                 failedResponse(QStringLiteral("req-b"),
                                                QStringLiteral("UNSUPPORTED_FORMAT")));
    QCOMPARE(h.model.rowCount(), 0);

    // Tracked success without task_id: sync action, nothing to track.
    h.model.trackRequest(QStringLiteral("req-c"), QStringLiteral("滤镜链"));
    emit h.backend.responseReady(QStringLiteral("req-c"), syncResponse(QStringLiteral("req-c")));
    QCOMPARE(h.model.rowCount(), 0);

    // Empty request ids are never tracked (task_model.cpp:33-38) and empty-id
    // responses are ignored.
    h.model.trackRequest(QString(), QStringLiteral("无名"));
    emit h.backend.responseReady(QString(), successResponse(QString(), QStringLiteral("task-e")));
    QCOMPARE(h.model.rowCount(), 0);

    // Events for unknown tasks / without a task_id are ignored.
    emit h.backend.taskEvent(completedEvent(QStringLiteral("task-ghost")));
    emit h.backend.taskEvent(QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.completed")},
    });
    QCOMPARE(h.model.rowCount(), 0);
}

void TestTaskModel::progressEventsUpdateRow()
{
    Harness h;
    QAbstractItemModelTester tester(&h.model);
    QSignalSpy changed(&h.model, &QAbstractItemModel::dataChanged);
    h.spawn(QStringLiteral("req-1"), QStringLiteral("task-1"), QStringLiteral("滤镜预览"));
    changed.clear();

    emit h.backend.taskEvent(progressEvent(QStringLiteral("task-1"), 40));
    QCOMPARE(h.model.index(0, 0).data(TaskModel::StatusRole).toString(), QStringLiteral("running"));
    QCOMPARE(h.model.index(0, 0).data(TaskModel::ProgressRole).toInt(), 40);

    // Percentages are clamped into 0-100 (qBound in TaskModel::onTaskEvent).
    emit h.backend.taskEvent(progressEvent(QStringLiteral("task-1"), 150));
    QCOMPARE(h.model.index(0, 0).data(TaskModel::ProgressRole).toInt(), 100);
    emit h.backend.taskEvent(progressEvent(QStringLiteral("task-1"), -7));
    QCOMPARE(h.model.index(0, 0).data(TaskModel::ProgressRole).toInt(), 0);

    // A progress frame without a numeric field keeps the previous value
    // (QJsonValue::toInt default = current row progress).
    emit h.backend.taskEvent(QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.progress")},
        {QStringLiteral("task_id"), QStringLiteral("task-1")},
    });
    QCOMPARE(h.model.index(0, 0).data(TaskModel::ProgressRole).toInt(), 0);

    // Each update notifies the view with exactly the roles QML consumes.
    emit h.backend.taskEvent(progressEvent(QStringLiteral("task-1"), 55));
    QCOMPARE(changed.count(), 4);
    QCOMPARE(changed.last().at(2).value<QList<int>>(),
             (QList<int>{TaskModel::StatusRole, TaskModel::ProgressRole, TaskModel::ErrorRole}));
    QCOMPARE(h.model.index(0, 0).data(TaskModel::ProgressRole).toInt(), 55);
}

void TestTaskModel::completedEventIsTerminal()
{
    Harness h;
    QAbstractItemModelTester tester(&h.model);
    h.spawn(QStringLiteral("req-1"), QStringLiteral("task-1"), QStringLiteral("滤镜预览"));
    emit h.backend.taskEvent(progressEvent(QStringLiteral("task-1"), 88));

    emit h.backend.taskEvent(completedEvent(QStringLiteral("task-1")));

    const auto index = h.model.index(0, 0);
    QCOMPARE(index.data(TaskModel::StatusRole).toString(), QStringLiteral("completed"));
    QCOMPARE(index.data(TaskModel::ProgressRole).toInt(), 100);
    QVERIFY(index.data(TaskModel::ErrorRole).toString().isEmpty());
}

void TestTaskModel::failedEventCarriesError()
{
    Harness h;
    QAbstractItemModelTester tester(&h.model);
    h.spawn(QStringLiteral("req-1"), QStringLiteral("task-1"), QStringLiteral("滤镜预览"));
    emit h.backend.taskEvent(progressEvent(QStringLiteral("task-1"), 30));

    emit h.backend.taskEvent(failedEvent(QStringLiteral("task-1"), QStringLiteral("ENGINE_ERROR"),
                                         QStringLiteral("处理器执行异常")));

    const auto index = h.model.index(0, 0);
    QCOMPARE(index.data(TaskModel::StatusRole).toString(), QStringLiteral("failed"));
    QCOMPARE(index.data(TaskModel::ProgressRole).toInt(), 30);  // progress retained
    QCOMPARE(index.data(TaskModel::ErrorRole).toString(), QStringLiteral("处理器执行异常"));
}

void TestTaskModel::cancelledCodeMapsToCancelled()
{
    Harness h;
    QAbstractItemModelTester tester(&h.model);
    h.spawn(QStringLiteral("req-1"), QStringLiteral("task-1"), QStringLiteral("滤镜预览"));
    emit h.backend.taskEvent(progressEvent(QStringLiteral("task-1"), 55));

    // docs/ipc-protocol.md §7: cancellation surfaces as task.failed + CANCELLED;
    // the model must present it as its own status, not as a failure.
    emit h.backend.taskEvent(failedEvent(QStringLiteral("task-1"), QStringLiteral("CANCELLED"),
                                         QStringLiteral("任务已取消")));

    const auto index = h.model.index(0, 0);
    QCOMPARE(index.data(TaskModel::StatusRole).toString(), QStringLiteral("cancelled"));
    QCOMPARE(index.data(TaskModel::ProgressRole).toInt(), 55);
    QCOMPARE(index.data(TaskModel::ErrorRole).toString(), QStringLiteral("任务已取消"));
}

void TestTaskModel::cancelTaskFlipsActiveRowAndForwards()
{
    Harness h;
    QAbstractItemModelTester tester(&h.model);
    QSignalSpy changed(&h.model, &QAbstractItemModel::dataChanged);
    h.spawn(QStringLiteral("req-1"), QStringLiteral("task-1"), QStringLiteral("滤镜预览"));
    changed.clear();

    // Forward trace: BackendManager::cancelTask and sendAction share the
    // request_id counter (backend_manager.cpp:108/113-118). A probe before and
    // after the cancel proves the forward consumed exactly one slot each time.
    QCOMPARE(h.backend.sendAction(QStringLiteral("probe.before")), QStringLiteral("req-1"));

    h.model.cancelTask(QStringLiteral("task-1"));
    QCOMPARE(h.model.index(0, 0).data(TaskModel::StatusRole).toString(),
             QStringLiteral("cancelling"));
    QCOMPARE(changed.count(), 1);
    QVERIFY(changed.last().at(2).value<QList<int>>().contains(TaskModel::StatusRole));

    // Cancelling again: no duplicate notification, but the forward still runs.
    h.model.cancelTask(QStringLiteral("task-1"));
    QCOMPARE(changed.count(), 1);

    // Unknown task id: nothing in the model, forward still issued.
    h.model.cancelTask(QStringLiteral("task-unknown"));
    QCOMPARE(changed.count(), 1);
    // Counter walk: probe.before(1) + cancel task-1(2) + cancel task-1(3)
    // + cancel task-unknown(4) → probe.after consumes slot 5.
    QCOMPARE(h.backend.sendAction(QStringLiteral("probe.after")), QStringLiteral("req-5"));

    // Without a wired backend (Application always wires one; this is the
    // defensive path) cancelling is a local no-op on an empty model.
    TaskModel standalone;
    standalone.cancelTask(QStringLiteral("anything"));
    QCOMPARE(standalone.rowCount(), 0);
}

void TestTaskModel::cancelTaskRejectsTerminalRows()
{
    Harness h;
    QAbstractItemModelTester tester(&h.model);
    QSignalSpy changed(&h.model, &QAbstractItemModel::dataChanged);
    h.spawn(QStringLiteral("req-1"), QStringLiteral("task-1"), QStringLiteral("滤镜预览"));
    h.spawn(QStringLiteral("req-2"), QStringLiteral("task-2"), QStringLiteral("图像保存"));
    emit h.backend.taskEvent(completedEvent(QStringLiteral("task-1")));
    emit h.backend.taskEvent(failedEvent(QStringLiteral("task-2"), QStringLiteral("ENGINE_ERROR"),
                                         QStringLiteral("处理器执行异常")));
    changed.clear();

    // docs/ipc-protocol.md §7: 已完成任务不可取消. Terminal rows are rejected
    // locally *before* the backend is consulted (task_model.cpp:43-46) — the
    // counter probe proves no forward happened.
    h.model.cancelTask(QStringLiteral("task-1"));
    h.model.cancelTask(QStringLiteral("task-2"));
    QCOMPARE(changed.count(), 0);
    QCOMPARE(h.model.index(0, 0).data(TaskModel::StatusRole).toString(),
             QStringLiteral("completed"));
    QCOMPARE(h.model.index(1, 0).data(TaskModel::StatusRole).toString(), QStringLiteral("failed"));
    QCOMPARE(h.backend.sendAction(QStringLiteral("probe")), QStringLiteral("req-1"));
}

void TestTaskModel::terminalRowsCappedAtSixtyFour()
{
    QCOMPARE(TaskModel::kMaxTerminalRows, 64);

    Harness h;
    QAbstractItemModelTester tester(&h.model);
    for (int i = 1; i <= 70; ++i) {
        const QString id = QStringLiteral("task-%1").arg(i);
        h.spawn(QStringLiteral("req-%1").arg(i), id, QStringLiteral("任务%1").arg(i));
        emit h.backend.taskEvent(completedEvent(id));
    }

    QCOMPARE(h.model.rowCount(), TaskModel::kMaxTerminalRows);
    // The oldest terminal rows were trimmed (FIFO), the newest survive.
    QCOMPARE(h.model.index(0, 0).data(TaskModel::TaskIdRole).toString(),
             QStringLiteral("task-7"));
    QCOMPARE(h.model.index(h.model.rowCount() - 1, 0).data(TaskModel::TaskIdRole).toString(),
             QStringLiteral("task-70"));
}

void TestTaskModel::activeRowsSurviveTrimming()
{
    Harness h;
    QAbstractItemModelTester tester(&h.model);
    for (int i = 1; i <= 64; ++i) {
        const QString id = QStringLiteral("task-%1").arg(i);
        h.spawn(QStringLiteral("req-%1").arg(i), id, QStringLiteral("任务%1").arg(i));
        emit h.backend.taskEvent(completedEvent(id));
    }
    QCOMPARE(h.model.rowCount(), TaskModel::kMaxTerminalRows);

    // One active row: trimming only evicts the oldest *terminal* rows, never
    // a queued/running/cancelling one (task_model.cpp:129-151).
    h.spawn(QStringLiteral("req-65"), QStringLiteral("task-65"), QStringLiteral("长任务"));
    QCOMPARE(h.model.rowCount(), TaskModel::kMaxTerminalRows + 1);

    for (int i = 66; i <= 69; ++i) {
        const QString id = QStringLiteral("task-%1").arg(i);
        h.spawn(QStringLiteral("req-%1").arg(i), id, QStringLiteral("任务%1").arg(i));
        emit h.backend.taskEvent(completedEvent(id));
    }

    QCOMPARE(h.model.rowCount(), TaskModel::kMaxTerminalRows + 1);
    QVERIFY(rowOfTaskId(h.model, QStringLiteral("task-65")) >= 0);
    QCOMPARE(h.model.index(rowOfTaskId(h.model, QStringLiteral("task-65")), 0)
                 .data(TaskModel::StatusRole).toString(), QStringLiteral("queued"));
    QVERIFY(rowOfTaskId(h.model, QStringLiteral("task-1")) < 0);
    QVERIFY(rowOfTaskId(h.model, QStringLiteral("task-4")) < 0);
    QVERIFY(rowOfTaskId(h.model, QStringLiteral("task-5")) >= 0);
}

QTEST_MAIN(TestTaskModel)
#include "test_task_model.moc"
