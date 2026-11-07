// Toolbox 2.0 desktop application entry point (Phase 2 prototype).
//
// The QML UI lives under ui/; C++ services live under native/.
// Startup rules (master plan §15.4): no reliance on the current working
// directory; all paths resolved from Q StandardPaths or the executable.
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQuickStyle>
#include <QTimer>
#include <QUrl>
#include <QtCore/qlogging.h>

int main(int argc, char *argv[]) {
    // --qml-smoke：打包产物自检模式（v2.0.0-alpha.1 实机反馈催生）。
    // 强制 offscreen 真加载主壳 QML，创建成功即退出 0，失败退出 1。
    // release.yml 在三平台打包后各跑一次，把 "CI 构建绿但运行时 QML 坏"
    // （如插件缺失、QML 模块没随包）拦在发布之前。
    const bool smoke = argc > 1 && qstrcmp(argv[1], "--qml-smoke") == 0;
    // 仅在未显式指定平台时才默认 offscreen（macOS runner 有 WindowServer，
    // 强制 offscreen 反而可能因 offscreen 插件未随 macdeployqt 部署而失败）。
    if (smoke && !qEnvironmentVariableIsSet("QT_QPA_PLATFORM")) {
        qputenv("QT_QPA_PLATFORM", "offscreen");
    }

    QGuiApplication app(argc, argv);
    QGuiApplication::setOrganizationName(QStringLiteral("Emo"));
    QGuiApplication::setApplicationName(QStringLiteral("Toolbox2"));
    // 与 pyproject.toml version（单一来源）对齐，见 CHANGELOG.md
    // v2.0.0-alpha.2 条目。
    QGuiApplication::setApplicationVersion(QStringLiteral("2.0.0-alpha.2"));

    // Basic style: unstyled primitives that our design system fully controls.
    QQuickStyle::setStyle(QStringLiteral("Basic"));

    QQmlApplicationEngine engine;
    QObject::connect(
        &engine, &QQmlApplicationEngine::objectCreationFailed, &app,
        [] { QCoreApplication::exit(1); }, Qt::QueuedConnection);
    engine.load(QUrl(QStringLiteral("qrc:/Toolbox/ui/Main.qml")));

    if (smoke) {
        // load() 同步完成：root 对象非空即通过；短转一圈事件循环让首批
        // 绑定求值/告警浮出，再以 0 退出。
        if (engine.rootObjects().isEmpty()) {
            return 1;
        }
        QTimer::singleShot(300, &app, [] { QCoreApplication::exit(0); });
        return app.exec();
    }

    return app.exec();
}
