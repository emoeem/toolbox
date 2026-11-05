#pragma once

#include <QFont>
#include <QObject>
#include <QStringList>
#include <QVariantMap>
#include <QtQml/qqml.h>

namespace toolbox {

// Font resolution for the application shell, mirroring app/fonts.py semantics:
// - an empty family means "platform default" (app/fonts.py:6-7 SYSTEM_DEFAULT);
// - the UI font uses the SansSerif hint + PreferAntialias + PreferFullHinting
//   (app/fonts.py:49-55 ui_font);
// - the mono font uses the Monospace hint (app/fonts.py:58-63 mono_font).
//
// The SANS/MONO candidate chains live here (sansCandidates()/monoCandidates())
// so the settings page offers the same lists the resolver was built for; the
// caller resolves a family with resolveFamily() before applyToApplication().
// Phase 4 task 4 of the project plan ("字体角色和字体设置").
class FontService : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

public:
    static constexpr int kDefaultFontSize = 11;  // app/fonts.py DEFAULT_SIZE

    explicit FontService(QObject *parent = nullptr);
    ~FontService() override;

    // Process-wide instance getter: Application wires it during startup and
    // QML's own singleton lookup must return the same object, never a second.
    static FontService *instance();

    // QML singleton factory, mirroring Application::create: ownership stays
    // with QML so the instance outlives engine bindings.
    static FontService *create(QQmlEngine *qmlEngine, QJSEngine *jsEngine);

    // First installed family among preferred + candidates (preferred wins).
    // Returns an empty string when nothing matches = platform default
    // (app/fonts.py:33-39 resolve_family).
    Q_INVOKABLE QString resolveFamily(const QString &preferred,
                                      const QStringList &candidates) const;

    // Applies family/point size to the whole application via
    // QGuiApplication::setFont. family is expected pre-resolved (or empty =
    // platform default); a non-positive size falls back to kDefaultFontSize,
    // mirroring resolve_size's default-on-failure (app/fonts.py:42-46).
    Q_INVOKABLE void applyToApplication(const QString &family, int size);

    // Full resolution report for the settings page diagnostics. Shape:
    //   ui/mono → { requested, resolved (QFontInfo), size (pointSize),
    //               coverage: { latin, digit, cjk, symbol, emoji },
    //               fallback: { <unset key> → installed families covering
    //                           that set's first code point, max 8 } }
    // Mirrors app/fonts.py diagnose (109-131) with the fallback lists nested
    // per font instead of one ui-only top-level dict.
    Q_INVOKABLE QVariantMap diagnose(const QString &family, const QString &mono,
                                     int size) const;

    // Candidate chains (see class comment for their origin).
    Q_INVOKABLE QStringList sansCandidates() const;
    Q_INVOKABLE QStringList monoCandidates() const;

private:
    QFont uiFont(const QString &family, int size) const;
    QFont monoFont(const QString &family, int size) const;
    QVariantMap glyphReport(const QFont &font, const QString &requested) const;
    QStringList fallbackCandidates(char32_t codePoint) const;
};

} // namespace toolbox
