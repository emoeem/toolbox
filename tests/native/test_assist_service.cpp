// Phase 7 service tests: AssistService as the assist tools page facade
// (辅助工具页，总纲 §9.9 / §13 Phase 7).
//
// Simulation strategy — same as test_task_model.cpp / test_filter_service.cpp /
// test_studio_service.cpp (no Python Worker in native tests): the tests emit
// BackendManager's responseReady/taskEvent signals directly. The manager is
// never started, so sendAction only consumes its request_id counter slot
// (backend_manager.cpp:102-107, "req-<counter>"): each Q_INVOKABLE sends a
// known number of requests, so tests predict request ids by call order relative
// to a probe sendAction, and probe-before/after proves locally-rejected calls
// sent nothing. Wire-side action shapes are locked by tests/test_worker_assist.py.
//
// Protocol alignment: assist.list and the assist action family are defined in
// docs/ipc-protocol.md §3.8 (Phase 7; Worker side python_worker/adapters/
// assist_adapter.py + dispatcher.py action table, locked by
// tests/test_worker_assist.py). Entry keys ARE the run action names
// ("checksum.file" / "ocr.run" / ...): sync tools answer directly (§3.8),
// async tools answer {task_id, status} (§2.3) with progress/terminal states on
// task.* events (§7); a missing-dependency submission is rejected with
// DEPENDENCY_MISSING (§5, details.missing). The fixtures below use the real
// §3.8 action vocabulary; the tests still inject responses via BackendManager's
// signals (no Worker process), locking the §2.3/§7 consumer contract and the
// response-shape sync/async dispatch (result with task_id = async acceptance,
// without = sync direct answer).
//
// No DocumentService/SettingsService dependency here (unlike
// test_studio_service.cpp): AssistService delegates nothing — no singleton
// split caveat, every test function constructs a fresh service.
#include <QtTest/QAbstractItemModelTester>
#include <QtTest/QtTest>

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSignalSpy>

#include "backend/backend_manager.h"
#include "backend/ipc_protocol.h"
#include "models/assist_model.h"
#include "models/task_model.h"
#include "services/assist_service.h"

using toolbox::AssistModel;
using toolbox::AssistService;
using toolbox::BackendManager;
using toolbox::TaskModel;

namespace {

QString reqId(int n) {
    return QStringLiteral("req-%1").arg(n);
}

// Probe: consumes one request-id slot and returns its number, giving every test
// a stable offset regardless of execution order (same trace trick as
// test_filter_service.cpp / test_studio_service.cpp).
int probeSlot(BackendManager &backend) {
    return backend.sendAction(QStringLiteral("probe")).mid(4).toInt();
}

QJsonObject successResponse(const QString &requestId, const QJsonObject &result) {
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("request_id"), requestId},
        {QStringLiteral("success"), true},
        {QStringLiteral("result"), result},
    };
}

QJsonObject failedResponse(const QString &requestId, const QString &code, const QString &message) {
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("request_id"), requestId},
        {QStringLiteral("success"), false},
        {QStringLiteral("error"),
         QJsonObject{
             {QStringLiteral("code"), code},
             {QStringLiteral("message"), message},
             {QStringLiteral("details"), QJsonObject{}},
         }},
    };
}

// async 动作受理响应（§2.3 异步动作受理形态，与 filter.apply/batch.start/
// generate.render 的受理回执同构）。
QJsonObject asyncAcceptedResponse(const QString &requestId, const QString &taskId) {
    return successResponse(requestId, QJsonObject{
                                          {QStringLiteral("task_id"), taskId},
                                          {QStringLiteral("status"), QStringLiteral("queued")},
                                      });
}

QJsonObject completedEvent(const QString &taskId, const QJsonObject &result) {
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.completed")},
        {QStringLiteral("task_id"), taskId},
        {QStringLiteral("result"), result},
    };
}

QJsonObject failedEvent(const QString &taskId, const QString &code, const QString &message) {
    return QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.failed")},
        {QStringLiteral("task_id"), taskId},
        {QStringLiteral("error"),
         QJsonObject{
             {QStringLiteral("code"), code},
             {QStringLiteral("message"), message},
             {QStringLiteral("details"), QJsonObject{}},
         }},
    };
}

