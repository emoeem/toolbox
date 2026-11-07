#pragma once

#include <QAbstractListModel>
#include <QJsonObject>
#include <QStringList>
#include <QVariant>
#include <QVector>
#include <QtQml/qqml.h>

namespace toolbox {

// 滤镜目录行（docs/ipc-protocol.md §3 filter.list；docs/ui-component-spec.md §3
// AppFilterCard / AppFilterParameterGroup 的数据源）。数据由 FilterService 从
// filter.list 的同步响应经 reloadFrom() 填入：result = {filters: [{key, name,
// category, category_label, description, available, optional_deps, params}]}
// （Worker 端形状见 python_worker/adapters/filter_adapter.py:21-38）。
//
// 模型自身不连 BackendManager：填充入口只有 reloadFrom（HistoryModel::refreshFrom
// 同款模式，history_model.cpp:10-39），空对象/缺 filters 字段视为清空，不抛错。
// UI 不硬编码任何滤镜参数表（docs/user-flows.md 流程 2 关键约束）——参数定义
// 原样以 paramsJson 交给 AppFilterParameterGroup 自动生成控件。
class FilterModel : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT

  public:
    struct Entry {
        QString key;              // 协议字段 key（filter.preview/apply 的 filter_key）
        QString name;             // 协议字段 name（显示名，"title"）
        QString categoryLabel;    // 协议字段 category_label（缺省回落 category 原值）
        QString paramsJson;       // 协议字段 params 数组的紧凑 JSON 文本
        bool available = false;   // 协议字段 available（缺可选依赖时 false → 置灰）
        QStringList optionalDeps; // 协议字段 optional_deps（置灰原因，如 "gmic"）
        QString description;      // 协议字段 description
    };

    enum Roles {
        FilterKeyRole = Qt::UserRole + 1,
        FilterNameRole,
        CategoryLabelRole,
        ParamsJsonRole,
        AvailableRole,
        OptionalDepsRole,
        DescriptionRole,
    };

    explicit FilterModel(QObject *parent = nullptr);

    // 整表重建（beginResetModel）：以最近一次 filter.list 结果为准；缺失的
    // available 按不可用处理（宁可置灰，不谎称可用）。
    Q_INVOKABLE void reloadFrom(const QJsonObject &filterListResult);

    // 搜索：对 name（title）与关键词（key / category_label / description /
    // optional_deps，总集拼串）做大小写不敏感的包含匹配；空查询返回全部条目。
    // 返回 QVariantMap 列表（键与角色同名），可直接作 QML ListView 模型。
    Q_INVOKABLE QVariantList search(const QString &query) const;

    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

  private:
    static QVariantMap entryToVariantMap(const Entry &entry);

    QVector<Entry> m_entries;
};

} // namespace toolbox
