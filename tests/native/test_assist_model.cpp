// Phase 7 model tests: AssistModel as the assist.list catalog frontend
// (辅助工具页，docs/ipc-protocol.md §3.8 / 总纲 §9.9 / §13 Phase 7).
//
// 纯数据模型：不连 BackendManager（填充入口 reloadFrom 由 AssistService 或测试
// 直接调用），所以无需 Harness 发信号——直接构造、直接喂 assist.list 的
// result 形状（{tools: [...]}，与 §3 filter.list / generate.list 同构；形状
// 契约见 docs/ipc-protocol.md §3.8，Python 侧 python_worker/adapters/
// assist_adapter.py list_tools，Worker 测试锁 tests/test_worker_assist.py）。
// 条目 key 即运行动作名（§3.8 "条目 key 即动作名"），固件使用真实动作词汇
// （ocr.run / checksum.file / base64.encode / barcode.decode）；角色名断言锁
// 定辅助工具页（工具名/分类/置灰）要消费的 QML 契约。
#include <QtTest/QAbstractItemModelTester>
#include <QtTest/QtTest>

#include <QJsonArray>
#include <QJsonObject>
#include <QSignalSpy>

#include "models/assist_model.h"

using toolbox::AssistModel;

namespace {

// 一条完整的 assist.list 条目（形状 = §3.8 条目词汇，见 assist_model.h
// 头注释的协议对齐说明）。
QJsonObject toolEntry(const QString &key, const QString &name, const QString &category,
                      const QString &categoryLabel, bool available, const QStringList &deps) {
    QJsonArray depsArray;
    for (const auto &dep : deps)
        depsArray.append(dep);
    QJsonObject entry{
        {QStringLiteral("key"), key},
        {QStringLiteral("name"), name},
        {QStringLiteral("category"), category},
        {QStringLiteral("available"), available},
        {QStringLiteral("optional_deps"), depsArray},
    };
    if (!categoryLabel.isEmpty())
        entry.insert(QStringLiteral("category_label"), categoryLabel);
    return entry;
}

QJsonObject assistListResult(std::initializer_list<QJsonObject> tools) {
    QJsonArray array;
    for (const auto &item : tools)
        array.append(item);
    return QJsonObject{{QStringLiteral("tools"), array}};
}

} // namespace

class TestAssistModel : public QObject {
    Q_OBJECT

  private slots:
    void roleNamesMatchImplementation();
    void reloadFromParsesProtocolShape();
    void reloadFromFallsBackToCategory();
    void reloadFromClearsAndReplaces();
    void reloadFromSkipsKeylessEntries();
    void dataOnInvalidIndexes();

  private:
    static QModelIndex found(const QAbstractItemModel &model, int role, const QString &value);
};

QModelIndex TestAssistModel::found(const QAbstractItemModel &model, int role,
                                   const QString &value) {
    for (int row = 0; row < model.rowCount(); ++row) {
        if (model.index(row, 0).data(role).toString() == value)
            return model.index(row, 0);
    }
    return {};
}

void TestAssistModel::roleNamesMatchImplementation() {
    AssistModel model;
    QAbstractItemModelTester tester(&model);

    const auto roles = model.roleNames();
    QCOMPARE(roles.size(), 5);
    // 辅助工具页按这些名字取值（toolKey/toolName/categoryLabel/available/
    // optionalDeps，任务清单指定的五个角色）。
    QCOMPARE(roles.value(AssistModel::ToolKeyRole), QByteArray("toolKey"));
    QCOMPARE(roles.value(AssistModel::ToolNameRole), QByteArray("toolName"));
    QCOMPARE(roles.value(AssistModel::CategoryLabelRole), QByteArray("categoryLabel"));
    QCOMPARE(roles.value(AssistModel::AvailableRole), QByteArray("available"));
    QCOMPARE(roles.value(AssistModel::OptionalDepsRole), QByteArray("optionalDeps"));
}

void TestAssistModel::reloadFromParsesProtocolShape() {
    AssistModel model;
    QAbstractItemModelTester tester(&model);
    QSignalSpy resetSpy(&model, &QAbstractItemModel::modelReset);

    model.reloadFrom(assistListResult(
        {toolEntry(QStringLiteral("ocr.run"), QStringLiteral("OCR 文字识别"),
                   QStringLiteral("ocr"), QStringLiteral("OCR 文字识别"), true, {}),
         toolEntry(QStringLiteral("barcode.decode"), QStringLiteral("识别条码/二维码"),
                   QStringLiteral("barcode"), QStringLiteral("条形码"), false,
                   {QStringLiteral("pyzbar")})}));
    QCOMPARE(resetSpy.count(), 1);
    QCOMPARE(model.rowCount(), 2);

    const auto ocr = found(model, AssistModel::ToolKeyRole, QStringLiteral("ocr.run"));
    QVERIFY(ocr.isValid());
    QCOMPARE(ocr.data(AssistModel::ToolNameRole).toString(), QStringLiteral("OCR 文字识别"));
    QCOMPARE(ocr.data(AssistModel::CategoryLabelRole).toString(), QStringLiteral("OCR 文字识别"));
    QCOMPARE(ocr.data(AssistModel::AvailableRole).toBool(), true);
    QCOMPARE(ocr.data(AssistModel::OptionalDepsRole).toStringList(), QStringList{});

    // 不可用条目携带依赖列表——置灰 + 原因（§3.8：pyzbar 缺失 → available=
    // false + optional_deps 列出缺失名；总纲 Phase 7："缺少模型或二进制时
    // 不得显示虚假的可用状态"）。
    const auto decode =
        found(model, AssistModel::ToolKeyRole, QStringLiteral("barcode.decode"));
    QVERIFY(decode.isValid());
    QCOMPARE(decode.data(AssistModel::AvailableRole).toBool(), false);
    QCOMPARE(decode.data(AssistModel::OptionalDepsRole).toStringList(),
             QStringList{QStringLiteral("pyzbar")});
}

