#pragma once

#include <QAbstractListModel>
#include <QJsonArray>
#include <QJsonObject>
#include <QVector>
#include <QtQml/qqml.h>

namespace toolbox {

// 滤镜链行（docs/ui-component-spec.md §3 AppFilterChainItem：启用开关、名称、
// 参数摘要、上移/下移/删除）。行数据与协议 filter.preview/apply 的 steps 数组
// 元素一一对应：{filter_key, params, enabled}（docs/ipc-protocol.md §3；
// processors/filter_chain.py FilterStep.from_dict 的 enabled 缺省 true）。
//
// 模型自身不连 BackendManager：装填入口 replaceFrom（FilterService 载入预设与
// 测试用），编辑入口 addStep/removeRow/moveUp/moveDown/setEnabled 供 QML 直接
// 调用；previewChain/applyChain 的序列化在 FilterService 一侧按行读回。
class FilterChainModel : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT

    // 当前行数（AppFilterChainItem 徽标、空链提示与 FilterService 组装 steps
    // 的遍历上界）。仅在行数真正变化时通知。
    Q_PROPERTY(int stepCount READ stepCount NOTIFY stepCountChanged)

  public:
    struct Step {
        QString key;        // filter_key
        QJsonObject params; // 参数对象（协议原样，链内不校验——校验归 Worker）
        bool enabled = true;
    };

    enum Roles {
        ChainFilterKeyRole = Qt::UserRole + 1,
        ChainParamsRole,
        ChainEnabledRole,
        ChainIndexRole,
    };

    explicit FilterChainModel(QObject *parent = nullptr);

    // 整链重建（beginResetModel）：steps 元素缺 filter_key 的跳过；缺 params
    // 记为空对象；缺 enabled 按协议缺省 true（FilterStep.from_dict 语义）。
    // stepCount 仅在行数变化时通知。
    Q_INVOKABLE void replaceFrom(const QJsonArray &steps);

    // 追加一步（enabled=true）。key 为空时忽略（无 key 的步骤无法提交）。
    Q_INVOKABLE void addStep(const QString &key, const QJsonObject &params = {});

    // 越界行号静默忽略（QML 侧先于模型知道行号的竞态下不抛错）。
    Q_INVOKABLE void removeRow(int row);
    Q_INVOKABLE void moveUp(int row);
    Q_INVOKABLE void moveDown(int row);
    // 同值写入不发射 dataChanged（TaskModel::updateRow 同款防抖纪律）。
    Q_INVOKABLE void setEnabled(int row, bool enabled);

    int stepCount() const { return m_steps.size(); }

    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

  signals:
    void stepCountChanged();

  private:
    QVector<Step> m_steps;
};

} // namespace toolbox
