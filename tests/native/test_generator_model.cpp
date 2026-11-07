// Phase 6C model tests: GeneratorModel as the generate.list catalog frontend
// (Texture Studio, docs/toolbox-2.0-project-plan.md §9.7).
//
// 纯数据模型：不连 BackendManager（填充入口 reloadFrom 由 StudioService 或测试
// 直接调用），所以无需 Harness 发信号——直接构造、直接喂 generate.list 的
// result 形状（{generators: [...]}，与 §3 filter.list 同构；generate.* 尚未
// 写入 docs/ipc-protocol.md，形状契约的出处见 studio_service.h 头注释）。
// 角色名断言锁定 TexturePage 左栏（生成器/置灰/搜索）要消费的 QML 契约。
#include <QtTest/QAbstractItemModelTester>
#include <QtTest/QtTest>

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSignalSpy>

#include "models/generator_model.h"

using toolbox::GeneratorModel;

namespace {

// 一条完整的 generate.list 条目（形状 = filter.list 条目的同构映射，见
// studio_service.h 头注释的协议状态注记）。
QJsonObject generatorEntry(const QString &key, const QString &name, const QString &category,
                           const QString &categoryLabel, bool available, const QStringList &deps,
                           const QJsonArray &params = QJsonArray{}) {
    QJsonArray depsArray;
    for (const auto &dep : deps)
        depsArray.append(dep);
    QJsonObject entry{
        {QStringLiteral("key"), key},
        {QStringLiteral("name"), name},
        {QStringLiteral("category"), category},
        {QStringLiteral("available"), available},
        {QStringLiteral("optional_deps"), depsArray},
        {QStringLiteral("params"), params},
    };
    if (!categoryLabel.isEmpty())
        entry.insert(QStringLiteral("category_label"), categoryLabel);
    return entry;
}

QJsonObject generatorListResult(std::initializer_list<QJsonObject> generators) {
    QJsonArray array;
    for (const auto &item : generators)
        array.append(item);
    return QJsonObject{{QStringLiteral("generators"), array}};
}

// 带一个参数定义的 params 数组（AppFilterParameterGroup 式自动控件的输入）。
QJsonArray seedParams() {
    return QJsonArray{
        QJsonObject{
            {QStringLiteral("name"), QStringLiteral("seed")},
            {QStringLiteral("label"), QStringLiteral("随机种子")},
            {QStringLiteral("type"), QStringLiteral("int")},
            {QStringLiteral("default"), 0},
            {QStringLiteral("minimum"), 0},
            {QStringLiteral("maximum"), 999999},
            {QStringLiteral("description"), QString()},
        },
    };
}

} // namespace

class TestGeneratorModel : public QObject {
    Q_OBJECT

  private slots:
    void roleNamesMatchImplementation();
    void reloadFromParsesProtocolShape();
    void reloadFromFallsBackToCategory();
    void reloadFromClearsAndReplaces();
    void reloadFromSkipsKeylessEntries();
    void searchMatchesTitleAndKeywords();
    void searchCaseInsensitiveAndEmptyQuery();
    void dataOnInvalidIndexes();

  private:
    static QModelIndex found(const QAbstractItemModel &model, int role, const QString &value);
};

QModelIndex TestGeneratorModel::found(const QAbstractItemModel &model, int role,
                                      const QString &value) {
    for (int row = 0; row < model.rowCount(); ++row) {
        if (model.index(row, 0).data(role).toString() == value)
            return model.index(row, 0);
    }
    return {};
}

void TestGeneratorModel::roleNamesMatchImplementation() {
    GeneratorModel model;
    QAbstractItemModelTester tester(&model);

    const auto roles = model.roleNames();
    QCOMPARE(roles.size(), 6);
    // TexturePage 左栏按这些名字取值（generatorKey/generatorName/categoryLabel/
    // paramsJson/available/optionalDeps，任务清单指定的六个角色）。
    QCOMPARE(roles.value(GeneratorModel::GeneratorKeyRole), QByteArray("generatorKey"));
    QCOMPARE(roles.value(GeneratorModel::GeneratorNameRole), QByteArray("generatorName"));
    QCOMPARE(roles.value(GeneratorModel::CategoryLabelRole), QByteArray("categoryLabel"));
    QCOMPARE(roles.value(GeneratorModel::ParamsJsonRole), QByteArray("paramsJson"));
    QCOMPARE(roles.value(GeneratorModel::AvailableRole), QByteArray("available"));
    QCOMPARE(roles.value(GeneratorModel::OptionalDepsRole), QByteArray("optionalDeps"));
}

