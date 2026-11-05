#include "settings_service.h"

#include <QJSEngine>
#include <QQmlEngine>
#include <QVariant>

namespace toolbox {

namespace {

// Stored value that is neither "dark" nor "light" (any case) is normalized to
// the canonical "system", keeping the themeMode invariant from the header.
QString normalizeThemeMode(const QString &mode)
{
    if (mode.compare(QStringLiteral("dark"), Qt::CaseInsensitive) == 0)
        return QStringLiteral("dark");
    if (mode.compare(QStringLiteral("light"), Qt::CaseInsensitive) == 0)
        return QStringLiteral("light");
    return QStringLiteral("system");
}

// Mirrors app/fonts.py resolve_size (42-46): an unreadable stored value falls
// back to the default instead of propagating a bogus number.
int readInt(const QVariant &value, int fallback)
{
    bool ok = false;
    const int result = value.toInt(&ok);
    return ok ? result : fallback;
}

SettingsService *s_instance = nullptr;  // process-wide singleton identity

} // namespace

SettingsService::SettingsService(QObject *parent)
    : QObject(parent)
    , m_settings(QStringLiteral("Emo"), QStringLiteral("Toolbox2"))
{
    load();
}

SettingsService::~SettingsService()
{
    if (s_instance == this)
        s_instance = nullptr;
}

SettingsService *SettingsService::instance()
{
    if (!s_instance)
        s_instance = new SettingsService();
    return s_instance;
}

SettingsService *SettingsService::create(QQmlEngine *qmlEngine, QJSEngine *jsEngine)
{
    // The instance must outlive the engine bindings; ownership stays with QML.
    Q_UNUSED(qmlEngine);
    Q_UNUSED(jsEngine);
    return instance();
}

void SettingsService::load()
{
    m_themeMode = normalizeThemeMode(
        m_settings.value(QStringLiteral("appearance/themeMode"), QStringLiteral("system")).toString());
    m_navExpanded = m_settings.value(QStringLiteral("layout/navExpanded"), false).toBool();
    m_inspectorCollapsed = m_settings.value(QStringLiteral("layout/inspectorCollapsed"), false).toBool();
    m_uiFontFamily = m_settings.value(QStringLiteral("font/family"), QString()).toString();
    m_monoFontFamily = m_settings.value(QStringLiteral("font/mono"), QString()).toString();
    m_uiFontSize = readInt(m_settings.value(QStringLiteral("font/size"), kDefaultFontSize),
                           kDefaultFontSize);
    m_previewQuality = readInt(m_settings.value(QStringLiteral("preview/quality"), kDefaultPreviewQuality),
                               kDefaultPreviewQuality);
    m_concurrentTasks = readInt(m_settings.value(QStringLiteral("tasks/concurrent"), kDefaultConcurrentTasks),
                                kDefaultConcurrentTasks);
    m_recentFiles = m_settings.value(QStringLiteral("files/recent"), QStringList()).toStringList();
    if (m_recentFiles.size() > kMaxRecentFiles)
        m_recentFiles = m_recentFiles.mid(0, kMaxRecentFiles);
    // Backend launcher keys: Application::startBackend() reads the raw store
    // via value() (application.cpp:58-59), while the settings page displays
    // these properties. Persisting the defaults when the keys are absent keeps
    // the store identical to what the page shows, so startBackend() sees the
    // same values the user sees instead of failing on a hidden empty store.
    m_backendPython = m_settings.value(QStringLiteral("backend/python"), QStringLiteral("python3")).toString();
    m_backendRepoRoot = m_settings.value(QStringLiteral("backend/repoRoot"), QString()).toString();
    if (!m_settings.contains(QStringLiteral("backend/python"))) {
        m_settings.setValue(QStringLiteral("backend/python"), m_backendPython);
        m_settings.sync();
    }
    if (!m_settings.contains(QStringLiteral("backend/repoRoot"))) {
        m_settings.setValue(QStringLiteral("backend/repoRoot"), m_backendRepoRoot);
        m_settings.sync();
    }
}

void SettingsService::setThemeMode(const QString &mode)
{
    const QString normalized = normalizeThemeMode(mode);
    if (m_themeMode == normalized)
        return;
    m_themeMode = normalized;
    m_settings.setValue(QStringLiteral("appearance/themeMode"), m_themeMode);
    m_settings.sync();
    emit themeModeChanged();
}

void SettingsService::setNavExpanded(bool expanded)
{
    if (m_navExpanded == expanded)
        return;
    m_navExpanded = expanded;
    m_settings.setValue(QStringLiteral("layout/navExpanded"), m_navExpanded);
    m_settings.sync();
    emit navExpandedChanged();
}

void SettingsService::setInspectorCollapsed(bool collapsed)
{
    if (m_inspectorCollapsed == collapsed)
        return;
    m_inspectorCollapsed = collapsed;
    m_settings.setValue(QStringLiteral("layout/inspectorCollapsed"), m_inspectorCollapsed);
    m_settings.sync();
    emit inspectorCollapsedChanged();
}

void SettingsService::setUiFontFamily(const QString &family)
{
    if (m_uiFontFamily == family)
        return;
    m_uiFontFamily = family;
    m_settings.setValue(QStringLiteral("font/family"), m_uiFontFamily);
    m_settings.sync();
    emit uiFontFamilyChanged();
}

void SettingsService::setMonoFontFamily(const QString &family)
{
    if (m_monoFontFamily == family)
        return;
    m_monoFontFamily = family;
    m_settings.setValue(QStringLiteral("font/mono"), m_monoFontFamily);
    m_settings.sync();
    emit monoFontFamilyChanged();
}

void SettingsService::setUiFontSize(int size)
{
    if (m_uiFontSize == size)
        return;
    m_uiFontSize = size;
    m_settings.setValue(QStringLiteral("font/size"), m_uiFontSize);
    m_settings.sync();
    emit uiFontSizeChanged();
}

void SettingsService::setPreviewQuality(int quality)
{
    if (m_previewQuality == quality)
        return;
    m_previewQuality = quality;
    m_settings.setValue(QStringLiteral("preview/quality"), m_previewQuality);
    m_settings.sync();
    emit previewQualityChanged();
}

void SettingsService::setConcurrentTasks(int tasks)
{
    if (m_concurrentTasks == tasks)
        return;
    m_concurrentTasks = tasks;
    m_settings.setValue(QStringLiteral("tasks/concurrent"), m_concurrentTasks);
    m_settings.sync();
    emit concurrentTasksChanged();
}

void SettingsService::setBackendPython(const QString &python)
{
    if (m_backendPython == python)
        return;
    m_backendPython = python;
    m_settings.setValue(QStringLiteral("backend/python"), m_backendPython);
    m_settings.sync();
    emit backendChanged();
}

void SettingsService::setBackendRepoRoot(const QString &repoRoot)
{
    if (m_backendRepoRoot == repoRoot)
        return;
    m_backendRepoRoot = repoRoot;
    m_settings.setValue(QStringLiteral("backend/repoRoot"), m_backendRepoRoot);
    m_settings.sync();
    emit backendChanged();
}

void SettingsService::addRecentFile(const QString &path)
{
    if (path.isEmpty())
        return;
    QStringList updated = m_recentFiles;
    updated.removeAll(path);
    updated.prepend(path);
    if (updated.size() > kMaxRecentFiles)
        updated = updated.mid(0, kMaxRecentFiles);
    if (updated == m_recentFiles)
        return;
    m_recentFiles = updated;
    m_settings.setValue(QStringLiteral("files/recent"), m_recentFiles);
    m_settings.sync();
    emit recentFilesChanged();
}

void SettingsService::resetLayout()
{
    setNavExpanded(false);
    setInspectorCollapsed(false);
}

QVariant SettingsService::value(const QString &key, const QVariant &fallback) const
{
    return m_settings.value(key, fallback);
}

} // namespace toolbox
