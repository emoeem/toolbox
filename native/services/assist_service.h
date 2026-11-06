#pragma once

#include <QHash>
#include <QJsonObject>
#include <QObject>
#include <QString>
#include <QtQml/qqml.h>

// AssistModel 必须完整包含：Q_PROPERTY 的指针类型在 moc 生成的元类型注册
// 代码里做 sizeof（document_service.h:11-14 / filter_service.h:11-15 同款
// CI 实证），前置声明不够；#include 只能放在 namespace 之外——放进 namespace
// 会把整个 Qt 头展开进 toolbox（CI 实证）。TaskModel 只出现在 Q_INVOKABLE
// 参数里，但 DocumentService::bindTaskModel 的既有实证（document_service.h:14，
// studio_service.h:18 跟随）对它同样采用完整包含——本文件跟随该先例。
// BackendManager 只出现在 Q_INVOKABLE 参数里（document_service.h:18 同款前置
// 声明即可），完整类型在 .cpp 引入。
#include "models/assist_model.h"
#include "models/task_model.h"

namespace toolbox {

class BackendManager;

// 辅助工具页 facade（docs/ipc-protocol.md §3.8，总纲 §9.9 "工具箱与辅助
// 页面"、§13 Phase 7 "AI 与辅助工具"，ui/pages/ToolsPage.qml 经
// AppToolsPage.qml 的数据源）：assistModel（assist.list 目录）+ runTool
// （按工具上送运行动作，sync 直答 / async 受理两种形态）。
//
// 协议对齐（docs/ipc-protocol.md §3.8，Phase 7 增补；Python 侧
// python_worker/adapters/assist_adapter.py + dispatcher.py 动作表，Worker 测
// 试锁为 tests/test_worker_assist.py）：
//   - assist.list（sync，目录类动作与 §3 filter.list / generate.list 同构）：
//       result = {tools: [{key, name, category, category_label, description,
//       type, available, optional_deps}]}
//     description / type 协议面保留、AssistModel 角色面不含（任务清单指定
//     五角色；GeneratorModel 对 description 的同一处置，§3.7 Phase 6C 复查
//     注）。
//   - 工具运行动作：条目 key 即该工具的动作名（§3.8 "条目 key 即动作名"，
//     "sendAction 对应动作"的落地口径——动作随工具而异，runTool 原样以 key
//     上送），params 为该工具自有的参数对象（§3 动作表逐动作定义，QML 装配
//     上送）。sync 动作直接以工具结果对象作 result 应答（不产生任务行，
//     §3.4 预设动作的同一原则）；async 动作按 §2.3 受理 {task_id, status}，
//     进度/终态走 task.* 事件（§7）。C++ 侧按响应形状判定两种形态（result
//     有无 task_id），不依赖目录 type 字段——对动作 type 漂移更稳健。
//   - 接入未含 §3.8 动作的旧 Worker 会得到 UNKNOWN_ACTION（§5），本服务如实
//     上报、不伪造目录或运行结果；依赖缺失的动作提交得到 §5 新增的
//     DEPENDENCY_MISSING（details.missing 列出缺失名），走同一错误通道。
//
// 关联模式与 FilterService / StudioService 同款 tracked dispatch：每个
// Q_INVOKABLE 在 sendAction 时把 request_id 记入 m_pendingByRequest，响应按
// request_id 取回上下文（工具 key）；async 受理后上下文迁移到 m_pendingByTask
// （事件只携带 task_id，studio_service.cpp:168-183 同款）。未跟踪帧
// （worker.hello、image.*、filter.*、batch.*、generate.*）一律忽略——那些
// 动作的关联归各自服务，本服务绝不越权认领。
class AssistService : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    // 由本服务创建并持有（FilterService::filterModel 同款，CONSTANT：实例与
    // 进程同寿命，指针身份不变）。
    Q_PROPERTY(AssistModel *assistModel READ assistModel CONSTANT)
    // assist.list 在途（loadTools 发出 → 响应落定）；未绑定后端时恒 false
    // （FilterService::loadingFilters 同款，filter_service.h:47-48）。
    Q_PROPERTY(bool loadingTools READ loadingTools NOTIFY loadingToolsChanged)

  public:
    explicit AssistService(QObject *parent = nullptr);
    ~AssistService() override;

    // Process-wide instance getter + QML singleton factory，与 FilterService /
    // StudioService（filter_service.h:54-57）同款：QML 查找与 C++ 接线必须
    // 拿到同一对象。
    static AssistService *instance();
    static AssistService *create(QQmlEngine *qmlEngine, QJSEngine *jsEngine);

    AssistModel *assistModel() const { return m_assistModel; }
    bool loadingTools() const { return m_loadingTools; }

