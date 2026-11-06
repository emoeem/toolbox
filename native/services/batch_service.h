#pragma once

#include <QHash>
#include <QJsonArray>
#include <QJsonObject>
#include <QObject>
#include <QString>
#include <QStringList>
#include <QtQml/qqml.h>

// BatchModel 必须完整包含：Q_PROPERTY 的指针类型在 moc 生成的元类型注册代码里
// 做 sizeof（document_service.h:11-14 / filter_service.h:11-15 同款 CI 实证），
// 前置声明不够；#include 只能放在 namespace 之外——放进 namespace 会把整个
// Qt 头展开进 toolbox（CI 实证）。BackendManager 只出现在 Q_INVOKABLE 参数里
// （document_service.h:18 同款前置声明即可），其完整类型在 .cpp 引入。
#include "models/batch_model.h"

namespace toolbox {

class BackendManager;

// 批量页 facade（docs/toolbox-2.0-project-plan.md §9.4 批量处理工作区，
// ui/pages/BatchPage.qml 的数据源）：batchModel（文件行）+ startBatch
// （batch.start 异步提交）+ cancelBatch（task.cancel 转发，§7 取消语义）。
//
// 关联模式与 DocumentService（document_service.cpp:266-305）同款 tracked
// dispatch：startBatch 把 request_id 记入 m_pendingByRequest；受理响应按
// request_id 取回提交上下文（源文件清单），整表重建 batchModel（全部行起点
// pending）并交付 batchStarted(taskId)。此后该批次的任务事件按 task_id 关联：
// 逐文件进度事件原样映射 BatchModel::updateFrom；完成事件的 result.items（若
// 携带）整表刷新补登失败文件；失败事件按错误码收尾——CANCELLED 把残余
// pending/running 行归 skipped（processors/batch_filter_chain.py 取消语义的
// 2.0 词汇映射），其余错误行保持最后已知状态。
//
// 单活动批次：batchModel 是单一视图，服务只跟踪最近一次受理的 task_id；受理
// 新批次即覆盖旧跟踪，更早批次的迟到事件按 task_id 不匹配忽略（TaskModel 对
// 未知 task_id 的处置同款，task_model.cpp:84-86）。
class BatchService : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    // 由本服务创建并持有（FilterService::filterModel 同款，CONSTANT：实例与
    // 进程同寿命，指针身份不变）。
    Q_PROPERTY(BatchModel *batchModel READ batchModel CONSTANT)

  public:
    explicit BatchService(QObject *parent = nullptr);
    ~BatchService() override;

    // Process-wide instance getter + QML singleton factory，与 FilterService
    // （filter_service.h:56-57）同款：QML 查找与 C++ 接线必须拿到同一对象。
    static BatchService *instance();
    static BatchService *create(QQmlEngine *qmlEngine, QJSEngine *jsEngine);

    BatchModel *batchModel() const { return m_batchModel; }

    // DocumentService::bindBackend 同款（document_service.cpp:38-46）：QML 侧
    // BatchService.bindBackend(Application.backend) 完成接线；幂等重绑无害。
    // 未绑定时 startBatch 如实报错（batchError INTERNAL），绝不伪造提交。
    Q_INVOKABLE void bindBackend(BackendManager *backend);

    // batch.start（async，受理模式见 docs/ipc-protocol.md §2.3）：paths/
    // output_dir/format/naming/pattern/steps 原样上送；quality < 0 时省略
    // quality 字段（image.save 同款约定，document_service.cpp:157-158）；
    // steps 允许为空（纯格式转换批次，对应 1.0 batch 面板 convert 模式）。
    //
    // 返回值为提交关联号 request_id（空 = 本地拒绝，未上送）。协议受理是异步
    // 的（§2.3：task_id 只随响应到达），无法同步返回 task_id——Worker 受理后
    // 的真实 task_id 经 batchStarted(taskId) 交付；cancelBatch 两者都接受
    // （提交号在受理后自动翻译成 task_id）。
    // 本地拒绝（paths 为空 / outputDir 为空 / 后端未绑定）：emit batchError
    // 且恰好一次、不上送（DocumentService::applyFilters 空链拒绝同款契约，
    // document_service.cpp:196-204）。
    Q_INVOKABLE QString startBatch(const QStringList &paths, const QString &outputDir,
                                   const QString &format, int quality, const QString &naming,
                                   const QString &pattern, const QJsonArray &steps);

    // task.cancel 转发（TaskModel::cancelTask 的转发路径同款，
    // task_model.cpp:47-48）：行状态不在本地翻转，由 CANCELLED task.failed
    // 事件统一驱动（§7）。taskId 接受 batchStarted 交付的 task_id，也接受
    // 当前活动批次的受理来源提交号（翻译见 m_activeRequestId）。未绑定后端 /
    // 空 id 为本地 no-op；其余未知 id 原样转发（Worker 报 UNKNOWN_TASK，§5）。
    Q_INVOKABLE void cancelBatch(const QString &taskId);

  signals:
    // 受理响应落地（result.task_id）——task_id 的唯一交付路径（§2.3）。
    void batchStarted(const QString &taskId);
    // task.completed 落地：批次终态，行数据已按 result.items 或逐文件事件
    // 收敛（§9.4 "完成后打开输出目录"入口挂本信号）。
    void batchFinished(const QString &taskId);
    // code/message 见 docs/ipc-protocol.md §5：本地拒绝（INVALID_PARAMS /
    // INTERNAL）、提交前同步拒绝、task.failed、协议违约（INTERNAL）。纯用户
    // 呈现（Toast）；行状态收敛归 batchModel，本信号不携带行上下文。
    void batchError(const QString &code, const QString &message);

  private slots:
    void onResponseReady(const QString &requestId, const QJsonObject &message);
    void onTaskEvent(const QJsonObject &event);

  private:
    struct Pending {
        QStringList paths; // 提交的源文件清单（受理后整表重建行的依据）
    };

    BackendManager *m_backend = nullptr;
    BatchModel *m_batchModel = nullptr;       // 本服务创建并持有
    QHash<QString, Pending> m_pendingByRequest; // request_id → 提交上下文
    QString m_activeRequestId; // 当前活动批次的受理来源提交号（受理时登记，
                               // cancelBatch 把 startBatch 返回值翻译成
                               // task_id 的键；被同步拒绝的提交号绝不翻译
                               // ——它们没有产生任务，翻译会误伤上一批次）
    QString m_taskId;          // 最近一次受理的批次任务（空 = 无活动批次）
};

} // namespace toolbox
