// Phase 6 batch model tests: BatchModel as the batch-workspace file list
// (docs/toolbox-2.0-project-plan.md §9.4).
//
// BatchModel is a pure data model (no BackendManager wiring — FilterModel /
// FilterChainModel pattern): rows are filled through the Q_INVOKABLE fill API
// (resetFrom / updateFrom / clear), so the Harness is just the model itself and
// every test drives it directly. QAbstractItemModelTester watches every
// mutation for contract violations.
//
// Role-name assertions lock the QML contract consumed by the future
// AppBatchItem (required properties batchFile/batchState/batchProgress/
// batchError/batchOutputPath). Entry shapes mirror the task-list contract in
// native/models/batch_model.h (keys file/state/progress/error/output_path;
// state vocabulary pending|running|done|failed|skipped).
#include <QtTest/QAbstractItemModelTester>
#include <QtTest/QtTest>

#include <QJsonArray>
#include <QJsonObject>
#include <QSignalSpy>

#include "models/batch_model.h"

using toolbox::BatchModel;

namespace {

// Entry builders keep the wire shape in one place (same trick as the message
// builders in test_task_model.cpp).
QJsonObject entry(const QString &file, const QString &state = {}, int progress = 0,
                  const QString &error = {}, const QString &outputPath = {}) {
    QJsonObject object{
        {QStringLiteral("file"), file},
    };
    if (!state.isEmpty())
        object.insert(QStringLiteral("state"), state);
    if (progress != 0)
        object.insert(QStringLiteral("progress"), progress);
    if (!error.isEmpty())
        object.insert(QStringLiteral("error"), error);
    if (!outputPath.isEmpty())
        object.insert(QStringLiteral("output_path"), outputPath);
    return object;
}

// Owns the model; the tester must outlive it, so destruction order inside the
// struct handles that (same idea as the Harness in test_task_model.cpp).
struct Harness {
    BatchModel model;
};

} // namespace

class TestBatchModel : public QObject {
    Q_OBJECT

  private slots:
    void roleNamesMatchImplementation();
    void resetFromBuildsRowsWithDefaults();
    void resetFromSkipsMalformedEntries();
    void updateFromAppliesOnlyPresentFields();
    void updateFromIgnoresUnknownAndKeylessPayloads();
    void markActiveAsSweepsUnfinishedRowsOnly();
    void clearEmptiesModel();
    void summaryCountersTrackStates();

  private:
    static int rowOfFile(const QAbstractItemModel &model, const QString &file);
};

int TestBatchModel::rowOfFile(const QAbstractItemModel &model, const QString &file) {
    for (int row = 0; row < model.rowCount(); ++row) {
        if (model.index(row, 0).data(BatchModel::BatchFileRole).toString() == file)
            return row;
    }
    return -1;
}

void TestBatchModel::roleNamesMatchImplementation() {
    Harness h;
    QAbstractItemModelTester tester(&h.model);

    const auto roles = h.model.roleNames();
    QCOMPARE(roles.size(), 5);
    // QML will consume these names via required properties (AppBatchItem).
    QCOMPARE(roles.value(BatchModel::BatchFileRole), QByteArray("batchFile"));
    QCOMPARE(roles.value(BatchModel::BatchStateRole), QByteArray("batchState"));
    QCOMPARE(roles.value(BatchModel::BatchProgressRole), QByteArray("batchProgress"));
    QCOMPARE(roles.value(BatchModel::BatchErrorRole), QByteArray("batchError"));
    QCOMPARE(roles.value(BatchModel::BatchOutputPathRole), QByteArray("batchOutputPath"));
}

