// Toolbox 2.0 desktop application entry point (Phase 2 prototype).
//
// The QML UI lives under ui/; C++ services live under native/.
// Startup rules (master plan §15.4): no reliance on the current working
// directory; all paths resolved from Q StandardPaths or the executable.
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQuickStyle>
#include <QUrl>
#include <QtLogging>

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    QGuiApplication::setOrganizationName(QStringLiteral("Emo"));
    QGuiApplication::setApplicationName(QStringLiteral("Toolbox2"));
    QGuiApplication::setApplicationVersion(QStringLiteral("0.2.0"));

    // Basic style: unstyled primitives that our design system fully controls.
    QQuickStyle::setStyle(QStringLiteral("Basic"));

    QQmlApplicationEngine engine;
    QObject::connect(
        &engine, &QQmlApplicationEngine::objectCreationFailed, &app,
        [] { QCoreApplication::exit(1); }, Qt::QueuedConnection);
    engine.load(QUrl(QStringLiteral("qrc:/Toolbox/ui/Main.qml")));

    return app.exec();
}
