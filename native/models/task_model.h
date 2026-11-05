#pragma once

#include <QAbstractListModel>
#include <QHash>
#include <QJsonObject>
#include <QVector>
#include <QtQml/qqml.h>

namespace toolbox {

class BackendManager;

// Task rows mirror the async-task lifecycle of the Python Worker
// (docs/ipc-protocol.md §2.3/§7): queued → running → completed | failed, and
// queued|running → cancelling → cancelled. A row is created when a request
// registered via trackRequest() answers success with result.task_id; a failure
// response for a tracked request never produces a row. task.progress /
// task.completed / task.failed events update the matching row; terminal rows
// are trimmed to the most recent kMaxTerminalRows entries.
class TaskModel : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT

  public:
    static constexpr int kMaxTerminalRows = 64;

    struct Entry {
        QString taskId;
        QString name;
        QString status;   // queued|running|completed|failed|cancelled|cancelling
        int progress = 0; // percent, 0-100
        QString error;
    };

    enum Roles { TaskIdRole = Qt::UserRole + 1, NameRole, StatusRole, ProgressRole, ErrorRole };

    explicit TaskModel(QObject *parent = nullptr);

    // Wires the Worker-driven signals of the manager Application owns.
    void setBackend(BackendManager *backend);

    // Remembers requestId → name so the async response can name its row.
    Q_INVOKABLE void trackRequest(const QString &requestId, const QString &name);

    // Forwards to BackendManager::cancelTask after flipping an active row
    // (queued/running) to cancelling; terminal rows are rejected locally
    // (docs/ipc-protocol.md §7: 已完成任务不可取消).
    Q_INVOKABLE void cancelTask(const QString &taskId);

    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

  private slots:
    void onResponseReady(const QString &requestId, const QJsonObject &message);
    void onTaskEvent(const QJsonObject &event);

  private:
    int indexOfTaskId(const QString &taskId) const;
    void updateRow(int row, const QString &status, int progress, const QString &error);
    void trimTerminalRows();

    QVector<Entry> m_entries;
    QHash<QString, QString> m_pendingNames; // request_id → task name
    BackendManager *m_backend = nullptr;
};

} // namespace toolbox
