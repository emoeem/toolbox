#include "generator_model.h"

#include <QJsonArray>
#include <QJsonDocument>

namespace toolbox {

GeneratorModel::GeneratorModel(QObject *parent) : QAbstractListModel(parent) {}

void GeneratorModel::reloadFrom(const QJsonObject &generateListResult) {
    const QJsonArray generators = generateListResult.value(QStringLiteral("generators")).toArray();
    QVector<Entry> next;
    next.reserve(generators.size());
    for (const auto &value : generators) {
        const QJsonObject item = value.toObject();
        // 无 key 的条目无法在 generate.render 中引用，防御性跳过（FilterModel
        // 对无 key 滤镜条目的同款处置，filter_model.cpp:16-19）。
        const QString key = item.value(QStringLiteral("key")).toString();
        if (key.isEmpty())
            continue;
        Entry entry;
        entry.key = key;
        entry.name = item.value(QStringLiteral("name")).toString();
        // category_label 是本地化显示名；缺省回落到 category 原值（同一条目
        // 至少有类别可显，filter.list 两侧总成对出现的同一约定）。
        entry.categoryLabel = item.value(QStringLiteral("category_label")).toString();
        if (entry.categoryLabel.isEmpty())
            entry.categoryLabel = item.value(QStringLiteral("category")).toString();
        const QJsonArray params = item.value(QStringLiteral("params")).toArray();
        entry.paramsJson = QString::fromUtf8(QJsonDocument(params).toJson(QJsonDocument::Compact));
        entry.available = item.value(QStringLiteral("available")).toBool(false);
        for (const auto &dep : item.value(QStringLiteral("optional_deps")).toArray())
            entry.optionalDeps.append(dep.toString());
        next.append(entry);
    }

    beginResetModel();
    m_entries = next;
    endResetModel();
}

QVariantList GeneratorModel::search(const QString &query) const {
    // "title" = name（显示名）；"keywords" = key + category_label + optional_deps。
    // 总集拼串后做一次大小写不敏感包含匹配——生成器目录量级与滤镜目录相当
    // （~百级），不值得建索引（filter_model.cpp:42-47 同款结论）。
    const QString needle = query.trimmed();
    QVariantList results;
    for (const auto &entry : m_entries) {
        if (!needle.isEmpty()) {
            QStringList keywords = entry.optionalDeps;
            keywords.prepend(entry.key);
            keywords.prepend(entry.categoryLabel);
            keywords.prepend(entry.name); // title
            if (!keywords.join(QStringLiteral(" ")).contains(needle, Qt::CaseInsensitive))
                continue;
        }
        results.append(entryToVariantMap(entry));
    }
    return results;
}

QVariantMap GeneratorModel::entryToVariantMap(const Entry &entry) {
    return QVariantMap{
        {QStringLiteral("key"), entry.key},
        {QStringLiteral("name"), entry.name},
        {QStringLiteral("categoryLabel"), entry.categoryLabel},
        {QStringLiteral("paramsJson"), entry.paramsJson},
        {QStringLiteral("available"), entry.available},
        {QStringLiteral("optionalDeps"), entry.optionalDeps},
    };
}

int GeneratorModel::rowCount(const QModelIndex &parent) const {
    return parent.isValid() ? 0 : m_entries.size();
}

QVariant GeneratorModel::data(const QModelIndex &index, int role) const {
    if (!index.isValid() || index.row() >= m_entries.size())
        return {};
    const auto &entry = m_entries.at(index.row());
    switch (role) {
    case GeneratorKeyRole:
        return entry.key;
    case GeneratorNameRole:
        return entry.name;
    case CategoryLabelRole:
        return entry.categoryLabel;
    case ParamsJsonRole:
        return entry.paramsJson;
    case AvailableRole:
        return entry.available;
    case OptionalDepsRole:
        return entry.optionalDeps;
    default:
        return {};
    }
}

QHash<int, QByteArray> GeneratorModel::roleNames() const {
    return {
        {GeneratorKeyRole, "generatorKey"},   {GeneratorNameRole, "generatorName"},
        {CategoryLabelRole, "categoryLabel"}, {ParamsJsonRole, "paramsJson"},
        {AvailableRole, "available"},         {OptionalDepsRole, "optionalDeps"},
    };
}

} // namespace toolbox
