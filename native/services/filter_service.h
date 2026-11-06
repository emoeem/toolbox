#pragma once

#include <QHash>
#include <QJsonArray>
#include <QJsonObject>
#include <QObject>
#include <QString>
#include <QVariant>
#include <QtQml/qqml.h>

// FilterModel / FilterChainModel 是属性与返回值里的指针类型：moc 生成的元类型
// 注册代码需要完整类型（document_service.h:10-13 同款 CI 实证），前置声明不够；
// #include 必须放在 namespace 之外。
#include "models/filter_chain_model.h"
#include "models/filter_model.h"

namespace toolbox {

class BackendManager;

// 滤镜页 facade（docs/user-flows.md 流程 2、docs/ui-component-spec.md §3/§4）：
// filterModel（filter.list 目录）+ chainModel（当前滤镜链）+ 预设（
// filter.presets.*）+ 预览/应用委托（filter.preview / filter.apply 经
// DocumentService::applyFilters，版本语义与任务行登记都在那一层）。
//
// 关联模式与 DocumentService（document_service.cpp:230-269）同款 tracked
// dispatch：每个 Q_INVOKABLE 在 sendAction 时把 request_id 记入
// m_pendingByRequest，同步响应按 request_id 取回上下文；未跟踪帧（worker.hello、
// image.*、filter.preview/apply 的异步受理与事件）一律忽略——filter.* 的
// 预览/应用任务归 DocumentService 关联，本服务绝不越权认领。
//
// 预设动作（filter.presets.list/save/load/delete）是 docs/ipc-protocol.md §3.4
// 的同步动作：无 task_id、不产生任务行（TaskModel 不登记）、与文档版本无关。
// fire-and-forget 关联模式（同上）：调用即发送，结果经信号交付——presetsList()
// 返回最近一次缓存（响应到达后 presetsChanged 通知），loadPreset 的 steps 经
// presetLoaded 交付并写入 chainModel（fire-and-forget 模式下同步返回值拿不到
// 响应数据）。
class FilterService : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    // 两个子模型由本服务创建并持有（QML 只读引用，CONSTANT：实例与进程
    // 同寿命，指针身份不变）。
    Q_PROPERTY(FilterModel *filterModel READ filterModel CONSTANT)
    Q_PROPERTY(FilterChainModel *chainModel READ chainModel CONSTANT)
    // filter.list 在途（loadFilters 发出 → 响应落定）；未绑定后端时恒 false。
    Q_PROPERTY(bool loadingFilters READ loadingFilters NOTIFY loadingFiltersChanged)

  public:
    explicit FilterService(QObject *parent = nullptr);
    ~FilterService() override;

    // Process-wide instance getter + QML singleton factory，与 DocumentService
    // （document_service.h:65-76）同款：QML 查找与 C++ 接线必须拿到同一对象。
    static FilterService *instance();
    static FilterService *create(QQmlEngine *qmlEngine, QJSEngine *jsEngine);

    FilterModel *filterModel() const { return m_filterModel; }
    FilterChainModel *chainModel() const { return m_chainModel; }
    bool loadingFilters() const { return m_loadingFilters; }

    // DocumentService::bindBackend 同款（document_service.cpp:38-46）：QML 侧
    // FilterService.bindBackend(Application.backend) 完成接线；幂等重绑无害。
    Q_INVOKABLE void bindBackend(BackendManager *backend);

    // filter.list（sync）：成功响应经 filterModel->reloadFrom 落地；成败都收
    // loadingFilters（false）。后端未绑定时只发 filterError(INTERNAL)。
    Q_INVOKABLE void loadFilters();

    // ---- 预设（filter.presets.*，docs/ipc-protocol.md §3.4，fire-and-forget）----
    // 读取：发送 filter.presets.list 并返回最近一次缓存的列表（QVariantMap：
    // {name, step_count}，协议只暴露这两个字段）；响应到达后更新缓存并 emit
    // presetsChanged——QML 需要重新读取（绑定式调用注意别在 presetsChanged
    // 里再触发 presetsList，防自激）。
    Q_INVOKABLE QVariantList presetsList();

    // 保存：chainModel 当前链序列化为 steps（{filter_key, params, enabled}）
    // + name 经 filter.presets.save 上送；成功 emit presetSaved(name) 并自动
    // 刷新预设缓存。name 为空在本地拒绝（filterError）。
    Q_INVOKABLE void savePreset(const QString &name);

    // 加载：name 经 filter.presets.load 上送；成功后 steps 写入 chainModel
    // （replaceFrom）并 emit presetLoaded(steps)——fire-and-forget 下这是
    // steps 的唯一交付路径。
    Q_INVOKABLE void loadPreset(const QString &name);

    // 删除：name 经 filter.presets.delete 上送；成功 emit presetDeleted(name)
    // 并自动刷新预设缓存。
    Q_INVOKABLE void deletePreset(const QString &name);

    // ---- 预览/应用委托（组装链 → DocumentService::applyFilters）----
    // previewChain：preview=true，maxSide < 0 时由 Worker 取缺省 768（§3.2
    // 同一语义）；applyChain：preview=false 全分辨率。空链经
    // DocumentService::applyFilters 本地拒绝（INVALID_PARAMS + actionFailed），
    // 本层不重复拦截。
    Q_INVOKABLE void previewChain(int maxSide = -1);
    Q_INVOKABLE void applyChain();

  signals:
    // code/message 见 docs/ipc-protocol.md §5（含未绑定后端的 INTERNAL、预设
    // 动作的同步错误）。纯用户呈现（Toast）；预览/应用失败另有
    // DocumentService::documentActionFailed 的在途门控通道。
    void filterError(const QString &code, const QString &message);

    // 预设缓存已更新（presetsList 响应 / save、delete 成功后的自动刷新）。
    void presetsChanged();
    void presetSaved(const QString &name);
    // 预设已写入 chainModel；steps 为该预设的 {filter_key, params, enabled}
    // 数组（QVariantMap 列表），供调用方高亮/回显。
    void presetLoaded(const QVariantList &steps);
    void presetDeleted(const QString &name);
    void loadingFiltersChanged();

  private slots:
    void onResponseReady(const QString &requestId, const QJsonObject &message);

  private:
    enum class PendingKind { FilterList, PresetsList, PresetSave, PresetLoad, PresetDelete };

    struct Pending {
        PendingKind kind = PendingKind::FilterList;
        QString name; // 预设操作的目标名
    };

    // 同步动作发送（fire-and-forget 不登记 TaskModel；响应按 request_id 关联）。
    // 后端未绑定时发 filterError(INTERNAL) 并返回空 id。
    QString sendTracked(PendingKind kind, const QString &action, const QJsonObject &params,
                        const QString &name = {});

    // savePreset/deletePreset 成功后的缓存刷新（filter.presets.list 再来一发）。
    void refreshPresets();
    void setLoadingFilters(bool loading);

    // chainModel 当前链 → 协议 steps 数组（链顺序即数组顺序）。
    QJsonArray currentChainSteps() const;

    BackendManager *m_backend = nullptr;
    FilterModel *m_filterModel = nullptr;
    FilterChainModel *m_chainModel = nullptr;
    QHash<QString, Pending> m_pendingByRequest; // request_id → 提交上下文
    QVariantList m_presets;                     // 最近一次 filter.presets.list 的缓存
    bool m_loadingFilters = false;
};

} // namespace toolbox
