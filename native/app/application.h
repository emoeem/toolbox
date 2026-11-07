#pragma once

#include "backend/backend_manager.h"
#include "models/task_model.h"
#include "models/tool_model.h"
#include "services/font_service.h"
#include "services/settings_service.h"

#include <QObject>
#include <QUrl>
#include <QtQml/qqml.h>

namespace toolbox {

// Application-wide singleton exposed to QML: owns the catalog models, the
// task queue, the Worker manager and the preference/font services, plus page
// routing. Deliberately thin — further services (Document/Filter) arrive in
// later phases and must be wired here, not into QML.
class Application : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    Q_PROPERTY(NavModel *navModel READ navModel CONSTANT)
    Q_PROPERTY(ToolModel *toolModel READ toolModel CONSTANT)
    Q_PROPERTY(TaskModel *taskModel READ taskModel CONSTANT)
    Q_PROPERTY(BackendManager *backend READ backend CONSTANT)
    Q_PROPERTY(SettingsService *settingsService READ settingsService CONSTANT)
    Q_PROPERTY(FontService *fontService READ fontService CONSTANT)
    Q_PROPERTY(QUrl currentPage READ currentPage WRITE setCurrentPage NOTIFY currentPageChanged)
    Q_PROPERTY(QString version READ version CONSTANT)
    Q_PROPERTY(QString qtVersion READ qtVersion CONSTANT)

  public:
    explicit Application(QObject *parent = nullptr);

    static Application *create(QQmlEngine *qmlEngine, QJSEngine *jsEngine);

    // 返回成员地址的访问器不能是 const 成员函数：const 上下文中 &m_x 得到
    // const 指针（CI 实证 -fpermissive 拒绝）。Q_PROPERTY READ 不要求 const。
    NavModel *navModel() { return &m_navModel; }
    ToolModel *toolModel() { return &m_toolModel; }
    TaskModel *taskModel() { return &m_taskModel; }
    BackendManager *backend() { return &m_backend; }
    SettingsService *settingsService() const { return m_settingsService; }
    FontService *fontService() const { return m_fontService; }
    QUrl currentPage() const { return m_currentPage; }
    void setCurrentPage(const QUrl &page);
    // 与 pyproject.toml version（单一来源）对齐，见 CHANGELOG.md
    // v2.0.0-alpha.1 条目。
    QString version() const { return QStringLiteral("2.0.0-alpha.1"); }
    QString qtVersion() const;

    Q_INVOKABLE void navigate(const QString &pageId);

    // Configures the Worker from the SettingsService keys backend/python and
    // backend/repoRoot, then starts it. Missing/incomplete keys surface as
    // BackendManager::errorOccurred(WORKER_START_FAILED) from start()
    // (backend_manager.cpp:74-78) — no separate Application-level signal.
    Q_INVOKABLE void startBackend();

  signals:
    void currentPageChanged();

  private:
    void buildCatalog();

    BackendManager m_backend;
    TaskModel m_taskModel;
    SettingsService *m_settingsService = nullptr;
    FontService *m_fontService = nullptr;
    NavModel m_navModel;
    ToolModel m_toolModel;
    QUrl m_currentPage;
};

} // namespace toolbox