void TestGeneratorModel::reloadFromParsesProtocolShape() {
    GeneratorModel model;
    QAbstractItemModelTester tester(&model);
    QSignalSpy resetSpy(&model, &QAbstractItemModel::modelReset);

    model.reloadFrom(generatorListResult(
        {generatorEntry(QStringLiteral("perlin_noise"), QStringLiteral("柏林噪声"),
                        QStringLiteral("noise"), QStringLiteral("噪声"), true, {}, seedParams()),
         generatorEntry(QStringLiteral("gmic_texture"), QStringLiteral("G'MIC 纹理"),
                        QStringLiteral("texture"), QStringLiteral("纹理"), false,
                        {QStringLiteral("gmic")})}));
    QCOMPARE(resetSpy.count(), 1);
    QCOMPARE(model.rowCount(), 2);

    const auto noise =
        found(model, GeneratorModel::GeneratorKeyRole, QStringLiteral("perlin_noise"));
    QVERIFY(noise.isValid());
    QCOMPARE(noise.data(GeneratorModel::GeneratorNameRole).toString(), QStringLiteral("柏林噪声"));
    QCOMPARE(noise.data(GeneratorModel::CategoryLabelRole).toString(), QStringLiteral("噪声"));
    QCOMPARE(noise.data(GeneratorModel::AvailableRole).toBool(), true);
    QCOMPARE(noise.data(GeneratorModel::OptionalDepsRole).toStringList(), QStringList{});
    // paramsJson 必须是可反序列化的 params 数组（参数组件自动生成控件的输入）。
    const QString paramsJson = noise.data(GeneratorModel::ParamsJsonRole).toString();
    const auto params = QJsonDocument::fromJson(paramsJson.toUtf8()).array();
    QCOMPARE(params.size(), 1);
    QCOMPARE(params.at(0).toObject().value(QStringLiteral("name")).toString(),
             QStringLiteral("seed"));
    QCOMPARE(params.at(0).toObject().value(QStringLiteral("type")).toString(),
             QStringLiteral("int"));

    // 不可用条目携带依赖列表——置灰 + 原因（§9.7：G'MIC 缺失时该生成器置灰）。
    const auto gmic =
        found(model, GeneratorModel::GeneratorKeyRole, QStringLiteral("gmic_texture"));
    QVERIFY(gmic.isValid());
    QCOMPARE(gmic.data(GeneratorModel::AvailableRole).toBool(), false);
    QCOMPARE(gmic.data(GeneratorModel::OptionalDepsRole).toStringList(),
             QStringList{QStringLiteral("gmic")});
}

void TestGeneratorModel::reloadFromFallsBackToCategory() {
    GeneratorModel model;
    QAbstractItemModelTester tester(&model);

    // 缺 category_label 时回落 category 原值（同一条目至少有类别可显，
    // filter_model.cpp:23-27 的同一约定）。
    model.reloadFrom(
        generatorListResult({generatorEntry(QStringLiteral("brick"), QStringLiteral("砖墙"),
                                            QStringLiteral("pattern"), QString(), true, {})}));
    QCOMPARE(model.rowCount(), 1);
    QCOMPARE(model.index(0, 0).data(GeneratorModel::CategoryLabelRole).toString(),
             QStringLiteral("pattern"));
}

void TestGeneratorModel::reloadFromClearsAndReplaces() {
    GeneratorModel model;
    QAbstractItemModelTester tester(&model);

    model.reloadFrom(generatorListResult(
        {generatorEntry(QStringLiteral("a"), QStringLiteral("甲"), QStringLiteral("noise"),
                        QStringLiteral("噪声"), true, {}, {})}));
    QCOMPARE(model.rowCount(), 1);

    // 空对象 / 缺 generators 字段 = 清空（FilterModel::reloadFrom 同款语义，
    // test_filter_model.cpp:151-156）。
    model.reloadFrom(QJsonObject{});
    QCOMPARE(model.rowCount(), 0);

    model.reloadFrom(generatorListResult({}));
    QCOMPARE(model.rowCount(), 0);

    // 整表替换而非追加：第二次填充后旧条目不复存在。
    model.reloadFrom(generatorListResult(
        {generatorEntry(QStringLiteral("b"), QStringLiteral("乙"), QStringLiteral("pattern"),
                        QStringLiteral("图案"), true, {}, {})}));
    QCOMPARE(model.rowCount(), 1);
    QVERIFY(!found(model, GeneratorModel::GeneratorKeyRole, QStringLiteral("a")).isValid());
    QCOMPARE(found(model, GeneratorModel::GeneratorKeyRole, QStringLiteral("b")).isValid(), true);
}

