#include "history_model.h"

#include <QJsonArray>
#include <QJsonValue>

namespace toolbox {

HistoryModel::HistoryModel(QObject *parent) : QAbstractListModel(parent) {}

void HistoryModel::refreshFrom(const QJsonObject &history) {
    const QJsonArray entries = history.value(QStringLiteral("entries")).toArray();
    QVector<Entry> next;
    next.reserve(entries.size());
    int row = 0;
    for (const auto &value : entries) {
        const QJsonObject entry = value.toObject();
        // index 缺失时按行序兜底（协议保证 index == entries 下标，§3.3）。
        next.append({entry.value(QStringLiteral("index")).toInt(row),
                     entry.value(QStringLiteral("name")).toString()});
        ++row;
    }
    const int current = history.value(QStringLiteral("current")).toInt(-1);
    const bool canUndo = history.value(QStringLiteral("canUndo")).toBool(false);
    const bool canRedo = history.value(QStringLiteral("canRedo")).toBool(false);

    beginResetModel();
    m_entries = next;
    m_current = current;
    endResetModel();

    if (m_canUndo != canUndo) {
        m_canUndo = canUndo;
        emit canUndoChanged();
    }
    if (m_canRedo != canRedo) {
        m_canRedo = canRedo;
        emit canRedoChanged();
    }
}

int HistoryModel::rowCount(const QModelIndex &parent) const {
    return parent.isValid() ? 0 : m_entries.size();
}

QVariant HistoryModel::data(const QModelIndex &index, int role) const {
    if (!index.isValid() || index.row() >= m_entries.size())
        return {};
    const auto &entry = m_entries.at(index.row());
    switch (role) {
    case HistIndexRole:
        return entry.index;
    case HistNameRole:
        return entry.name;
    case HistCurrentRole:
        return entry.index == m_current;
    default:
        return {};
    }
}

QHash<int, QByteArray> HistoryModel::roleNames() const {
    return {
        {HistIndexRole, "histIndex"},
        {HistNameRole, "histName"},
        {HistCurrentRole, "histCurrent"},
    };
}

} // namespace toolbox