    // DocumentService::bindBackend 同款（document_service.cpp:38-46）：QML 侧
    // AssistService.bindBackend(Application.backend) 完成接线；幂等重绑无害。
    Q_INVOKABLE void bindBackend(BackendManager *backend);

    // TaskModel 注入（StudioService::bindTaskModel 同款，studio_service.cpp:
    // 51-53）：async 工具任务经 TaskModel::trackRequest 登记任务行——行显示名
    // 为该工具的目录显示名（目录未含该 key 时回落 key 本身），进度/取消呈现
    // 与既有任务完全同款（"进度模式对齐既有任务"；任务抽屉/行内取消因此
    // 可见）。不绑定时运行照常提交，只是不进任务队列——行为回到无任务行。
    Q_INVOKABLE void bindTaskModel(TaskModel *taskModel);

    // assist.list（sync）：成功响应经 assistModel->reloadFrom 落地；成败都收
    // loadingTools（false）。后端未绑定时只发 assistError(INTERNAL)。
    Q_INVOKABLE void loadTools();

    // 运行工具（动作名 = toolKey，见类头协议注记）：paramsJson 为该工具的
    // 参数"值"对象 JSON 文本，空/纯空白按 {} 上送；解析失败/非对象在本地
    // 拒绝（INVALID_PARAMS，不上送）。toolKey 为空同样本地拒绝。
    //
    // 返回值为提交关联号 request_id（空 = 本地拒绝，未上送）。协议受理是异步
    // 的，工具是 sync 还是 async 由 Worker 端按动作注册决定、C++ 侧无法预知
    // （§2.3：task_id 只随响应到达——batch_service.h:68-71 对 startBatch 的
    // 同一约束原文），无法同步返回 task_id——async 工具的真实 task_id 经
    // toolAccepted(toolKey, taskId) 交付；sync 工具的结果经 notifyToolResult
    // 交付。
    Q_INVOKABLE QString runTool(const QString &toolKey, const QString &paramsJson);

  signals:
    // code/message 见 docs/ipc-protocol.md §5（含未绑定后端的 INTERNAL、本地
    // 参数拒绝与提交前同步拒绝、§3.8 的 DEPENDENCY_MISSING、async 工具的
    // task.failed、协议违约）。纯用户呈现（Toast）；§7：取消以 task.failed +
    // CANCELLED 呈现，同一通道如实上报，不特判吞掉。
    void assistError(const QString &code, const QString &message);

    // async 工具受理响应落地（result.task_id）——task_id 的唯一交付路径
    // （§2.3，StudioService::renderAccepted 同款）。sync 工具（无 task_id 的
    // 成功响应）不发射本信号。
    void toolAccepted(const QString &toolKey, const QString &taskId);

    // 工具结果交付（resultJson = result 对象的紧凑 JSON 文本，工具自有形状
    // 原样透传，QML 按工具解析）：sync 工具在响应到达时交付一次；async 工具
    // 在 task.completed 到达时交付一次（completed result 原样序列化——
    // task_id/状态等生命周期字段已由 TaskModel 呈现，不再重复）。进度呈现归
    // TaskModel 行（task.progress 不经本信号）。
    void notifyToolResult(const QString &toolKey, const QString &resultJson);

    void loadingToolsChanged();

  private slots:
    void onResponseReady(const QString &requestId, const QJsonObject &message);
    void onTaskEvent(const QJsonObject &event);

  private:
    enum class PendingKind { ToolList, Run };

    struct Pending {
        PendingKind kind = PendingKind::ToolList;
        QString toolKey; // Run 提交的工具（= 上送的动作名）
    };

    // assist.list（sync）与工具运行动作共用发送路径：未绑定后端发
    // assistError(INTERNAL) 并返回空 id（FilterService::sendTracked 同款，
    // filter_service.cpp:48-62）。
    QString sendTracked(PendingKind kind, const QString &action, const QJsonObject &params,
                        const QString &toolKey = {});

    void setLoadingTools(bool loading);
    // 任务行显示名：目录中该 key 的显示名，未收录时回落 key 本身。
    QString toolDisplayName(const QString &toolKey) const;
    static QString compactJson(const QJsonObject &object);

    BackendManager *m_backend = nullptr;
    AssistModel *m_assistModel = nullptr; // 本服务创建并持有
    TaskModel *m_taskModel = nullptr;
    QHash<QString, Pending> m_pendingByRequest; // request_id → 提交上下文
    QHash<QString, Pending> m_pendingByTask;    // task_id → 提交上下文（async 终态）
    bool m_loadingTools = false;
};

} // namespace toolbox
