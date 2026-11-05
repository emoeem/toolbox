// Phase 4 service tests: SettingsService persistence contract.
//
// Store isolation: SettingsService stores through QSettings("Emo","Toolbox2")
// (settings_service.cpp:35-40), the same org/app names main.cpp sets. On the
// Linux target environment the native QSettings format is INI, so pointing the
// user-scope INI path at a fresh QTemporaryDir per test function gives every
// test a clean store and never touches a developer's real
// ~/.config/Emo/Toolbox2.conf.
//
// Where the native format is NOT INI (Windows registry, Apple CFPreferences —
// QSettings::NativeFormat docs) the redirect is a no-op and these tests would
// read a developer's real store and pollute it. initTestCase() skips the whole
// class on such platforms; they are written for the Linux target env / CI
// (docs/phase4-acceptance.md §2).
//
// Defaults asserted here are the key map documented in settings_service.h
// (themeMode "system", font size 11, preview quality 1, concurrent tasks 2,
// recent files capped at kMaxRecentFiles = 10).
#include <QtTest/QtTest>

#include <QSettings>
#include <QSignalSpy>
#include <QTemporaryDir>

#include <memory>

#include "services/settings_service.h"

using toolbox::SettingsService;

class TestSettingsService : public QObject {
    Q_OBJECT

  private slots:
    void initTestCase();
    void init();
    void cleanup();

    void defaultsOnEmptyStore();
    void writeReadRoundTripPersists();
    void unchangedWriteDoesNotNotify();
    void corruptStoreFallsBackToDefaults();
    void themeModeIsNormalized();
    void addRecentFileEmptyIgnored();
    void addRecentFileDeduplicatesAndMovesToFront();
    void addRecentFileCapsAtTen();
    void resetLayoutRestoresDefaults();

  private:
    std::unique_ptr<QTemporaryDir> m_storeDir;
};

void TestSettingsService::initTestCase() {
    // QSettings::setPath() redirects only IniFormat, while SettingsService
    // builds its store in the default (native) format. On Windows the native
    // format is the registry and on Apple platforms CFPreferences, so the
    // temporary-dir redirect in init() would be a no-op there:
    // defaultsOnEmptyStore() would read whatever the developer's real
    // HKCU\Software\Emo\Toolbox2 (or plist) holds and
    // writeReadRoundTripPersists()/corruptStoreFallsBackToDefaults() would
    // write to it. Skip the entire class instead (QSKIP in initTestCase()
    // skips every test function) — a runtime QSettings().format() comparison
    // cannot express this, since format() returns the requested enum value
    // (NativeFormat) even on Unix where native storage is INI.
#if defined(Q_OS_WIN) || defined(Q_OS_DARWIN)
    QSKIP("Native QSettings format on this platform is the registry/CFPreferences, "
          "not INI: the IniFormat store redirect cannot isolate the store here.");
#endif
}

void TestSettingsService::init() {
    m_storeDir = std::make_unique<QTemporaryDir>();
    QVERIFY(m_storeDir->isValid());
    QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, m_storeDir->path());
}

void TestSettingsService::cleanup() {
    m_storeDir.reset();
}

void TestSettingsService::defaultsOnEmptyStore() {
    const SettingsService service;

    QCOMPARE(service.themeMode(), QStringLiteral("system"));
    QVERIFY(!service.navExpanded());
    QVERIFY(!service.inspectorCollapsed());
    QVERIFY(service.uiFontFamily().isEmpty());
    QVERIFY(service.monoFontFamily().isEmpty());
    QCOMPARE(service.uiFontSize(), SettingsService::kDefaultFontSize);
    QCOMPARE(service.uiFontSize(), 11);
    QCOMPARE(service.previewQuality(), SettingsService::kDefaultPreviewQuality);
    QCOMPARE(service.concurrentTasks(), SettingsService::kDefaultConcurrentTasks);
    QVERIFY(service.recentFiles().isEmpty());
    QCOMPARE(service.backendPython(), QStringLiteral("python3"));
    QVERIFY(service.backendRepoRoot().isEmpty());
}

