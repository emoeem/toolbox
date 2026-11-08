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
#include <QDir>
#include <QGuiApplication>
#include <QImage>
#include <QLibraryInfo>
#include <QQmlApplicationEngine>
#include <QQuickItem>
#include <QQuickLoader>
#include <QQuickStyle>
#include <QQuickWindow>
#include <QSGRendererInterface>
#include <QSignalSpy>
#include <QTest>
#include <QUrl>
#include <QtQml/qqml.h>
#include <app/application.h>

class QmlSmokeTest : public QObject {
    Q_OBJECT

  private slots:
    // 主壳加载即门禁：任何类型解析失败都会让 rootObjects 为空，
    // QML 错误明细由默认消息处理器打到 stderr（ctest 失败输出可见）。
    void mainShellLoads() {
        QQuickStyle::setStyle(QStringLiteral("Basic"));
        QQmlApplicationEngine engine;
        // CI 实证：apt 布局下 QtQuick.Controls 报插件 "not found"（qmldir 可
        // 读但插件解析失败）——显式补 QLibraryInfo 的 Qml2Imports 并打印
        // 路径地面真相。
        engine.addImportPath(QLibraryInfo::path(QLibraryInfo::Qml2ImportsPath));
        qWarning() << "Qml2ImportsPath:" << QLibraryInfo::path(QLibraryInfo::Qml2ImportsPath);
        qWarning() << "importPaths:" << engine.importPathList();
        engine.load(QUrl(QStringLiteral("qrc:/Toolbox/ui/Main.qml")));
        QVERIFY2(!engine.rootObjects().isEmpty(),
                 "Main.qml 加载失败——QML 错误明细见上方 stderr 输出");
    }

    // 逐页截图：navigate 到每个一级入口，等渲染稳定后 grabWindow。
    // 离屏渲染走 software 光栅化（Grab 无 GPU 依赖）；每页 ~0.5s。
    // 页面加载错误必须在场即红（v2.0.0-alpha.2 判决：editor/batch/settings/
    // studio 四页空白加载，ctest 隐藏通过用例输出导致错误不可见——本断言
    // 强制所有页面级 QML 错误浮出）。
    void capturePages() {
        QQuickWindow::setGraphicsApi(QSGRendererInterface::Software);
        QQuickStyle::setStyle(QStringLiteral("Basic"));
        QQmlApplicationEngine engine;
        engine.addImportPath(QLibraryInfo::path(QLibraryInfo::Qml2ImportsPath));
        QStringList pageWarnings;
        QObject::connect(&engine, &QQmlApplicationEngine::warnings,
                         [&pageWarnings](const QList<QQmlError> &warnings) {
                             for (const auto &w : warnings) {
                                 pageWarnings << w.toString();
                             }
                         });
        engine.load(QUrl(QStringLiteral("qrc:/Toolbox/ui/Main.qml")));
        QVERIFY2(!engine.rootObjects().isEmpty(),
                 "Main.qml 加载失败——QML 错误明细见上方 stderr 输出");
        QVERIFY2(pageWarnings.isEmpty(),
                 qPrintable(QStringLiteral("Main.qml 加载产生警告：\n") + pageWarnings.join("\n")));
        auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().constFirst());
        QVERIFY2(window != nullptr, "根对象不是 QQuickWindow");
        // Qt 6.4 无 (uri, typeName) 模板重载（CI 实证），经 qmlTypeId 取。
        const int appTypeId = qmlTypeId("Toolbox", 1, 0, "Application");
        QVERIFY2(appTypeId != -1, "QML 类型 Toolbox/Application 未注册");
        auto *application = engine.singletonInstance<toolbox::Application *>(appTypeId);
        QVERIFY2(application != nullptr, "Application 单例不可达");

        QDir outDir(qEnvironmentVariable("SCREENSHOT_DIR", QStringLiteral("screenshots")));
        QVERIFY2(outDir.mkpath(QStringLiteral(".")), "SCREENSHOT_DIR 无法创建");
        // 窗口先稳定渲染一帧，避免首帧空白。
        QTest::qWait(300);
        // 页面 Loader（Main.qml objectName=pageLoader）：诊断四页空白的地面真相
        // ——status/item 几何/可见性逐页打印并断言。
        auto *loaderItem = window->findChild<QQuickItem *>(QStringLiteral("pageLoader"));
        QVERIFY2(loaderItem != nullptr, "找不到 pageLoader（Main.qml objectName 缺失）");
        QSignalSpy swapSpy(window, &QQuickWindow::frameSwapped);
        QVERIFY2(swapSpy.isValid(), "frameSwapped 信号监视无效");
        const QStringList pageIds = {
            QStringLiteral("home"),  QStringLiteral("editor"),   QStringLiteral("create"),
            QStringLiteral("batch"), QStringLiteral("analyze"),  QStringLiteral("ai"),
            QStringLiteral("files"), QStringLiteral("settings"),
        };
        for (const QString &id : pageIds) {
            const int before = pageWarnings.size();
            QMetaObject::invokeMethod(application, "navigate", Q_ARG(QString, id));
            // 等真实渲染帧（软件光栅下 grabWindow 前至少 3 帧），最多 8s。
            swapSpy.clear();
            qWaitFor([&swapSpy] { return swapSpy.size() >= 3; }, 8000);
            qWarning().nospace() << "[capture] " << id
                                 << " loader.status=" << loaderItem->property("status").toInt()
                                 << " item=" << loaderItem->property("item")
                                 << " warnings+=" << (pageWarnings.size() - before);
            QVERIFY2(loaderItem->property("status").toInt() == QQuickLoader::Ready,
                     qPrintable(QStringLiteral("页面 %1 Loader 未 Ready：status=").arg(id) +
                                loaderItem->property("status").toString()));
            QVERIFY2(pageWarnings.size() == before,
                     qPrintable(QStringLiteral("页面 %1 加载产生 QML 错误：\n%2")
                                    .arg(id, pageWarnings.join("\n"))));
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
