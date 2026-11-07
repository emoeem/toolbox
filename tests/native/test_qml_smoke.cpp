// QML 烟雾测试（v2.0.0-alpha.1 实机反馈催生）：offscreen 真加载主壳 QML。
// QML 类型解析/模块导入错误只有真实加载才暴露——ctest 模型测试拦不住
// "AppButton is not a type" 这类问题。与 toolbox 主程序共享同一份 qrc:/Toolbox
// 模块：本目标用相同 SOURCES/QML_FILES 重复声明 qt_add_qml_module（独立二进制，
// 不与主程序冲突），C++ QML 单例（Application/SettingsService 等）随源编入。
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQuickStyle>
#include <QTest>
#include <QUrl>

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
};

QTEST_MAIN(QmlSmokeTest)
#include "test_qml_smoke.moc"
