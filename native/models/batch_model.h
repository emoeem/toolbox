#pragma once

#include <QAbstractListModel>
#include <QHash>
#include <QJsonArray>
#include <QJsonObject>
#include <QVector>
#include <QtQml/qqml.h>

namespace toolbox {

// 批处理文件行（docs/toolbox-2.0-project-plan.md §9.4 批量处理工作区的"文件
// 列表、单项进度"与 docs/ui-component-spec.md BatchPage 的数据源）。行状态取
// 值固定为 "pending|running|done|failed|skipped"（任务清单锁定的 2.0 词汇）；
// 1.0 资产 processors/batch_filter_chain.py BatchItemStatus 的
// succeeded/cancelled → done/skipped 的映射归 Worker 侧，本模型原样存字符串。
//
// 模型自身不连 BackendManager（FilterModel/FilterChainModel 同款纯数据模型）：
// 装填入口 resetFrom（批次受理后整表重建，全部行起点 pending）、增量入口
// updateFrom（逐文件进度事件，按 file 行键定位）、收口 clear。取消收尾（整体
// 取消后残余未完成行归 skipped）由 BatchService 经 markActiveAs 完成，QML
// 无需感知该路径。
class BatchModel : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT

    // 行数与状态计数（进度汇总条 / "完成 n · 失败 m"，§9.4）。三者经同一
    // batchSummaryChanged 通知——它们总是随行状态一起变化，QML 三处绑定共用
    // 一个 notify 即可（值未变化的刷新不发射）。
    Q_PROPERTY(int totalCount READ totalCount NOTIFY batchSummaryChanged)
    Q_PROPERTY(int doneCount READ doneCount NOTIFY batchSummaryChanged)
    Q_PROPERTY(int failedCount READ failedCount NOTIFY batchSummaryChanged)

  public:
    struct Entry {
        QString file;       // 源文件路径（行键；协议字段 file）
        QString state;      // pending|running|done|failed|skipped
        int progress = 0;   // 0-100（单文件进度）
        QString error;      // 失败原因（state=failed 时有意义）
        QString outputPath; // 输出文件路径（state=done 时有意义）
    };

    enum Roles {
        BatchFileRole = Qt::UserRole + 1,
        BatchStateRole,
        BatchProgressRole,
        BatchErrorRole,
        BatchOutputPathRole,
    };

    explicit BatchModel(QObject *parent = nullptr);

    int totalCount() const { return m_entries.size(); }
    int doneCount() const;
    int failedCount() const;

    // 整表重建（beginResetModel）：entries 元素形状为
    // {file, state?, progress?, error?, output_path?}，state 缺省 "pending"、
    // progress 缺省 0。非对象元素与空 file 忽略（不造无名行）；progress 越界
    // 收敛到 0-100。
    Q_INVOKABLE void resetFrom(const QJsonArray &entries);

    // 逐行增量更新（BatchService 把批次任务的逐文件事件对象原样映射进来）：
    // progress 携带 file 作为行键；state/progress/error/output_path 字段按
    // "存在才更新"落地（QJsonValue undefined 检查），dataChanged 只携带真正
    // 变化的角色。未知 file 忽略（事件先于受理到达/跨批次迟到时不造行），
    // 无 file 字段的对象整体忽略。
    Q_INVOKABLE void updateFrom(const QJsonObject &progress);

    // 清空（新一轮批次配置前 QML 可显式调用；受理本身也会整表重建）。
    Q_INVOKABLE void clear();

    // BatchService 专用（C++ 调用，不入 QML）：把仍处 pending|running 的行
    // 统一置为 state——整体取消的收尾，对照 processors/batch_filter_chain.py
    // 第 63-66/94-97 行（残余 PENDING 与被中断的运行项一并 CANCELLED，2.0
    // 词汇即 skipped）；已终态的行（done/failed/skipped）保持原状。
    void markActiveAs(const QString &state);

    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

  signals:
    void batchSummaryChanged();

  private:
    int indexOfFile(const QString &file) const;
    // 行刷新后按 before/after 三元组决定是否发 batchSummaryChanged（值不变
    // 不发射——TaskModel::updateRow 的空操作契约同款，task_model.cpp:119-129）。
    void maybeEmitSummary(int totalBefore, int doneBefore, int failedBefore);

    QVector<Entry> m_entries;
};

} // namespace toolbox
