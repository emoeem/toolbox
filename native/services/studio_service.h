#pragma once

#include <QHash>
#include <QJsonObject>
#include <QObject>
#include <QString>
#include <QtQml/qqml.h>

// GeneratorModel 必须完整包含：Q_PROPERTY 的指针类型在 moc 生成的元类型注册
// 代码里做 sizeof（document_service.h:11-14 / filter_service.h:11-15 同款
// CI 实证），前置声明不够；#include 只能放在 namespace 之外——放进 namespace
// 会把整个 Qt 头展开进 toolbox（CI 实证）。TaskModel 只出现在 Q_INVOKABLE
// 参数里，但 DocumentService::bindTaskModel 的既有实证（document_service.h:14）
// 对它同样采用完整包含——本文件跟随该先例。BackendManager 只出现在
// Q_INVOKABLE 参数里（document_service.h:18 同款前置声明即可），完整类型在
// .cpp 引入。
#include "models/generator_model.h"
#include "models/task_model.h"

namespace toolbox {

class BackendManager;

// Studio 页 facade（docs/toolbox-2.0-project-plan.md §9.7 Texture Studio，
// ui/pages/TexturePage.qml 的数据源）：generatorModel（generate.list 目录）+
// render（generate.render 异步渲染，§2.3 受理模式）+ exportToEditor（把成品
// 图交给编辑器继续加工——委托 DocumentService::openDocument，通道与状态归
// 文档层所有）。
//
// 协议状态注记（诚实范围，test_batch_service.cpp 头注释对 batch.start 的同一
// 处理）：generate.list / generate.render 尚未写入 docs/ipc-protocol.md §3，
// Worker 端（python_worker/dispatcher.py + 适配器）由同阶段 Python 批次落地；
// 今天接入真实 Worker 会得到 UNKNOWN_ACTION（§5），本服务如实上报、不伪造
// 目录或渲染结果。此处编码的形状是 Worker 端实现必须满足的契约：
//   - generate.list（sync，目录类动作与 §3 filter.list 同构）：
//       result = {generators: [{key, name, category, category_label, available,
//       optional_deps, params}]}
//   - generate.render（async，§2.3 受理模式）：request =
//       {generator_key, params, width, height}；受理响应 {task_id, status}；
//       task.completed 的 result 携带预览图（§4 大图走临时文件路径 path，
//       内联数据走 data），task.failed 按 §7 呈现错误。
//
// 关联模式与 DocumentService / FilterService 同款 tracked dispatch：每个
// Q_INVOKABLE 在 sendAction 时把 request_id 记入 m_pendingByRequest，受理响应
// 按 request_id 取回上下文并迁移到 m_pendingByTask（事件只携带 task_id，
// document_service.cpp:287-290 同款）；未跟踪帧（worker.hello、image.*、
// filter.*、batch.*）一律忽略——那些动作的关联归各自服务，本服务绝不越权
// 认领。渲染无"单一活动任务"语义：多次渲染各自按 task_id 关联，完成各发
// notifyPreviewReady（预览图之间互不覆盖状态）。
class StudioService : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    // 由本服务创建并持有（FilterService::filterModel 同款，CONSTANT：实例与
    // 进程同寿命，指针身份不变）。
    Q_PROPERTY(GeneratorModel *generatorModel READ generatorModel CONSTANT)
    // generate.list 在途（loadGenerators 发出 → 响应落定）；未绑定后端时恒
    // false（FilterService::loadingFilters 同款，filter_service.h:47-48）。
    Q_PROPERTY(bool loadingGenerators READ loadingGenerators NOTIFY loadingGeneratorsChanged)

  public:
    explicit StudioService(QObject *parent = nullptr);
    ~StudioService() override;

    // Process-wide instance getter + QML singleton factory，与 FilterService
    // （filter_service.h:54-57）同款：QML 查找与 C++ 接线必须拿到同一对象。
    static StudioService *instance();
    static StudioService *create(QQmlEngine *qmlEngine, QJSEngine *jsEngine);

    GeneratorModel *generatorModel() const { return m_generatorModel; }
    bool loadingGenerators() const { return m_loadingGenerators; }

    // DocumentService::bindBackend 同款（document_service.cpp:38-46）：QML 侧
    // StudioService.bindBackend(Application.backend) 完成接线；幂等重绑无害。
    Q_INVOKABLE void bindBackend(BackendManager *backend);

