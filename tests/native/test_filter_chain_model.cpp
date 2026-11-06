// Phase 5 model tests: FilterChainModel as the AppFilterChainItem backend.
//
// 纯数据模型：不连 BackendManager（装填入口 replaceFrom 由 FilterService 载入
// 预设或测试直接调用）。行形状 = 协议 filter.preview/apply 的 steps 元素
// {filter_key, params, enabled}（docs/ipc-protocol.md §3；enabled 缺省 true
// 对齐 processors/filter_chain.py FilterStep.from_dict）。移动/删除的边界行为
// 与 stepCountChanged 的通知纪律在此锁定。
#include <QtTest/QAbstractItemModelTester>
#include <QtTest/QtTest>

#include <QJsonArray>
#include <QJsonObject>
#include <QSignalSpy>

#include "models/filter_chain_model.h"

using toolbox::FilterChainModel;

namespace {

QJsonObject step(const QString &key, bool enabled = true) {
    return QJsonObject{
        {QStringLiteral("filter_key"), key},
        {QStringLiteral("params"),
         QJsonObject{{QStringLiteral("radius"), 3}, {QStringLiteral("label"), QStringLiteral("x")}}},
        {QStringLiteral("enabled"), enabled},
    };
}

QJsonArray steps(std::initializer_list<QString> keys) {
    QJsonArray array;
    for (const auto &key : keys)
        array.append(step(key));
    return array;
}

QStringList keyOrder(const FilterChainModel &model) {
    QStringList keys;
    for (int row = 0; row < model.rowCount(); ++row)
        keys.append(model.index(row, 0).data(FilterChainModel::ChainFilterKeyRole).toString());
    return keys;
}

} // namespace

class TestFilterChainModel : public QObject {
    Q_OBJECT

  private slots:
    void roleNamesMatchImplementation();
    void replaceFromParsesSteps();
    void replaceFromSkipsKeylessAndNotifiesCount();
    void addStepAppendsAndNotifiesCount();
    void removeRowBoundsAndNotify();
    void moveUpSwapsAndRejectsEdges();
    void moveDownSwapsAndRejectsEdges();
    void moveRefreshesChainIndexRole();
    void setEnabledTogglesAndDebounces();
    void emptyKeyAddIgnored();
};

void TestFilterChainModel::roleNamesMatchImplementation() {
    FilterChainModel model;
    QAbstractItemModelTester tester(&model);

    const auto roles = model.roleNames();
    QCOMPARE(roles.size(), 4);
    // AppFilterChainItem 按这些名字取值（组件规格 §3）。
    QCOMPARE(roles.value(FilterChainModel::ChainFilterKeyRole), QByteArray("chainFilterKey"));
    QCOMPARE(roles.value(FilterChainModel::ChainParamsRole), QByteArray("chainParams"));
    QCOMPARE(roles.value(FilterChainModel::ChainEnabledRole), QByteArray("chainEnabled"));
    QCOMPARE(roles.value(FilterChainModel::ChainIndexRole), QByteArray("chainIndex"));
    QCOMPARE(model.stepCount(), 0);
}

void TestFilterChainModel::replaceFromParsesSteps() {
    FilterChainModel model;
    QAbstractItemModelTester tester(&model);
    QSignalSpy countSpy(&model, &FilterChainModel::stepCountChanged);

    QJsonArray array;
    array.append(step(QStringLiteral("gaussian_blur"), true));
    // enabled 缺省 true（FilterStep.from_dict 语义）。
    array.append(QJsonObject{{QStringLiteral("filter_key"), QStringLiteral("vignette")}});
    // enabled=false 的步骤保留在链中（不启用≠删除，AppFilterChainItem 开关）。
    array.append(step(QStringLiteral("vignette"), false));
    model.replaceFrom(array);

    QCOMPARE(model.rowCount(), 3);
    QCOMPARE(countSpy.count(), 1);
    QCOMPARE(model.stepCount(), 3);

    QCOMPARE(model.index(0, 0).data(FilterChainModel::ChainFilterKeyRole).toString(),
             QStringLiteral("gaussian_blur"));
    QCOMPARE(model.index(0, 0).data(FilterChainModel::ChainEnabledRole).toBool(), true);
    const auto params =
        model.index(0, 0).data(FilterChainModel::ChainParamsRole).value<QJsonObject>();
    QCOMPARE(params.value(QStringLiteral("radius")).toInt(), 3);
    QCOMPARE(model.index(1, 0).data(FilterChainModel::ChainEnabledRole).toBool(), true);
    QCOMPARE(model.index(1, 0).data(FilterChainModel::ChainFilterKeyRole).toString(),
             QStringLiteral("vignette"));
    QCOMPARE(model.index(2, 0).data(FilterChainModel::ChainEnabledRole).toBool(), false);

    // 空/缺失 steps = 清空链（与 FilterModel::reloadFrom 同款防御语义）。
    model.replaceFrom(QJsonArray{});
    QCOMPARE(model.rowCount(), 0);
}

