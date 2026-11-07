#pragma once

#include <QAbstractListModel>
#include <QJsonObject>
#include <QStringList>
#include <QVariant>
#include <QVector>
#include <QtQml/qqml.h>

namespace toolbox {

// 生成器目录行（Texture Studio 数据源，docs/toolbox-2.0-project-plan.md §9.7
// "生成器和预设列表"；docs/ui-page-spec.md §5 TexturePage 左栏）。数据由
// StudioService 从 generate.list 的同步响应经 reloadFrom() 填入：result =
// {generators: [{key, name, category, category_label, available, optional_deps,
// params}]}——形状与 §3 filter.list 同构（目录类同步动作的既有词汇）。generate.*
// 尚未写入 docs/ipc-protocol.md §3（诚实范围：本批任务只覆盖 native 侧，与
// test_batch_service.cpp 头注释对 batch.start 的处理同一模式）；Worker 端落地
// 时按此形状同步（总纲 §16.3 三端同步规则），非空目录 TODAY 由测试固件锁定。
//
// 模型自身不连 BackendManager：填充入口只有 reloadFrom（FilterModel::reloadFrom
// 同款模式，filter_model.cpp:10-40），空对象/缺 generators 字段视为清空，不抛错。
// UI 不硬编码任何生成器参数表——参数定义原样以 paramsJson 交给参数组件自动
// 生成控件（user-flows.md 流程 2 的同一约束在 Studio 页的延续）。
class GeneratorModel : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT

  public:
    struct Entry {
        QString key;            // 协议字段 key（generate.render 的 generator_key）
        QString name;           // 协议字段 name（显示名，"title"）
        QString categoryLabel;  // 协议字段 category_label（缺省回落 category 原值）
        QString paramsJson;     // 协议字段 params 数组的紧凑 JSON 文本（参数定义）
        bool available = false; // 协议字段 available（缺可选依赖时 false → 置灰，
                                // §9.7 "G'MIC 缺失时该生成器置灰"）
        QStringList optionalDeps; // 协议字段 optional_deps（置灰原因，如 "gmic"）
    };

    enum Roles {
        GeneratorKeyRole = Qt::UserRole + 1,
        GeneratorNameRole,
        CategoryLabelRole,
        ParamsJsonRole,
        AvailableRole,
        OptionalDepsRole,
    };

    explicit GeneratorModel(QObject *parent = nullptr);

    // 整表重建（beginResetModel）：以最近一次 generate.list 结果为准；缺失的
    // available 按不可用处理（宁可置灰，不谎称可用——FilterModel 同款语义）。
    Q_INVOKABLE void reloadFrom(const QJsonObject &generateListResult);

    // 搜索：对 name（title）与关键词（key / category_label / optional_deps，
    // 总集拼串）做大小写不敏感的包含匹配；空查询返回全部条目。返回 QVariantMap
    // 列表（键与角色同名），可直接作 QML ListView 模型（FilterModel::search
    // 同款，filter_model.cpp:42-61）。
    Q_INVOKABLE QVariantList search(const QString &query) const;

    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

  private:
    static QVariantMap entryToVariantMap(const Entry &entry);

    QVector<Entry> m_entries;
};

} // namespace toolbox
