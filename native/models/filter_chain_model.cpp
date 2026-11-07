#include "filter_chain_model.h"

namespace toolbox {

FilterChainModel::FilterChainModel(QObject *parent) : QAbstractListModel(parent) {}

void FilterChainModel::replaceFrom(const QJsonArray &steps) {
    QVector<Step> next;
    next.reserve(steps.size());
    for (const auto &value : steps) {
        const QJsonObject item = value.toObject();
        // 与 Worker 端 build_chain 一致（filter_adapter.py:61-62）：无
        // filter_key 的步骤提交时会被拒，这里同样不收。
        const QString key = item.value(QStringLiteral("filter_key")).toString();
        if (key.isEmpty())
            continue;
        next.append({key, item.value(QStringLiteral("params")).toObject(),
                     item.value(QStringLiteral("enabled")).toBool(true)});
    }

    const int previousCount = m_steps.size();
    beginResetModel();
    m_steps = next;
    endResetModel();
    if (m_steps.size() != previousCount)
        emit stepCountChanged();
}

void FilterChainModel::addStep(const QString &key, const QJsonObject &params) {
    if (key.isEmpty())
        return;
    const int row = m_steps.size();
    beginInsertRows(QModelIndex(), row, row);
    m_steps.append({key, params, true});
    endInsertRows();
    emit stepCountChanged();
}

void FilterChainModel::removeRow(int row) {
    if (row < 0 || row >= m_steps.size())
        return;
    beginRemoveRows(QModelIndex(), row, row);
    m_steps.removeAt(row);
    endRemoveRows();
    emit stepCountChanged();
}

void FilterChainModel::moveUp(int row) {
    if (row <= 0 || row >= m_steps.size())
        return;
    // Qt 移动语义：目标行 = 移动后应位于其"之前"的行。上移一行的目标是 row-1。
    beginMoveRows(QModelIndex(), row, row, QModelIndex(), row - 1);
    m_steps.insert(row - 1, m_steps.takeAt(row));
    endMoveRows();
}

void FilterChainModel::moveDown(int row) {
    if (row < 0 || row + 1 >= m_steps.size())
        return;
    // 下移一行的目标是 row+2（越过紧邻的下一行）；目标是 row+1 属同位移动，
    // Qt 会拒绝并警告，故边界必须如此判定。
    beginMoveRows(QModelIndex(), row, row, QModelIndex(), row + 2);
    m_steps.insert(row + 1, m_steps.takeAt(row));
    endMoveRows();
}

void FilterChainModel::setEnabled(int row, bool enabled) {
    if (row < 0 || row >= m_steps.size())
        return;
    if (m_steps.at(row).enabled == enabled)
        return;
    m_steps[row].enabled = enabled;
    emit dataChanged(index(row), index(row), {ChainEnabledRole});
}

int FilterChainModel::rowCount(const QModelIndex &parent) const {
    return parent.isValid() ? 0 : m_steps.size();
}

QVariant FilterChainModel::data(const QModelIndex &index, int role) const {
    if (!index.isValid() || index.row() >= m_steps.size())
        return {};
    const auto &step = m_steps.at(index.row());
    switch (role) {
    case ChainFilterKeyRole:
        return step.key;
    case ChainParamsRole:
        return step.params;
    case ChainEnabledRole:
        return step.enabled;
    case ChainIndexRole:
        return index.row();
    default:
        return {};
    }
}

QHash<int, QByteArray> FilterChainModel::roleNames() const {
    return {
        {ChainFilterKeyRole, "chainFilterKey"},
        {ChainParamsRole, "chainParams"},
        {ChainEnabledRole, "chainEnabled"},
        {ChainIndexRole, "chainIndex"},
    };
}

} // namespace toolbox
