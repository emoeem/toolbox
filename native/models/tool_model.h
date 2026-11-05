#pragma once

#include <QAbstractListModel>
#include <QHash>
#include <QUrl>
#include <QVector>
#include <QtQml/qqml.h>

namespace toolbox {

// Flat catalog entry. One model class serves both the navigation rail and the
// tool catalog: they differ only in payload and presentation.
//
// Phase 2: static data built in Application. Phase 4 will move the catalog
// into ToolCatalogService (search/favorites/recents) without changing roles.
class ToolModel : public QAbstractListModel
{
    Q_OBJECT
    QML_ELEMENT

public:
    struct Entry
    {
        QString id;
        QString title;
        QString category;
        bool available = false;
        QString phase;     // P0/P1/P2 — honest completion level, matrix-aligned
        QString keywords;  // space separated, for Phase 4 search
    };

    enum Roles
    {
        IdRole = Qt::UserRole + 1,
        TitleRole,
        CategoryRole,
        AvailableRole,
        PhaseRole,
        KeywordsRole
    };

    explicit ToolModel(QObject *parent = nullptr);

    Q_INVOKABLE int indexOfId(const QString &id) const;
    Q_INVOKABLE QVariantMap get(int row) const;

    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

    void addEntry(const Entry &entry);

private:
    QVector<Entry> m_entries;
};

// Navigation-only model: fixed entries with a target page URL.
class NavModel : public QAbstractListModel
{
    Q_OBJECT
    QML_ELEMENT

public:
    struct Entry
    {
        QString id;
        QString title;
        QUrl page;
        bool available = true;
        QString phase;
    };

    enum Roles
    {
        NavIdRole = Qt::UserRole + 1,
        NavTitleRole,
        NavPageRole,
        NavAvailableRole,
        NavPhaseRole
    };

    explicit NavModel(QObject *parent = nullptr);

    Q_INVOKABLE QUrl pageForId(const QString &id) const;
    Q_INVOKABLE QVariantMap get(int row) const;

    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

    void addEntry(const Entry &entry);

private:
    QVector<Entry> m_entries;
};

} // namespace toolbox
