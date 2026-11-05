// Phase 2 model tests: catalog data contract exposed to QML.
#include <QtTest/QAbstractItemModelTester>
#include <QtTest/QtTest>

#include "models/tool_model.h"

using toolbox::NavModel;
using toolbox::ToolModel;

class TestModels : public QObject
{
    Q_OBJECT

private slots:
    void toolModelRolesAndData();
    void toolModelIndexOfId();
    void navModelPageForId();
    void navModelRowCount();
};

void TestModels::toolModelRolesAndData()
{
    ToolModel model;
    model.addEntry({QStringLiteral("tool.ocr"), QStringLiteral("OCR"),
                    QStringLiteral("文件工具"), false, QStringLiteral("P2"),
                    QStringLiteral("ocr tesseract")});
    model.addEntry({QStringLiteral("tool.adjust"), QStringLiteral("调整"),
                    QStringLiteral("图像编辑"), true, QStringLiteral("P0"),
                    QStringLiteral("亮度 对比度")});

    QAbstractItemModelTester tester(&model); // aborts the test on model contract violation
    QCOMPARE(model.rowCount(), 2);

    const auto index = model.index(0, 0);
    QCOMPARE(index.data(ToolModel::IdRole).toString(), QStringLiteral("tool.ocr"));
    QCOMPARE(index.data(ToolModel::TitleRole).toString(), QStringLiteral("OCR"));
    QCOMPARE(index.data(ToolModel::AvailableRole).toBool(), false);
    QCOMPARE(index.data(ToolModel::PhaseRole).toString(), QStringLiteral("P2"));

    // QML role names are part of the contract (component spec §3).
    const auto roles = model.roleNames();
    QCOMPARE(roles.value(ToolModel::TitleRole), QByteArray("title"));
    QCOMPARE(roles.value(ToolModel::AvailableRole), QByteArray("available"));
}

void TestModels::toolModelIndexOfId()
{
    ToolModel model;
    model.addEntry({QStringLiteral("a"), QStringLiteral("A"), {}, true, {}, {}});
    QCOMPARE(model.indexOfId(QStringLiteral("a")), 0);
    QCOMPARE(model.indexOfId(QStringLiteral("missing")), -1);

    const auto map = model.get(0);
    QCOMPARE(map.value(QStringLiteral("id")).toString(), QStringLiteral("a"));
    QVERIFY(map.value(QStringLiteral("available")).toBool());
    QVERIFY(model.get(99).isEmpty());
}

void TestModels::navModelPageForId()
{
    NavModel model;
    const QUrl page{QStringLiteral("qrc:/Toolbox/ui/pages/HomePage.qml")};
    model.addEntry({QStringLiteral("home"), QStringLiteral("首页"), page, true, QStringLiteral("P0")});
    model.addEntry({QStringLiteral("ai"), QStringLiteral("AI"),
                    QUrl{QStringLiteral("qrc:/Toolbox/ui/pages/PlannedPage.qml")},
                    false, QStringLiteral("P2")});

    QCOMPARE(model.pageForId(QStringLiteral("home")), page);
    QVERIFY(model.pageForId(QStringLiteral("missing")).isEmpty());

    QAbstractItemModelTester tester(&model);
    QCOMPARE(model.rowCount(), 2);
    const auto roles = model.roleNames();
    QCOMPARE(roles.value(NavModel::NavPageRole), QByteArray("page"));
    QCOMPARE(roles.value(NavModel::NavAvailableRole), QByteArray("available"));
}

void TestModels::navModelRowCount()
{
    NavModel model;
    QCOMPARE(model.rowCount(), 0);
    model.addEntry({QStringLiteral("x"), {}, {}, false, {}});
    QCOMPARE(model.rowCount(), 1);
}

QTEST_MAIN(TestModels)
#include "test_models.moc"
