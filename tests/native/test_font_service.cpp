// Phase 4 service tests: FontService resolution + diagnostics, mirroring the
// coverage the Python suite locks in tests/test_fonts.py.
//
// resolveFamily() is a pure QFontDatabase::families() membership test
// (font_service.cpp:93-105), so the candidate-chain logic is deterministic in
// any environment; the two tests that need an actually installed family skip
// when none exists, mirroring tests/test_fonts.py ("系统未安装任何字体").
// diagnose() structural assertions hold everywhere: an unknown family produces
// an invalid QRawFont whose coverage is all-false with fallback lists still
// populated (font_service.cpp:44-53/162-180). The five diagnostic classes
// (latin/digit/cjk/symbol/emoji) mirror app/fonts.py DIAGNOSTIC_GLYPHS.
#include <QtTest/QtTest>

#include <QFontDatabase>
#include <QGuiApplication>
#include <QVariantMap>

#include "services/font_service.h"

using toolbox::FontService;

namespace {

const QStringList kCoverageClasses = {
    QStringLiteral("latin"),  QStringLiteral("digit"), QStringLiteral("cjk"),
    QStringLiteral("symbol"), QStringLiteral("emoji"),
};

constexpr int kFallbackLimit = 8; // font_service.cpp:184 (kFallbackLimit)

} // namespace

class TestFontService : public QObject {
    Q_OBJECT

  private slots:
    void resolveFamilyPrefersPreferredFamily();
    void resolveFamilyWalksCandidateChainInOrder();
    void resolveFamilyUnknownFallsBackToPlatformDefault();
    void diagnoseReportsUiAndMonoSections();
    void diagnoseCoverageHasFiveClasses();
    void diagnoseFallsBackToDefaultSize();
    void diagnoseFallbackListsAreBounded();
    void applyToApplicationSetsAppFont();
};

void TestFontService::resolveFamilyPrefersPreferredFamily() {
    if (QFontDatabase::families().isEmpty())
        QSKIP("系统未安装任何字体");

    FontService service;
    const QString installed = QFontDatabase::families().constFirst();
    // An installed preferred family wins over the whole candidate chain
    // (font_service.cpp:97-98), including an empty chain.
    QCOMPARE(service.resolveFamily(installed, {}), installed);
    QCOMPARE(
        service.resolveFamily(installed, QStringList{QStringLiteral("ToolboxTestMissingSans")}),
        installed);
}

void TestFontService::resolveFamilyWalksCandidateChainInOrder() {
    if (QFontDatabase::families().isEmpty())
        QSKIP("系统未安装任何字体");

    FontService service;
    const QStringList installed = QFontDatabase::families();
    // Preferred missing → the first *installed* entry of the chain wins.
    QCOMPARE(service.resolveFamily(
                 QStringLiteral("ToolboxTestMissingFont"),
                 QStringList{QStringLiteral("ToolboxTestMissingSans"), installed.at(0)}),
             installed.at(0));

    if (installed.size() >= 2) {
        // Two installed candidates: chain order decides, not QFontDatabase order.
        QCOMPARE(service.resolveFamily(QString(), QStringList{installed.at(1), installed.at(0)}),
                 installed.at(1));
    }
}

void TestFontService::resolveFamilyUnknownFallsBackToPlatformDefault() {
    FontService service;
    // Nothing installed among preferred + candidates → empty string, which the
    // caller maps to the platform default (app/fonts.py:6-7 SYSTEM_DEFAULT,
    // font_service.cpp:102-104). Works without any installed font.
    QVERIFY(service
                .resolveFamily(QStringLiteral("ToolboxTestMissingFont"),
                               QStringList{QStringLiteral("ToolboxTestMissingSans"),
                                           QStringLiteral("ToolboxTestMissingMono")})
                .isEmpty());
    QVERIFY(service.resolveFamily(QString(), {}).isEmpty());
}

void TestFontService::diagnoseReportsUiAndMonoSections() {
    FontService service;
    const QVariantMap report = service.diagnose(QStringLiteral("ToolboxTestMissingFont"),
                                                QStringLiteral("ToolboxTestMissingMono"), 13);
    // Top level carries exactly the ui/mono sections (font_service.cpp:112-118).
    QVERIFY(!report.contains(QStringLiteral("requested")));
    QVERIFY(report.contains(QStringLiteral("ui")));
    QVERIFY(report.contains(QStringLiteral("mono")));

    const QVariantMap ui = report.value(QStringLiteral("ui")).toMap();
    const QVariantMap mono = report.value(QStringLiteral("mono")).toMap();
    QVERIFY(!ui.isEmpty());
    QVERIFY(!mono.isEmpty());
    for (const QString &section :
         {QStringLiteral("requested"), QStringLiteral("resolved"), QStringLiteral("size"),
          QStringLiteral("coverage"), QStringLiteral("fallback")}) {
        QVERIFY2(ui.contains(section), qPrintable(QStringLiteral("ui 缺少 %1").arg(section)));
        QVERIFY2(mono.contains(section), qPrintable(QStringLiteral("mono 缺少 %1").arg(section)));
    }

    // The request is echoed verbatim; the size is applied to both roles.
    // (resolved is environment-dependent — an unknown family resolves through
    // fontconfig — so its value is deliberately not asserted.)
    QCOMPARE(ui.value(QStringLiteral("requested")).toString(),
             QStringLiteral("ToolboxTestMissingFont"));
    QCOMPARE(mono.value(QStringLiteral("requested")).toString(),
             QStringLiteral("ToolboxTestMissingMono"));
    QCOMPARE(ui.value(QStringLiteral("size")).toInt(), 13);
    QCOMPARE(mono.value(QStringLiteral("size")).toInt(), 13);
}

