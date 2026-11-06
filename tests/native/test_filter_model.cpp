// Phase 5 model tests: FilterModel as the filter.list catalog frontend.
//
// 纯数据模型：不连 BackendManager（填充入口 reloadFrom 由 FilterService 或测试
// 直接调用），所以无需 Harness 发信号——直接构造、直接喂 docs/ipc-protocol.md
// §3 filter.list 的 result 形状（{filters: [...]}，元素形状对照
// python_worker/adapters/filter_adapter.py list_filters）。角色名断言锁定
// AppFilterCard / AppFilterParameterGroup（Phase 6）要消费的 QML 契约。
#include <QtTest/QAbstractItemModelTester>
#include <QtTest/QtTest>

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSignalSpy>

#include "models/filter_model.h"

using toolbox::FilterModel;

namespace {

// 一条完整的 filter.list 条目（形状 = filter_adapter.list_filters 的输出）。
QJsonObject filterEntry(const QString &key, const QString &name, const QString &category,
                        const QString &categoryLabel, bool available, const QStringList &deps,
                        const QString &description) {
    QJsonArray depsArray;
    for (const auto &dep : deps)
        depsArray.append(dep);
    return QJsonObject{
        {QStringLiteral("key"), key},
        {QStringLiteral("name"), name},
        {QStringLiteral("category"), category},
        {QStringLiteral("category_label"), categoryLabel},
        {QStringLiteral("description"), description},
        {QStringLiteral("available"), available},
        {QStringLiteral("optional_deps"), depsArray},
        {QStringLiteral("params"),
         QJsonArray{
             QJsonObject{
                 {QStringLiteral("name"), QStringLiteral("radius")},
                 {QStringLiteral("label"), QStringLiteral("半径")},
                 {QStringLiteral("type"), QStringLiteral("float")},
                 {QStringLiteral("default"), 3.0},
                 {QStringLiteral("minimum"), 0.0},
                 {QStringLiteral("maximum"), 20.0},
                 {QStringLiteral("step"), 0.5},
                 {QStringLiteral("description"), QString()},
             },
         }},
    };
}

QJsonObject filterListResult(std::initializer_list<QJsonObject> filters) {
    QJsonArray array;
    for (const auto &item : filters)
        array.append(item);
    return QJsonObject{{QStringLiteral("filters"), array}};
}

} // namespace

class TestFilterModel : public QObject {
    Q_OBJECT

  private slots:
    void roleNamesMatchImplementation();
    void reloadFromParsesProtocolShape();
    void reloadFromClearsAndReplaces();
    void reloadFromSkipsKeylessEntries();
    void searchMatchesTitleAndKeywords();
    void searchCaseInsensitiveAndEmptyQuery();
    void dataOnInvalidIndexes();

  private:
    static QModelIndex found(const QAbstractItemModel &model, int role, const QString &value);
};

QModelIndex TestFilterModel::found(const QAbstractItemModel &model, int role, const QString &value) {
    for (int row = 0; row < model.rowCount(); ++row) {
        if (model.index(row, 0).data(role).toString() == value)
            return model.index(row, 0);
    }
    return {};
}

void TestFilterModel::roleNamesMatchImplementation() {
    FilterModel model;
    QAbstractItemModelTester tester(&model);

    const auto roles = model.roleNames();
    QCOMPARE(roles.size(), 7);
    // AppFilterCard/AppFilterParameterGroup 按这些名字取值（组件规格 §3/§4）。
    QCOMPARE(roles.value(FilterModel::FilterKeyRole), QByteArray("filterKey"));
    QCOMPARE(roles.value(FilterModel::FilterNameRole), QByteArray("filterName"));
    QCOMPARE(roles.value(FilterModel::CategoryLabelRole), QByteArray("categoryLabel"));
    QCOMPARE(roles.value(FilterModel::ParamsJsonRole), QByteArray("paramsJson"));
    QCOMPARE(roles.value(FilterModel::AvailableRole), QByteArray("available"));
    QCOMPARE(roles.value(FilterModel::OptionalDepsRole), QByteArray("optionalDeps"));
    QCOMPARE(roles.value(FilterModel::DescriptionRole), QByteArray("description"));
}

