#pragma once

#include <QObject>
#include <QSettings>
#include <QStringList>
#include <QVariant>
#include <QtQml/qqml.h>

namespace toolbox {

// Application-wide persisted preferences (Phase 4 task 8 of the project plan:
// "SettingsService 和布局持久化"). Deliberately a flat key/value facade, not a
// model: list-shaped state (recent files) is small and change-notified, while
// the file workflow itself stays in Phase 5.
//
// Store: QSettings("Emo", "Toolbox2") — matches the organization/application
// names set in main.cpp, so settings written here are exactly what a plain
// QSettings() reader (e.g. future services) would see. Every write is followed
// by sync() so a crash cannot lose the last change.
//
// Key map (QSettings root → property):
//   appearance/themeMode       themeMode           "dark"/"light"/"system" (default "system")
//   layout/navExpanded         navExpanded         docs/ui-component-spec.md §2 AppSidebar
//   layout/inspectorCollapsed  inspectorCollapsed  docs/ui-component-spec.md §2 InspectorPanel
//   font/family                uiFontFamily        empty = platform default (app/fonts.py:6-7)
//   font/mono                  monoFontFamily      empty = FontService candidate chain
//   font/size                  uiFontSize          point size, default 11 (app/fonts.py:21)
//   preview/quality            previewQuality      0=draft 1=balanced 2=high (default 1)
//   tasks/concurrent           concurrentTasks     default 2 (BackendManager maxWorkers)
//   files/recent               recentFiles         most-recent-first, capped at 10
class SettingsService : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    Q_PROPERTY(QString themeMode READ themeMode WRITE setThemeMode NOTIFY themeModeChanged)
    Q_PROPERTY(bool navExpanded READ navExpanded WRITE setNavExpanded NOTIFY navExpandedChanged)
    Q_PROPERTY(bool inspectorCollapsed READ inspectorCollapsed WRITE setInspectorCollapsed
                   NOTIFY inspectorCollapsedChanged)
    Q_PROPERTY(QString uiFontFamily READ uiFontFamily WRITE setUiFontFamily NOTIFY uiFontFamilyChanged)
    Q_PROPERTY(QString monoFontFamily READ monoFontFamily WRITE setMonoFontFamily
                   NOTIFY monoFontFamilyChanged)
    Q_PROPERTY(int uiFontSize READ uiFontSize WRITE setUiFontSize NOTIFY uiFontSizeChanged)
    Q_PROPERTY(int previewQuality READ previewQuality WRITE setPreviewQuality
                   NOTIFY previewQualityChanged)
    Q_PROPERTY(int concurrentTasks READ concurrentTasks WRITE setConcurrentTasks
                   NOTIFY concurrentTasksChanged)
    Q_PROPERTY(QStringList recentFiles READ recentFiles NOTIFY recentFilesChanged)
    // Backend launcher paths (Phase 4 settings page). Both share one NOTIFY:
    // they change together from the same form and no consumer needs to tell
    // them apart. Keys are exactly the ones Application::startBackend() reads
    // via value() (application.cpp:58-59), so a write here is immediately
    // visible to the next start.
    Q_PROPERTY(QString backendPython READ backendPython WRITE setBackendPython NOTIFY backendChanged)
    Q_PROPERTY(QString backendRepoRoot READ backendRepoRoot WRITE setBackendRepoRoot
                   NOTIFY backendChanged)

public:
    static constexpr int kMaxRecentFiles = 10;
    static constexpr int kDefaultFontSize = 11;        // app/fonts.py DEFAULT_SIZE
    static constexpr int kDefaultPreviewQuality = 1;   // balanced (0=draft, 2=high)
    static constexpr int kDefaultConcurrentTasks = 2;  // BackendManager::configure default

    explicit SettingsService(QObject *parent = nullptr);
    ~SettingsService() override;

    // Process-wide instance getter: Application wires it during startup and
    // QML's own singleton lookup must return the same object, never a second
    // one (both paths would otherwise write the same QSettings store).
    static SettingsService *instance();

    // QML singleton factory, mirroring Application::create: ownership stays
    // with QML so the instance outlives engine bindings.
    static SettingsService *create(QQmlEngine *qmlEngine, QJSEngine *jsEngine);

    QString themeMode() const { return m_themeMode; }
    void setThemeMode(const QString &mode);
    bool navExpanded() const { return m_navExpanded; }
    void setNavExpanded(bool expanded);
    bool inspectorCollapsed() const { return m_inspectorCollapsed; }
    void setInspectorCollapsed(bool collapsed);
    QString uiFontFamily() const { return m_uiFontFamily; }
    void setUiFontFamily(const QString &family);
    QString monoFontFamily() const { return m_monoFontFamily; }
    void setMonoFontFamily(const QString &family);
    int uiFontSize() const { return m_uiFontSize; }
    void setUiFontSize(int size);
    int previewQuality() const { return m_previewQuality; }
    void setPreviewQuality(int quality);
    int concurrentTasks() const { return m_concurrentTasks; }
    void setConcurrentTasks(int tasks);
    QStringList recentFiles() const { return m_recentFiles; }
    QString backendPython() const { return m_backendPython; }
    void setBackendPython(const QString &python);
    QString backendRepoRoot() const { return m_backendRepoRoot; }
    void setBackendRepoRoot(const QString &repoRoot);

    // Moves path to the front of recentFiles, de-duplicated, capped at
    // kMaxRecentFiles. Empty paths are ignored.
    Q_INVOKABLE void addRecentFile(const QString &path);

    // Restores layout persistence (nav rail expansion, inspector collapse) to
    // defaults, per the layout/* keys above.
    Q_INVOKABLE void resetLayout();

    // Read access to a raw settings key that has no typed property yet.
    // Writes keep going through the typed setters above so the sync()-per-
    // write rule holds (Application::startBackend() reads backend/* through
    // this channel; the keys themselves are typed properties since the
    // settings page landed).
    Q_INVOKABLE QVariant value(const QString &key, const QVariant &fallback = {}) const;

signals:
    void themeModeChanged();
    void navExpandedChanged();
    void inspectorCollapsedChanged();
    void uiFontFamilyChanged();
    void monoFontFamilyChanged();
    void uiFontSizeChanged();
    void previewQualityChanged();
    void concurrentTasksChanged();
    void recentFilesChanged();
    void backendChanged();

private:
    void load();

    QSettings m_settings;
    QString m_themeMode;
    bool m_navExpanded = false;          // icon rail is the default (product IA §1)
    bool m_inspectorCollapsed = false;
    QString m_uiFontFamily;
    QString m_monoFontFamily;
    int m_uiFontSize = kDefaultFontSize;
    int m_previewQuality = kDefaultPreviewQuality;
    int m_concurrentTasks = kDefaultConcurrentTasks;
    QStringList m_recentFiles;
    QString m_backendPython = QStringLiteral("python3");   // launcher default
    QString m_backendRepoRoot;
};

} // namespace toolbox
