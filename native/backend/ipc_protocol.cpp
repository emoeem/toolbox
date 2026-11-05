#include "ipc_protocol.h"

#include <QJsonValue>

namespace toolbox::ipc {

QJsonObject IpcProtocol::makeRequest(const QString &requestId, const QString &action,
                                     const QJsonObject &params)
{
    return QJsonObject{
        {QStringLiteral("protocol"), kProtocolVersion},
        {QStringLiteral("request_id"), requestId},
        {QStringLiteral("action"), action},
        {QStringLiteral("params"), params},
    };
}

QJsonObject IpcProtocol::makeCancelTask(const QString &requestId, const QString &taskId)
{
    return makeRequest(requestId, QStringLiteral("task.cancel"),
                       QJsonObject{{QStringLiteral("task_id"), taskId}});
}

FrameKind IpcProtocol::classify(const QJsonObject &message)
{
    if (message.contains(QStringLiteral("type")))
        return FrameKind::Event;
    if (message.contains(QStringLiteral("request_id")) && message.contains(QStringLiteral("success")))
        return FrameKind::Response;
    if (message.contains(QStringLiteral("request_id")) && message.contains(QStringLiteral("action")))
        return FrameKind::Request;
    return FrameKind::Invalid;
}

bool IpcProtocol::validateRequest(const QJsonObject &message, QString *error)
{
    auto fail = [error](const QString &reason) {
        if (error)
            *error = reason;
        return false;
    };
    const auto protocol = message.value(QStringLiteral("protocol"));
    if (!protocol.isDouble())
        return fail(QStringLiteral("缺少 protocol 字段"));
    if (protocol.toInt() != kProtocolVersion)
        return fail(QStringLiteral("协议版本不受支持: %1").arg(protocol.toInt()));
    const auto requestId = message.value(QStringLiteral("request_id"));
    if (!requestId.isString() || requestId.toString().isEmpty())
        return fail(QStringLiteral("缺少 request_id"));
    const auto action = message.value(QStringLiteral("action"));
    if (!action.isString() || action.toString().isEmpty())
        return fail(QStringLiteral("缺少 action"));
    return true;
}

QString IpcProtocol::requestIdOf(const QJsonObject &message)
{
    return message.value(QStringLiteral("request_id")).toString();
}

bool IpcProtocol::isSuccess(const QJsonObject &message)
{
    return message.value(QStringLiteral("success")).toBool(false);
}

QJsonObject IpcProtocol::resultOf(const QJsonObject &message)
{
    return message.value(QStringLiteral("result")).toObject();
}

QJsonObject IpcProtocol::errorOf(const QJsonObject &message)
{
    return message.value(QStringLiteral("error")).toObject();
}

QString IpcProtocol::eventTaskId(const QJsonObject &message)
{
    return message.value(QStringLiteral("task_id")).toString();
}

} // namespace toolbox::ipc
