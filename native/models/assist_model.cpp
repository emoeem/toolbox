#include "assist_model.h"

#include <QJsonArray>

namespace toolbox {

AssistModel::AssistModel(QObject *parent) : QAbstractListModel(parent) {}

void AssistModel::reloadFrom(const QJsonObject &assistListResult) {
    const QJsonArray tools = assistListResult.value(QStringLiteral("tools")).toArray();
    QVector<Entry> next;
    next.reserve(tools.size());
    for (const auto &value : tools) {
        const QJsonObject item = value.toObject();
        // 无 key 的条目既无法显示定位、也无法运行（key = 运行动作名，§3.8，
        // assist_model.h 头注释），防御性跳过（FilterModel / GeneratorModel
        // 对无 key 条目的同款处置，filter_model.cpp:16-19）。
        const QString key = item.value(QStringLiteral("key")).toString();
        if (key.isEmpty())
            continue;
        Entry entry;
        entry.key = key;
        entry.name = item.value(QStringLiteral("name")).toString();
        // category_label 是本地化显示名；缺省回落到 category 原值（同一条目
        // 至少有类别可显，filter.list / generate.list 两侧总成对出现的同一
        // 约定，filter_model.cpp:23-27）。
        entry.categoryLabel = item.value(QStringLiteral("category_label")).toString();
        if (entry.categoryLabel.isEmpty())
            entry.categoryLabel = item.value(QStringLiteral("category")).toString();
        entry.available = item.value(QStringLiteral("available")).toBool(false);
        for (const auto &dep : item.value(QStringLiteral("optional_deps")).toArray())
            entry.optionalDeps.append(dep.toString());
        next.append(entry);
    }

    beginResetModel();
    m_entries = next;
    endResetModel();
}

int AssistModel::rowCount(const QModelIndex &parent) const {
    return parent.isValid() ? 0 : m_entries.size();
}

QVariant AssistModel::data(const QModelIndex &index, int role) const {
    if (!index.isValid() || index.row() >= m_entries.size())
        return {};
    const auto &entry = m_entries.at(index.row());
    switch (role) {
    case ToolKeyRole:
        return entry.key;
    case ToolNameRole:
        return entry.name;
    case CategoryLabelRole:
        return entry.categoryLabel;
    case AvailableRole:
        return entry.available;
    case OptionalDepsRole:
        return entry.optionalDeps;
    default:
        return {};
    }
}

QHash<int, QByteArray> AssistModel::roleNames() const {
    return {
        {ToolKeyRole, "toolKey"},
        {ToolNameRole, "toolName"},
        {CategoryLabelRole, "categoryLabel"},
        {AvailableRole, "available"},
        {OptionalDepsRole, "optionalDeps"},
    };
}

} // namespace toolbox
