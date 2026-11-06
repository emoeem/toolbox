#pragma once

#include <QHash>
#include <QJsonObject>
#include <QObject>
#include <QString>
#include <QUrl>
#include <QtQml/qqml.h>

// TaskModel 必须完整包含：moc 生成的元类型注册代码对信号/属性里的指针类型
// 做 sizeof（CI 实证 incomplete type），前置声明不够。注意 #include 只能放
// 在 namespace 之外——放进 namespace 会把整个 Qt 头展开进 toolbox（CI 实证）。
#include "models/task_model.h"

namespace toolbox {

class BackendManager;

// Document-facing facade over the Worker protocol (docs/ipc-protocol.md §3):
// one current document plus the Phase 4 edit actions. image.open / image.save
// drive the current-document state (id/path/version/modified); image.adjust /
// image.transform / image.undo / image.redo / image.reset / image.history are
// submitted as tracked requests and resolved from the task lifecycle events.
//
// Pending-correlation mirrors TaskModel (task_model.cpp:59-77): every
// Q_INVOKABLE registers its request_id in m_pendingByRequest at submit time;
// a success response carrying task_id moves the context to m_pendingByTask
// (async events carry task_id, never request_id); sync actions resolve
// directly from the response. Untracked frames are ignored so other consumers
// (the future filter service) keep their own correlation.
//
// Task rows: async actions are also registered with the TaskModel via
// bindTaskModel() (QML wiring, same pattern as bindBackend) so the task
// drawer/status summary see one row per accepted action and rows can be
// cancelled in place (docs/ipc-protocol.md §2.3/§7; TaskModel only creates
// rows for request_ids registered through trackRequest, task_model.cpp:59-77).
//
// Version semantics follow docs/ipc-protocol.md §3.1 verbatim:
//   - image.open resets the version to 0; image.save never changes it.
//   - Full-resolution image.adjust/transform and undo/redo results carry
//     result.version, which becomes currentVersion and marks the document
//     modified; image.reset bumps the version too but clears the modified
//     flag instead — the pixels are back to the source image (the Worker
//     side sets modified=false, python_worker/adapters/image_adapter.py),
//     so UI truth (● / save button) matches image.metadata.
//   - Preview tasks (preview=true) carry the execute-time version (§2.3);
//     they emit previewReady(result) only and never touch version/modified.
class DocumentService : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    // currentDocumentId is empty when no document is open; documentPath is
    // the local path of the open file (they always change together).
    Q_PROPERTY(QString currentDocumentId READ currentDocumentId NOTIFY currentDocumentChanged)
    Q_PROPERTY(QString documentPath READ documentPath NOTIFY currentDocumentChanged)
    // Meaningful only while a document is open (0 right after image.open, §3.1).
    Q_PROPERTY(int currentVersion READ currentVersion NOTIFY documentVersionChanged)
    Q_PROPERTY(bool documentModified READ documentModified NOTIFY documentModifiedChanged)

  public:
    explicit DocumentService(QObject *parent = nullptr);
    ~DocumentService() override;

    // Process-wide instance getter + QML singleton factory, mirroring
    // SettingsService (settings_service.h:69-76): a later QML-side lookup and
    // any future C++ wiring must return the same object, never a second one.
    static DocumentService *instance();
    static DocumentService *create(QQmlEngine *qmlEngine, QJSEngine *jsEngine);

    QString currentDocumentId() const { return m_currentDocumentId; }
    QString documentPath() const { return m_documentPath; }
    int currentVersion() const { return m_currentVersion; }
    bool documentModified() const { return m_documentModified; }

    // TaskModel::setBackend 同款模式（task_model.cpp:20-28），但公开为
    // Q_INVOKABLE：QML 侧用 DocumentService.bindBackend(Application.backend)
    // 完成接线。bindTaskModel 同理：把 Application.taskModel 注入本服务，
    // dispatch 受理异步动作时经 TaskModel::trackRequest 登记任务行——
    // 不登记则编辑动作永远不会出现在任务抽屉/摘要里，也无法行内取消。
    Q_INVOKABLE void bindBackend(BackendManager *backend);
    Q_INVOKABLE void bindTaskModel(TaskModel *taskModel);

    // image.open（sync）：成功后设置 current* 状态、emit documentOpened 并把
    // 路径写入 SettingsService 最近文件。只接受本地文件 URL。
    Q_INVOKABLE void openDocument(const QUrl &file);

    // image.save（async）：quality < 0 时省略 quality 参数（Worker 用默认）。
    Q_INVOKABLE void saveDocument(const QString &path, int quality = -1);