void TestBatchModel::resetFromBuildsRowsWithDefaults() {
    Harness h;
    QAbstractItemModelTester tester(&h.model);

    h.model.resetFrom(QJsonArray{
        entry(QStringLiteral("/tmp/a.png")),
        entry(QStringLiteral("/tmp/b.png"), QStringLiteral("running"), 40),
        entry(QStringLiteral("/tmp/c.png"), QStringLiteral("failed"), 10,
              QStringLiteral("解码失败")),
        entry(QStringLiteral("/tmp/d.png"), QStringLiteral("done"), 100, {},
              QStringLiteral("/tmp/out/d.png")),
    });

    QCOMPARE(h.model.rowCount(), 4);
    QCOMPARE(h.model.totalCount(), 4);

    // Missing fields fall back to defaults: state=pending, progress=0.
    const auto first = h.model.index(0, 0);
    QCOMPARE(first.data(BatchModel::BatchFileRole).toString(), QStringLiteral("/tmp/a.png"));
    QCOMPARE(first.data(BatchModel::BatchStateRole).toString(), QStringLiteral("pending"));
    QCOMPARE(first.data(BatchModel::BatchProgressRole).toInt(), 0);
    QVERIFY(first.data(BatchModel::BatchErrorRole).toString().isEmpty());
    QVERIFY(first.data(BatchModel::BatchOutputPathRole).toString().isEmpty());

    const auto second = h.model.index(1, 0);
    QCOMPARE(second.data(BatchModel::BatchStateRole).toString(), QStringLiteral("running"));
    QCOMPARE(second.data(BatchModel::BatchProgressRole).toInt(), 40);
    QCOMPARE(h.model.index(2, 0).data(BatchModel::BatchErrorRole).toString(),
             QStringLiteral("解码失败"));
    QCOMPARE(h.model.index(3, 0).data(BatchModel::BatchOutputPathRole).toString(),
             QStringLiteral("/tmp/out/d.png"));

    // Flat table contract: no children, out-of-range queries answer invalid.
    QCOMPARE(h.model.rowCount(first), 0);
    QVERIFY(!h.model.index(4, 0).isValid());
    QVERIFY(!h.model.data(QModelIndex(), BatchModel::BatchStateRole).isValid());
}

