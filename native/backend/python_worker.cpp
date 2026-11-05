#include "python_worker.h"

#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>
#include <QtLogging>

#include "ipc_protocol.h"

namespace toolbox {

PythonWorker::PythonWorker(QObject *parent)
    : QObject(parent)
{
}

PythonWorker::~PythonWorker()
{
    stop();
}

void PythonWorker::configure(const QString &pythonExecutable, const QString &mainPyPath,
                             const QString &repoRoot, const QString &tempDir, int maxWorkers)
{
    m_python = pythonExecutable;
    m_mainPy = mainPyPath;
    m_repoRoot = repoRoot;
    m_tempDir = tempDir;
    m_maxWorkers = maxWorkers;
}

bool PythonWorker::start()
{
    if (isRunning())
        return true;
    if (m_python.isEmpty() || m_mainPy.isEmpty())
        return false;

    delete m_process;
    m_process = new QProcess(this);
    m_buffer.clear();
    m_stderrTail.clear();

    connect(m_process, &QProcess::readyReadStandardOutput,
            this, &PythonWorker::onReadyReadStandardOutput);
    connect(m_process, &QProcess::readyReadStandardError,
            this, &PythonWorker::onReadyReadStandardError);
    connect(m_process, &QProcess::finished,
            this, &PythonWorker::onFinished);
    connect(m_process, &QProcess::errorOccurred,
            this, &PythonWorker::onErrorOccurred);

    QStringList args;
    args << m_mainPy
         << QStringLiteral("--repo-root") << m_repoRoot
         << QStringLiteral("--max-workers") << QString::number(m_maxWorkers);
    if (!m_tempDir.isEmpty())
        args << QStringLiteral("--temp-dir") << m_tempDir;

    // Explicit environment: never depend on the launching shell's state
    // (master plan §15.4). PYTHONUNBUFFERED keeps stdout lines flowing.
    auto env = QProcessEnvironment::systemEnvironment();
    env.insert(QStringLiteral("PYTHONUNBUFFERED"), QStringLiteral("1"));
    m_process->setProcessEnvironment(env);
    // Working dir must NOT be required for imports; --repo-root handles that.
    m_process->start(m_python, args);
    return m_process->waitForStarted(5000);
}

void PythonWorker::stop()
{
    if (!m_process)
        return;
    if (m_process->state() == QProcess::NotRunning) {
        m_process->deleteLater();
        m_process = nullptr;
        return;
    }
    // Graceful first: worker exits its main loop on stdin EOF.
    m_process->closeWriteChannel();
    const auto proc = m_process;
    QTimer::singleShot(2000, this, [this, proc] {
        if (proc && proc->state() != QProcess::NotRunning)
            proc->terminate();
    });
    QTimer::singleShot(4000, this, [this, proc] {
        if (proc && proc->state() != QProcess::NotRunning)
            proc->kill();
    });
}

bool PythonWorker::isRunning() const
{
    return m_process && m_process->state() != QProcess::NotRunning;
}

void PythonWorker::sendRequest(const QString &requestId, const QString &action,
                               const QJsonObject &params)
{
    const QJsonObject request = ipc::IpcProtocol::makeRequest(requestId, action, params);
    sendLine(QJsonDocument(request).toJson(QJsonDocument::Compact));
}

void PythonWorker::sendLine(const QByteArray &line)
{
    if (!m_process || !isRunning())
        return;
    m_process->write(line.endsWith('\n') ? line : line + '\n');
}

void PythonWorker::onReadyReadStandardOutput()
{
    if (!m_process)
        return;
    m_buffer += m_process->readAllStandardOutput();
    int newline = -1;
    while ((newline = m_buffer.indexOf('\n')) >= 0) {
        const QByteArray line = m_buffer.left(newline);
        m_buffer.remove(0, newline + 1);
        if (line.trimmed().isEmpty())
            continue;
        dispatchFrame(line);
    }
}

void PythonWorker::onReadyReadStandardError()
{
    if (!m_process)
        return;
    const QByteArray chunk = m_process->readAllStandardError();
    // Keep a bounded tail for crash diagnostics; full logs go to app log.
    m_stderrTail.append(QString::fromUtf8(chunk));
    if (m_stderrTail.size() > 8192)
        m_stderrTail.remove(0, m_stderrTail.size() - 8192);
    qWarning("python-worker stderr: %s", QByteArray(chunk).constData());
}

void PythonWorker::dispatchFrame(const QByteArray &line)
{
    QJsonParseError parseError{};
    const QJsonDocument doc = QJsonDocument::fromJson(line, &parseError);
    if (parseError.error != QJsonParseError::NoError || !doc.isObject()) {
        emit protocolError(QStringLiteral("无法解析 Worker 消息: %1").arg(parseError.errorString()));
        return;
    }
    const QJsonObject message = doc.object();
    const ipc::FrameKind kind = ipc::IpcProtocol::classify(message);
    switch (kind) {
    case ipc::FrameKind::Response:
        emit responseReceived(ipc::IpcProtocol::requestIdOf(message), message);
        break;
    case ipc::FrameKind::Event:
        emit eventReceived(message);
        break;
    case ipc::FrameKind::Request:
    case ipc::FrameKind::Invalid:
        emit protocolError(QStringLiteral("未知消息类型: %1").arg(QString::fromUtf8(line.left(120))));
        break;
    }
}

void PythonWorker::onFinished(int exitCode, QProcess::ExitStatus status)
{
    emit processExited(exitCode, status);
}

void PythonWorker::onErrorOccurred(QProcess::ProcessError error)
{
    emit processError(error);
}

} // namespace toolbox
