#pragma once

#include <QJsonObject>
#include <QString>

namespace toolbox::ipc {

// Protocol constants and message builders (docs/ipc-protocol.md).
// Python-side counterpart: python_worker/protocol.py — both must stay in sync.
inline constexpr int kProtocolVersion = 1;

// Stable error codes (docs/ipc-protocol.md §5).
inline constexpr auto kErrParse = "PARSE_ERROR";
inline constexpr auto kErrProtocolMismatch = "PROTOCOL_MISMATCH";
inline constexpr auto kErrUnknownAction = "UNKNOWN_ACTION";
inline constexpr auto kErrInvalidParams = "INVALID_PARAMS";
inline constexpr auto kErrUnknownDocument = "UNKNOWN_DOCUMENT";
inline constexpr auto kErrUnknownTask = "UNKNOWN_TASK";
inline constexpr auto kErrFileNotFound = "FILE_NOT_FOUND";
inline constexpr auto kErrUnsupportedFormat = "UNSUPPORTED_FORMAT";
inline constexpr auto kErrUnredoable = "UNREDOABLE";
inline constexpr auto kErrCancelled = "CANCELLED";
inline constexpr auto kErrEngineError = "ENGINE_ERROR";
inline constexpr auto kErrInternal = "INTERNAL";

// Frame kinds on the wire.
enum class FrameKind { Request, Response, Event, Invalid };

class IpcProtocol {
  public:
    // Builders — C++ side.
    static QJsonObject makeRequest(const QString &requestId, const QString &action,
                                   const QJsonObject &params = {});
    static QJsonObject makeCancelTask(const QString &requestId, const QString &taskId);

    // Frame classification and validation — both directions.
    static FrameKind classify(const QJsonObject &message);
    static bool validateRequest(const QJsonObject &message, QString *error = nullptr);

    // Response/event accessors — Worker side messages.
    static QString requestIdOf(const QJsonObject &message);
    static bool isSuccess(const QJsonObject &message);
    static QJsonObject resultOf(const QJsonObject &message);
    static QJsonObject errorOf(const QJsonObject &message);
    static QString eventTaskId(const QJsonObject &message);
};

} // namespace toolbox::ipc
