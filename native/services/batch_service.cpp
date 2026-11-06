#include "batch_service.h"

// 连接 BackendManager 的信号需要完整类型（batch_service.h 只有前置声明），
// 与 task_model.cpp / document_service.cpp 的包含次序同一约定。
#include "backend/backend_manager.h"
#include "backend/ipc_protocol.h"

namespace toolbox {

namespace {

BatchService *s_instance = nullptr; // process-wide singleton identity

} // namespace

BatchService::BatchService(QObject *parent)
    : QObject(parent), m_batchModel(new BatchModel(this)) {}

BatchService::~BatchService() {
    if (s_instance == this)
        s_instance = nullptr;
}

BatchService *BatchService::instance() {
    if (!s_instance)
        s_instance = new BatchService();
    return s_instance;
}

BatchService *BatchService::create(QQmlEngine *qmlEngine, QJSEngine *jsEngine) {
    // The instance must outlive the engine bindings; ownership stays with QML.
    Q_UNUSED(qmlEngine);
    Q_UNUSED(jsEngine);
    return instance();
}

void BatchService::bindBackend(BackendManager *backend) {
    if (m_backend == backend)
        return;
    m_backend = backend;
    if (!m_backend)
        return;
    connect(m_backend, &BackendManager::responseReady, this, &BatchService::onResponseReady);
    connect(m_backend, &BackendManager::taskEvent, this, &BatchService::onTaskEvent);
}

QString BatchService::startBatch(const QStringList &paths, const QString &outputDir,
                                 const QString &format, int quality, const QString &naming,
                                 const QString &pattern, const QJsonArray &steps) {
    // 本地拒绝（§9.4：文件与输出目录是批量批次的最小配置）与 DocumentService
    // 的空链拒绝同一契约：错误 + 恰好一次 batchError，且不上送（QML 门控的
    // 唯一解除路径）。
    if (paths.isEmpty()) {
        emit batchError(QStringLiteral("INVALID_PARAMS"), QStringLiteral("批量文件列表为空"));
        return {};
    }
    if (outputDir.isEmpty()) {
        emit batchError(QStringLiteral("INVALID_PARAMS"), QStringLiteral("输出目录为空"));
        return {};
    }
    if (!m_backend) {
        // BackendManager::errorOccurred 的 WORKER_START_FAILED 只覆盖进程层面；
        // 这里是调用层面未接线，归入未分类的内部错误（§5，document_service.cpp
        // 同款处置）。本次调用未发出，但 QML 可能已按"已提交"置位——如实上报。
        emit batchError(QStringLiteral("INTERNAL"),
                        QStringLiteral("后端未绑定，无法执行批量任务"));
        return {};
    }
    QJsonObject params{
        {QStringLiteral("paths"), QJsonArray::fromStringList(paths)},
        {QStringLiteral("output_dir"), outputDir},
        {QStringLiteral("format"), format},
        {QStringLiteral("naming"), naming},
        {QStringLiteral("pattern"), pattern},
        {QStringLiteral("steps"), steps},
    };
    if (quality >= 0)
        params.insert(QStringLiteral("quality"), quality);
    const QString requestId =
        m_backend->sendAction(QStringLiteral("batch.start"), params);
    // 受理上下文只登记在 m_pendingByRequest；m_activeRequestId 留给受理响应
    // 登记（onResponseReady）——在途提交号不进翻译键，避免拒绝后误翻译。
    if (!requestId.isEmpty())
        m_pendingByRequest.insert(requestId, Pending{paths});
    return requestId;
}

void BatchService::cancelBatch(const QString &taskId) {
    if (taskId.isEmpty() || !m_backend)
        return;
    // 提交号翻译：startBatch 同步返回 request_id，受理后自动翻译成 task_id，
    // QML 两种令牌都能传（翻译仅在活动批次上成立，其余 id 原样转发）。
    const QString target =
        (taskId == m_activeRequestId && !m_taskId.isEmpty()) ? m_taskId : taskId;
    m_backend->cancelTask(target);
}

void BatchService::onResponseReady(const QString &requestId, const QJsonObject &message) {
    const auto pending = m_pendingByRequest.constFind(requestId);
    if (pending == m_pendingByRequest.cend())
        return; // 未跟踪请求（worker.hello 归 BackendManager；image.* 归
                // DocumentService、filter.* 归 FilterService 各自关联）

    const Pending context = pending.value();
    m_pendingByRequest.erase(pending);

    if (!ipc::IpcProtocol::isSuccess(message)) {
        // 提交前同步拒绝（UNKNOWN_ACTION / INVALID_PARAMS / FILE 系列等，§5）。
        // 不受理就不造行：batchModel 保持现状（上一批次或空），不伪造进度。
        // m_activeRequestId 不动——被拒的提交号没有产生任务，绝不进入翻译键。
        const QJsonObject error = ipc::IpcProtocol::errorOf(message);
        emit batchError(error.value(QStringLiteral("code")).toString(),
                        error.value(QStringLiteral("message")).toString());
        return;
    }

    const QString taskId =
        ipc::IpcProtocol::resultOf(message).value(QStringLiteral("task_id")).toString();
    if (taskId.isEmpty()) {
        // 协议违约：batch.start 是异步动作，成功响应必带 task_id（§2.3）；
        // 不伪造受理——该提交永远不会有事件跟进，必须按未落定上报。
        emit batchError(QStringLiteral("INTERNAL"),
                        QStringLiteral("batch.start 响应缺少 task_id"));
        return;
    }

    // 受理（§2.3）：单活动批次语义——新批次覆盖旧跟踪（更早批次的迟到事件按
    // task_id 不匹配被忽略），整表重建为全 pending 行；受理来源提交号同步
    // 登记，startBatch 的返回值从此翻译到本批次。
    m_taskId = taskId;
    m_activeRequestId = requestId;
    QJsonArray entries;
    for (const QString &path : context.paths)
        entries.append(QJsonObject{{QStringLiteral("file"), path}});
    m_batchModel->resetFrom(entries);
    emit batchStarted(taskId);
}

void BatchService::onTaskEvent(const QJsonObject &event) {
    const QString type = event.value(QStringLiteral("type")).toString();
    const QString taskId = ipc::IpcProtocol::eventTaskId(event);
    if (taskId.isEmpty() || taskId != m_taskId)
        return; // 未知/过期批次的迟到事件（单活动批次语义）

    if (type == QStringLiteral("task.progress")) {
        // 逐文件进度：事件对象携带 file（行键）与 state/progress/error/
        // output_path 增量字段，原样映射进行（BatchModel::updateFrom）。
        // 无 file 的纯整体进度帧在此被忽略——整体进度由 UI 以
        // batchSummaryChanged 的计数推导，不做第二真相源。
        m_batchModel->updateFrom(event);
        return;
    }
    if (type == QStringLiteral("task.failed")) {
        m_taskId.clear(); // 终态
        const QJsonObject error = event.value(QStringLiteral("error")).toObject();
        const QString code = error.value(QStringLiteral("code")).toString();
        if (code == QStringLiteral("CANCELLED")) {
            // §7：取消以 task.failed + CANCELLED 呈现。残余未完成行收尾为
            // skipped（processors/batch_filter_chain.py 取消时把 PENDING 与
            // 被中断项一并置 CANCELLED 的 2.0 词汇映射）；已终态行保持原状。
            m_batchModel->markActiveAs(QStringLiteral("skipped"));
        }
        // 非 CANCELLED 失败：行保持逐文件事件的最后已知状态（失败文件若由
        // 完成侧补登，见 task.completed 的 items 刷新；整体失败批次没有
        // completed 事件，行状态如实停在最后一帧）。
        emit batchError(code, error.value(QStringLiteral("message")).toString());
        return;
    }
    if (type == QStringLiteral("task.completed")) {
        m_taskId.clear(); // 终态
        // 完成结果可选携带 items 全量数组（{file, state, progress?, error?,
        // output_path?}）：把逐文件事件遗漏的终态（如整体失败文件、输出路径）
        // 一次补齐；未携带 items 时行保持已收敛状态，不空转重置。
        const QJsonArray items =
            event.value(QStringLiteral("result")).toObject()
                .value(QStringLiteral("items"))
                .toArray();
        if (!items.isEmpty())
            m_batchModel->resetFrom(items);
        emit batchFinished(taskId);
        return;
    }
}

} // namespace toolbox
