#include "document_service.h"

// 连接 BackendManager 的信号需要完整类型（document_service.h 只有前置声明），
// 与 task_model.cpp 的包含次序同一约定。
#include "backend/backend_manager.h"
#include "backend/ipc_protocol.h"
#include "models/task_model.h"
#include "services/settings_service.h"

namespace toolbox {

namespace {

DocumentService *s_instance = nullptr; // process-wide singleton identity

} // namespace

DocumentService::DocumentService(QObject *parent) : QObject(parent) {}

DocumentService::~DocumentService() {
    if (s_instance == this)
        s_instance = nullptr;
}

DocumentService *DocumentService::instance() {
    if (!s_instance)
        s_instance = new DocumentService();
    return s_instance;
}

DocumentService *DocumentService::create(QQmlEngine *qmlEngine, QJSEngine *jsEngine) {
    // The instance must outlive the engine bindings; ownership stays with QML.
    Q_UNUSED(qmlEngine);
    Q_UNUSED(jsEngine);
    return instance();
}

void DocumentService::bindBackend(BackendManager *backend) {
    if (m_backend == backend)
        return;
    m_backend = backend;
    if (!m_backend)
        return;
    connect(m_backend, &BackendManager::responseReady, this, &DocumentService::onResponseReady);
    connect(m_backend, &BackendManager::taskEvent, this, &DocumentService::onTaskEvent);
}

void DocumentService::bindTaskModel(TaskModel *taskModel) {
    m_taskModel = taskModel; // 幂等重绑无害；未绑定时不登记，行为回到无任务行
}

QString DocumentService::taskDisplayName(PendingKind kind, bool preview) {
    switch (kind) {
    case PendingKind::Save:
        return QStringLiteral("保存图像");
    case PendingKind::Adjust:
        return preview ? QStringLiteral("调整预览") : QStringLiteral("应用调整");
    case PendingKind::Transform:
    case PendingKind::ApplyTransform:
        // 组合线形与旧 op 线形共用行名：统一变换语义，提交线形由请求形状
        // 区分（任务抽屉/摘要不感知差异）。
        return preview ? QStringLiteral("变换预览") : QStringLiteral("应用变换");
    case PendingKind::ApplyFilters:
        // 任务清单指定：滤镜链的预览与全分辨率行统一叫"滤镜链"——链级任务
        // 行不区分二者，提交形态由 actionId() 的 filter.preview/apply 区分。
        return QStringLiteral("滤镜链");
    case PendingKind::ApplyAnnotate:
        return QStringLiteral("应用标注");
    case PendingKind::Undo:
        return QStringLiteral("撤销");
    case PendingKind::Redo:
        return QStringLiteral("重做");
    case PendingKind::Reset:
        return QStringLiteral("重置");
    case PendingKind::Open:
    case PendingKind::History:
        break; // 同步动作不产生任务（响应无 task_id），永不建行
    }
    return {};
}

QString DocumentService::actionId(PendingKind kind, bool preview) {
    switch (kind) {
    case PendingKind::Open:
        return QStringLiteral("image.open");
    case PendingKind::Save:
        return QStringLiteral("image.save");
    case PendingKind::Adjust:
        return preview ? QStringLiteral("image.adjust-preview") : QStringLiteral("image.adjust");
    case PendingKind::Transform:
    case PendingKind::ApplyTransform:
        // 同一协议动作 image.transform：新旧线形只是请求形状差异（顶层 op
        // 有无），actionId 不区分——QML 在途门控按动作名解锁即可。
        return preview ? QStringLiteral("image.transform-preview")
                       : QStringLiteral("image.transform");
    case PendingKind::ApplyFilters:
        return preview ? QStringLiteral("filter.preview") : QStringLiteral("filter.apply");
    case PendingKind::ApplyAnnotate:
        return QStringLiteral("image.annotate");
    case PendingKind::Undo:
        return QStringLiteral("image.undo");
    case PendingKind::Redo:
        return QStringLiteral("image.redo");
    case PendingKind::Reset:
        return QStringLiteral("image.reset");
    case PendingKind::History:
        return QStringLiteral("image.history");
    }
    return {};
}

QString DocumentService::dispatch(PendingKind kind, const QString &action,
                                  const QJsonObject &params, const QString &path, bool preview) {
    if (!m_backend) {
        // BackendManager::errorOccurred 的 WORKER_START_FAILED 只覆盖进程层面；
        // 这里是调用层面未接线，归入未分类的内部错误（docs/ipc-protocol.md §5）。
        // 本次调用未发出，但调用方（QML）可能已置在途标志——按未落定上报。
        emit documentError(QStringLiteral("INTERNAL"),
                           QStringLiteral("后端未绑定，无法执行文档操作"));
        emit documentActionFailed(m_currentDocumentId, actionId(kind, preview));
        return {};
    }
    const QString requestId = m_backend->sendAction(action, params);
    if (!requestId.isEmpty()) {
        m_pendingByRequest.insert(requestId, Pending{kind, path, m_currentDocumentId, preview});
        // 任务行登记（§2.3）：TaskModel 只为 trackRequest 登记过的 request_id
        // 建行（task_model.cpp:59-77），不登记则该动作永远不进任务抽屉/摘要，
        // 也没有行内取消入口。同步动作（open/history）无 task_id，不登记。
        if (m_taskModel) {
            const QString name = taskDisplayName(kind, preview);
            if (!name.isEmpty())
                m_taskModel->trackRequest(requestId, name);
        }
    }
    return requestId;
}

void DocumentService::openDocument(const QUrl &file) {
    const QString path = file.toLocalFile();
    if (path.isEmpty()) {
        // Worker 只接受文件系统路径（§3 image.open {path}）；非本地 URL 在
        // 本地直接拒绝，不上送。
        emit documentError(QStringLiteral("INVALID_PARAMS"),
                           QStringLiteral("打开路径不是本地文件: %1").arg(file.toString()));
        return;
    }
    dispatch(PendingKind::Open, QStringLiteral("image.open"),
             QJsonObject{{QStringLiteral("path"), path}}, path);
}

void DocumentService::saveDocument(const QString &path, int quality, int targetKb) {
    if (m_currentDocumentId.isEmpty()) {
        // 本地拒绝同样发 actionFailed：统一契约——每个未落定的动作调用恰好
        // 对应一次失败信号，QML 在途门控永不卡死（CI 实证 unboundBackend 用例）。
        emit documentError(QStringLiteral("UNKNOWN_DOCUMENT"), QStringLiteral("尚未打开文档"));
        emit documentActionFailed(m_currentDocumentId, actionId(PendingKind::Save, false));
        return;
    }
    if (path.isEmpty()) {
        emit documentError(QStringLiteral("INVALID_PARAMS"), QStringLiteral("保存路径为空"));
        return;
    }
    QJsonObject params{
        {QStringLiteral("document_id"), m_currentDocumentId},
        {QStringLiteral("path"), path},
    };
    if (quality >= 0)
        params.insert(QStringLiteral("quality"), quality);
    // §3.9（Phase 9）：target_kb 只在 > 0 时携带，targetKb <= 0 的请求与
    // 既有两参调用形状逐字节一致（协议兼容性规则：既有请求不携带新键）。
    if (targetKb > 0)
        params.insert(QStringLiteral("target_kb"), targetKb);
    dispatch(PendingKind::Save, QStringLiteral("image.save"), params, path);
}

void DocumentService::adjust(const QJsonObject &adjustments, bool preview, int maxSide) {
    if (m_currentDocumentId.isEmpty()) {
        emit documentError(QStringLiteral("UNKNOWN_DOCUMENT"), QStringLiteral("尚未打开文档"));
        emit documentActionFailed(m_currentDocumentId, actionId(PendingKind::Adjust, preview));
        return;
    }
    QJsonObject params{
        {QStringLiteral("document_id"), m_currentDocumentId},
        {QStringLiteral("adjustments"), adjustments},
        {QStringLiteral("preview"), preview},
    };
    if (maxSide >= 0)
        params.insert(QStringLiteral("max_side"), maxSide);
    dispatch(PendingKind::Adjust, QStringLiteral("image.adjust"), params, {}, preview);
}

void DocumentService::transform(const QString &op, const QJsonObject &params, bool preview,
                                int maxSide) {
    // 旧 {op, params} 线形保留原样（既有 QML 调用点 rotate90/flip 与 Worker
    // 侧 op 校验语义不变，dispatcher.py _image_transform_job 要求顶层 op）；
    // 未把旧线形改写为 applyTransform 的组合键控线形——那会在 Worker 组合
    // 扩展落地前打断既有调用。统一在分发自下方完成：同一 actionId、同一
    // 任务行名、同一 handleCompleted 分支（PendingKind::Transform 与
    // ApplyTransform 共用），QML 旋转90/翻转按钮随变换页签迁移到 applyTransform。
    if (m_currentDocumentId.isEmpty()) {
        emit documentError(QStringLiteral("UNKNOWN_DOCUMENT"), QStringLiteral("尚未打开文档"));
        emit documentActionFailed(m_currentDocumentId, actionId(PendingKind::Transform, preview));
        return;
    }
    QJsonObject request{
        {QStringLiteral("document_id"), m_currentDocumentId},
        {QStringLiteral("op"), op},
        {QStringLiteral("params"), params},
        {QStringLiteral("preview"), preview},
    };
    if (maxSide >= 0)
        request.insert(QStringLiteral("max_side"), maxSide);
    dispatch(PendingKind::Transform, QStringLiteral("image.transform"), request, {}, preview);
}

void DocumentService::applyFilters(const QJsonArray &steps, bool preview, int maxSide) {
    // 空链本地拒绝（与 openDocument 非 URL 拒绝同一契约）：未发出请求也要
    // 恰好一次失败上报，QML 在途门控才有唯一的解除路径。
    if (steps.isEmpty()) {
        emit documentError(QStringLiteral("INVALID_PARAMS"), QStringLiteral("滤镜链为空"));
        emit documentActionFailed(m_currentDocumentId,
                                  actionId(PendingKind::ApplyFilters, preview));
        return;
    }
    if (m_currentDocumentId.isEmpty()) {
        emit documentError(QStringLiteral("UNKNOWN_DOCUMENT"), QStringLiteral("尚未打开文档"));
        emit documentActionFailed(m_currentDocumentId,
                                  actionId(PendingKind::ApplyFilters, preview));
        return;
    }
    // filter.preview/apply 的 steps 参数（docs/ipc-protocol.md §3）：数组原样
    // 上送，元素形状 {filter_key, params, enabled} 的校验归 Worker（提交前
    // 同步报 INVALID_PARAMS，dispatcher.py _filter_preview_job 注释）。
    QJsonObject request{
        {QStringLiteral("document_id"), m_currentDocumentId},
        {QStringLiteral("filters"), steps},
        {QStringLiteral("preview"), preview},
    };
    if (maxSide >= 0)
        request.insert(QStringLiteral("max_side"), maxSide);
    dispatch(PendingKind::ApplyFilters,
             preview ? QStringLiteral("filter.preview") : QStringLiteral("filter.apply"), request,
             {}, preview);
}

void DocumentService::applyTransform(const QJsonObject &params, bool preview, int maxSide) {
    // 空组合本地拒绝（applyFilters 空链同款契约，先于无文档判定）：一个不含
    // 任何 op 键的变换请求必然是调用方组装错误，不上送、恰好一次失败上报。
    if (params.isEmpty()) {
        emit documentError(QStringLiteral("INVALID_PARAMS"), QStringLiteral("变换参数为空"));
        emit documentActionFailed(m_currentDocumentId,
                                  actionId(PendingKind::ApplyTransform, preview));
        return;
    }
    if (m_currentDocumentId.isEmpty()) {
        emit documentError(QStringLiteral("UNKNOWN_DOCUMENT"), QStringLiteral("尚未打开文档"));
        emit documentActionFailed(m_currentDocumentId,
                                  actionId(PendingKind::ApplyTransform, preview));
        return;
    }
    // Phase 9 组合线形（docs/ipc-protocol.md §3 image.transform，Phase 9 批次
    // 扩展）：params 按"op 名 → op 参数"组合对象**原样透传**——与 applyFilters
    // 的 steps 数组同一转发方式（document_service 直接作为请求字段值嵌入，线
    // 上由 PythonWorker::sendRequest 的 QJsonDocument::toJson 序列化，
    // python_worker.cpp sendRequest），本层不做 QJsonDocument 往返改写。
    // 不带顶层 op：旧 {op, params} 线形由 transform() 保留，Worker 两种线形
    // 并存（既有语义不变，只加可选形态）。
    QJsonObject request{
        {QStringLiteral("document_id"), m_currentDocumentId},
        {QStringLiteral("params"), params},
        {QStringLiteral("preview"), preview},
    };
    if (maxSide >= 0)
        request.insert(QStringLiteral("max_side"), maxSide);
    dispatch(PendingKind::ApplyTransform, QStringLiteral("image.transform"), request, {}, preview);
}

void DocumentService::applyAnnotate(const QJsonArray &ops) {
    // 空 ops 本地拒绝（applyFilters 空链同款契约）：无操作的标注提交必然是
    // 调用方状态错误（[完成标注] 只应在待提交 ops 非空时可用）。
    if (ops.isEmpty()) {
        emit documentError(QStringLiteral("INVALID_PARAMS"), QStringLiteral("标注操作为空"));
        emit documentActionFailed(m_currentDocumentId, actionId(PendingKind::ApplyAnnotate, false));
        return;
    }
    if (m_currentDocumentId.isEmpty()) {
        emit documentError(QStringLiteral("UNKNOWN_DOCUMENT"), QStringLiteral("尚未打开文档"));
        emit documentActionFailed(m_currentDocumentId, actionId(PendingKind::ApplyAnnotate, false));
        return;
    }
    // image.annotate（Phase 9 新增 async 动作，docs/ipc-protocol.md §3 动作表
    // 随批次更新）：ops 数组原样透传，只提交全分辨率应用（无预览形态），
    // preview 分支不存在——completed result 按 §2.3 全分辨率变更类一律携带
    // version，完成路径见 handleCompleted 的 ApplyAnnotate 分支。
    const QJsonObject request{
        {QStringLiteral("document_id"), m_currentDocumentId},
        {QStringLiteral("ops"), ops},
    };
    dispatch(PendingKind::ApplyAnnotate, QStringLiteral("image.annotate"), request);
}

void DocumentService::undo() {
    if (m_currentDocumentId.isEmpty()) {
        emit documentError(QStringLiteral("UNKNOWN_DOCUMENT"), QStringLiteral("尚未打开文档"));
        emit documentActionFailed(m_currentDocumentId, actionId(PendingKind::Undo, false));
        return;
    }
    dispatch(PendingKind::Undo, QStringLiteral("image.undo"),
             QJsonObject{{QStringLiteral("document_id"), m_currentDocumentId}});
}

void DocumentService::redo() {
    if (m_currentDocumentId.isEmpty()) {
        emit documentError(QStringLiteral("UNKNOWN_DOCUMENT"), QStringLiteral("尚未打开文档"));
        emit documentActionFailed(m_currentDocumentId, actionId(PendingKind::Redo, false));
        return;
    }
    dispatch(PendingKind::Redo, QStringLiteral("image.redo"),
             QJsonObject{{QStringLiteral("document_id"), m_currentDocumentId}});
}

void DocumentService::reset() {
    if (m_currentDocumentId.isEmpty()) {
        emit documentError(QStringLiteral("UNKNOWN_DOCUMENT"), QStringLiteral("尚未打开文档"));
        emit documentActionFailed(m_currentDocumentId, actionId(PendingKind::Reset, false));
        return;
    }
    dispatch(PendingKind::Reset, QStringLiteral("image.reset"),
             QJsonObject{{QStringLiteral("document_id"), m_currentDocumentId}});
}

void DocumentService::requestHistory() {
    if (m_currentDocumentId.isEmpty()) {
        emit documentError(QStringLiteral("UNKNOWN_DOCUMENT"), QStringLiteral("尚未打开文档"));
        emit documentActionFailed(m_currentDocumentId, actionId(PendingKind::History, false));
        return;
    }
    dispatch(PendingKind::History, QStringLiteral("image.history"),
             QJsonObject{{QStringLiteral("document_id"), m_currentDocumentId}});
}

void DocumentService::onResponseReady(const QString &requestId, const QJsonObject &message) {
    const auto pending = m_pendingByRequest.constFind(requestId);
    if (pending == m_pendingByRequest.cend())
        return; // 未跟踪请求（worker.hello 由 BackendManager 消费；filter.* 归他方）

    const Pending context = pending.value();
    m_pendingByRequest.erase(pending);

    if (!ipc::IpcProtocol::isSuccess(message)) {
        // 提交前同步拒绝：image.open 的 FILE_NOT_FOUND、image.adjust 的
        // INVALID_PARAMS、image.undo 的 UNREDOABLE 等（§3.2/§3.3/§5）。
        // 动作未落定，按失败上报（QML 在途门控的相关性依据，见信号注释）。
        const QJsonObject error = ipc::IpcProtocol::errorOf(message);
        emit documentError(error.value(QStringLiteral("code")).toString(),
                           error.value(QStringLiteral("message")).toString());
        emit documentActionFailed(context.documentId, actionId(context.kind, context.preview));
        return;
    }

    const QJsonObject result = ipc::IpcProtocol::resultOf(message);
    const QString taskId = result.value(QStringLiteral("task_id")).toString();
    if (!taskId.isEmpty()) {
        // 异步动作已受理（§2.3）：生命周期改由 taskEvent 按 task_id 关联。
        m_pendingByTask.insert(taskId, context);
        return;
    }

    // 同步动作（image.open / image.history）在此直接完成。
    if (context.kind == PendingKind::Open)
        applyOpened(context.path, result);
    else if (context.kind == PendingKind::History)
        emit historyReady(result);
    else {
        // 异步动作的成功响应必带 task_id（§2.3）；缺失视为协议违约，不伪造
        // 受理。该动作永远不会有事件跟进，必须按未落定上报，否则在途标志
        // 失去唯一的解除路径。
        emit documentError(QStringLiteral("INTERNAL"), QStringLiteral("异步动作响应缺少 task_id"));
        emit documentActionFailed(context.documentId, actionId(context.kind, context.preview));
    }
}

void DocumentService::onTaskEvent(const QJsonObject &event) {
    const QString type = event.value(QStringLiteral("type")).toString();
    if (type == QStringLiteral("task.progress"))
        return; // 进度呈现归 TaskModel；文档状态只关心终态

    const QString taskId = ipc::IpcProtocol::eventTaskId(event);
    if (taskId.isEmpty())
        return;
    const auto pending = m_pendingByTask.constFind(taskId);
    if (pending == m_pendingByTask.cend())
        return; // 未知任务（filter.* 任务、他人创建早于本服务的任务）

    const Pending context = pending.value();
    if (type == QStringLiteral("task.failed")) {
        m_pendingByTask.erase(pending);
        // 失败只上报不改状态；即使文档已切换也如实呈现（错误是一次性提示，
        // 不携带文档状态，docs/ipc-protocol.md §7）。动作未落定另按提交
        // 上下文上报（QML 在途门控的相关性依据，见信号注释）。
        const QJsonObject error = event.value(QStringLiteral("error")).toObject();
        emit documentError(error.value(QStringLiteral("code")).toString(),
                           error.value(QStringLiteral("message")).toString());
        emit documentActionFailed(context.documentId, actionId(context.kind, context.preview));
        return;
    }
    if (type == QStringLiteral("task.completed")) {
        m_pendingByTask.erase(pending);
        handleCompleted(context, event.value(QStringLiteral("result")).toObject());
    }
}

void DocumentService::handleCompleted(const Pending &context, const QJsonObject &result) {
    // 陈旧任务丢弃的依据是 version 而非请求时序（总纲 §6.4 / §3.1）：提交时
    // 记录 documentId，完成时已切换文档的结果不再触碰任何文档状态。
    const bool stale = context.documentId != m_currentDocumentId;

    switch (context.kind) {
    case PendingKind::Save: {
        // save 写的是目标文件，与"当前文档"无关：切换文档后完成也如实上报；
        // 但只有保存的就是当前文档才清除未保存标记（§3.1：save 不改 version）。
        QString savedPath = result.value(QStringLiteral("path")).toString();
        if (savedPath.isEmpty())
            savedPath = context.path;
        if (!stale && m_documentModified) {
            m_documentModified = false;
            emit documentModifiedChanged();
        }
        emit documentSaved(savedPath);
        return;
    }
    case PendingKind::Adjust:
    case PendingKind::Transform:
    case PendingKind::ApplyTransform:
        if (stale)
            return;
        if (context.preview) {
            // 预览不改 version / modified（§3.2：result.version 为执行时版本）。
            emit previewReady(result);
            return;
        }
        applyCompletedVersion(result, true);
        return;
    case PendingKind::ApplyFilters:
        if (stale)
            return;
        if (context.preview) {
            // filter.preview 完成：result = {path, width, height, sha256,
            // preview_of, fingerprint}，不含 version（§3.1：预览不递增版本），
            // 只刷新画布。
            emit previewReady(result);
            return;
        }
        // filter.apply 完成：result = {version, width, height}（§3.1：全分辨率
        // 递增 version、置 modified；历史条目名 filter.apply，§3.3）。无像素
        // 文件，不发 previewReady。
        applyCompletedVersion(result, true);
        return;
    case PendingKind::ApplyAnnotate:
        if (stale)
            return;
        // image.annotate 完成（全分辨率，无预览形态）：result = {version,
        // width, height}（§2.3 全分辨率变更类一律携带 version；ops 参数化进
        // 历史条目，undo 重放归 Worker 端 HistoryEntry 参数化机制）。无像素
        // 文件，不发 previewReady——与 filter.apply 全分辨率同一处理。
        applyCompletedVersion(result, true);
        return;
    case PendingKind::Undo:
    case PendingKind::Redo:
        if (stale)
            return;
        applyCompletedVersion(result, true);
        // §3.3：undo/redo/reset 完成时写一份恢复后图像的降采样预览文件
        // "供画布立即刷新"，result 携带 path/sha256 —— 复用 previewReady 通道。
        emit previewReady(result);
        return;
    case PendingKind::Reset:
        if (stale)
            return;
        // §3.1：reset 同样 version += 1；但像素回到源图，modified 与 Worker
        // 端一致地清除（image_adapter.py reset 置 modified=False）——顶栏 ●
        // 熄灭、保存按钮禁用，与 image.metadata 的 modified 真值保持一致。
        applyCompletedVersion(result, false);
        emit previewReady(result);
        return;
    case PendingKind::Open:
    case PendingKind::History:
        return; // 同步动作不经事件通道，防御性忽略
    }
}

void DocumentService::applyOpened(const QString &path, const QJsonObject &result) {
    const QString documentId = result.value(QStringLiteral("document_id")).toString();
    if (documentId.isEmpty()) {
        // 成功响应必带 document_id（§3）；缺失视为协议违约，不得伪造状态。
        emit documentError(QStringLiteral("INTERNAL"),
                           QStringLiteral("image.open 响应缺少 document_id"));
        return;
    }
    const QString previousDocumentId = m_currentDocumentId;
    m_currentDocumentId = documentId;
    m_documentPath = path;
    emit currentDocumentChanged();
    if (m_currentVersion != 0) {
        m_currentVersion = 0; // §3.1：image.open 时 version = 0（重开新文档需复位）
        emit documentVersionChanged(m_currentVersion);
    }
    if (m_documentModified) {
        m_documentModified = false;
        emit documentModifiedChanged();
    }
    emit documentOpened(documentId, path, result.value(QStringLiteral("width")).toInt(0),
                        result.value(QStringLiteral("height")).toInt(0));
    SettingsService::instance()->addRecentFile(path);
    closePreviousDocument(previousDocumentId);
}

void DocumentService::closePreviousDocument(const QString &previousDocumentId) {
    if (previousDocumentId.isEmpty() || previousDocumentId == m_currentDocumentId || !m_backend)
        return;
    // 旧文档仍有在途任务（含尚未回执的提交）时不关：close 会让任务体内的
    // store.get 抛 UNKNOWN_DOCUMENT，把合法的保存/应用打成失败。被跳过的
    // 旧文档随下次切换或 Worker 退出回收（CHANGELOG 已知限制）。
    for (const auto &pending : m_pendingByTask) {
        if (pending.documentId == previousDocumentId)
            return;
    }
    for (const auto &pending : m_pendingByRequest) {
        if (pending.documentId == previousDocumentId)
            return;
    }
    // fire-and-forget：不登记 pending，响应（closed:true 或 UNKNOWN_DOCUMENT）
    // 落在未跟踪帧路径被忽略；同步 close 在 Worker 主循环内顺序执行，
    // 一定晚于刚完成的 image.open（§1：JSON Lines 顺序处理）。
    m_backend->sendAction(QStringLiteral("image.close"),
                          QJsonObject{{QStringLiteral("document_id"), previousDocumentId}});
}

void DocumentService::applyCompletedVersion(const QJsonObject &result, bool markModified) {
    // §3.1：全分辨率 adjust/transform 与 undo/redo/reset 完成时 result.version
    // 为新版本（undo/redo/reset 同样递增，与内容是否"回到旧值"无关）。
    const int version = result.value(QStringLiteral("version")).toInt(m_currentVersion);
    if (version != m_currentVersion) {
        m_currentVersion = version;
        emit documentVersionChanged(m_currentVersion);
    }
    // markModified=false 仅用于 reset（像素回到源图，无未保存修改，§3.3）；
    // 值不变不发射，避免瞬时 true→false 抖动（test_document_service 锁定）。
    if (m_documentModified != markModified) {
        m_documentModified = markModified;
        emit documentModifiedChanged();
    }
}

} // namespace toolbox
