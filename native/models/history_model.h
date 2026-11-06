#pragma once

#include <QAbstractListModel>
#include <QHash>
#include <QJsonObject>
#include <QVector>
#include <QtQml/qqml.h>

namespace toolbox {

// 撤销历史行（docs/ipc-protocol.md §3.3、docs/ui-page-spec.md §2 TopToolbar）。
// 数据源是 DocumentService::historyReady(history) 广播的同步 image.history
// 结果：{entries: [{index, name}], current, canUndo, canRedo}。QML 侧把该信号
// 转发给 refreshFrom（Connections / Binding），行数据与 canUndo/canRedo 一并
// 重建；撤销/重做按钮按 canUndo/canRedo 启停，条目名本地化由 QML 侧负责
// （协议原文：name 为产生该条目的动作名，如 "image.adjust"）。
class HistoryModel : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(bool canUndo READ canUndo NOTIFY canUndoChanged)
    Q_PROPERTY(bool canRedo READ canRedo NOTIFY canRedoChanged)

  public:
    struct Entry {
        int index = 0; // 协议字段 index：entries 下标，也是 histCurrent 的判定值
        QString name;  // 产生该条目的动作名（如 "open" / "image.adjust"）
    };

    enum Roles { HistIndexRole = Qt::UserRole + 1, HistNameRole, HistCurrentRole };

    explicit HistoryModel(QObject *parent = nullptr);

    // 整表重建（beginResetModel）：条目数与 current 状态以最近一次刷新为准。
    // canUndo/canRedo 仅在值变化时通知；空对象/缺字段视为无历史
    // （0 行、canUndo = canRedo = false），不抛错也不保留旧行。
    Q_INVOKABLE void refreshFrom(const QJsonObject &history);

    bool canUndo() const { return m_canUndo; }
    bool canRedo() const { return m_canRedo; }

    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

  signals:
    void canUndoChanged();
    void canRedoChanged();

  private:
    QVector<Entry> m_entries;
    int m_current = -1; // entries[current] 为当前状态；无历史时 -1
    bool m_canUndo = false;
    bool m_canRedo = false;
};

} // namespace toolbox