void TestFilterChainModel::replaceFromSkipsKeylessAndNotifiesCount() {
    FilterChainModel model;
    QAbstractItemModelTester tester(&model);
    QSignalSpy countSpy(&model, &FilterChainModel::stepCountChanged);

    // 无 filter_key 的步骤提交时会被 Worker 拒（filter_adapter.build_chain），
    // 模型层同样不收。
    QJsonArray array;
    array.append(QJsonObject{{QStringLiteral("params"), QJsonObject{}}});
    array.append(step(QStringLiteral("ok")));
    model.replaceFrom(array);

    QCOMPARE(model.rowCount(), 1);
    QCOMPARE(countSpy.count(), 1); // 0 → 1
    // 行数不变的整链重建不通知（头文件声明的通知纪律）。
    model.replaceFrom(array);
    QCOMPARE(countSpy.count(), 1);
    QCOMPARE(model.index(0, 0).data(FilterChainModel::ChainFilterKeyRole).toString(),
             QStringLiteral("ok"));
}

void TestFilterChainModel::addStepAppendsAndNotifiesCount() {
    FilterChainModel model;
    QAbstractItemModelTester tester(&model);
    QSignalSpy countSpy(&model, &FilterChainModel::stepCountChanged);

    model.addStep(QStringLiteral("gaussian_blur"),
                  QJsonObject{{QStringLiteral("radius"), 5}});
    QCOMPARE(model.rowCount(), 1);
    QCOMPARE(countSpy.count(), 1);
    QCOMPARE(model.stepCount(), 1);
    QCOMPARE(model.index(0, 0).data(FilterChainModel::ChainFilterKeyRole).toString(),
             QStringLiteral("gaussian_blur"));
    QCOMPARE(model.index(0, 0).data(FilterChainModel::ChainEnabledRole).toBool(), true);

    // params 缺省空对象（FilterService 组装时 Worker 端回落参数默认值）。
    model.addStep(QStringLiteral("vignette"));
    QCOMPARE(model.stepCount(), 2);
    QCOMPARE(countSpy.count(), 2);
    QVERIFY(
        model.index(1, 0).data(FilterChainModel::ChainParamsRole).value<QJsonObject>().isEmpty());
}

void TestFilterChainModel::removeRowBoundsAndNotify() {
    FilterChainModel model;
    QAbstractItemModelTester tester(&model);
    QSignalSpy countSpy(&model, &FilterChainModel::stepCountChanged);
    QSignalSpy removed(&model, &QAbstractItemModel::rowsRemoved);
    model.replaceFrom(steps({QStringLiteral("a"), QStringLiteral("b"), QStringLiteral("c")}));
    countSpy.clear();

    // 删中间行：后续行前移（b 随之消失，c 上移）。
    model.removeRow(1);
    QCOMPARE(countSpy.count(), 1);
    QCOMPARE(removed.count(), 1);
    QCOMPARE(keyOrder(model), (QStringList{QStringLiteral("a"), QStringLiteral("c")}));

    // 越界行号静默忽略（-1 / 超尾 / 空链），不发通知。
    model.removeRow(-1);
    model.removeRow(5);
    QCOMPARE(countSpy.count(), 1);
    QCOMPARE(removed.count(), 1);

    model.removeRow(0);
    model.removeRow(0);
    QCOMPARE(model.stepCount(), 0);
    QCOMPARE(countSpy.count(), 3);
}

