// QML 烟雾测试 + UI 截图基建（v2.0.0-alpha.1 实机反馈催生）。
//
// mainShellLoads：offscreen 真加载主壳 QML。QML 类型解析/模块导入错误只有
// 真实加载才暴露——ctest 模型测试拦不住 "AppButton is not a type" 这类问题。
//
// capture_pages：逐页导航 + grabWindow 存 PNG（SCREENSHOT_DIR，CI 上传为
// artifact）。UI 观感此前无任何视觉评审闭环，截图基建让"改 UI → 看图 →
// 再改"成为可能。与主程序共享同一份 qrc:/Toolbox 模块：本目标用相同
// SOURCES/QML_FILES 重复声明 qt_add_qml_module（独立二进制，不与主程序冲突），
// C++ QML 单例（Application/SettingsService 等）随源编入。
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQuickStyle>
#include <QQuickWindow>
#include <QSGRendererInterface>
#include <QUrl>
#include <QDir>
#include <QImage>
#include <QtQml/qqml.h>
#include <QTest>
#include <app/application.h>

class QmlSmokeTest : public QObject {
    Q_OBJECT

private slots:
    // 主壳加载即门禁：任何类型解析失败都会让 rootObjects 为空，
    // QML 错误明细由默认消息处理器打到 stderr（ctest 失败输出可见）。
    void mainShellLoads() {
        QQuickStyle::setStyle(QStringLiteral("Basic"));
        QQmlApplicationEngine engine;
        engine.load(QUrl(QStringLiteral("qrc:/Toolbox/ui/Main.qml")));
        QVERIFY2(!engine.rootObjects().isEmpty(),
                 "Main.qml 加载失败——QML 错误明细见上方 stderr 输出");
    }

    // 逐页截图：navigate 到每个一级入口，等渲染稳定后 grabWindow。
    // 离屏渲染走 software 光栅化（Grab 无 GPU 依赖）；每页 ~0.5s。
    void capturePages() {
        QQuickWindow::setGraphicsApi(QSGRendererInterface::Software);
        QQuickStyle::setStyle(QStringLiteral("Basic"));
        QQmlApplicationEngine engine;
        engine.load(QUrl(QStringLiteral("qrc:/Toolbox/ui/Main.qml")));
        QVERIFY2(!engine.rootObjects().isEmpty(),
                 "Main.qml 加载失败——QML 错误明细见上方 stderr 输出");
        auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().constFirst());
        QVERIFY2(window != nullptr, "根对象不是 QQuickWindow");
        // Qt 6.4 无 (uri, typeName) 模板重载（CI 实证），经 qmlTypeId 取。
        const int appTypeId = qmlTypeId("Toolbox", "Application");
        QVERIFY2(appTypeId != -1, "QML 类型 Toolbox/Application 未注册");
        auto *application = engine.singletonInstance<toolbox::Application *>(appTypeId);
        QVERIFY2(application != nullptr, "Application 单例不可达");

        QDir outDir(qEnvironmentVariable("SCREENSHOT_DIR", QStringLiteral("screenshots")));
        QVERIFY2(outDir.mkpath(QStringLiteral(".")), "SCREENSHOT_DIR 无法创建");
        // 窗口先稳定渲染一帧，避免首帧空白。
        QTest::qWait(300);
        const QStringList pageIds = {
            QStringLiteral("home"),  QStringLiteral("editor"), QStringLiteral("create"),
            QStringLiteral("batch"), QStringLiteral("analyze"), QStringLiteral("ai"),
            QStringLiteral("files"), QStringLiteral("settings"),
        };
        for (const QString &id : pageIds) {
            QMetaObject::invokeMethod(application, "navigate", Q_ARG(QString, id));
            QTest::qWait(400);
            const QImage shot = window->grabWindow();
            const QString path = outDir.filePath(id + QStringLiteral(".png"));
            QVERIFY2(shot.save(path), qPrintable(QStringLiteral("截图保存失败: ") + path));
            qInfo().nospace() << "screenshot: " << id << " -> " << path;
        }
        // 回首页，保持测试后状态确定。
        QMetaObject::invokeMethod(application, "navigate", Q_ARG(QString, QStringLiteral("home")));
    }
};

QTEST_MAIN(QmlSmokeTest)
#include "test_qml_smoke.moc"
