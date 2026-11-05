#include "tool_model.h"

namespace toolbox {

// ---- ToolModel -----------------------------------------------------------

ToolModel::ToolModel(QObject *parent)
    : QAbstractListModel(parent)
{
}

int ToolModel::indexOfId(const QString &id) const
{
    for (int i = 0; i < m_entries.size(); ++i) {
        if (m_entries.at(i).id == id)
            return i;
    }
    return -1;
}

QVariantMap ToolModel::get(int row) const
{
    QVariantMap map;
    if (row < 0 || row >= m_entries.size())
        return map;
    const auto &entry = m_entries.at(row);
    map.insert(QStringLiteral("id"), entry.id);
    map.insert(QStringLiteral("title"), entry.title);
    map.insert(QStringLiteral("category"), entry.category);
    map.insert(QStringLiteral("available"), entry.available);
    map.insert(QStringLiteral("phase"), entry.phase);
    map.insert(QStringLiteral("keywords"), entry.keywords);
    return map;
}

int ToolModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : m_entries.size();
}

QVariant ToolModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() >= m_entries.size())
        return {};
    const auto &entry = m_entries.at(index.row());
    switch (role) {
    case IdRole: return entry.id;
    case TitleRole: return entry.title;
    case CategoryRole: return entry.category;
    case AvailableRole: return entry.available;
    case PhaseRole: return entry.phase;
    case KeywordsRole: return entry.keywords;
    default: return {};
    }
}

QHash<int, QByteArray> ToolModel::roleNames() const
{
    return {
        {IdRole, "toolId"},
        {TitleRole, "title"},
        {CategoryRole, "category"},
        {AvailableRole, "available"},
        {PhaseRole, "phase"},
        {KeywordsRole, "keywords"},
    };
}

void ToolModel::addEntry(const Entry &entry)
{
    beginInsertRows(QModelIndex(), m_entries.size(), m_entries.size());
    m_entries.append(entry);
    endInsertRows();
}

// ---- NavModel ------------------------------------------------------------

NavModel::NavModel(QObject *parent)
    : QAbstractListModel(parent)
{
}

QUrl NavModel::pageForId(const QString &id) const
{
    for (const auto &entry : m_entries) {
        if (entry.id == id)
            return entry.page;
    }
    return {};
}

QVariantMap NavModel::get(int row) const
{
    QVariantMap map;
    if (row < 0 || row >= m_entries.size())
        return map;
    const auto &entry = m_entries.at(row);
    map.insert(QStringLiteral("id"), entry.id);
    map.insert(QStringLiteral("title"), entry.title);
    map.insert(QStringLiteral("page"), entry.page);
    map.insert(QStringLiteral("available"), entry.available);
    map.insert(QStringLiteral("phase"), entry.phase);
    return map;
}

int NavModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : m_entries.size();
}

QVariant NavModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() >= m_entries.size())
        return {};
    const auto &entry = m_entries.at(index.row());
    switch (role) {
    case NavIdRole: return entry.id;
    case NavTitleRole: return entry.title;
    case NavPageRole: return entry.page;
    case NavAvailableRole: return entry.available;
    case NavPhaseRole: return entry.phase;
    default: return {};
    }
}

QHash<int, QByteArray> NavModel::roleNames() const
{
    return {
        {NavIdRole, "navId"},
        {NavTitleRole, "title"},
        {NavPageRole, "page"},
        {NavAvailableRole, "available"},
        {NavPhaseRole, "phase"},
    };
}

void NavModel::addEntry(const Entry &entry)
{
    beginInsertRows(QModelIndex(), m_entries.size(), m_entries.size());
    m_entries.append(entry);
    endInsertRows();
}

} // namespace toolbox