void TestFontService::diagnoseCoverageHasFiveClasses() {
    FontService service;
    const QVariantMap ui =
        service.diagnose(QString(), QString(), 11).value(QStringLiteral("ui")).toMap();
    const QVariantMap coverage = ui.value(QStringLiteral("coverage")).toMap();
    const QVariantMap fallback = ui.value(QStringLiteral("fallback")).toMap();

    for (const QString &key : kCoverageClasses) {
        QVERIFY2(coverage.contains(key), qPrintable(QStringLiteral("coverage 缺少 %1").arg(key)));
        QVERIFY2(coverage.value(key).typeId() == QMetaType::Bool,
                 qPrintable(QStringLiteral("coverage.%1 不是布尔值").arg(key)));
    }

    // fallback entries exist only for uncovered classes, never for covered ones.
    for (auto it = fallback.constBegin(); it != fallback.constEnd(); ++it)
        QVERIFY2(!coverage.value(it.key()).toBool(),
                 qPrintable(QStringLiteral("已覆盖的 %1 不应出现在 fallback").arg(it.key())));

    if (QFontDatabase::families().isEmpty()) {
        // Without any installed font the QRawFont is invalid: nothing is
        // covered, and the report still carries a fallback list per class
        // (coversAll → false, font_service.cpp:44-53).
        for (const QString &key : kCoverageClasses) {
            QVERIFY(!coverage.value(key).toBool());
            QVERIFY(fallback.contains(key));
        }
    }
}

void TestFontService::diagnoseFallsBackToDefaultSize() {
    FontService service;
    // resolve_size semantics (app/fonts.py:42-46): a non-positive size cannot
    // be applied and falls back to DEFAULT_SIZE = 11 (font_service.cpp:58-61).
    QCOMPARE(service.diagnose(QString(), QString(), 0)
                 .value(QStringLiteral("ui"))
                 .toMap()
                 .value(QStringLiteral("size"))
                 .toInt(),
             FontService::kDefaultFontSize);
    QCOMPARE(service.diagnose(QString(), QString(), -3)
                 .value(QStringLiteral("mono"))
                 .toMap()
                 .value(QStringLiteral("size"))
                 .toInt(),
             11);
}

void TestFontService::diagnoseFallbackListsAreBounded() {
    FontService service;
    const QVariantMap fallback = service.diagnose(QString(), QString(), 11)
                                     .value(QStringLiteral("mono"))
                                     .toMap()
                                     .value(QStringLiteral("fallback"))
                                     .toMap();
    const QStringList installed = QFontDatabase::families();

    for (auto it = fallback.constBegin(); it != fallback.constEnd(); ++it) {
        const QStringList families = it.value().toStringList();
        QVERIFY2(families.size() <= kFallbackLimit,
                 qPrintable(QStringLiteral("%1 回退列表超过 8 项").arg(it.key())));
        for (const QString &family : families) {
            // Every fallback candidate must be a real installed family.
            QVERIFY2(installed.contains(family),
                     qPrintable(QStringLiteral("%1 回退项 %2 未安装").arg(it.key(), family)));
        }
    }
}

void TestFontService::applyToApplicationSetsAppFont() {
    // applyToApplication mirrors app/fonts.py ui_font: it applies the request
    // to the whole application via QGuiApplication::setFont
    // (font_service.cpp:107-110); per-widget resolution happens later.
    FontService service;
    service.applyToApplication(QStringLiteral("ToolboxTestMissingFont"), 14);
    QCOMPARE(QGuiApplication::font().family(), QStringLiteral("ToolboxTestMissingFont"));
    QCOMPARE(QGuiApplication::font().pointSize(), 14);

    // Non-positive size falls back to the default instead of reaching Qt.
    service.applyToApplication(QString(), 0);
    QCOMPARE(QGuiApplication::font().pointSize(), FontService::kDefaultFontSize);
}

QTEST_MAIN(TestFontService)
#include "test_font_service.moc"