// assist.list 的 result（{tools: [...]}，形状契约见 docs/ipc-protocol.md
// §3.8）：可用工具 + 依赖置灰工具（key 即动作名，固件用真实 §3.8 动作词汇；
// pyzbar 为 §3.8 barcode.decode 的真实缺失依赖名）。
QJsonObject assistListResult() {
    return QJsonObject{
        {QStringLiteral("tools"),
         QJsonArray{
             QJsonObject{
                 {QStringLiteral("key"), QStringLiteral("ocr.run")},
                 {QStringLiteral("name"), QStringLiteral("OCR 文字识别")},
                 {QStringLiteral("category"), QStringLiteral("ocr")},
                 {QStringLiteral("category_label"), QStringLiteral("OCR 文字识别")},
                 {QStringLiteral("available"), true},
                 {QStringLiteral("optional_deps"), QJsonArray{}},
             },
             QJsonObject{
                 {QStringLiteral("key"), QStringLiteral("barcode.decode")},
                 {QStringLiteral("name"), QStringLiteral("识别条码/二维码")},
                 {QStringLiteral("category"), QStringLiteral("barcode")},
                 {QStringLiteral("category_label"), QStringLiteral("条形码")},
                 {QStringLiteral("available"), false},
                 {QStringLiteral("optional_deps"), QJsonArray{QStringLiteral("pyzbar")}},
             },
         }},
    };
}

QString compact(const QJsonObject &object) {
    return QString::fromUtf8(QJsonDocument(object).toJson(QJsonDocument::Compact));
}

} // namespace

class TestAssistService : public QObject {
    Q_OBJECT

  private slots:
    // 服务默认态 + 未绑定后端（每个 Q_INVOKABLE 如实报错、不上送）。
    void defaultsAndUnboundBackend();
    // assist.list 填充 assistModel + loadingTools 生命周期；未跟踪帧忽略。
    void loadToolsFillsModel();
    // assist.list 失败：收在途标志、报错、目录保持旧数据。
    void loadToolsFailureKeepsCatalog();
    // 同步拒绝（旧 Worker 未含 §3.8 动作表 → UNKNOWN_ACTION，§5）。
    void assistListSyncRejection();
    // runTool 本地拒绝：空 key / 非对象 paramsJson（零上送）。
    void runToolLocalRejections();
    // sync 工具：成功响应无 task_id → notifyToolResult 原样交付，不产生任务行。
    void runToolSyncResult();
    // async 工具：受理交付 toolAccepted + 任务行（目录显示名；未收录 key 回落
    // key 本身）→ 进度归 TaskModel → completed result 经 notifyToolResult 交付；
    // 未知任务帧忽略。
    void runToolAsyncAcceptanceAndCompletion();
    // §7：task.failed（含 CANCELLED）→ assistError，不发射结果信号。
    void runToolFailureEvents();

  private:
    BackendManager m_backend;
};

