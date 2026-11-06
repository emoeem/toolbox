#include "studio_service.h"

// 连接 BackendManager 的信号需要完整类型（studio_service.h 只有前置声明），
// 与 document_service.cpp / filter_service.cpp 的包含次序同一约定。
#include "backend/backend_manager.h"
#include "backend/ipc_protocol.h"
#include "core/document_service.h"

#include <QJsonDocument>
#include <QUrl>

namespace toolbox {

namespace {

StudioService *s_instance = nullptr; // process-wide singleton identity

} // namespace

StudioService::StudioService(QObject *parent)
    : QObject(parent), m_generatorModel(new GeneratorModel(this)) {}

StudioService::~StudioService() {
    if (s_instance == this)
        s_instance = nullptr;
}

StudioService *StudioService::instance() {
    if (!s_instance)
        s_instance = new StudioService();
    return s_instance;
}

StudioService *StudioService::create(QQmlEngine *qmlEngine, QJSEngine *jsEngine) {
    // The instance must outlive the engine bindings; ownership stays with QML.
    Q_UNUSED(qmlEngine);
    Q_UNUSED(jsEngine);
    return instance();
}

void StudioService::bindBackend(BackendManager *backend) {
    if (m_backend == backend)
        return;
    m_backend = backend;
    if (!m_backend)
        return;
    connect(m_backend, &BackendManager::responseReady, this, &StudioService::onResponseReady);
    connect(m_backend, &BackendManager::taskEvent, this, &StudioService::onTaskEvent);
}

void StudioService::bindTaskModel(TaskModel *taskModel) {
    m_taskModel = taskModel; // 幂等重绑无害；未绑定时渲染无任务行（见头注释）
}

void StudioService::setLoadingGenerators(bool loading) {
    if (m_loadingGenerators == loading)
        return;
    m_loadingGenerators = loading;
    emit loadingGeneratorsChanged();
}

QString StudioService::sendTracked(PendingKind kind, const QString &action,
                                   const QJsonObject &params) {
    if (!m_backend) {
        // BackendManager::errorOccurred 的 WORKER_START_FAILED 只覆盖进程层面；
        // 这里是调用层面未接线，归入未分类的内部错误（§5，filter_service.cpp
        // 同款处置）。本次调用未发出，但 QML 可能已按"已提交"置位——如实上报。
        emit studioError(QStringLiteral("INTERNAL"),
                         QStringLiteral("后端未绑定，无法执行 Studio 操作"));
        return {};
    }
    const QString requestId = m_backend->sendAction(action, params);
    if (!requestId.isEmpty())
        m_pendingByRequest.insert(requestId, Pending{kind});
    return requestId;
}

void StudioService::loadGenerators() {
    // 未发出（未绑定后端）不进入在途状态——loadingGenerators 只描述真实在途
    // 的 generate.list；成功/失败响应都会收掉标志（onResponseReady 分支）。
    const QString requestId =
        sendTracked(PendingKind::GeneratorList, QStringLiteral("generate.list"), {});
    if (!requestId.isEmpty())
        setLoadingGenerators(true);
}

QString StudioService::render(const QString &generatorKey, const QString &paramsJson, int width,
                              int height) {
    // 本地拒绝（与 DocumentService::applyFilters 空链拒绝同一契约：错误 + 不
    // 上送，恰好一次失败上报）。generator_key 是 render 的最小定位字段。
    if (generatorKey.trimmed().isEmpty()) {
        emit studioError(QStringLiteral("INVALID_PARAMS"), QStringLiteral("生成器 key 为空"));
        return {};
    }
    if (width <= 0 || height <= 0) {
        emit studioError(QStringLiteral("INVALID_PARAMS"), QStringLiteral("渲染尺寸无效"));
        return {};
    }
    // paramsJson 是 UI 装配后的参数"值"对象；空/纯空白按 {} 上送（无参生成器
    // 合法）。可解析但不是对象（数组/标量）视为本地参数错误——不上送垃圾帧。
    QJsonObject params;
    const QString trimmed = paramsJson.trimmed();
    if (!trimmed.isEmpty()) {
        const QJsonDocument parsed = QJsonDocument::fromJson(trimmed.toUtf8());
        if (!parsed.isObject()) {
            emit studioError(QStringLiteral("INVALID_PARAMS"),
                             QStringLiteral("参数不是 JSON 对象"));
            return {};
        }
        params = parsed.object();
    }
    const QString requestId = sendTracked(PendingKind::Render, QStringLiteral("generate.render"),
                                          QJsonObject{
                                              {QStringLiteral("generator_key"), generatorKey},
                                              {QStringLiteral("params"), params},
                                              {QStringLiteral("width"), width},
                                              {QStringLiteral("height"), height},
                                          });
    // 任务行登记（§2.3）：TaskModel 只为 trackRequest 登记过的 request_id 建
    // 行（task_model.cpp:59-77）；不登记则渲染永远不进任务抽屉、也无法行内
    // 取消（document_service.cpp:114-123 同款）。行显示名"生成渲染"（TaskModel
    // NameRole，与滤镜链的"滤镜链"同款命名层级——行名归提交方，
    // document_service.cpp:52-75）。
    if (!requestId.isEmpty() && m_taskModel)
        m_taskModel->trackRequest(requestId, QStringLiteral("生成渲染"));
    return requestId;
}

void StudioService::exportToEditor(const QString &imagePath) {
    if (imagePath.trimmed().isEmpty()) {
        emit studioError(QStringLiteral("INVALID_PARAMS"), QStringLiteral("导出路径为空"));
        return;
    }
    // 打开动作的关联与状态迁移归 DocumentService（document_service.cpp:128-139）：
    // 成功经 documentOpened 交付，失败（含 FILE_NOT_FOUND）经 documentError——
    // 本服务不复制文档状态，也不把文档层错误转述成 studioError（通道分离，
    // test_filter_service.cpp:434 的同一契约）。
    DocumentService::instance()->openDocument(QUrl::fromLocalFile(imagePath));
}

void StudioService::onResponseReady(const QString &requestId, const QJsonObject &message) {
    const auto pending = m_pendingByRequest.constFind(requestId);
    if (pending == m_pendingByRequest.cend())
        return; // 未跟踪请求（worker.hello 归 BackendManager；image.* / filter.* /
                // batch.* 的受理与事件归各自服务）

    const Pending context = pending.value();
    m_pendingByRequest.erase(pending);

    if (!ipc::IpcProtocol::isSuccess(message)) {
        // 同步拒绝（UNKNOWN_ACTION / INVALID_PARAMS / FILE 系列等，§5）：动作
        // 未落定，只报错不改任何状态。GeneratorList 的在途标志一并收掉。
        if (context.kind == PendingKind::GeneratorList)
            setLoadingGenerators(false);
        const QJsonObject error = ipc::IpcProtocol::errorOf(message);
        emit studioError(error.value(QStringLiteral("code")).toString(),
                         error.value(QStringLiteral("message")).toString());
        return;
    }

    const QJsonObject result = ipc::IpcProtocol::resultOf(message);
    switch (context.kind) {
    case PendingKind::GeneratorList: {
        setLoadingGenerators(false);
        m_generatorModel->reloadFrom(result);
        return;
    }
    case PendingKind::Render: {
        // 异步动作已受理（§2.3）：生命周期改由 taskEvent 按 task_id 关联；
        // task_id 的同步可观察交付只有 renderAccepted（batch_service.cpp
        // 受理分支同款）。
        const QString taskId = result.value(QStringLiteral("task_id")).toString();
        if (taskId.isEmpty()) {
            // 成功响应必带 task_id（§2.3）；缺失视为协议违约，不伪造受理——
            // 该提交永远不会有事件跟进。
            emit studioError(QStringLiteral("INTERNAL"),
                             QStringLiteral("generate.render 响应缺少 task_id"));
            return;
        }
        m_pendingByTask.insert(taskId, context);
        emit renderAccepted(taskId);
        return;
    }
    }
}

void StudioService::onTaskEvent(const QJsonObject &event) {
    const QString type = event.value(QStringLiteral("type")).toString();
    if (type == QStringLiteral("task.progress"))
        return; // 进度呈现归 TaskModel；预览交付只关心终态

    const QString taskId = ipc::IpcProtocol::eventTaskId(event);
    if (taskId.isEmpty())
        return;
    const auto pending = m_pendingByTask.constFind(taskId);
    if (pending == m_pendingByTask.cend())
        return; // 未知任务（image.* / filter.* 任务、他人创建早于本服务的任务）

    if (type == QStringLiteral("task.failed")) {
        m_pendingByTask.erase(pending);
        // §7：取消以 task.failed + CANCELLED 呈现，与其他失败同一通道如实上报
        // （区分留给 QML 按 code 呈现，FilterService 的预设失败同款不特判）。
        const QJsonObject error = event.value(QStringLiteral("error")).toObject();
        emit studioError(error.value(QStringLiteral("code")).toString(),
                         error.value(QStringLiteral("message")).toString());
        return;
    }
    if (type == QStringLiteral("task.completed")) {
        m_pendingByTask.erase(pending);
        // 预览图交付（§4 大图走临时文件路径）：path 优先，内联 data 兜底；
        // 二者皆缺视为协议违约——不发射空路径的 notifyPreviewReady（QML 会把
        // 空串当真图源，宁可显式报错）。
        const QJsonObject result = event.value(QStringLiteral("result")).toObject();
        QString image = result.value(QStringLiteral("path")).toString();
        if (image.isEmpty())
            image = result.value(QStringLiteral("data")).toString();
        if (image.isEmpty()) {
            emit studioError(QStringLiteral("INTERNAL"),
                             QStringLiteral("generate.render 完成结果缺少预览图"));
            return;
        }
        emit notifyPreviewReady(image);
        return;
    }
}

} // namespace toolbox