void TestFilterModel::reloadFromParsesProtocolShape() {
    FilterModel model;
    QAbstractItemModelTester tester(&model);
    QSignalSpy resetSpy(&model, &QAbstractItemModel::modelReset);

    model.reloadFrom(filterListResult(
        {filterEntry(QStringLiteral("gaussian_blur"), QStringLiteral("高斯模糊"),
                     QStringLiteral("blur"), QStringLiteral("模糊"), true, {},
                     QStringLiteral("经典高斯核模糊")),
         filterEntry(QStringLiteral("gmic_relight"), QStringLiteral("G'MIC 光影"),
                     QStringLiteral("lighting"), QStringLiteral("光影"), false,
                     {QStringLiteral("gmic")}, QStringLiteral("需要 G'MIC"))}));
    QCOMPARE(resetSpy.count(), 1);
    QCOMPARE(model.rowCount(), 2);

    const auto blur = found(model, FilterModel::FilterKeyRole, QStringLiteral("gaussian_blur"));
    QVERIFY(blur.isValid());
    QCOMPARE(blur.data(FilterModel::FilterNameRole).toString(), QStringLiteral("高斯模糊"));
    QCOMPARE(blur.data(FilterModel::CategoryLabelRole).toString(), QStringLiteral("模糊"));
    QCOMPARE(blur.data(FilterModel::AvailableRole).toBool(), true);
    QCOMPARE(blur.data(FilterModel::OptionalDepsRole).toStringList(), QStringList{});
    QCOMPARE(blur.data(FilterModel::DescriptionRole).toString(), QStringLiteral("经典高斯核模糊"));
    // paramsJson 必须是可反序列化的 params 数组（AppFilterParameterGroup 的输入）。
    const QString paramsJson = blur.data(FilterModel::ParamsJsonRole).toString();
    const auto params = QJsonDocument::fromJson(paramsJson.toUtf8()).array();
    QCOMPARE(params.size(), 1);
    QCOMPARE(params.at(0).toObject().value(QStringLiteral("name")).toString(),
             QStringLiteral("radius"));
    QCOMPARE(params.at(0).toObject().value(QStringLiteral("type")).toString(),
             QStringLiteral("float"));

    // 不可用条目携带依赖列表——置灰 + 原因（组件规格 §3：需要 G'MIC）。
    const auto relight = found(model, FilterModel::FilterKeyRole, QStringLiteral("gmic_relight"));
    QVERIFY(relight.isValid());
    QCOMPARE(relight.data(FilterModel::AvailableRole).toBool(), false);
    QCOMPARE(relight.data(FilterModel::OptionalDepsRole).toStringList(),
             QStringList{QStringLiteral("gmic")});
}

void TestFilterModel::reloadFromClearsAndReplaces() {
    FilterModel model;
    QAbstractItemModelTester tester(&model);

    model.reloadFrom(filterListResult({filterEntry(QStringLiteral("a"), QStringLiteral("甲"),
                                                   QStringLiteral("blur"), QStringLiteral("模糊"),
                                                   true, {}, {})}));
    QCOMPARE(model.rowCount(), 1);

    // 空对象 / 缺 filters 字段 = 清空（HistoryModel::refreshFrom 同款语义）。
    model.reloadFrom(QJsonObject{});
    QCOMPARE(model.rowCount(), 0);

    model.reloadFrom(filterListResult({}));
    QCOMPARE(model.rowCount(), 0);

    // 整表替换而非追加：第二次填充后旧条目不复存在。
    model.reloadFrom(filterListResult(
        {filterEntry(QStringLiteral("b"), QStringLiteral("乙"), QStringLiteral("color"),
                     QStringLiteral("色彩"), true, {}, {})}));
    QCOMPARE(model.rowCount(), 1);
    QVERIFY(!found(model, FilterModel::FilterKeyRole, QStringLiteral("a")).isValid());
    QCOMPARE(found(model, FilterModel::FilterKeyRole, QStringLiteral("b")).isValid(), true);
}

void TestFilterModel::reloadFromSkipsKeylessEntries() {
    FilterModel model;
    QAbstractItemModelTester tester(&model);

    // 无 key 的条目无法在 filter.preview/apply 中引用（build_chain 会拒），
    // 模型层同样不收——目录条目必须能提交成链步骤。
    model.reloadFrom(filterListResult(
        {QJsonObject{{QStringLiteral("name"), QStringLiteral("无键条目")},
                     {QStringLiteral("category_label"), QStringLiteral("其他")}},
         filterEntry(QStringLiteral("ok"), QStringLiteral("有效"), QStringLiteral("noise"),
                     QStringLiteral("噪声"), true, {}, {})}));
    QCOMPARE(model.rowCount(), 1);
    QCOMPARE(model.index(0, 0).data(FilterModel::FilterKeyRole).toString(), QStringLiteral("ok"));
}

