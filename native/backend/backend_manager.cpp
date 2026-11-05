#include "backend_manager.h"

#include <QDir>
#include <QFileInfo>

namespace toolbox {

BackendManager::BackendManager(QObject *parent)
    : QObject(parent)
{
    m_handshakeTimer.setSingleShot(true);
    connect(&m_handshakeTimer, &QTimer::timeout, this, &BackendManager::onHandshakeTimeout);
    connect(&m_worker, &PythonWorker::responseReceived,
            this, &BackendManager::onWorkerResponse);
    connect(&m_worker, &PythonWorker::eventReceived,
            this, &BackendManager::onWorkerEvent);
    connect(&m_worker, &PythonWorker::processExited,
            this, &BackendManager::onWorkerExited);
    connect(&m_worker, &PythonWorker::protocolError, this,
            [this](const QString &reason) {
                emit errorOccurred(QStringLiteral("PROTOCOL_ERROR"), reason);
            });
    connect(&m_worker, &PythonWorker::processError, this,
            [this](QProcess::ProcessError error) {
                if (error == QProcess::FailedToStart) {
                    setState(State::Crashed);
                    emit errorOccurred(QStringLiteral("WORKER_START_FAILED"),
                                       QStringLiteral("无法启动 Python Worker，请检查 Python 路径与依赖"));
                }
            });
}

BackendManager::~BackendManager()
{
    shutdown();
}

void BackendManager::configure(const QString &pythonExecutable, const QString &repoRoot,
                               const QString &tempDir, int maxWorkers)
{
    m_python = pythonExecutable;
    m_repoRoot = repoRoot;
    m_tempDir = tempDir;
    m_maxWorkers = maxWorkers;
    const QString mainPy = QDir(repoRoot).filePath(QStringLiteral("python_worker/main.py"));
    m_worker.configure(pythonExecutable, mainPy, repoRoot, tempDir, maxWorkers);
}

QString BackendManager::state() const
{
    switch (m_state) {
    case State::Idle: return QStringLiteral("idle");
    case State::Starting: return QStringLiteral("starting");
    case State::Handshaking: return QStringLiteral("handshaking");
    case State::Ready: return QStringLiteral("ready");
    case State::Crashed: return QStringLiteral("crashed");
    case State::Stopped: return QStringLiteral("stopped");
    }
    return QStringLiteral("unknown");
}

void BackendManager::setState(State state)
{
    if (m_state == state)
        return;
    m_state = state;
    emit stateChanged(state());
}

void BackendManager::start()
{
    if (isRunning())
        return;
    if (m_python.isEmpty() || !QFileInfo::exists(m_repoRoot + QStringLiteral("/python_worker/main.py"))) {
        emit errorOccurred(QStringLiteral("WORKER_START_FAILED"),
                           QStringLiteral("Worker 配置不完整（Python 路径或仓库根缺失）"));
        return;
    }
    setState(State::Starting);
    if (!m_worker.start()) {
        setState(State::Crashed);
        emit errorOccurred(QStringLiteral("WORKER_START_FAILED"),
                           QStringLiteral("Worker 进程启动失败"));
        return;
    }
    beginHandshake();
}

void BackendManager::beginHandshake()
{
    setState(State::Handshaking);
    m_handshakeTimer.start(kHandshakeTimeoutMs);
    sendAction(QStringLiteral("worker.hello"));
}

void BackendManager::onHandshakeTimeout()
{
    if (m_state != State::Handshaking)
        return;
    m_worker.stop();
    setState(State::Crashed);
    emit errorOccurred(QStringLiteral("HANDSHAKE_TIMEOUT"),
                       QStringLiteral("Worker 握手超时（%1ms）").arg(kHandshakeTimeoutMs));
}

QString BackendManager::sendAction(const QString &action, const QJsonObject &params)
{
    const QString requestId = QStringLiteral("req-%1").arg(++m_requestCounter);
    m_worker.sendRequest(requestId, action, params);
    return requestId;
}

void BackendManager::cancelTask(const QString &taskId)
{
    m_worker.sendRequest(QStringLiteral("req-%1").arg(++m_requestCounter),
                         QStringLiteral("task.cancel"),
                         QJsonObject{{QStringLiteral("task_id"), taskId}});
}

void BackendManager::shutdown()
{
    m_handshakeTimer.stop();
    if (m_state != State::Idle && m_worker.isRunning())
        m_worker.sendRequest(QStringLiteral("req-shutdown"), QStringLiteral("worker.shutdown"));
    m_worker.stop();
    setState(State::Stopped);
}

void BackendManager::onWorkerResponse(const QString &requestId, const QJsonObject &message)
{
    // The handshake response is the very first reply; finish becoming Ready.
    const bool success = ipc::IpcProtocol::isSuccess(message);
    if (m_state == State::Handshaking) {
        m_handshakeTimer.stop();
        if (!success) {
            m_worker.stop();
            setState(State::Crashed);
            const QJsonObject err = ipc::IpcProtocol::errorOf(message);
            emit errorOccurred(err.value(QStringLiteral("code")).toString(),
                               err.value(QStringLiteral("message")).toString());
            return;
        }
        const QJsonObject result = ipc::IpcProtocol::resultOf(message);
        const int protocol = result.value(QStringLiteral("protocol")).toInt(0);
        if (protocol != ipc::kProtocolVersion) {
            m_worker.stop();
            setState(State::Crashed);
            emit errorOccurred(QStringLiteral("PROTOCOL_MISMATCH"),
                               QStringLiteral("Worker 协议版本 %1 与应用 %2 不一致")
                                   .arg(protocol)
                                   .arg(ipc::kProtocolVersion));
            return;
        }
        m_restartCount = 0; // healthy start resets the crash-loop guard
        setState(State::Ready);
        m_capabilities = result;
        emit ready(result);
        return; // hello response is consumed by the manager, not forwarded
    }
    emit responseReady(requestId, message);
}

void BackendManager::onWorkerEvent(const QJsonObject &message)
{
    emit taskEvent(message);
}

void BackendManager::onWorkerExited(int exitCode, QProcess::ExitStatus status)
{
    // shutdown()/stop() 的退出是预期行为，不是崩溃；到达的退出事件不得覆盖状态。
    if (m_state == State::Stopped || m_state == State::Idle)
        return;
    const bool wasReady = m_state == State::Ready;
    setState(State::Crashed);
    if (status == QProcess::CrashExit || exitCode != 0) {
        emit errorOccurred(QStringLiteral("WORKER_CRASHED"),
                           QStringLiteral("Worker 异常退出 (code=%1)。%2")
                               .arg(exitCode)
                               .arg(wasReady
                                        ? QStringLiteral("未保存的编辑状态不可恢复，请从源文件重新打开。")
                                        : QString()));
    }
    // Auto-restart only when the worker had been usable; bounded by §6.5.
    if (wasReady && m_restartCount < kMaxRestarts) {
        scheduleRestart();
    }
}

void BackendManager::scheduleRestart()
{
    ++m_restartCount;
    QTimer::singleShot(1000, this, [this] {
        if (m_state == State::Crashed)
            start();
    });
}

} // namespace toolbox
