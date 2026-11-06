#include "filter_service.h"

// 连接 BackendManager 的信号需要完整类型（filter_service.h 只有前置声明），
// 与 document_service.cpp 的包含次序同一约定。
#include "backend/backend_manager.h"
#include "backend/ipc_protocol.h"
#include "core/document_service.h"

namespace toolbox {

namespace {

FilterService *s_instance = nullptr; // process-wide singleton identity

} // namespace

FilterService::FilterService(QObject *parent)
    : QObject(parent), m_filterModel(new FilterModel(this)),
      m_chainModel(new FilterChainModel(this)) {}

FilterService::~FilterService() {
    if (s_instance == this)
        s_instance = nullptr;
}

FilterService *FilterService::instance() {
    if (!s_instance)
        s_instance = new FilterService();
    return s_instance;
}

FilterService *FilterService::create(QQmlEngine *qmlEngine, QJSEngine *jsEngine) {
    // The instance must outlive the engine bindings; ownership stays with QML.
    Q_UNUSED(qmlEngine);
    Q_UNUSED(jsEngine);
    return instance();
}

void FilterService::bindBackend(BackendManager *backend) {
    if (m_backend == backend)
        return;
    m_backend = backend;
    if (!m_backend)
        return;
    connect(m_backend, &BackendManager::responseReady, this, &FilterService::onResponseReady);
}

QString FilterService::sendTracked(PendingKind kind, const QString &action,
                                   const QJsonObject &params, const QString &name) {
    if (!m_backend) {
        // BackendManager::errorOccurred 的 WORKER_START_FAILED 只覆盖进程层面；
        // 这里是调用层面未接线，归入未分类的内部错误（§5，document_service.cpp
        // 同款处置）。本次调用未发出，但 QML 可能已按"已提交"置位——如实上报。
        emit filterError(QStringLiteral("INTERNAL"),
                         QStringLiteral("后端未绑定，无法执行滤镜操作"));
        return {};
    }
    const QString requestId = m_backend->sendAction(action, params);
    if (!requestId.isEmpty())
        m_pendingByRequest.insert(requestId, Pending{kind, name});
    return requestId;
}

void FilterService::setLoadingFilters(bool loading) {
    if (m_loadingFilters == loading)
        return;
    m_loadingFilters = loading;
    emit loadingFiltersChanged();
}

void FilterService::loadFilters() {
    // 未发出（未绑定后端）不进入在途状态——loadingFilters 只描述真实在途的
    // filter.list；成功/失败响应都会收掉标志（onResponseReady FilterList 分支）。
    const QString requestId =
        sendTracked(PendingKind::FilterList, QStringLiteral("filter.list"), {});
    if (!requestId.isEmpty())
        setLoadingFilters(true);
}

QVariantList FilterService::presetsList() {
    // 调用即刷新（fire-and-forget）：返回缓存供首次渲染，真实列表随响应经
    // presetsChanged 交付。
    sendTracked(PendingKind::PresetsList, QStringLiteral("filter.presets.list"), {});
    return m_presets;
}

void FilterService::savePreset(const QString &name) {
    // 与 Worker 端 save_preset 一致（filter_presets.py:83-84）：名称不能为空；
    // 本地先拒，不上送。
    if (name.trimmed().isEmpty()) {
        emit filterError(QStringLiteral("INVALID_PARAMS"), QStringLiteral("预设名称不能为空"));
        return;
    }
    QJsonObject params{
        {QStringLiteral("name"), name},
        {QStringLiteral("steps"), currentChainSteps()},
    };
    sendTracked(PendingKind::PresetSave, QStringLiteral("filter.presets.save"), params, name);
}

void FilterService::loadPreset(const QString &name) {
    if (name.trimmed().isEmpty()) {
        emit filterError(QStringLiteral("INVALID_PARAMS"), QStringLiteral("预设名称不能为空"));
        return;
    }
    sendTracked(PendingKind::PresetLoad, QStringLiteral("filter.presets.load"),
                QJsonObject{{QStringLiteral("name"), name}}, name);
}

void FilterService::deletePreset(const QString &name) {
    if (name.trimmed().isEmpty()) {
        emit filterError(QStringLiteral("INVALID_PARAMS"), QStringLiteral("预设名称不能为空"));
        return;
    }
    sendTracked(PendingKind::PresetDelete, QStringLiteral("filter.presets.delete"),
                QJsonObject{{QStringLiteral("name"), name}}, name);
}

void FilterService::refreshPresets() {
    sendTracked(PendingKind::PresetsList, QStringLiteral("filter.presets.list"), {});
}

void FilterService::previewChain(int maxSide) {
    DocumentService::instance()->applyFilters(currentChainSteps(), true, maxSide);
}

void FilterService::applyChain() {
    DocumentService::instance()->applyFilters(currentChainSteps(), false, -1);
}

QJsonArray FilterService::currentChainSteps() const {
    // 链顺序即 steps 顺序（filter_adapter.build_chain 按数组顺序构造链）。
    // data() 返回 QVariant，经 QJsonValue::fromVariant 显式落回 JSON 类型。
    QJsonArray steps;
    for (int row = 0; row < m_chainModel->stepCount(); ++row) {
        const auto modelIndex = m_chainModel->index(row);
        steps.append(QJsonObject{
            {QStringLiteral("filter_key"),
             QJsonValue::fromVariant(modelIndex.data(FilterChainModel::ChainFilterKeyRole))},
            {QStringLiteral("params"),
             QJsonValue::fromVariant(modelIndex.data(FilterChainModel::ChainParamsRole))},
            {QStringLiteral("enabled"),
             QJsonValue::fromVariant(modelIndex.data(FilterChainModel::ChainEnabledRole))},
        });
    }
    return steps;
}

void FilterService::onResponseReady(const QString &requestId, const QJsonObject &message) {
    const auto pending = m_pendingByRequest.constFind(requestId);
    if (pending == m_pendingByRequest.cend())
        return; // 未跟踪请求（worker.hello 归 BackendManager；image.* 与
                // filter.preview/apply 归 DocumentService 各自关联）

    const Pending context = pending.value();
    m_pendingByRequest.erase(pending);

    if (!ipc::IpcProtocol::isSuccess(message)) {
        // 同步拒绝（UNKNOWN_ACTION / INVALID_PARAMS / FILE 系列等，§5）：动作
        // 未落定，只报错不改任何状态。FilterList 的在途标志一并收掉。
        if (context.kind == PendingKind::FilterList)
            setLoadingFilters(false);
        const QJsonObject error = ipc::IpcProtocol::errorOf(message);
        emit filterError(error.value(QStringLiteral("code")).toString(),
                         error.value(QStringLiteral("message")).toString());
        return;
    }

    const QJsonObject result = ipc::IpcProtocol::resultOf(message);
    switch (context.kind) {
    case PendingKind::FilterList: {
        setLoadingFilters(false);
        m_filterModel->reloadFrom(result);
        return;
    }
    case PendingKind::PresetsList: {
        m_presets = result.value(QStringLiteral("presets")).toArray().toVariantList();
        emit presetsChanged();
        return;
    }
    case PendingKind::PresetSave: {
        // 成功后自动刷新缓存，QML 只需听 presetsChanged / presetSaved。
        emit presetSaved(context.name);
        refreshPresets();
        return;
    }
    case PendingKind::PresetLoad: {
        const QJsonArray steps = result.value(QStringLiteral("steps")).toArray();
        m_chainModel->replaceFrom(steps);
        emit presetLoaded(steps.toVariantList());
        return;
    }
    case PendingKind::PresetDelete: {
        emit presetDeleted(context.name);
        refreshPresets();
        return;
    }
    }
}

} // namespace toolbox