void TestFilterModel::searchMatchesTitleAndKeywords() {
    FilterModel model;
    QAbstractItemModelTester tester(&model);
    model.reloadFrom(filterListResult(
        {filterEntry(QStringLiteral("gaussian_blur"), QStringLiteral("高斯模糊"),
                     QStringLiteral("blur"), QStringLiteral("模糊"), true, {},
                     QStringLiteral("经典高斯核模糊")),
         filterEntry(QStringLiteral("gmic_relight"), QStringLiteral("G'MIC 光影"),
                     QStringLiteral("lighting"), QStringLiteral("光影"), false,
                     {QStringLiteral("gmic")}, QStringLiteral("依赖 G'MIC 引擎")),
         filterEntry(QStringLiteral("vignette"), QStringLiteral("暗角"),
                     QStringLiteral("stylize"), QStringLiteral("风格化"), true, {},
                     QStringLiteral("边缘压暗"))}));

    // title 匹配（显示名）。
    QCOMPARE(model.search(QStringLiteral("暗角")).size(), 1);
    // key 匹配（关键词）。
    QCOMPARE(model.search(QStringLiteral("relight")).size(), 1);
    QCOMPARE(model.search(QStringLiteral("relight")).first().toMap().value(QStringLiteral("key"))
                 .toString(),
             QStringLiteral("gmic_relight"));
    // category_label 匹配："风格化"只命中暗角。
    QCOMPARE(model.search(QStringLiteral("风格化")).size(), 1);
    // description 匹配。
    QCOMPARE(model.search(QStringLiteral("引擎")).size(), 1);
    // optional_deps 匹配。
    QCOMPARE(model.search(QStringLiteral("gmic")).size(), 1);
    // 无命中。
    QCOMPARE(model.search(QStringLiteral("不存在的滤镜")).size(), 0);
    // 搜索结果携带与角色同键的字段，可直接作 QML 模型。
    const auto hit = model.search(QStringLiteral("暗角")).first().toMap();
    QCOMPARE(hit.value(QStringLiteral("name")).toString(), QStringLiteral("暗角"));
    QCOMPARE(hit.value(QStringLiteral("available")).toBool(), true);
    QVERIFY(hit.contains(QStringLiteral("paramsJson")));
}

void TestFilterModel::searchCaseInsensitiveAndEmptyQuery() {
    FilterModel model;
    QAbstractItemModelTester tester(&model);
    model.reloadFrom(filterListResult(
        {filterEntry(QStringLiteral("Gaussian_Blur"), QStringLiteral("高斯模糊"),
                     QStringLiteral("blur"), QStringLiteral("模糊"), true, {}, {})}));

    // 大小写不敏感的包含匹配。
    QCOMPARE(model.search(QStringLiteral("GAUSSIAN")).size(), 1);
    QCOMPARE(model.search(QStringLiteral("gaussian")).size(), 1);
    // 空查询/纯空白返回全部（清空搜索框 = 全目录）。
    QCOMPARE(model.search(QString()).size(), 1);
    QCOMPARE(model.search(QStringLiteral("   ")).size(), 1);
}

void TestFilterModel::dataOnInvalidIndexes() {
    FilterModel model;
    QAbstractItemModelTester tester(&model);
    model.reloadFrom(filterListResult(
        {filterEntry(QStringLiteral("gaussian_blur"), QStringLiteral("高斯模糊"),
                     QStringLiteral("blur"), QStringLiteral("模糊"), true, {},
                     QStringLiteral("经典高斯核模糊"))}));
    QCOMPARE(model.rowCount(), 1);

    // 扁平表契约（TaskModel::trackedResponseCreatesRow 同款）：负行/越界行/
    // 带父索引的查询一律回答无效索引与无效值，而非崩溃或读出脏数据
    // （filter_model.cpp data() 的防御分支——UI 传错行号不得越界取值）。
    QVERIFY(!model.index(-1, 0).isValid());
    QVERIFY(!model.index(model.rowCount(), 0).isValid());
    const QModelIndex row0 = model.index(0, 0);
    QCOMPARE(model.rowCount(row0), 0);
    QVERIFY(!model.index(0, 0, row0).isValid());
    QVERIFY(!model.index(-1, 0).data(FilterModel::FilterKeyRole).isValid());
    QVERIFY(!model.index(model.rowCount(), 0).data(FilterModel::AvailableRole).isValid());
    QVERIFY(!model.data(QModelIndex(), FilterModel::FilterKeyRole).isValid());
}

QTEST_MAIN(TestFilterModel)
#include "test_filter_model.moc"