void TestSettingsService::writeReadRoundTripPersists() {
    SettingsService writer;
    writer.setThemeMode(QStringLiteral("light"));
    writer.setNavExpanded(true);
    writer.setInspectorCollapsed(true);
    writer.setUiFontFamily(QStringLiteral("Noto Sans CJK SC"));
    writer.setMonoFontFamily(QStringLiteral("JetBrains Mono"));
    writer.setUiFontSize(13);
    writer.setPreviewQuality(0);
    writer.setConcurrentTasks(4);
    writer.setBackendPython(QStringLiteral("/usr/bin/python3"));
    writer.setBackendRepoRoot(QStringLiteral("/opt/toolbox"));
    writer.addRecentFile(QStringLiteral("/tmp/a.png"));
    writer.addRecentFile(QStringLiteral("/tmp/b.png"));

    // Every write is followed by sync() (settings_service.h:20-21), so a fresh
    // instance reads exactly what the first persisted.
    const SettingsService reader;
    QCOMPARE(reader.themeMode(), QStringLiteral("light"));
    QVERIFY(reader.navExpanded());
    QVERIFY(reader.inspectorCollapsed());
    QCOMPARE(reader.uiFontFamily(), QStringLiteral("Noto Sans CJK SC"));
    QCOMPARE(reader.monoFontFamily(), QStringLiteral("JetBrains Mono"));
    QCOMPARE(reader.uiFontSize(), 13);
    QCOMPARE(reader.previewQuality(), 0);
    QCOMPARE(reader.concurrentTasks(), 4);
    QCOMPARE(reader.backendPython(), QStringLiteral("/usr/bin/python3"));
    QCOMPARE(reader.backendRepoRoot(), QStringLiteral("/opt/toolbox"));
    QCOMPARE(reader.recentFiles(),
             (QStringList{QStringLiteral("/tmp/b.png"), QStringLiteral("/tmp/a.png")}));

    // Raw store access matches the typed properties (Application::startBackend
    // reads backend/* through this channel, application.cpp:58-59).
    QCOMPARE(reader.value(QStringLiteral("appearance/themeMode")).toString(),
             QStringLiteral("light"));
    QCOMPARE(reader.value(QStringLiteral("layout/navExpanded")).toBool(), true);
    QCOMPARE(reader.value(QStringLiteral("font/size")).toInt(), 13);
    QCOMPARE(reader.value(QStringLiteral("files/recent")).toStringList().size(), 2);
    QCOMPARE(reader.value(QStringLiteral("nonexistent.key"), QStringLiteral("fallback")).toString(),
             QStringLiteral("fallback"));
}

void TestSettingsService::unchangedWriteDoesNotNotify() {
    SettingsService service;
    service.setThemeMode(QStringLiteral("light"));

    QSignalSpy themeChanged(&service, &SettingsService::themeModeChanged);
    QSignalSpy sizeChanged(&service, &SettingsService::uiFontSizeChanged);
    QSignalSpy backendChanged(&service, &SettingsService::backendChanged);

    service.setThemeMode(QStringLiteral("light")); // unchanged → no signal
    service.setUiFontSize(SettingsService::kDefaultFontSize);
    service.setBackendPython(QStringLiteral("python3"));
    QCOMPARE(themeChanged.count(), 0);
    QCOMPARE(sizeChanged.count(), 0);
    QCOMPARE(backendChanged.count(), 0);

    service.setThemeMode(QStringLiteral("dark"));
    service.setUiFontSize(14);
    service.setBackendPython(QStringLiteral("/opt/pyenv/bin/python"));
    QCOMPARE(themeChanged.count(), 1);
    QCOMPARE(sizeChanged.count(), 1);
    QCOMPARE(backendChanged.count(), 1);
}

void TestSettingsService::corruptStoreFallsBackToDefaults() {
    {
        // Values written directly into the store (unreadable types), mirroring
        // app/fonts.py resolve_size's unreadable-value path. IniFormat explicit:
        // the service constructs its store with IniFormat (see settings_service.cpp).
        QSettings raw(QSettings::IniFormat, QSettings::UserScope, QStringLiteral("Emo"),
                      QStringLiteral("Toolbox2"));
        raw.setValue(QStringLiteral("font/size"), QStringLiteral("abc"));
        raw.setValue(QStringLiteral("preview/quality"), QStringLiteral("not-a-number"));
        raw.setValue(QStringLiteral("appearance/themeMode"), QStringLiteral("purple"));
        raw.sync();
    }

    const SettingsService service;
    QCOMPARE(service.uiFontSize(), SettingsService::kDefaultFontSize);
    QCOMPARE(service.previewQuality(), SettingsService::kDefaultPreviewQuality);
    QCOMPARE(service.themeMode(), QStringLiteral("system"));
}

