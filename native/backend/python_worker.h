#pragma once

#include <QByteArray>
#include <QObject>
#include <QProcess>
#include <QStringList>
#include <QJsonObject>

namespace toolbox {

// One Python worker process: JSON Lines over stdin/stdout (docs/ipc-protocol.md §1).
// Lifecycle/ownership/restart policy lives in BackendManager; this class only
// owns the QProcess and the byte-stream framing.
class PythonWorker : public QObject
{
    Q_OBJECT

public:
    explicit PythonWorker(QObject *parent = nullptr);
    ~PythonWorker() override;

    void configure(const QString &pythonExecutable, const QString &mainPyPath,
                   const QString &repoRoot, const QString &tempDir, int maxWorkers);
    bool start();
    // Graceful stop: close stdin, wait up to 2s, then terminate/kill.
    void stop();
    bool isRunning() const;

    void sendRequest(const QString &requestId, const QString &action,
                     const QJsonObject &params = {});
    // Convenience for tests and BackendManager: raw JSON line.
    void sendLine(const QByteArray &line);

    QString lastStderrTail() const { return m_stderrTail; }

signals:
    void responseReceived(const QString &requestId, const QJsonObject &message);
    void eventReceived(const QJsonObject &message);
    void protocolError(const QString &reason);
    void processStarted();
    void processExited(int exitCode, QProcess::ExitStatus status);
    void processError(QProcess::ProcessError error);

private slots:
    void onReadyReadStandardOutput();
    void onReadyReadStandardError();
    void onFinished(int exitCode, QProcess::ExitStatus status);
    void onErrorOccurred(QProcess::ProcessError error);

private:
    void dispatchFrame(const QByteArray &line);

    QProcess *m_process = nullptr;
    QString m_python;
    QString m_mainPy;
    QString m_repoRoot;
    QString m_tempDir;
    int m_maxWorkers = 2;
    QByteArray m_buffer;
    QString m_stderrTail;
};

} // namespace toolbox