    // TaskModel 注入（DocumentService::bindTaskModel 同款，
    // document_service.cpp:48-50）：render 受理的异步任务经 TaskModel::
    // trackRequest 登记任务行（显示名"生成渲染"），任务抽屉/行内取消因此
    // 可见（总纲：各 Studio 共享任务组件）。不绑定时渲染照常提交，只是
    // 不出现在任务队列——行为回到无任务行。
    Q_INVOKABLE void bindTaskModel(TaskModel *taskModel);

    // generate.list（sync）：成功响应经 generatorModel->reloadFrom 落地；成败
    // 都收 loadingGenerators（false）。后端未绑定时只发 studioError(INTERNAL)。
    Q_INVOKABLE void loadGenerators();

    // generate.render（async，§2.3）：paramsJson 为参数值对象的 JSON 文本
    //（如 {"seed":42,...}，与 generatorModel 的 paramsJson 角色——参数"定义"
    // 数组——是两种形状；本参数是 UI 装配后的"值"），空/纯空白按 {} 上送，
    // 解析失败/非对象在本地拒绝（INVALID_PARAMS，不上送）。width/height 必须
    // > 0，否则本地拒绝。
    //
    // 返回值为提交关联号 request_id（空 = 本地拒绝，未上送）。协议受理是异步
    // 的（§2.3：task_id 只随响应到达——batch_service.h:68-71 对 startBatch 的
    // 同一约束原文），无法同步返回 task_id——Worker 受理后的真实 task_id 经
    // renderAccepted(taskId) 交付；预览图路径/数据经 notifyPreviewReady(imagePath)
    // 交付。
    Q_INVOKABLE QString render(const QString &generatorKey, const QString &paramsJson, int width,
                               int height);

    // 导出到编辑器：imagePath 委托 DocumentService::openDocument（image.open，
    // sync）——打开成败与文档状态（currentDocumentId/version/modified）归文档
    // 层，经 documentOpened/documentError 交付，不经本服务转述（FilterService
    // 委托链的同一通道分离，filter_service.cpp:123-129）。空路径本地拒绝。
    Q_INVOKABLE void exportToEditor(const QString &imagePath);

  signals:
    // code/message 见 docs/ipc-protocol.md §5（含未绑定后端的 INTERNAL、本地
    // 参数拒绝的 INVALID_PARAMS、同步拒绝、task.failed 与协议违约）。纯用户
    // 呈现（Toast）；文档层错误不经本信号（见 exportToEditor）。
    void studioError(const QString &code, const QString &message);

    // 受理响应落地（result.task_id）——task_id 的唯一交付路径（§2.3，
    // BatchService::batchStarted 同款）。
    void renderAccepted(const QString &taskId);

    // generate.render 完成（task.completed）：预览图交付。imagePath 优先取
    // result.path（§4 临时文件路径，QML Image 可直载）；Worker 内联返回时取
    // result.data（base64/data-URL 文本，QML Image 同样可直载）——路径与数据
    // 两种形状按协议择一交付，二者皆缺视为协议违约（INTERNAL，不发射本信号）。
    void notifyPreviewReady(const QString &imagePath);

    void loadingGeneratorsChanged();

  private slots:
    void onResponseReady(const QString &requestId, const QJsonObject &message);
    void onTaskEvent(const QJsonObject &event);

  private:
    enum class PendingKind { GeneratorList, Render };

    struct Pending {
        PendingKind kind = PendingKind::GeneratorList;
    };

    // 同步动作发送（generate.list）与异步提交（generate.render）共用：未绑定
    // 后端发 studioError(INTERNAL) 并返回空 id（FilterService::sendTracked
    // 同款，filter_service.cpp:48-62）。
    QString sendTracked(PendingKind kind, const QString &action, const QJsonObject &params);

    void setLoadingGenerators(bool loading);

    BackendManager *m_backend = nullptr;
    GeneratorModel *m_generatorModel = nullptr; // 本服务创建并持有
    TaskModel *m_taskModel = nullptr;
    QHash<QString, Pending> m_pendingByRequest; // request_id → 提交上下文
    QHash<QString, Pending> m_pendingByTask;    // task_id → 提交上下文（渲染完成）
    bool m_loadingGenerators = false;
};

} // namespace toolbox
