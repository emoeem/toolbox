#include "filter_model.h"

#include <QJsonArray>
#include <QJsonDocument>

namespace toolbox {

FilterModel::FilterModel(QObject *parent) : QAbstractListModel(parent) {}

void FilterModel::reloadFrom(const QJsonObject &filterListResult) {
    const QJsonArray filters = filterListResult.value(QStringLiteral("filters")).toArray();
    QVector<Entry> next;
    next.reserve(filters.size());
    for (const auto &value : filters) {
        const QJsonObject item = value.toObject();
        // 无 key 的条目无法在 filter.preview/apply 中引用，防御性跳过。
        const QString key = item.value(QStringLiteral("key")).toString();
        if (key.isEmpty())
            continue;
        Entry entry;
        entry.key = key;
        entry.name = item.value(QStringLiteral("name")).toString();
        // category_label 是本地化显示名；缺省回落到 category 原值（同一条目
        // 至少有类别可显，Worker 端两者总成对出现，filter_adapter.py:28-29）。
        entry.categoryLabel = item.value(QStringLiteral("category_label")).toString();
        if (entry.categoryLabel.isEmpty())
            entry.categoryLabel = item.value(QStringLiteral("category")).toString();
        const QJsonArray params = item.value(QStringLiteral("params")).toArray();
        entry.paramsJson = QString::fromUtf8(QJsonDocument(params).toJson(QJsonDocument::Compact));
        entry.available = item.value(QStringLiteral("available")).toBool(false);
        for (const auto &dep : item.value(QStringLiteral("optional_deps")).toArray())
            entry.optionalDeps.append(dep.toString());
        entry.description = item.value(QStringLiteral("description")).toString();
        next.append(entry);
    }

    beginResetModel();
    m_entries = next;
    endResetModel();
}

QVariantList FilterModel::search(const QString &query) const {
    // "title" = name（显示名）；"keywords" = key + category_label + description
    // + optional_deps。总集拼串后做一次大小写不敏感包含匹配——滤镜条目量级
    // （~150，capabilities.list filter_count）不值得建索引。
    const QString needle = query.trimmed();
    QVariantList results;
    for (const auto &entry : m_entries) {
        if (!needle.isEmpty()) {
            QStringList keywords = entry.optionalDeps;
            keywords.prepend(entry.key);
            keywords.prepend(entry.categoryLabel);
            keywords.prepend(entry.description);
            keywords.prepend(entry.name); // title
            if (!keywords.join(QStringLiteral(" ")).contains(needle, Qt::CaseInsensitive))
                continue;
        }
        results.append(entryToVariantMap(entry));
    }
    return results;
}

QVariantMap FilterModel::entryToVariantMap(const Entry &entry) {
    return QVariantMap{
        {QStringLiteral("key"), entry.key},
        {QStringLiteral("name"), entry.name},
        {QStringLiteral("categoryLabel"), entry.categoryLabel},
        {QStringLiteral("paramsJson"), entry.paramsJson},
        {QStringLiteral("available"), entry.available},
        {QStringLiteral("optionalDeps"), entry.optionalDeps},
        {QStringLiteral("description"), entry.description},
    };
}

int FilterModel::rowCount(const QModelIndex &parent) const {
    return parent.isValid() ? 0 : m_entries.size();
}

QVariant FilterModel::data(const QModelIndex &index, int role) const {
    if (!index.isValid() || index.row() >= m_entries.size())
        return {};
    const auto &entry = m_entries.at(index.row());
    switch (role) {
    case FilterKeyRole:
        return entry.key;
    case FilterNameRole:
        return entry.name;
    case CategoryLabelRole:
        return entry.categoryLabel;
    case ParamsJsonRole:
        return entry.paramsJson;
    case AvailableRole:
        return entry.available;
    case OptionalDepsRole:
        return entry.optionalDeps;
    case DescriptionRole:
        return entry.description;
    default:
        return {};
    }
}

QHash<int, QByteArray> FilterModel::roleNames() const {
    return {
        {FilterKeyRole, "filterKey"},         {FilterNameRole, "filterName"},
        {CategoryLabelRole, "categoryLabel"}, {ParamsJsonRole, "paramsJson"},
        {AvailableRole, "available"},         {OptionalDepsRole, "optionalDeps"},
        {DescriptionRole, "description"},
    };
}

} // namespace toolbox