void TestAssistModel::reloadFromFallsBackToCategory() {
    AssistModel model;
    QAbstractItemModelTester tester(&model);

    // 缺 category_label 时回落 category 原值（同一条目至少有类别可显，
    // filter_model.cpp:23-27 的同一约定）。
    model.reloadFrom(assistListResult(
        {toolEntry(QStringLiteral("checksum.file"), QStringLiteral("校验和"),
                   QStringLiteral("checksum"), QString(), true, {})}));
    QCOMPARE(model.rowCount(), 1);
    QCOMPARE(model.index(0, 0).data(AssistModel::CategoryLabelRole).toString(),
             QStringLiteral("checksum"));
}

void TestAssistModel::reloadFromClearsAndReplaces() {
    AssistModel model;
    QAbstractItemModelTester tester(&model);

    model.reloadFrom(assistListResult(
        {toolEntry(QStringLiteral("ocr.run"), QStringLiteral("OCR 文字识别"),
                   QStringLiteral("ocr"), QStringLiteral("OCR 文字识别"), true, {})}));
    QCOMPARE(model.rowCount(), 1);

    // 空对象 / 缺 tools 字段 = 清空（FilterModel::reloadFrom 同款语义，
    // test_filter_model.cpp 对空 result 的处置）。
    model.reloadFrom(QJsonObject{});
    QCOMPARE(model.rowCount(), 0);

    model.reloadFrom(assistListResult({}));
    QCOMPARE(model.rowCount(), 0);

    // 整表替换而非追加：第二次填充后旧条目不复存在。
    model.reloadFrom(assistListResult(
        {toolEntry(QStringLiteral("base64.encode"), QStringLiteral("Base64 编码"),
                   QStringLiteral("base64"), QStringLiteral("Base64"), true, {})}));
    QCOMPARE(model.rowCount(), 1);
    QVERIFY(!found(model, AssistModel::ToolKeyRole, QStringLiteral("ocr.run")).isValid());
    QCOMPARE(found(model, AssistModel::ToolKeyRole, QStringLiteral("base64.encode")).isValid(),
             true);
}

void TestAssistModel::reloadFromSkipsKeylessEntries() {
    AssistModel model;
    QAbstractItemModelTester tester(&model);

    // 无 key 的条目无法运行（key = 运行动作名，§3.8，assist_model.h 头注释），
    // 模型层同样不收——目录条目必须能提交成 runTool 请求。
    model.reloadFrom(assistListResult(
        {QJsonObject{{QStringLiteral("name"), QStringLiteral("无键条目")},
                     {QStringLiteral("category_label"), QStringLiteral("其他")}},
         toolEntry(QStringLiteral("ocr.run"), QStringLiteral("有效"),
                   QStringLiteral("ocr"), QStringLiteral("OCR 文字识别"), true, {})}));
    QCOMPARE(model.rowCount(), 1);
    QCOMPARE(model.index(0, 0).data(AssistModel::ToolKeyRole).toString(),
             QStringLiteral("ocr.run"));
}

void TestAssistModel::dataOnInvalidIndexes() {
    AssistModel model;
    QAbstractItemModelTester tester(&model);
    model.reloadFrom(assistListResult(
        {toolEntry(QStringLiteral("ocr.run"), QStringLiteral("OCR 文字识别"),
                   QStringLiteral("ocr"), QStringLiteral("OCR 文字识别"), true, {})}));
    QCOMPARE(model.rowCount(), 1);

    // 扁平表契约（FilterModel::dataOnInvalidIndexes 同款）：负行/越界行/带父
    // 索引的查询一律回答无效索引与无效值，而非崩溃或读出脏数据
    //（assist_model.cpp data() 的防御分支——UI 传错行号不得越界取值）。
    QVERIFY(!model.index(-1, 0).isValid());
    QVERIFY(!model.index(model.rowCount(), 0).isValid());
    const QModelIndex row0 = model.index(0, 0);
    QCOMPARE(model.rowCount(row0), 0);
    QVERIFY(!model.index(0, 0, row0).isValid());
    QVERIFY(!model.index(-1, 0).data(AssistModel::ToolKeyRole).isValid());
    QVERIFY(!model.index(model.rowCount(), 0).data(AssistModel::AvailableRole).isValid());
    QVERIFY(!model.data(QModelIndex(), AssistModel::ToolKeyRole).isValid());
}

QTEST_MAIN(TestAssistModel)
#include "test_assist_model.moc"
