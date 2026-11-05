#include "font_service.h"

#include <QFontDatabase>
#include <QFontInfo>
#include <QGuiApplication>
#include <QJSEngine>
#include <QQmlEngine>
#include <QRawFont>
#include <QSet>
#include <QVector>

#include <string_view>

namespace toolbox {

namespace {

struct GlyphSet
{
    const char *id;             // report key: latin/digit/cjk/symbol/emoji
    std::u32string_view chars;  // checked code points; the first one drives the
                                // fallback probe (app/fonts.py:100 chars[:1])
};

// Diagnostic character sets, mirroring app/fonts.py DIAGNOSTIC_GLYPHS (24-30):
// latin 'Ag', digit '09', cjk 中文像素, symbol →€, emoji 😀 (U+1F600).
// Written as \u escapes so the code points stay correct regardless of the
// compiler's execution charset; QRawFont::supportsCharacter is called per
// code point, matching Python's ord(c) in app/fonts.py:85-86.
const QVector<GlyphSet> &diagnosticGlyphs()
{
    static const QVector<GlyphSet> sets = {
        {"latin", U"Ag"},
        {"digit", U"09"},
        {"cjk", U"\u4E2D\u6587\u50CF\u7D20"},
        {"symbol", U"\u2192\u20AC"},
        {"emoji", U"\U0001F600"},
    };
    return sets;
}

// Mirrors app/fonts.py _covers (85-86): a valid font must cover every code
// point of the set; an invalid QRawFont (unknown family) covers nothing.
bool coversAll(const QRawFont &raw, std::u32string_view chars)
{
    if (!raw.isValid())
        return false;
    for (const char32_t codePoint : chars) {
        if (!raw.supportsCharacter(codePoint))
            return false;
    }
    return true;
}

// A non-positive size cannot be applied to a QFont (Qt rejects it with a
// warning); fall back to the default like resolve_size does for unreadable
// stored values (app/fonts.py:42-46).
int effectivePointSize(int size)
{
    return size > 0 ? size : FontService::kDefaultFontSize;
}

FontService *s_instance = nullptr;  // process-wide singleton identity

} // namespace

FontService::FontService(QObject *parent)
    : QObject(parent)
{
}

FontService::~FontService()
{
    if (s_instance == this)
        s_instance = nullptr;
}

FontService *FontService::instance()
{
    if (!s_instance)
        s_instance = new FontService();
    return s_instance;
}

FontService *FontService::create(QQmlEngine *qmlEngine, QJSEngine *jsEngine)
{
    // The instance must outlive the engine bindings; ownership stays with QML.
    Q_UNUSED(qmlEngine);
    Q_UNUSED(jsEngine);
    return instance();
}

QString FontService::resolveFamily(const QString &preferred, const QStringList &candidates) const
{
    const QStringList installed = QFontDatabase::families();
    const QSet<QString> installedSet(installed.cbegin(), installed.cend());
    if (!preferred.isEmpty() && installedSet.contains(preferred))
        return preferred;
    for (const QString &candidate : candidates) {
        if (!candidate.isEmpty() && installedSet.contains(candidate))
            return candidate;
    }
    // Empty = platform default, mirroring app/fonts.py SYSTEM_DEFAULT.
    return {};
}

void FontService::applyToApplication(const QString &family, int size)
{
    QGuiApplication::setFont(uiFont(family, size));
}

QVariantMap FontService::diagnose(const QString &family, const QString &mono, int size) const
{
    QVariantMap report;
    report.insert(QStringLiteral("ui"), glyphReport(uiFont(family, size), family));
    report.insert(QStringLiteral("mono"), glyphReport(monoFont(mono, size), mono));
    return report;
}

QStringList FontService::sansCandidates() const
{
    return {
        QStringLiteral("Noto Sans CJK SC"),
        QStringLiteral("Sarasa UI SC"),
        QStringLiteral("Source Han Sans SC"),
        QStringLiteral("Microsoft YaHei UI"),
        QStringLiteral("Microsoft YaHei"),
        QStringLiteral("WenQuanYi Zen Hei"),
        QStringLiteral("LXGW ZhenKai"),
    };
}

QStringList FontService::monoCandidates() const
{
    // 与 app/fonts.py MONO_CANDIDATES 保持同序同项（9 项），评审修正补齐。
    return {
        QStringLiteral("Maple Mono Normal NF CN"),
        QStringLiteral("Maple Mono NF CN"),
        QStringLiteral("Maple Mono"),
        QStringLiteral("JetBrains Mono"),
        QStringLiteral("Cascadia Mono"),
        QStringLiteral("Cascadia Code"),
        QStringLiteral("Consolas"),
        QStringLiteral("Noto Sans Mono CJK SC"),
        QStringLiteral("DejaVu Sans Mono"),
    };
}

QFont FontService::uiFont(const QString &family, int size) const
{
    QFont font(family, effectivePointSize(size));
    font.setStyleHint(QFont::SansSerif);
    font.setStyleStrategy(QFont::PreferAntialias);
    font.setHintingPreference(QFont::PreferFullHinting);
    return font;
}

QFont FontService::monoFont(const QString &family, int size) const
{
    QFont font(family, effectivePointSize(size));
    font.setStyleHint(QFont::Monospace);
    return font;
}

QVariantMap FontService::glyphReport(const QFont &font, const QString &requested) const
{
    const QRawFont raw = QRawFont::fromFont(font);
    QVariantMap coverage;
    QVariantMap fallback;
    for (const GlyphSet &set : diagnosticGlyphs()) {
        const bool covered = coversAll(raw, set.chars);
        coverage.insert(QString::fromLatin1(set.id), covered);
        if (!covered)
            fallback.insert(QString::fromLatin1(set.id), fallbackCandidates(set.chars.front()));
    }
    QVariantMap report;
    report.insert(QStringLiteral("requested"), requested);
    report.insert(QStringLiteral("resolved"), QFontInfo(font).family());
    report.insert(QStringLiteral("size"), font.pointSize());
    report.insert(QStringLiteral("coverage"), coverage);
    report.insert(QStringLiteral("fallback"), fallback);
    return report;
}

QStringList FontService::fallbackCandidates(char32_t codePoint) const
{
    static constexpr int kFallbackLimit = 8;  // app/fonts.py fallback_candidates limit
    const std::u32string_view probe{&codePoint, 1};
    QStringList found;
    const QStringList families = QFontDatabase::families();
    for (const QString &family : families) {
        if (coversAll(QRawFont::fromFont(QFont(family)), probe))
            found.append(family);
        if (found.size() >= kFallbackLimit)
            break;
    }
    return found;
}

} // namespace toolbox
