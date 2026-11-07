// Phase 3 IPC protocol codec tests. Locks the message shapes documented in
// docs/ipc-protocol.md; the Python side (tests/test_worker_protocol.py) locks
// the same contract from the worker direction.
#include <QtTest/QtTest>

#include "backend/ipc_protocol.h"

using namespace toolbox::ipc;

class TestIpcProtocol : public QObject {
    Q_OBJECT

  private slots:
    void makeRequestShape();
    void classifyFrames();
    void validateRequest();
    void responseAccessors();
    void errorCodesAreStable();
};

void TestIpcProtocol::makeRequestShape() {
    const QJsonObject request = IpcProtocol::makeRequest(
        QStringLiteral("req-1"), QStringLiteral("image.open"),
        QJsonObject{{QStringLiteral("path"), QStringLiteral("/tmp/a.png")}});

    QCOMPARE(request.value(QStringLiteral("protocol")).toInt(), kProtocolVersion);
    QCOMPARE(request.value(QStringLiteral("request_id")).toString(), QStringLiteral("req-1"));
    QCOMPARE(request.value(QStringLiteral("action")).toString(), QStringLiteral("image.open"));
    QCOMPARE(
        request.value(QStringLiteral("params")).toObject().value(QStringLiteral("path")).toString(),
        QStringLiteral("/tmp/a.png"));

    // Compact JSON must be one line for the JSON Lines stream.
    const QJsonDocument doc(request);
    QVERIFY(!doc.toJson(QJsonDocument::Compact).contains('\n'));
}

void TestIpcProtocol::classifyFrames() {
    QCOMPARE(
        IpcProtocol::classify(IpcProtocol::makeRequest(QStringLiteral("r"), QStringLiteral("a"))),
        FrameKind::Request);
    QCOMPARE(IpcProtocol::classify(QJsonObject{
                 {QStringLiteral("protocol"), 1},
                 {QStringLiteral("request_id"), QStringLiteral("r")},
                 {QStringLiteral("success"), true},
             }),
             FrameKind::Response);
    QCOMPARE(IpcProtocol::classify(QJsonObject{
                 {QStringLiteral("protocol"), 1},
                 {QStringLiteral("type"), QStringLiteral("task.progress")},
                 {QStringLiteral("task_id"), QStringLiteral("t")},
             }),
             FrameKind::Event);
    QCOMPARE(IpcProtocol::classify(QJsonObject{{QStringLiteral("junk"), true}}),
             FrameKind::Invalid);
}

void TestIpcProtocol::validateRequest() {
    QString error;
    QVERIFY(IpcProtocol::validateRequest(
        IpcProtocol::makeRequest(QStringLiteral("r"), QStringLiteral("a")), &error));
    QVERIFY(error.isEmpty());

    QJsonObject missingAction = IpcProtocol::makeRequest(QStringLiteral("r"), QStringLiteral("a"));
    missingAction.remove(QStringLiteral("action"));
    QVERIFY(!IpcProtocol::validateRequest(missingAction, &error));
    QVERIFY(!error.isEmpty());

    QJsonObject badVersion = IpcProtocol::makeRequest(QStringLiteral("r"), QStringLiteral("a"));
    badVersion.insert(QStringLiteral("protocol"), 42);
    QVERIFY(!IpcProtocol::validateRequest(badVersion, &error));
    QVERIFY(error.contains(QStringLiteral("42")));

    QJsonObject missingId = IpcProtocol::makeRequest(QStringLiteral("r"), QStringLiteral("a"));
    missingId.remove(QStringLiteral("request_id"));
    QVERIFY(!IpcProtocol::validateRequest(missingId, &error));
}

void TestIpcProtocol::responseAccessors() {
    QJsonObject ok{
        {QStringLiteral("protocol"), 1},
        {QStringLiteral("request_id"), QStringLiteral("req-9")},
        {QStringLiteral("success"), true},
        {QStringLiteral("result"),
         QJsonObject{{QStringLiteral("document_id"), QStringLiteral("doc-1")}}},
    };
    QVERIFY(IpcProtocol::isSuccess(ok));
    QCOMPARE(IpcProtocol::requestIdOf(ok), QStringLiteral("req-9"));
    QCOMPARE(IpcProtocol::resultOf(ok).value(QStringLiteral("document_id")).toString(),
             QStringLiteral("doc-1"));

    QJsonObject fail{
        {QStringLiteral("protocol"), 1},
        {QStringLiteral("request_id"), QStringLiteral("req-9")},
        {QStringLiteral("success"), false},
        {
            QStringLiteral("error"),
            QJsonObject{{QStringLiteral("code"), QStringLiteral("FILE_NOT_FOUND")},
                        {QStringLiteral("message"), QStringLiteral("文件不存在")},
                        {QStringLiteral("details"), QJsonObject{}}},
        },
    };
    QVERIFY(!IpcProtocol::isSuccess(fail));
    QCOMPARE(IpcProtocol::errorOf(fail).value(QStringLiteral("code")).toString(),
             QStringLiteral("FILE_NOT_FOUND"));

    QJsonObject event{
        {QStringLiteral("protocol"), 1},
        {QStringLiteral("type"), QStringLiteral("task.completed")},
        {QStringLiteral("task_id"), QStringLiteral("task-7")},
    };
    QCOMPARE(IpcProtocol::eventTaskId(event), QStringLiteral("task-7"));
}

void TestIpcProtocol::errorCodesAreStable() {
    // These strings cross the process boundary and are locked by the spec.
    QCOMPARE(QString::fromLatin1(kErrParse), QStringLiteral("PARSE_ERROR"));
    QCOMPARE(QString::fromLatin1(kErrProtocolMismatch), QStringLiteral("PROTOCOL_MISMATCH"));
    QCOMPARE(QString::fromLatin1(kErrUnknownAction), QStringLiteral("UNKNOWN_ACTION"));
    QCOMPARE(QString::fromLatin1(kErrInvalidParams), QStringLiteral("INVALID_PARAMS"));
    QCOMPARE(QString::fromLatin1(kErrUnknownDocument), QStringLiteral("UNKNOWN_DOCUMENT"));
    QCOMPARE(QString::fromLatin1(kErrUnknownTask), QStringLiteral("UNKNOWN_TASK"));
    QCOMPARE(QString::fromLatin1(kErrFileNotFound), QStringLiteral("FILE_NOT_FOUND"));
    QCOMPARE(QString::fromLatin1(kErrUnsupportedFormat), QStringLiteral("UNSUPPORTED_FORMAT"));
    QCOMPARE(QString::fromLatin1(kErrCancelled), QStringLiteral("CANCELLED"));
    QCOMPARE(QString::fromLatin1(kErrEngineError), QStringLiteral("ENGINE_ERROR"));
    QCOMPARE(QString::fromLatin1(kErrInternal), QStringLiteral("INTERNAL"));
}

QTEST_MAIN(TestIpcProtocol)
#include "test_ipc_protocol.moc"