void TestBatchModel::resetFromSkipsMalformedEntries() {
    Harness h;
    QAbstractItemModelTester tester(&h.model);

    QJsonArray entries;
    entries.append(QStringLiteral("not-an-object")); // 非对象元素
    entries.append(entry(QString()));                // 空 file：不造无名行
    entries.append(QJsonObject{
        {QStringLiteral("state"), QStringLiteral("done")}, // 缺 file
    });
    entries.append(entry(QStringLiteral("/tmp/a.png"), QStringLiteral("done"), 150));
    h.model.resetFrom(entries);

    // Only the well-formed entry survives; progress beyond 100 clamps to 100.
    QCOMPARE(h.model.rowCount(), 1);
    QCOMPARE(h.model.index(0, 0).data(BatchModel::BatchFileRole).toString(),
             QStringLiteral("/tmp/a.png"));
    QCOMPARE(h.model.index(0, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("done"));
    QCOMPARE(h.model.index(0, 0).data(BatchModel::BatchProgressRole).toInt(), 100);
}

void TestBatchModel::updateFromAppliesOnlyPresentFields() {
    Harness h;
    QAbstractItemModelTester tester(&h.model);
    h.model.resetFrom(QJsonArray{entry(QStringLiteral("/tmp/a.png"))});

    // state only → only BatchStateRole is reported.
    QSignalSpy changed(&h.model, &QAbstractItemModel::dataChanged);
    h.model.updateFrom(QJsonObject{
        {QStringLiteral("file"), QStringLiteral("/tmp/a.png")},
        {QStringLiteral("state"), QStringLiteral("running")},
    });
    QCOMPARE(changed.count(), 1);
    QCOMPARE(changed.last().at(2).value<QList<int>>(), (QList<int>{BatchModel::BatchStateRole}));
    QCOMPARE(h.model.index(0, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("running"));

    // progress + output_path together, clamped into 0-100.
    h.model.updateFrom(QJsonObject{
        {QStringLiteral("file"), QStringLiteral("/tmp/a.png")},
        {QStringLiteral("progress"), 150},
        {QStringLiteral("output_path"), QStringLiteral("/tmp/out/a.png")},
    });
    QCOMPARE(changed.count(), 2);
    QCOMPARE(changed.last().at(2).value<QList<int>>(),
             (QList<int>{BatchModel::BatchProgressRole, BatchModel::BatchOutputPathRole}));
    QCOMPARE(h.model.index(0, 0).data(BatchModel::BatchProgressRole).toInt(), 100);
    QCOMPARE(h.model.index(0, 0).data(BatchModel::BatchOutputPathRole).toString(),
             QStringLiteral("/tmp/out/a.png"));

    // Same values again: no notification at all (TaskModel::updateRow contract,
    // task_model.cpp:119-129 — no-op refreshes are silent).
    h.model.updateFrom(QJsonObject{
        {QStringLiteral("file"), QStringLiteral("/tmp/a.png")},
        {QStringLiteral("progress"), 100},
        {QStringLiteral("output_path"), QStringLiteral("/tmp/out/a.png")},
    });
    QCOMPARE(changed.count(), 2);

    // Absent keys never touch the row: error stays empty.
    h.model.updateFrom(QJsonObject{
        {QStringLiteral("file"), QStringLiteral("/tmp/a.png")},
        {QStringLiteral("state"), QStringLiteral("failed")},
    });
    QCOMPARE(changed.count(), 3);
    QCOMPARE(h.model.index(0, 0).data(BatchModel::BatchErrorRole).toString(), QString());
}

void TestBatchModel::updateFromIgnoresUnknownAndKeylessPayloads() {
    Harness h;
    QAbstractItemModelTester tester(&h.model);
    QSignalSpy changed(&h.model, &QAbstractItemModel::dataChanged);
    h.model.resetFrom(QJsonArray{entry(QStringLiteral("/tmp/a.png"))});
    changed.clear();

    // Unknown file: no row is fabricated for a late/cross-batch event.
    h.model.updateFrom(QJsonObject{
        {QStringLiteral("file"), QStringLiteral("/tmp/ghost.png")},
        {QStringLiteral("state"), QStringLiteral("done")},
    });
    QCOMPARE(h.model.rowCount(), 1);
    QCOMPARE(changed.count(), 0);

    // No file key at all (pure overall-progress frame): ignored as a whole.
    h.model.updateFrom(QJsonObject{
        {QStringLiteral("progress"), 42},
        {QStringLiteral("state"), QStringLiteral("running")},
    });
    QCOMPARE(changed.count(), 0);
    QCOMPARE(h.model.index(0, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("pending"));
    QCOMPARE(h.model.index(0, 0).data(BatchModel::BatchProgressRole).toInt(), 0);

    // Empty file key behaves like a missing key.
    h.model.updateFrom(QJsonObject{
        {QStringLiteral("file"), QString()},
        {QStringLiteral("state"), QStringLiteral("done")},
    });
    QCOMPARE(changed.count(), 0);
}

void TestBatchModel::markActiveAsSweepsUnfinishedRowsOnly() {
    Harness h;
    QAbstractItemModelTester tester(&h.model);
    h.model.resetFrom(QJsonArray{
        entry(QStringLiteral("/tmp/a.png"), QStringLiteral("done")),
        entry(QStringLiteral("/tmp/b.png"), QStringLiteral("failed"), 10,
              QStringLiteral("解码失败")),
        entry(QStringLiteral("/tmp/c.png"), QStringLiteral("running"), 55),
        entry(QStringLiteral("/tmp/d.png")),
    });

    h.model.markActiveAs(QStringLiteral("skipped"));

    // Terminal rows (done/failed) keep their state; pending/running converge
    // to skipped (processors/batch_filter_chain.py:63-66/94-97 cancellation
    // sweep, in the 2.0 vocabulary).
    QCOMPARE(h.model.index(0, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("done"));
    QCOMPARE(h.model.index(1, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("failed"));
    QCOMPARE(h.model.index(2, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("skipped"));
    QCOMPARE(h.model.index(3, 0).data(BatchModel::BatchStateRole).toString(),
             QStringLiteral("skipped"));

    // Progress is not rewritten by the sweep (last known per-file value stays).
    QCOMPARE(h.model.index(2, 0).data(BatchModel::BatchProgressRole).toInt(), 55);
}

void TestBatchModel::clearEmptiesModel() {
    Harness h;
    QAbstractItemModelTester tester(&h.model);
    h.model.resetFrom(QJsonArray{
        entry(QStringLiteral("/tmp/a.png"), QStringLiteral("done")),
        entry(QStringLiteral("/tmp/b.png")),
    });
    QSignalSpy summary(&h.model, &BatchModel::batchSummaryChanged);

    h.model.clear();
    QCOMPARE(h.model.rowCount(), 0);
    QCOMPARE(h.model.totalCount(), 0);
    QCOMPARE(h.model.doneCount(), 0);
    QCOMPARE(h.model.failedCount(), 0);
    QCOMPARE(summary.count(), 1); // 2/1/0 → 0/0/0 changed

    // Clearing an already-empty model is a silent no-op.
    h.model.clear();
    QCOMPARE(summary.count(), 1);
}

void TestBatchModel::summaryCountersTrackStates() {
    Harness h;
    QAbstractItemModelTester tester(&h.model);
    QSignalSpy summary(&h.model, &BatchModel::batchSummaryChanged);

    QCOMPARE(h.model.totalCount(), 0);
    QCOMPARE(h.model.doneCount(), 0);
    QCOMPARE(h.model.failedCount(), 0);

    h.model.resetFrom(QJsonArray{
        entry(QStringLiteral("/tmp/a.png")),
        entry(QStringLiteral("/tmp/b.png")),
        entry(QStringLiteral("/tmp/c.png")),
    });
    QCOMPARE(summary.count(), 1); // 0 rows → 3 rows
    QCOMPARE(h.model.totalCount(), 3);
    QCOMPARE(h.model.doneCount(), 0);
    QCOMPARE(h.model.failedCount(), 0);

    h.model.updateFrom(QJsonObject{
        {QStringLiteral("file"), QStringLiteral("/tmp/a.png")},
        {QStringLiteral("state"), QStringLiteral("done")},
    });
    QCOMPARE(summary.count(), 2); // doneCount 0 → 1
    QCOMPARE(h.model.doneCount(), 1);

    h.model.updateFrom(QJsonObject{
        {QStringLiteral("file"), QStringLiteral("/tmp/b.png")},
        {QStringLiteral("progress"), 50}, // 状态不变：计数不变，无汇总通知
    });
    QCOMPARE(summary.count(), 2);

    h.model.updateFrom(QJsonObject{
        {QStringLiteral("file"), QStringLiteral("/tmp/c.png")},
        {QStringLiteral("state"), QStringLiteral("failed")},
    });
    QCOMPARE(summary.count(), 3); // failedCount 0 → 1
    QCOMPARE(h.model.failedCount(), 1);

    // Reset to the same content: rows identical → no summary notification.
    h.model.resetFrom(QJsonArray{
        entry(QStringLiteral("/tmp/a.png"), QStringLiteral("done")),
        entry(QStringLiteral("/tmp/b.png"), QStringLiteral("running"), 50),
        entry(QStringLiteral("/tmp/c.png"), QStringLiteral("failed"), 0,
              QStringLiteral("解码失败")),
    });
    QCOMPARE(summary.count(), 3);
    QCOMPARE(h.model.totalCount(), 3);
}

QTEST_MAIN(TestBatchModel)
#include "test_batch_model.moc"