    // image.adjust / image.transform（async）：preview=true 走降采样预览管线，
    // maxSide >= 0 时随请求携带 max_side，否则由 Worker 取缺省 768（§3.2）。
    Q_INVOKABLE void adjust(const QJsonObject &adjustments, bool preview = false, int maxSide = -1);
    Q_INVOKABLE void transform(const QString &op, const QJsonObject &params, bool preview = false,
                               int maxSide = -1);

    // image.undo / image.redo / image.reset（async，§3.3）。
    Q_INVOKABLE void undo();
    Q_INVOKABLE void redo();
    Q_INVOKABLE void reset();

    // image.history（sync，§3.3）：结果经 historyReady(history) 广播，由
    // HistoryModel::refreshFrom 消费。
    Q_INVOKABLE void requestHistory();

  signals:
    void currentDocumentChanged();
    void documentModifiedChanged();
    void documentOpened(const QString &documentId, const QString &path, int width, int height);
    void documentSaved(const QString &path);
    // Preview file ready for the canvas: preview=true 的 image.* 任务，以及
    // undo/redo/reset 完成时携带的画布刷新文件（§3.3 写一份降采样预览文件
    // "供画布立即刷新"，复用同一通道交付）。result 形状见 §3.2/§3.3。
    void previewReady(const QJsonObject &result);
    void documentVersionChanged(int version);
    // code/message 见 docs/ipc-protocol.md §5。纯用户呈现（Toast）；在途提交
    // 的状态机迁移走 documentActionFailed（本信号不带动作上下文，QML 不能
    // 据此解除门控——无关错误一律解锁会重新打开门控要阻止的历史栈竞态窗口）。
    void documentError(const QString &code, const QString &message);
    // 一个已跟踪（tracked）动作未成功落定：提交前同步拒绝、task.failed、
    // 异步响应缺 task_id 的协议违约、后端未绑定。documentId 为提交时的
    // currentDocumentId（陈旧判定同款上下文）；action 为动作标识（协议动作
    // 名，预览任务带 "-preview" 后缀，见 actionId()）。QML 在途门控据此只在
    // "当前文档的全分辨率 adjust/transform 失败"时解锁——documentId 区分
    // 换文档后的旧文档失败，action 后缀区分同文档的预览失败。
    void documentActionFailed(const QString &documentId, const QString &action);
    void historyReady(const QJsonObject &history);

  private slots:
    void onResponseReady(const QString &requestId, const QJsonObject &message);
    void onTaskEvent(const QJsonObject &event);

  private:
    enum class PendingKind { Open, Save, Adjust, Transform, Undo, Redo, Reset, History };

    struct Pending {
        PendingKind kind = PendingKind::Open;
        QString path;       // Open: 源路径；Save: 目标路径
        QString documentId; // 提交时的 currentDocumentId（陈旧任务丢弃依据）
        bool preview = false;
    };

    // Sends one tracked request. Emits documentError(INTERNAL) and returns an
    // empty id when no backend is bound — never fakes progress. Async kinds
    // are additionally registered with the bound TaskModel (trackRequest) so
    // the acceptance response creates a task row.
    QString dispatch(PendingKind kind, const QString &action, const QJsonObject &params,
                     const QString &path = {}, bool preview = false);

    // 任务行显示名（TaskModel NameRole；与页面用语一致，条目名本地化归本层）。
    static QString taskDisplayName(PendingKind kind, bool preview);

    // 动作标识（documentActionFailed 的 action 参数）：协议动作名，预览任务
    // 带 "-preview" 后缀，供 QML 区分全分辨率提交与预览提交的失败。
    static QString actionId(PendingKind kind, bool preview);

    void applyOpened(const QString &path, const QJsonObject &result);
    // 换文档成功后回收旧文档（image.close，fire-and-forget）：旧 Document 的
    // image/source_image/快照不随多次打开滞留 Worker。旧文档仍有在途任务时
    // 跳过（close 会让任务体的 store.get 抛 UNKNOWN_DOCUMENT，把合法的保存/
    // 应用打成失败）；被跳过的旧文档随下次切换或 Worker 退出回收。
    void closePreviousDocument(const QString &previousDocumentId);
    void handleCompleted(const Pending &pending, const QJsonObject &result);
    // markModified=false 仅用于 image.reset（像素回到源图，无未保存修改，
    // 与 Worker 端 image_adapter.py 的 reset 语义一致）。
    void applyCompletedVersion(const QJsonObject &result, bool markModified);

    BackendManager *m_backend = nullptr;
    TaskModel *m_taskModel = nullptr;
    QHash<QString, Pending> m_pendingByRequest; // request_id → 提交上下文
    QHash<QString, Pending> m_pendingByTask;    // task_id → 提交上下文
    QString m_currentDocumentId;
    QString m_documentPath;
    int m_currentVersion = 0;
    bool m_documentModified = false;
};

} // namespace toolbox
