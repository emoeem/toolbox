#pragma once

#include "tool_model.h"

#include <QObject>
#include <QUrl>
#include <QtQml/qqml.h>

namespace toolbox {

// Application-wide singleton exposed to QML: owns the catalog models and
// page routing. Deliberately thin — services (Document/Task/Filter) arrive
// in Phase 3+ and must be wired here, not into QML.
class Application : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    Q_PROPERTY(NavModel *navModel READ navModel CONSTANT)
    Q_PROPERTY(ToolModel *toolModel READ toolModel CONSTANT)
    Q_PROPERTY(QUrl currentPage READ currentPage WRITE setCurrentPage NOTIFY currentPageChanged)
    Q_PROPERTY(QString version READ version CONSTANT)
    Q_PROPERTY(QString qtVersion READ qtVersion CONSTANT)

public:
    explicit Application(QObject *parent = nullptr);

    static Application *create(QQmlEngine *qmlEngine, QJSEngine *jsEngine);

    NavModel *navModel() const { return &m_navModel; }
    ToolModel *toolModel() const { return &m_toolModel; }
    QUrl currentPage() const { return m_currentPage; }
    void setCurrentPage(const QUrl &page);
    QString version() const { return QStringLiteral("0.2.0"); }
    QString qtVersion() const;

    Q_INVOKABLE void navigate(const QString &pageId);

signals:
    void currentPageChanged();

private:
    void buildCatalog();

    NavModel m_navModel;
    ToolModel m_toolModel;
    QUrl m_currentPage;
};

} // namespace toolbox
