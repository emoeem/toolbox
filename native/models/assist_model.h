#pragma once

#include <QAbstractListModel>
#include <QJsonObject>
#include <QStringList>
#include <QVariant>
#include <QVector>
#include <QtQml/qqml.h>

namespace toolbox {

// 辅助工具目录行（docs/ipc-protocol.md §3.8 assist.list，Phase 7 增补；总纲
// §9.9 "工具箱与辅助页面" 的数据源）。数据由 AssistService 从 assist.list 的
// 同步响应经 reloadFrom() 填入：result = {tools: [{key, name, category,
// category_label, description, type, available, optional_deps}]}——形状与
// §3 filter.list / generate.list 同构（目录类同步动作的既有词汇）。Python
// 侧实现于 python_worker/adapters/assist_adapter.py（list_tools），Worker 测
// 试锁为 tests/test_worker_assist.py。
//
// 角色面取任务清单指定的五个字段；协议面保留的 description（工具说明）与
// type（sync|async）不进角色（GeneratorModel 对 description 的同一处置，
// docs/ipc-protocol.md §3.7 Phase 6C 复查注），消费方忽略未知字段（§2.3）。
//
// 协议注记（key 的双重身份，§3.8 "条目 key 即动作名"）：条目 key 同时是该
// 工具的运行动作名——AssistService::runTool 原样以 key 上送 sendAction；
// sync/async 由 Worker 端按动作注册决定（§2.3：受理响应是否携带 task_id；
// 目录 type 字段为 QML 呈现参考，本模型不消费）。因此无 key 的条目既无法
// 显示定位、也无法运行，模型层防御性跳过（FilterModel / GeneratorModel
// 同款）。
//
// 模型自身不连 BackendManager：填充入口只有 reloadFrom（FilterModel::
// reloadFrom 同款模式，filter_model.cpp:10-40），空对象/缺 tools 字段视为
// 清空，不抛错。available 由 Worker 端依赖探测如实给出（§3.8：模块/外部
// 二进制/模型文件缺失 → false + optional_deps 列出缺失名）；缺失的
// available 按不可用处理——宁可置灰，不谎称可用（总纲 Phase 7："缺少模型
// 或二进制时不得显示虚假的可用状态"）。
class AssistModel : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT

  public:
    struct Entry {
        QString key;           // 协议字段 key（= 该工具的运行动作名）
        QString name;          // 协议字段 name（显示名，"title"）
        QString categoryLabel; // 协议字段 category_label（缺省回落 category 原值）
        bool available = false; // 协议字段 available（缺可选依赖/模型时 false → 置灰）
        QStringList optionalDeps; // 协议字段 optional_deps（置灰原因，如 "tesseract"）
    };

    enum Roles {
        ToolKeyRole = Qt::UserRole + 1,
        ToolNameRole,
        CategoryLabelRole,
        AvailableRole,
        OptionalDepsRole,
    };

    explicit AssistModel(QObject *parent = nullptr);

    // 整表重建（beginResetModel）：以最近一次 assist.list 结果为准；缺失的
    // available 按不可用处理（宁可置灰，不谎称可用）。
    Q_INVOKABLE void reloadFrom(const QJsonObject &assistListResult);

    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

  private:
    QVector<Entry> m_entries;
};

} // namespace toolbox
