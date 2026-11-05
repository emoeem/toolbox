#include "task_model.h"

// 连接 BackendManager 的信号需要完整类型（task_model.h 只有前置声明）。
#include "backend/backend_manager.h"
#include "backend/ipc_protocol.h"

namespace toolbox {

namespace {

bool isTerminalStatus(const QString &status) {
    return status == QStringLiteral("completed") || status == QStringLiteral("failed") ||
           status == QStringLiteral("cancelled");
}

} // namespace

TaskModel::TaskModel(QObject *parent) : QAbstractListModel(parent) {}

void TaskModel::setBackend(BackendManager *backend) {
    if (m_backend == backend)
        return;
    m_backend = backend;
    if (!m_backend)
        return;
    connect(m_backend, &BackendManager::responseReady, this, &TaskModel::onResponseReady);
    connect(m_backend, &BackendManager::taskEvent, this, &TaskModel::onTaskEvent);
}

void TaskModel::trackRequest(const QString &requestId, const QString &name) {
    if (requestId.isEmpty())
        return;
    m_pendingNames.insert(requestId, name);
}

void TaskModel::cancelTask(const QString &taskId) {
    const int row = indexOfTaskId(taskId);
    if (row >= 0) {
        const QString &status = m_entries.at(row).status;
        if (isTerminalStatus(status))
            return;
        if (status != QStringLiteral("cancelling")) {
            m_entries[row].status = QStringLiteral("cancelling");
            emit dataChanged(index(row), index(row), {StatusRole});
        }
    }
    if (m_backend)
        m_backend->cancelTask(taskId);
}

int TaskModel::indexOfTaskId(const QString &taskId) const {
    for (int i = 0; i < m_entries.size(); ++i) {
        if (m_entries.at(i).taskId == taskId)
            return i;
    }
    return -1;
}

void TaskModel::onResponseReady(const QString &requestId, const QJsonObject &message) {
    const auto pending = m_pendingNames.constFind(requestId);
    if (pending == m_pendingNames.cend())
        return; // untracked request (worker.hello, task.cancel, sync actions)

    const QString name = pending.value();
    m_pendingNames.erase(pending);
    if (!ipc::IpcProtocol::isSuccess(message))
        return; // tracked request failed — it will never produce a task

    const QString taskId =
        ipc::IpcProtocol::resultOf(message).value(QStringLiteral("task_id")).toString();
    if (taskId.isEmpty())
        return; // sync action answered — nothing to track

    beginInsertRows(QModelIndex(), m_entries.size(), m_entries.size());
    m_entries.append({taskId, name, QStringLiteral("queued"), 0, {}});
    endInsertRows();
}

void TaskModel::onTaskEvent(const QJsonObject &event) {
    const QString type = event.value(QStringLiteral("type")).toString();
    const QString taskId = ipc::IpcProtocol::eventTaskId(event);
    if (taskId.isEmpty())
        return;
    const int row = indexOfTaskId(taskId);
    if (row < 0)
        return; // task unknown to this model (e.g. created before it existed)

    if (type == QStringLiteral("task.progress")) {
        const int progress = qBound(
            0, event.value(QStringLiteral("progress")).toInt(m_entries.at(row).progress), 100);
        // The Worker keeps emitting task.progress until its thread reaches a
        // cancel checkpoint (python_worker/task_runtime.py progress_cb does not
        // check the cancel token), so a row already in cancelling must stay
        // there: progress events may refresh the percentage but never walk the
        // state machine backwards (docs/ipc-protocol.md §7 and the lifecycle
        // comment in task_model.h).
        const bool cancelling = m_entries.at(row).status == QStringLiteral("cancelling");
        updateRow(row, cancelling ? QStringLiteral("cancelling") : QStringLiteral("running"),
                  progress, {});
        return;
    }
    if (type == QStringLiteral("task.completed")) {
        updateRow(row, QStringLiteral("completed"), 100, {});
        trimTerminalRows();
        return;
    }
    if (type == QStringLiteral("task.failed")) {
        const QJsonObject error = event.value(QStringLiteral("error")).toObject();
        // docs/ipc-protocol.md §7: cancellation surfaces as task.failed + CANCELLED.
        const bool cancelled =
            error.value(QStringLiteral("code")).toString() == QStringLiteral("CANCELLED");
        updateRow(row, cancelled ? QStringLiteral("cancelled") : QStringLiteral("failed"),
                  m_entries.at(row).progress, error.value(QStringLiteral("message")).toString());
        trimTerminalRows();
        return;
    }
}

void TaskModel::updateRow(int row, const QString &status, int progress, const QString &error) {
    Entry &entry = m_entries[row];
    // 值未变化时不发射：无数字字段的 task.progress 落到"保持原值"路径，对
    // QML 视图而言这次刷新是空操作（test_task_model 把该行为固化为契约）。
    if (entry.status == status && entry.progress == progress && entry.error == error)
        return;
    entry.status = status;
    entry.progress = progress;
    entry.error = error;
    emit dataChanged(index(row), index(row), {StatusRole, ProgressRole, ErrorRole});
}

void TaskModel::trimTerminalRows() {
    int terminal = 0;
    for (const auto &entry : m_entries) {
        if (isTerminalStatus(entry.status))
            ++terminal;
    }
    while (terminal > kMaxTerminalRows) {
        int oldest = -1;
        for (int i = 0; i < m_entries.size(); ++i) {
            if (isTerminalStatus(m_entries.at(i).status)) {
                oldest = i;
                break;
            }
        }
        if (oldest < 0)
            return;
        beginRemoveRows(QModelIndex(), oldest, oldest);
        m_entries.removeAt(oldest);
        endRemoveRows();
        --terminal;
    }
}

int TaskModel::rowCount(const QModelIndex &parent) const {
    return parent.isValid() ? 0 : m_entries.size();
}

QVariant TaskModel::data(const QModelIndex &index, int role) const {
    if (!index.isValid() || index.row() >= m_entries.size())
        return {};
    const auto &entry = m_entries.at(index.row());
    switch (role) {
    case TaskIdRole:
        return entry.taskId;
    case NameRole:
        return entry.name;
    case StatusRole:
        return entry.status;
    case ProgressRole:
        return entry.progress;
    case ErrorRole:
        return entry.error;
    default:
        return {};
    }
}

QHash<int, QByteArray> TaskModel::roleNames() const {
    return {
        {TaskIdRole, "taskTaskId"},     {NameRole, "taskName"},   {StatusRole, "taskStatus"},
        {ProgressRole, "taskProgress"}, {ErrorRole, "taskError"},
    };
}

} // namespace toolbox
