#include "assist_service.h"

// 连接 BackendManager 的信号需要完整类型（assist_service.h 只有前置声明），
// 与 filter_service.cpp / studio_service.cpp 的包含次序同一约定。
#include "backend/backend_manager.h"
#include "backend/ipc_protocol.h"

#include <QJsonDocument>

namespace toolbox {

namespace {

AssistService *s_instance = nullptr; // process-wide singleton identity

} // namespace

AssistService::AssistService(QObject *parent)
    : QObject(parent), m_assistModel(new AssistModel(this)) {}

AssistService::~AssistService() {
    if (s_instance == this)
        s_instance = nullptr;
}

AssistService *AssistService::instance() {
    if (!s_instance)
        s_instance = new AssistService();
    return s_instance;
}

AssistService *AssistService::create(QQmlEngine *qmlEngine, QJSEngine *jsEngine) {
    // The instance must outlive the engine bindings; ownership stays with QML.
    Q_UNUSED(qmlEngine);
    Q_UNUSED(jsEngine);
    return instance();
}

void AssistService::bindBackend(BackendManager *backend) {
    if (m_backend == backend)
        return;
    m_backend = backend;
    if (!m_backend)
        return;
    connect(m_backend, &BackendManager::responseReady, this, &AssistService::onResponseReady);
    connect(m_backend, &BackendManager::taskEvent, this, &AssistService::onTaskEvent);
}

void AssistService::bindTaskModel(TaskModel *taskModel) {
    m_taskModel = taskModel; // 幂等重绑无害；未绑定时运行无任务行（见头注释）
}

void AssistService::setLoadingTools(bool loading) {
    if (m_loadingTools == loading)
        return;
    m_loadingTools = loading;
    emit loadingToolsChanged();
}

QString AssistService::sendTracked(PendingKind kind, const QString &action,
                                   const QJsonObject &params, const QString &toolKey) {
    if (!m_backend) {
        // BackendManager::errorOccurred 的 WORKER_START_FAILED 只覆盖进程层面；
        // 这里是调用层面未接线，归入未分类的内部错误（§5，filter_service.cpp
        // 同款处置）。本次调用未发出，但 QML 可能已按"已提交"置位——如实上报。
        emit assistError(QStringLiteral("INTERNAL"),
                         QStringLiteral("后端未绑定，无法执行辅助工具操作"));
        return {};
    }
    const QString requestId = m_backend->sendAction(action, params);
    if (!requestId.isEmpty())
        m_pendingByRequest.insert(requestId, Pending{kind, toolKey});
    return requestId;
}

void AssistService::loadTools() {
    // 未发出（未绑定后端）不进入在途状态——loadingTools 只描述真实在途的
    // assist.list；成功/失败响应都会收掉标志（onResponseReady ToolList 分支）。
    const QString requestId = sendTracked(PendingKind::ToolList, QStringLiteral("assist.list"), {});
    if (!requestId.isEmpty())
        setLoadingTools(true);
}

QString AssistService::runTool(const QString &toolKey, const QString &paramsJson) {
    // 本地拒绝（与 StudioService::render 的 key 校验同一契约：错误 + 不上送，
    // 恰好一次失败上报）。toolKey 即运行动作名，是 run 的最小定位字段。
    if (toolKey.trimmed().isEmpty()) {
        emit assistError(QStringLiteral("INVALID_PARAMS"), QStringLiteral("工具 key 为空"));
        return {};
    }
    // paramsJson 是该工具的参数"值"对象；空/纯空白按 {} 上送（无参工具合法）。
    // 可解析但不是对象（数组/标量）视为本地参数错误——不上送垃圾帧。
    QJsonObject params;
    const QString trimmed = paramsJson.trimmed();
    if (!trimmed.isEmpty()) {
        const QJsonDocument parsed = QJsonDocument::fromJson(trimmed.toUtf8());
        if (!parsed.isObject()) {
            emit assistError(QStringLiteral("INVALID_PARAMS"),
                             QStringLiteral("参数不是 JSON 对象"));
            return {};
        }
        params = parsed.object();
    }
    const QString requestId = sendTracked(PendingKind::Run, toolKey, params, toolKey);
    // 任务行登记（"进度模式对齐既有任务"）：TaskModel 只为 trackRequest 登记
    // 过的 request_id 建 row，且 sync 动作的成功响应不产生任务行
    // （task_model.cpp:66-72 "sync action answered — nothing to track"）——
    // 因此无需预知工具是 sync 还是 async，统一登记即可：async 工具受理后
    // 自动画出任务行，sync 工具不留任何痕迹。显示名取目录显示名（未收录时
    // 回落 key；行名归提交方，document_service.cpp:52-75 同一命名层级）。
    if (!requestId.isEmpty() && m_taskModel)
        m_taskModel->trackRequest(requestId, toolDisplayName(toolKey));
    return requestId;
}

QString AssistService::toolDisplayName(const QString &toolKey) const {
    for (int row = 0; row < m_assistModel->rowCount(); ++row) {
        if (m_assistModel->index(row).data(AssistModel::ToolKeyRole).toString() == toolKey)
            return m_assistModel->index(row).data(AssistModel::ToolNameRole).toString();
    }
    return toolKey;
}

QString AssistService::compactJson(const QJsonObject &object) {
    return QString::fromUtf8(QJsonDocument(object).toJson(QJsonDocument::Compact));
}

void AssistService::onResponseReady(const QString &requestId, const QJsonObject &message) {
    const auto pending = m_pendingByRequest.constFind(requestId);
    if (pending == m_pendingByRequest.cend())
        return; // 未跟踪请求（worker.hello 归 BackendManager；image.* / filter.* /
                // batch.* / generate.* 的受理与事件归各自服务）

    const Pending context = pending.value();
    m_pendingByRequest.erase(pending);

    if (!ipc::IpcProtocol::isSuccess(message)) {
        // 同步拒绝（UNKNOWN_ACTION / INVALID_PARAMS / FILE_NOT_FOUND /
        // DEPENDENCY_MISSING 等，§5/§3.8）：动作未落定，只报错不改任何状态。
        // ToolList 的在途标志一并收掉。
        if (context.kind == PendingKind::ToolList)
            setLoadingTools(false);
        const QJsonObject error = ipc::IpcProtocol::errorOf(message);
        emit assistError(error.value(QStringLiteral("code")).toString(),
                         error.value(QStringLiteral("message")).toString());
        return;
    }

    const QJsonObject result = ipc::IpcProtocol::resultOf(message);
    switch (context.kind) {
    case PendingKind::ToolList: {
        setLoadingTools(false);
        m_assistModel->reloadFrom(result);
        return;
    }
    case PendingKind::Run: {
        // sync / async 由响应形状判定（§2.3，类头协议注记）：result 带 task_id
        // = async 受理，生命周期改由 onTaskEvent 按 task_id 关联；不带 task_id
        // = sync 工具直接应答，结果对象原样交付（不产生任务行——trackRequest
        // 登记过的 request_id 遇 sync 应答被 TaskModel 自行忽略）。
        const QString taskId = result.value(QStringLiteral("task_id")).toString();
        if (!taskId.isEmpty()) {
            m_pendingByTask.insert(taskId, context);
            emit toolAccepted(context.toolKey, taskId);
            return;
        }
        emit notifyToolResult(context.toolKey, compactJson(result));
        return;
    }
    }
}

void AssistService::onTaskEvent(const QJsonObject &event) {
    const QString type = event.value(QStringLiteral("type")).toString();
    if (type == QStringLiteral("task.progress"))
        return; // 进度呈现归 TaskModel 行（"进度模式对齐既有任务"）；结果交付
                // 只关心终态

    const QString taskId = ipc::IpcProtocol::eventTaskId(event);
    if (taskId.isEmpty())
        return;
    const auto pending = m_pendingByTask.constFind(taskId);
    if (pending == m_pendingByTask.cend())
        return; // 未知任务（image.* / filter.* 等任务归各自服务）

    const Pending context = pending.value();
    m_pendingByTask.erase(pending);

    if (type == QStringLiteral("task.failed")) {
        // §7：取消以 task.failed + CANCELLED 呈现，与其他失败同一通道如实上报
        // （区分留给 QML 按 code 呈现，StudioService 的渲染失败同款不特判）。
        const QJsonObject error = event.value(QStringLiteral("error")).toObject();
        emit assistError(error.value(QStringLiteral("code")).toString(),
                         error.value(QStringLiteral("message")).toString());
        return;
    }
    if (type == QStringLiteral("task.completed")) {
        // async 工具结果交付：completed result 原样序列化（工具自有形状，QML
        // 按工具解析；空 result 交付 "{}"——C++ 只透传，不猜测工具形状）。
        emit notifyToolResult(context.toolKey,
                              compactJson(event.value(QStringLiteral("result")).toObject()));
        return;
    }
}

} // namespace toolbox