void TestFilterChainModel::moveUpSwapsAndRejectsEdges() {
    FilterChainModel model;
    QAbstractItemModelTester tester(&model);
    model.replaceFrom(steps({QStringLiteral("a"), QStringLiteral("b"), QStringLiteral("c")}));

    model.moveUp(1);
    QCOMPARE(keyOrder(model), (QStringList{QStringLiteral("b"), QStringLiteral("a"),
                                           QStringLiteral("c")}));

    // 首行上移 / 越界 = 无操作（不发 move 信号）。
    QSignalSpy moved(&model, &QAbstractItemModel::rowsAboutToBeMoved);
    model.moveUp(0);
    model.moveUp(-1);
    model.moveUp(3);
    QCOMPARE(moved.count(), 0);
    QCOMPARE(keyOrder(model), (QStringList{QStringLiteral("b"), QStringLiteral("a"),
                                           QStringLiteral("c")}));
}

void TestFilterChainModel::moveDownSwapsAndRejectsEdges() {
    FilterChainModel model;
    QAbstractItemModelTester tester(&model);
    model.replaceFrom(steps({QStringLiteral("a"), QStringLiteral("b"), QStringLiteral("c")}));

    model.moveDown(0);
    QCOMPARE(keyOrder(model), (QStringList{QStringLiteral("b"), QStringLiteral("a"),
                                           QStringLiteral("c")}));

    // 末行下移 / 越界 = 无操作。
    QSignalSpy moved(&model, &QAbstractItemModel::rowsAboutToBeMoved);
    model.moveDown(2);
    model.moveDown(-1);
    model.moveDown(3);
    QCOMPARE(moved.count(), 0);
    QCOMPARE(keyOrder(model), (QStringList{QStringLiteral("b"), QStringLiteral("a"),
                                           QStringLiteral("c")}));
}

void TestFilterChainModel::moveRefreshesChainIndexRole() {
    FilterChainModel model;
    QAbstractItemModelTester tester(&model);
    model.replaceFrom(steps({QStringLiteral("a"), QStringLiteral("b"), QStringLiteral("c")}));

    // chainIndex 是行号（AppFilterChainItem 序号显示），移动后按新序读取。
    model.moveUp(2);
    QCOMPARE(keyOrder(model), (QStringList{QStringLiteral("a"), QStringLiteral("c"),
                                           QStringLiteral("b")}));
    QCOMPARE(model.index(1, 0).data(FilterChainModel::ChainIndexRole).toInt(), 1);
    QCOMPARE(model.index(2, 0).data(FilterChainModel::ChainIndexRole).toInt(), 2);
    QCOMPARE(model.index(2, 0).data(FilterChainModel::ChainFilterKeyRole).toString(),
             QStringLiteral("b"));
}

void TestFilterChainModel::setEnabledTogglesAndDebounces() {
    FilterChainModel model;
    QAbstractItemModelTester tester(&model);
    model.replaceFrom(steps({QStringLiteral("a"), QStringLiteral("b")}));
    QSignalSpy changed(&model, &QAbstractItemModel::dataChanged);

    model.setEnabled(0, false);
    QCOMPARE(changed.count(), 1);
    QCOMPARE(model.index(0, 0).data(FilterChainModel::ChainEnabledRole).toBool(), false);
    QVERIFY(changed.last().at(2).value<QList<int>>().contains(FilterChainModel::ChainEnabledRole));
    QCOMPARE(model.index(1, 0).data(FilterChainModel::ChainEnabledRole).toBool(), true);

    // 同值写入不发通知（TaskModel::updateRow 同款防抖纪律）。
    model.setEnabled(0, false);
    QCOMPARE(changed.count(), 1);

    // 越界静默忽略。
    model.setEnabled(-1, true);
    model.setEnabled(2, true);
    QCOMPARE(changed.count(), 1);

    // 恢复 true 再发一次。
    model.setEnabled(0, true);
    QCOMPARE(changed.count(), 2);
    QCOMPARE(model.index(0, 0).data(FilterChainModel::ChainEnabledRole).toBool(), true);
}

void TestFilterChainModel::emptyKeyAddIgnored() {
    FilterChainModel model;
    QAbstractItemModelTester tester(&model);
    QSignalSpy countSpy(&model, &FilterChainModel::stepCountChanged);

    // 无 key 步骤无法提交（build_chain 拒），addStep 同样不收。
    model.addStep(QString());
    QCOMPARE(model.stepCount(), 0);
    QCOMPARE(countSpy.count(), 0);
}

QTEST_MAIN(TestFilterChainModel)
#include "test_filter_chain_model.moc"