void TestAssistService::defaultsAndUnboundBackend() {
    // 不 bindBackend 的裸服务：默认态干净，未绑定的调用一律 assistError(INTERNAL)
    // 且不上送（探针证明 request_id 计数器没被消费）。
    AssistService service;
    QAbstractItemModelTester modelTester(service.assistModel());
    QSignalSpy errors(&service, &AssistService::assistError);

    QVERIFY(!service.loadingTools());
    QCOMPARE(service.assistModel()->rowCount(), 0);

    const int n = probeSlot(m_backend);
    service.loadTools();
    QCOMPARE(service.runTool(QStringLiteral("ocr.run"), QStringLiteral("{}")), QString());
    QCOMPARE(service.runTool(QString(), QStringLiteral("{}")), QString()); // key 校验在前
    QCOMPARE(service.runTool(QStringLiteral("ocr.run"), QStringLiteral("{not json")), QString());
    QCOMPARE(errors.count(), 4);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INTERNAL"));
    QCOMPARE(errors.at(1).at(0).toString(), QStringLiteral("INTERNAL"));
    QCOMPARE(errors.at(2).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(errors.at(3).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(probeSlot(m_backend), n + 1); // 四次调用零上送
    QVERIFY(!service.loadingTools());      // 未发出不进入在途状态
}

void TestAssistService::loadToolsFillsModel() {
    AssistService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.assistModel());
    QSignalSpy loading(&service, &AssistService::loadingToolsChanged);
    QSignalSpy errors(&service, &AssistService::assistError);

    const int n = probeSlot(m_backend);
    service.loadTools();
    QCOMPARE(service.loadingTools(), true);
    QCOMPARE(loading.count(), 1); // false → true

    emit m_backend.responseReady(reqId(n + 1),
                                 successResponse(reqId(n + 1), assistListResult()));

    QCOMPARE(service.loadingTools(), false);
    QCOMPARE(loading.count(), 2); // true → false
    QCOMPARE(errors.count(), 0);
    QCOMPARE(service.assistModel()->rowCount(), 2);
    QCOMPARE(service.assistModel()->index(0, 0).data(AssistModel::ToolKeyRole).toString(),
             QStringLiteral("ocr.run"));
    QCOMPARE(service.assistModel()->index(0, 0).data(AssistModel::AvailableRole).toBool(), true);
    QCOMPARE(service.assistModel()->index(1, 0).data(AssistModel::AvailableRole).toBool(), false);
    QCOMPARE(service.assistModel()->index(1, 0).data(AssistModel::OptionalDepsRole).toStringList(),
             QStringList{QStringLiteral("pyzbar")});

    // 未跟踪帧不落 assistModel：他人动作的受理响应与未知 request_id 一律被
    // AssistService 忽略（assist_service.cpp 关联注释）。
    emit m_backend.responseReady(reqId(n + 7),
                                 asyncAcceptedResponse(reqId(n + 7), QStringLiteral("task-ghost")));
    QCOMPARE(service.assistModel()->rowCount(), 2);
    QCOMPARE(errors.count(), 0);
    QCOMPARE(service.loadingTools(), false);
}

void TestAssistService::loadToolsFailureKeepsCatalog() {
    AssistService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester tester(service.assistModel());
    QSignalSpy loading(&service, &AssistService::loadingToolsChanged);
    QSignalSpy errors(&service, &AssistService::assistError);

    // 先成功填一次目录。
    const int n = probeSlot(m_backend);
    service.loadTools();
    emit m_backend.responseReady(reqId(n + 1), successResponse(reqId(n + 1), assistListResult()));
    QCOMPARE(service.assistModel()->rowCount(), 2);

    // 第二次刷新被拒：收在途标志 + 报错；目录保持旧数据（不填新、不清旧）。
    service.loadTools();
    QCOMPARE(service.loadingTools(), true);
    emit m_backend.responseReady(
        reqId(n + 2),
        failedResponse(reqId(n + 2), QStringLiteral("INTERNAL"), QStringLiteral("worker 异常")));
    QCOMPARE(service.loadingTools(), false);
    QCOMPARE(loading.count(), 4); // true→false→true→false
    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INTERNAL"));
    QCOMPARE(service.assistModel()->rowCount(), 2); // 旧目录仍在
}

void TestAssistService::assistListSyncRejection() {
    AssistService service;
    service.bindBackend(&m_backend);
    QSignalSpy errors(&service, &AssistService::assistError);

    // 同步拒绝（§5）：旧 Worker（未含 §3.8 动作表）对 assist.list 应答
    // UNKNOWN_ACTION——降级路径如实锁定；在途标志收掉、错误如实上报（辅助
    // 工具页的错误态），模型不动。§3.8 落地后的现实拒绝（DEPENDENCY_MISSING /
    // INTERNAL 等）走同一 onResponseReady 通道（loadToolsFailureKeepsCatalog
    // 已锁 INTERNAL 样本）。
    const int n = probeSlot(m_backend);
    service.loadTools();
    emit m_backend.responseReady(reqId(n + 1),
                                 failedResponse(reqId(n + 1), QStringLiteral("UNKNOWN_ACTION"),
                                                QStringLiteral("未知动作: assist.list")));
    QCOMPARE(service.loadingTools(), false);
    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("UNKNOWN_ACTION"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("未知动作: assist.list"));
}

void TestAssistService::runToolLocalRejections() {
    AssistService service;
    service.bindBackend(&m_backend);
    QSignalSpy accepted(&service, &AssistService::toolAccepted);
    QSignalSpy results(&service, &AssistService::notifyToolResult);
    QSignalSpy errors(&service, &AssistService::assistError);

    const int n = probeSlot(m_backend);
    // 空 key（key 即运行动作名，run 的最小定位字段）。
    QCOMPARE(service.runTool(QString(), QStringLiteral("{}")), QString());
    QCOMPARE(service.runTool(QStringLiteral("   "), QStringLiteral("{}")), QString());
    // paramsJson 解析失败 / 非对象。
    QCOMPARE(service.runTool(QStringLiteral("ocr.run"), QStringLiteral("{not json")), QString());
    QCOMPARE(service.runTool(QStringLiteral("ocr.run"), QStringLiteral("[1,2]")), QString());
    QCOMPARE(errors.count(), 4);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("工具 key 为空"));
    QCOMPARE(errors.at(2).at(0).toString(), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(errors.at(2).at(1).toString(), QStringLiteral("参数不是 JSON 对象"));
    QCOMPARE(probeSlot(m_backend), n + 1); // 四次拒绝零上送
    QCOMPARE(accepted.count(), 0);
    QCOMPARE(results.count(), 0);
}

void TestAssistService::runToolSyncResult() {
    AssistService service;
    service.bindBackend(&m_backend);
    QSignalSpy accepted(&service, &AssistService::toolAccepted);
    QSignalSpy results(&service, &AssistService::notifyToolResult);
    QSignalSpy errors(&service, &AssistService::assistError);

    // 任务行观察：sync 工具的成功响应不产生任务行（task_model.cpp:66-72
    // "sync action answered — nothing to track"，§3.4 预设动作的同一原则）。
    TaskModel taskModel;
    QAbstractItemModelTester taskTester(&taskModel);
    taskModel.setBackend(&m_backend);
    service.bindTaskModel(&taskModel);

    // 1) 提交：返回提交关联号 request_id；空 paramsJson 按 {} 上送（无参工具）。
    const int n = probeSlot(m_backend);
    const QString submitted =
        service.runTool(QStringLiteral("checksum.file"), QStringLiteral("{\"path\":\"a.png\"}"));
    QCOMPARE(submitted, reqId(n + 1));
    QCOMPARE(taskModel.rowCount(), 0); // 响应前不造任务行（不伪造进度）

    // 2) sync 应答（result 无 task_id）：结果对象原样交付（紧凑 JSON），不发射
    //    toolAccepted，不产生任务行。
    const QJsonObject result{{QStringLiteral("sha256"), QStringLiteral("abc")}};
    emit m_backend.responseReady(reqId(n + 1), successResponse(reqId(n + 1), result));
    QCOMPARE(results.count(), 1);
    QCOMPARE(results.at(0).at(0).toString(), QStringLiteral("checksum.file"));
    QCOMPARE(results.at(0).at(1).toString(), compact(result));
    QCOMPARE(accepted.count(), 0);
    QCOMPARE(taskModel.rowCount(), 0);
    QCOMPARE(errors.count(), 0);

    // 3) 重复帧：request_id 关联已消费，同 id 再来的响应被忽略（不重复交付）。
    emit m_backend.responseReady(reqId(n + 1), successResponse(reqId(n + 1), result));
    QCOMPARE(results.count(), 1);
}

void TestAssistService::runToolAsyncAcceptanceAndCompletion() {
    AssistService service;
    service.bindBackend(&m_backend);
    QAbstractItemModelTester modelTester(service.assistModel());
    QSignalSpy accepted(&service, &AssistService::toolAccepted);
    QSignalSpy results(&service, &AssistService::notifyToolResult);
    QSignalSpy errors(&service, &AssistService::assistError);

    // 任务行：async 工具受理进 TaskModel，进度呈现归 TaskModel
    //（"进度模式对齐既有任务"）。
    TaskModel taskModel;
    QAbstractItemModelTester taskTester(&taskModel);
    taskModel.setBackend(&m_backend);
    service.bindTaskModel(&taskModel);

    // 0) 先填目录——任务行显示名取自目录显示名。
    const int n = probeSlot(m_backend);
    service.loadTools();
    emit m_backend.responseReady(reqId(n + 1), successResponse(reqId(n + 1), assistListResult()));

    // 1) 提交：受理前不造任务行。
    const QString submitted =
        service.runTool(QStringLiteral("ocr.run"), QStringLiteral("{\"lang\":\"zh\"}"));
    QCOMPARE(submitted, reqId(n + 2));
    QCOMPARE(taskModel.rowCount(), 0);

    // 2) 受理：task_id 唯一交付路径 toolAccepted（§2.3）+ 任务行建立（显示名 =
    //    目录显示名"OCR 文字识别"）。
    emit m_backend.responseReady(reqId(n + 2),
                                 asyncAcceptedResponse(reqId(n + 2), QStringLiteral("task-1")));
    QCOMPARE(accepted.count(), 1);
    QCOMPARE(accepted.at(0).at(0).toString(), QStringLiteral("ocr.run"));
    QCOMPARE(accepted.at(0).at(1).toString(), QStringLiteral("task-1"));
    QCOMPARE(taskModel.rowCount(), 1);
    QCOMPARE(taskModel.index(0, 0).data(TaskModel::NameRole).toString(),
             QStringLiteral("OCR 文字识别"));
    QCOMPARE(taskModel.index(0, 0).data(TaskModel::StatusRole).toString(),
             QStringLiteral("queued"));

    // 3) 进度事件：AssistService 不发结果（进度呈现归 TaskModel 行）。
    emit m_backend.taskEvent(QJsonObject{
        {QStringLiteral("protocol"), toolbox::ipc::kProtocolVersion},
        {QStringLiteral("type"), QStringLiteral("task.progress")},
        {QStringLiteral("task_id"), QStringLiteral("task-1")},
        {QStringLiteral("progress"), 40},
    });
    QCOMPARE(taskModel.index(0, 0).data(TaskModel::StatusRole).toString(),
             QStringLiteral("running"));
    QCOMPARE(results.count(), 0);
    QCOMPARE(errors.count(), 0);

    // 4) 完成（task.completed）：result 原样序列化经 notifyToolResult 交付。
    const QJsonObject done{{QStringLiteral("text"), QStringLiteral("识别文本")}};
    emit m_backend.taskEvent(completedEvent(QStringLiteral("task-1"), done));
    QCOMPARE(results.count(), 1);
    QCOMPARE(results.at(0).at(0).toString(), QStringLiteral("ocr.run"));
    QCOMPARE(results.at(0).at(1).toString(), compact(done));
    QCOMPARE(taskModel.index(0, 0).data(TaskModel::StatusRole).toString(),
             QStringLiteral("completed"));
    QCOMPARE(errors.count(), 0);

    // 5) 未收录 key 的任务行：显示名回落 key 本身（toolDisplayName 的兜底分支）。
    const QString submitted2 = service.runTool(QStringLiteral("unknown.action"), QString());
    QCOMPARE(submitted2, reqId(n + 3));
    emit m_backend.responseReady(reqId(n + 3),
                                 asyncAcceptedResponse(reqId(n + 3), QStringLiteral("task-2")));
    QCOMPARE(accepted.count(), 2);
    QCOMPARE(taskModel.rowCount(), 2);
    QCOMPARE(taskModel.index(1, 0).data(TaskModel::NameRole).toString(),
             QStringLiteral("unknown.action"));

    // 6) 空 completed result：原样交付 "{}"（C++ 只透传，不猜测工具形状）。
    emit m_backend.taskEvent(completedEvent(QStringLiteral("task-2"), QJsonObject{}));
    QCOMPARE(results.count(), 2);
    QCOMPARE(results.at(1).at(0).toString(), QStringLiteral("unknown.action"));
    QCOMPARE(results.at(1).at(1).toString(), QStringLiteral("{}"));

    // 7) 未知任务的终态帧：忽略（image.* / filter.* 任务归各自服务）。
    emit m_backend.taskEvent(completedEvent(
        QStringLiteral("task-other"), QJsonObject{{QStringLiteral("path"), QStringLiteral("/x")}}));
    QCOMPARE(results.count(), 2);
    QCOMPARE(errors.count(), 0);
}

void TestAssistService::runToolFailureEvents() {
    AssistService service;
    service.bindBackend(&m_backend);
    QSignalSpy results(&service, &AssistService::notifyToolResult);
    QSignalSpy errors(&service, &AssistService::assistError);

    const int n = probeSlot(m_backend);
    service.runTool(QStringLiteral("ocr.run"), QStringLiteral("{}"));
    emit m_backend.responseReady(reqId(n + 1),
                                 asyncAcceptedResponse(reqId(n + 1), QStringLiteral("task-1")));

    // §7：非取消失败（如引擎异常）→ assistError 透传 code/message。
    emit m_backend.taskEvent(failedEvent(QStringLiteral("task-1"), QStringLiteral("ENGINE_ERROR"),
                                         QStringLiteral("处理器执行异常")));
    QCOMPARE(errors.count(), 1);
    QCOMPARE(errors.at(0).at(0).toString(), QStringLiteral("ENGINE_ERROR"));
    QCOMPARE(errors.at(0).at(1).toString(), QStringLiteral("处理器执行异常"));
    QCOMPARE(results.count(), 0);

    // §7：取消以 task.failed + CANCELLED 呈现——同一通道如实上报，不特判吞掉。
    service.runTool(QStringLiteral("ocr.run"), QStringLiteral("{}"));
    emit m_backend.responseReady(reqId(n + 2),
                                 asyncAcceptedResponse(reqId(n + 2), QStringLiteral("task-2")));
    emit m_backend.taskEvent(failedEvent(QStringLiteral("task-2"), QStringLiteral("CANCELLED"),
                                         QStringLiteral("任务已取消")));
    QCOMPARE(errors.count(), 2);
    QCOMPARE(errors.at(1).at(0).toString(), QStringLiteral("CANCELLED"));
    QCOMPARE(results.count(), 0);
}

QTEST_MAIN(TestAssistService)
#include "test_assist_service.moc"