void TestSettingsService::themeModeIsNormalized() {
    SettingsService service;
    service.setThemeMode(QStringLiteral("DARK"));
    QCOMPARE(service.themeMode(), QStringLiteral("dark"));
    service.setThemeMode(QStringLiteral("Light"));
    QCOMPARE(service.themeMode(), QStringLiteral("light"));
    service.setThemeMode(QStringLiteral("bogus-mode"));
    QCOMPARE(service.themeMode(), QStringLiteral("system"));

    // The canonical value is what lands in the store.
    const SettingsService reloaded;
    QCOMPARE(reloaded.value(QStringLiteral("appearance/themeMode")).toString(),
             QStringLiteral("system"));
}

void TestSettingsService::addRecentFileEmptyIgnored() {
    SettingsService service;
    service.addRecentFile(QStringLiteral("/tmp/a.png"));

    QSignalSpy changed(&service, &SettingsService::recentFilesChanged);
    service.addRecentFile(QString());
    service.addRecentFile({});

    QCOMPARE(service.recentFiles(), QStringList{QStringLiteral("/tmp/a.png")});
    QCOMPARE(changed.count(), 0);
}

void TestSettingsService::addRecentFileDeduplicatesAndMovesToFront() {
    SettingsService service;
    service.addRecentFile(QStringLiteral("/tmp/a.png"));
    service.addRecentFile(QStringLiteral("/tmp/b.png"));
    service.addRecentFile(QStringLiteral("/tmp/c.png"));
    QCOMPARE(service.recentFiles(),
             (QStringList{QStringLiteral("/tmp/c.png"), QStringLiteral("/tmp/b.png"),
                          QStringLiteral("/tmp/a.png")}));

    // Re-adding an existing entry moves it to the front without duplicating.
    service.addRecentFile(QStringLiteral("/tmp/a.png"));
    QCOMPARE(service.recentFiles(),
             (QStringList{QStringLiteral("/tmp/a.png"), QStringLiteral("/tmp/c.png"),
                          QStringLiteral("/tmp/b.png")}));

    // The entry that is already first: no change, no notification.
    QSignalSpy changed(&service, &SettingsService::recentFilesChanged);
    service.addRecentFile(QStringLiteral("/tmp/a.png"));
    QCOMPARE(changed.count(), 0);
    QCOMPARE(service.recentFiles().size(), 3);
}

void TestSettingsService::addRecentFileCapsAtTen() {
    SettingsService service;
    for (int i = 1; i <= 12; ++i)
        service.addRecentFile(QStringLiteral("/tmp/f%1.png").arg(i));

    QCOMPARE(SettingsService::kMaxRecentFiles, 10);
    QCOMPARE(service.recentFiles().size(), SettingsService::kMaxRecentFiles);
    QCOMPARE(service.recentFiles().first(), QStringLiteral("/tmp/f12.png"));
    QCOMPARE(service.recentFiles().last(), QStringLiteral("/tmp/f3.png"));

    // The persisted list is capped too, not just the in-memory one.
    const SettingsService reloaded;
    QCOMPARE(reloaded.recentFiles().size(), 10);
    QCOMPARE(reloaded.recentFiles().first(), QStringLiteral("/tmp/f12.png"));
}

void TestSettingsService::resetLayoutRestoresDefaults() {
    SettingsService service;
    service.setThemeMode(QStringLiteral("dark"));
    service.setUiFontSize(14);
    service.setNavExpanded(true);
    service.setInspectorCollapsed(true);

    QSignalSpy navChanged(&service, &SettingsService::navExpandedChanged);
    QSignalSpy inspectorChanged(&service, &SettingsService::inspectorCollapsedChanged);

    service.resetLayout();

    QVERIFY(!service.navExpanded());
    QVERIFY(!service.inspectorCollapsed());
    QCOMPARE(navChanged.count(), 1);
    QCOMPARE(inspectorChanged.count(), 1);

    // Persisted: a fresh instance starts from the reset layout state, and the
    // reset only touched the layout/* group, not other preferences.
    const SettingsService reloaded;
    QVERIFY(!reloaded.navExpanded());
    QVERIFY(!reloaded.inspectorCollapsed());
    QCOMPARE(reloaded.themeMode(), QStringLiteral("dark"));
    QCOMPARE(reloaded.uiFontSize(), 14);
}

QTEST_MAIN(TestSettingsService)
#include "test_settings_service.moc"
