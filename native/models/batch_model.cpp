#include "batch_model.h"

namespace toolbox {

namespace {

// 缺省状态（resetFrom 未携带 state 时的起点）。
const QString kPendingState = QStringLiteral("pending");

bool isDoneState(const QString &state) {
    return state == QStringLiteral("done");
}

bool isFailedState(const QString &state) {
    return state == QStringLiteral("failed");
}

} // namespace

BatchModel::BatchModel(QObject *parent) : QAbstractListModel(parent) {}

int BatchModel::doneCount() const {
    int count = 0;
    for (const auto &entry : m_entries) {
        if (isDoneState(entry.state))
            ++count;
    }
    return count;
}

int BatchModel::failedCount() const {
    int count = 0;
    for (const auto &entry : m_entries) {
        if (isFailedState(entry.state))
            ++count;
    }
    return count;
}

void BatchModel::resetFrom(const QJsonArray &entries) {
    const int totalBefore = totalCount();
    const int doneBefore = doneCount();
    const int failedBefore = failedCount();

    QVector<Entry> next;
    next.reserve(entries.size());
    for (const auto &value : entries) {
        if (!value.isObject())
            continue; // 非对象元素忽略
        const QJsonObject object = value.toObject();
        const QString file = object.value(QStringLiteral("file")).toString();
        if (file.isEmpty())
            continue; // 空 file 不造无名行（行键是 updateFrom 的定位依据）
        Entry entry;
        entry.file = file;
        entry.state = object.value(QStringLiteral("state")).toString(kPendingState);
        if (entry.state.isEmpty())
            entry.state = kPendingState;
        entry.progress =
            qBound(0, object.value(QStringLiteral("progress")).toInt(0), 100);
        entry.error = object.value(QStringLiteral("error")).toString();
        entry.outputPath = object.value(QStringLiteral("output_path")).toString();
        next.append(entry);
    }

    beginResetModel();
    m_entries = next;
    endResetModel();
    maybeEmitSummary(totalBefore, doneBefore, failedBefore);
}

void BatchModel::updateFrom(const QJsonObject &progress) {
    const QString file = progress.value(QStringLiteral("file")).toString();
    if (file.isEmpty())
        return; // 无行键（纯整体进度帧）不落行
    const int row = indexOfFile(file);
    if (row < 0)
        return; // 未知 file（事件早于受理 / 跨批次迟到）不造行

    const int totalBefore = totalCount();
    const int doneBefore = doneCount();
    const int failedBefore = failedCount();

    QList<int> changedRoles;
    Entry &entry = m_entries[row];
    const auto stateValue = progress.value(QStringLiteral("state"));
    if (stateValue.isString() && !stateValue.toString().isEmpty() &&
        stateValue.toString() != entry.state) {
        entry.state = stateValue.toString();
        changedRoles.append(BatchStateRole);
    }
    const auto progressValue = progress.value(QStringLiteral("progress"));
    if (progressValue.isDouble()) {
        const int clamped = qBound(0, progressValue.toInt(entry.progress), 100);
        if (clamped != entry.progress) {
            entry.progress = clamped;
            changedRoles.append(BatchProgressRole);
        }
    }
    const auto errorValue = progress.value(QStringLiteral("error"));
    if (errorValue.isString() && errorValue.toString() != entry.error) {
        entry.error = errorValue.toString();
        changedRoles.append(BatchErrorRole);
    }
    const auto outputValue = progress.value(QStringLiteral("output_path"));
    if (outputValue.isString() && outputValue.toString() != entry.outputPath) {
        entry.outputPath = outputValue.toString();
        changedRoles.append(BatchOutputPathRole);
    }

    if (changedRoles.isEmpty())
        return; // 全部字段与现值一致：空操作，不发射
    emit dataChanged(index(row), index(row), changedRoles);
    maybeEmitSummary(totalBefore, doneBefore, failedBefore);
}

void BatchModel::clear() {
    const int totalBefore = totalCount();
    const int doneBefore = doneCount();
    const int failedBefore = failedCount();

    beginResetModel();
    m_entries.clear();
    endResetModel();
    maybeEmitSummary(totalBefore, doneBefore, failedBefore);
}

void BatchModel::markActiveAs(const QString &state) {
    const int totalBefore = totalCount();
    const int doneBefore = doneCount();
    const int failedBefore = failedCount();

    bool touched = false;
    for (int row = 0; row < m_entries.size(); ++row) {
        Entry &entry = m_entries[row];
        if (entry.state != kPendingState && entry.state != QStringLiteral("running"))
            continue; // 已终态的行不动
        entry.state = state;
        touched = true;
        emit dataChanged(index(row), index(row), {BatchStateRole});
    }
    if (touched)
        maybeEmitSummary(totalBefore, doneBefore, failedBefore);
}

int BatchModel::indexOfFile(const QString &file) const {
    for (int i = 0; i < m_entries.size(); ++i) {
        if (m_entries.at(i).file == file)
            return i;
    }
    return -1;
}

void BatchModel::maybeEmitSummary(int totalBefore, int doneBefore, int failedBefore) {
    if (totalCount() == totalBefore && doneCount() == doneBefore &&
        failedCount() == failedBefore)
        return;
    emit batchSummaryChanged();
}

int BatchModel::rowCount(const QModelIndex &parent) const {
    return parent.isValid() ? 0 : m_entries.size();
}

QVariant BatchModel::data(const QModelIndex &index, int role) const {
    if (!index.isValid() || index.row() >= m_entries.size())
        return {};
    const auto &entry = m_entries.at(index.row());
    switch (role) {
    case BatchFileRole:
        return entry.file;
    case BatchStateRole:
        return entry.state;
    case BatchProgressRole:
        return entry.progress;
    case BatchErrorRole:
        return entry.error;
    case BatchOutputPathRole:
        return entry.outputPath;
    default:
        return {};
    }
}

QHash<int, QByteArray> BatchModel::roleNames() const {
    return {
        {BatchFileRole, "batchFile"},
        {BatchStateRole, "batchState"},
        {BatchProgressRole, "batchProgress"},
        {BatchErrorRole, "batchError"},
        {BatchOutputPathRole, "batchOutputPath"},
    };
}

} // namespace toolbox
