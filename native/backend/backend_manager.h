#pragma once

#include <QObject>
#include <QStringList>
#include <QTimer>
#include <QJsonObject>

#include "python_worker.h"

namespace toolbox {

// Worker lifecycle owner: handshake, crash recovery, request correlation.
// Exposes a minimal QML-friendly surface; real QML wiring lands in Phase 4
// (master plan Phase 3 acceptance runs through C++ tests + Linux env, not QML).
class BackendManager : public QObject
{
    Q_OBJECT

    Q_PROPERTY(QString state READ state NOTIFY stateChanged)
    Q_PROPERTY(bool running READ isRunning NOTIFY stateChanged)

public:
    enum class State { Idle, Starting, Handshaking, Ready, Crashed, Stopped };
    Q_ENUM(State)

    static constexpr int kMaxRestarts = 3;       // crash-loop guard (§6.5)
    static constexpr int kHandshakeTimeoutMs = 5000;

    explicit BackendManager(QObject *parent = nullptr);
    ~BackendManager() override;

    void configure(const QString &pythonExecutable, const QString &repoRoot,
                   const QString &tempDir = {}, int maxWorkers = 2);

    Q_INVOKABLE void start();
    Q_INVOKABLE void shutdown();

    // Returns the generated request_id; response arrives via responseReady.
    Q_INVOKABLE QString sendAction(const QString &action, const QJsonObject &params = {});
    Q_INVOKABLE void cancelTask(const QString &taskId);

    QString state() const;
    bool isRunning() const { return m_state == State::Ready || m_state == State::Handshaking; }
    QJsonObject capabilities() const { return m_capabilities; }

signals:
    void stateChanged(const QString &state);
    void ready(const QJsonObject &capabilities);
    void responseReady(const QString &requestId, const QJsonObject &payload);
    void taskEvent(const QJsonObject &event);
    void errorOccurred(const QString &code, const QString &message);

private slots:
    void onWorkerResponse(const QString &requestId, const QJsonObject &message);
    void onWorkerEvent(const QJsonObject &message);
    void onWorkerExited(int exitCode, QProcess::ExitStatus status);
    void onHandshakeTimeout();

private:
    void setState(State state);
    void beginHandshake();
    void scheduleRestart();

    PythonWorker m_worker;
    QTimer m_handshakeTimer;
    State m_state = State::Idle;
    int m_restartCount = 0;
    int m_requestCounter = 0;
    QString m_python;
    QString m_repoRoot;
    QString m_tempDir;
    int m_maxWorkers = 2;
    QJsonObject m_capabilities;
};

} // namespace toolbox