void TestGeneratorModel::reloadFromSkipsKeylessEntries() {
    GeneratorModel model;
    QAbstractItemModelTester tester(&model);

    // 无 key 的条目无法在 generate.render 中引用（generator_key 必填），模型
    // 层同样不收——目录条目必须能提交成渲染请求。
    model.reloadFrom(generatorListResult(
        {QJsonObject{{QStringLiteral("name"), QStringLiteral("无键条目")},
                     {QStringLiteral("category_label"), QStringLiteral("其他")}},
         generatorEntry(QStringLiteral("ok"), QStringLiteral("有效"), QStringLiteral("noise"),
                        QStringLiteral("噪声"), true, {}, {})}));
    QCOMPARE(model.rowCount(), 1);
    QCOMPARE(model.index(0, 0).data(GeneratorModel::GeneratorKeyRole).toString(),
             QStringLiteral("ok"));
}

void TestGeneratorModel::searchMatchesTitleAndKeywords() {
    GeneratorModel model;
    QAbstractItemModelTester tester(&model);
    model.reloadFrom(generatorListResult(
        {generatorEntry(QStringLiteral("perlin_noise"), QStringLiteral("柏林噪声"),
                        QStringLiteral("noise"), QStringLiteral("噪声"), true, {}),
         generatorEntry(QStringLiteral("gmic_texture"), QStringLiteral("G'MIC 纹理"),
                        QStringLiteral("texture"), QStringLiteral("纹理"), false,
                        {QStringLiteral("gmic")}),
         generatorEntry(QStringLiteral("brick"), QStringLiteral("砖墙"), QStringLiteral("pattern"),
                        QStringLiteral("图案"), true, {})}));

    // title 匹配（显示名）。
    QCOMPARE(model.search(QStringLiteral("砖墙")).size(), 1);
    // key 匹配（关键词）。
    QCOMPARE(model.search(QStringLiteral("perlin")).size(), 1);
    QCOMPARE(model.search(QStringLiteral("perlin"))
                 .first()
                 .toMap()
                 .value(QStringLiteral("key"))
                 .toString(),
             QStringLiteral("perlin_noise"));
    // category_label 匹配："图案"只命中砖墙。
    QCOMPARE(model.search(QStringLiteral("图案")).size(), 1);
    // optional_deps 匹配（置灰原因可搜）。
    QCOMPARE(model.search(QStringLiteral("gmic")).size(), 1);
    // 无命中。
    QCOMPARE(model.search(QStringLiteral("不存在的生成器")).size(), 0);
    // 搜索结果携带与角色同键的字段，可直接作 QML 模型。
    const auto hit = model.search(QStringLiteral("砖墙")).first().toMap();
    QCOMPARE(hit.value(QStringLiteral("name")).toString(), QStringLiteral("砖墙"));
    QCOMPARE(hit.value(QStringLiteral("available")).toBool(), true);
    QVERIFY(hit.contains(QStringLiteral("paramsJson")));
}

void TestGeneratorModel::searchCaseInsensitiveAndEmptyQuery() {
    GeneratorModel model;
    QAbstractItemModelTester tester(&model);
    model.reloadFrom(generatorListResult(
        {generatorEntry(QStringLiteral("Perlin_Noise"), QStringLiteral("柏林噪声"),
                        QStringLiteral("noise"), QStringLiteral("噪声"), true, {})}));

    // 大小写不敏感的包含匹配。
    QCOMPARE(model.search(QStringLiteral("PERLIN")).size(), 1);
    QCOMPARE(model.search(QStringLiteral("perlin")).size(), 1);
    // 空查询/纯空白返回全部（清空搜索框 = 全目录）。
    QCOMPARE(model.search(QString()).size(), 1);
    QCOMPARE(model.search(QStringLiteral("   ")).size(), 1);
}

void TestGeneratorModel::dataOnInvalidIndexes() {
    GeneratorModel model;
    QAbstractItemModelTester tester(&model);
    model.reloadFrom(generatorListResult(
        {generatorEntry(QStringLiteral("perlin_noise"), QStringLiteral("柏林噪声"),
                        QStringLiteral("noise"), QStringLiteral("噪声"), true, {})}));
    QCOMPARE(model.rowCount(), 1);

    // 扁平表契约（FilterModel::dataOnInvalidIndexes 同款）：负行/越界行/带父
    // 索引的查询一律回答无效索引与无效值，而非崩溃或读出脏数据
    // （generator_model.cpp data() 的防御分支——UI 传错行号不得越界取值）。
    QVERIFY(!model.index(-1, 0).isValid());
    QVERIFY(!model.index(model.rowCount(), 0).isValid());
    const QModelIndex row0 = model.index(0, 0);
    QCOMPARE(model.rowCount(row0), 0);
    QVERIFY(!model.index(0, 0, row0).isValid());
    QVERIFY(!model.index(-1, 0).data(GeneratorModel::GeneratorKeyRole).isValid());
    QVERIFY(!model.index(model.rowCount(), 0).data(GeneratorModel::AvailableRole).isValid());
    QVERIFY(!model.data(QModelIndex(), GeneratorModel::GeneratorKeyRole).isValid());
}

QTEST_MAIN(TestGeneratorModel)
#include "test_generator_model.moc"
