import Toolbox
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 滤镜参数面板（ui-component-spec.md §3 AppFilterParameterGroup）：输入
// FilterDef 参数定义 JSON（FilterModel 的 paramsJson 角色——filter.list 的
// params 数组紧凑文本，形状见 python_worker/adapters/filter_adapter.py
// _param_to_dict：name/label/type/default/minimum/maximum/step/choices/
// description），按 type 自动生成控件：
//   float → AppSliderField / int → AppNumberField / bool → AppToggleField /
//   enum → AppSelectField / color → AppColorField / string → AppTextField
//
// 输出与协议 filter.preview/apply 的 params 语义一致（docs/ipc-protocol.md
// §3；Worker 端 FilterDef.validate_params 会把缺省键合并为 FilterDef 默认值，
// processors/filter_defs.py）——currentParams() 返回全部已声明参数（键=param
// name），未改动的键取 default，即"整表发送、Worker 兜底合并"。
// currentParams() 在 QML 中以根对象函数声明（QML 函数对 C++
// QMetaObject::invokeMethod 可调，即 Q_INVOKABLE 等价物）；filter.* 的实际
// 组包在 FilterService（链步骤 addStep 时快照），本组件不做任何 sendAction。
//
// 值的存储纪律：values（name → 当前值）始终保存协议形状的 JS 类型（number/
// boolean/string；color 存 "#rrggbb" 十六进制文本，_validate_color 接受），
// 控件在 current()/applyValue() 边界做类型转换。用户编辑经 commitValue 落入
// values 并发 paramsChanged()；程序化写入（rebuild/reset/applyValue）不触发。
Column {
    id: root

    // FilterDef 参数定义数组 JSON 文本（FilterModel::roleNames ParamsJsonRole）。
    property string paramsJson: ""

    // 解析后的定义数组（readonly 语义，rebuild 以整体赋值驱动重建）。
    property var definitions: []

    // name → 当前值（协议形状）。成员级写入不通知（无需通知：控件自身持有
    // 显示状态）；整体重赋值仅在 rebuild/reset 时发生。
    property var values: ({})

    // 任意用户编辑后发射（ui-component-spec.md §3：任意变更 → paramsChanged）。
    signal paramsChanged()

    readonly property bool hasParameters: root.definitions.length > 0

    spacing: Theme.spacingMd

    onParamsJsonChanged: root.rebuild()
    Component.onCompleted: root.rebuild()

    // ---- 数据整形 ------------------------------------------------------------
    // 畸形 JSON / 非数组：清空面板不抛错（FilterModel::reloadFrom 同款宽容纪律）。
    function rebuild() {
        let defs = [];
        try {
            const parsed = JSON.parse(root.paramsJson);
            if (Array.isArray(parsed))
                defs = parsed;
        } catch (e) {
            defs = [];
        }
        const seeded = {};
        for (let i = 0; i < defs.length; ++i) {
            const def = defs[i];
            if (!def || typeof def.name !== "string" || def.name === "")
                continue;
            if (!root.isSupportedType(def.type))
                continue;  // 未知类型不进 values → currentParams 交给 Worker 默认值
            seeded[def.name] = root.normalizeDefault(def);
        }
        root.values = seeded;      // 先 values：委托创建时读取种子
        root.definitions = defs;   // 再 definitions：Repeater 重建委托
    }

    function isSupportedType(type) {
        return type === "float" || type === "int" || type === "bool"
               || type === "enum" || type === "color" || type === "string";
    }

    // default 的协议形状归一（FilterParam.__post_init__ 的缺省纪律一致：bool
    // 缺省 false、int 缺省 0、float 缺省 0.0）。
    function normalizeDefault(def) {
        if (!def)
            return undefined;
        switch (String(def.type)) {
        case "float": {
            const n = Number(def.default);
            return Number.isFinite(n) ? n : 0.0;
        }
        case "int": {
            const n = Math.round(Number(def.default));
            return Number.isFinite(n) ? n : 0;
        }
        case "bool":
            return def.default === true;
        case "enum":
            return String(def.default !== undefined && def.default !== null ? def.default : "");
        case "color":
            return root.colorToHex(def.default);
        case "string":
            return def.default !== undefined && def.default !== null ? String(def.default) : "";
        default:
            return undefined;
        }
    }

    // color 协议形状：十六进制文本（Worker _validate_color 接受
    // #RGB/#RRGGBB/#RRGGBBAA 与 [r,g,b] 数组；UI 统一发 #RRGGBB）。
    function colorToHex(defaultValue) {
        if (typeof defaultValue === "string" && defaultValue.charAt(0) === "#") {
            const parsed = Qt.color(defaultValue);
            return root.hexOf(parsed);
        }
        if (Array.isArray(defaultValue) && defaultValue.length >= 3) {
            return root.hexOf(Qt.rgba(Number(defaultValue[0]) / 255,
                                      Number(defaultValue[1]) / 255,
                                      Number(defaultValue[2]) / 255, 1));
        }
        return "#ffffff";  // 畸形默认值：白色兜底（不谎称解析成功）
    }

    function hexOf(c) {
        const hex2 = (v) => Math.round(v * 255).toString(16).padStart(2, "0");
        return "#" + hex2(c.r) + hex2(c.g) + hex2(c.b);
    }

    // float/int 的数值边界（minimum/maximum 为 null 时 UI 侧兜底范围：default
    // ±10——校验权在 Worker，这只是滑杆/步进器的可操作区间）。
    // def 尚未注入（Loader 创建瞬间）时给出中性兜底，避免绑定期异常。
    function boundMin(def) {
        if (!def)
            return -10;
        if (def.minimum !== null && def.minimum !== undefined) {
            const n = Number(def.minimum);
            if (Number.isFinite(n))
                return n;
        }
        const d = Number(def.default);
        return Number.isFinite(d) ? d - 10 : -10;
    }

    function boundMax(def) {
        if (!def)
            return 10;
        if (def.maximum !== null && def.maximum !== undefined) {
            const n = Number(def.maximum);
            if (Number.isFinite(n))
                return n;
        }
        const d = Number(def.default);
        return Number.isFinite(d) ? d + 10 : 10;
    }

    // step 兜底：非法/缺省时 float 取 0.01、int 取 1（Worker 对推导参数的
    // 习惯步长，filter_defs.py _infer_params_from_signature）。
    function stepOf(def) {
        if (!def)
            return 1;
        const s = Number(def.step);
        if (Number.isFinite(s) && s > 0)
            return s;
        return String(def.type) === "int" ? 1 : 0.01;
    }

    // enum choices 两种形状（FilterParam.choices：list[str] | dict[str, Any]）：
    // list → 值即标签；dict → 键为合法值、值为标签（非字符串值回落键名）。
    function enumValueList(def) {
        if (!def)
            return [];
        const c = def.choices;
        if (Array.isArray(c))
            return c.map(String);
        if (c && typeof c === "object")
            return Object.keys(c);
        return [];
    }

    function enumLabelList(def) {
        if (!def)
            return [];
        const c = def.choices;
        if (Array.isArray(c))
            return c.map(String);
        if (c && typeof c === "object") {
            return Object.keys(c).map((k) => typeof c[k] === "string" ? c[k] : k);
        }
        return [];
    }

    // ---- 读写通道 --------------------------------------------------------------
    // 用户编辑：写入 values（成员级，无通知）+ paramsChanged。只收协议形状值。
    function commitValue(name, value) {
        root.values[name] = value;
        root.paramsChanged();
    }

    function initialValue(def) {
        const v = root.values[def.name];
        return v !== undefined ? v : root.normalizeDefault(def);
    }

    // Q_INVOKABLE 等价（见文件头注释）：键=param name，值=当前值（未改动的
    // 键为 default）。未知类型跳过——Worker 端 validate_params 以 FilterDef
    // 默认值合并补齐，缺键等价于默认。
    function currentParams() {
        const out = {};
        for (let i = 0; i < root.definitions.length; ++i) {
            const def = root.definitions[i];
            const type = String(def.type);
            if (!root.isSupportedType(type) || typeof def.name !== "string")
                continue;
            let v = root.values[def.name];
            if (v === undefined)
                v = root.normalizeDefault(def);
            // 类型安全网：控件边界已转换，这里再按协议形状钳一次。
            switch (type) {
            case "float": {
                const n = Number(v);
                out[def.name] = Number.isFinite(n) ? n : 0.0;
                break;
            }
            case "int": {
                const n = Math.round(Number(v));
                out[def.name] = Number.isFinite(n) ? n : 0;
                break;
            }
            case "bool":
                out[def.name] = v === true;
                break;
            case "enum":
            case "string":
                out[def.name] = String(v);
                break;
            case "color":
                out[def.name] = typeof v === "string" && v.charAt(0) === "#"
                        ? v : root.colorToHex(v);
                break;
            }
        }
        return out;
    }

    // 全部参数回 default（控件一并复位）。
    function reset() {
        const seeded = {};
        for (let i = 0; i < root.definitions.length; ++i) {
            const def = root.definitions[i];
            if (root.isSupportedType(def.type))
                seeded[def.name] = root.normalizeDefault(def);
        }
        root.values = seeded;
        for (let i = 0; i < paramRepeater.count; ++i) {
            const row = paramRepeater.itemAt(i);
            if (row && seeded[row.def.name] !== undefined)
                row.applyValue(seeded[row.def.name]);
        }
        root.paramsChanged();
    }

    // ---- 控件生成 --------------------------------------------------------------
    Repeater {
        id: paramRepeater
        model: root.definitions

        delegate: Column {
            id: paramRow

            required property int index
            required property var modelData
            readonly property var def: modelData
            readonly property bool supported: root.isSupportedType(String(def.type))

            width: root.width
            spacing: Theme.spacingXs

            function applyValue(v) {
                if (paramLoader.item)
                    paramLoader.item.applyValue(v);
            }

            // 类型无内建标签的（slider 自带 label 行、toggle 文本即标签）
            // 不再补一行。
            readonly property bool needsLabel: paramRow.supported
                                               && String(paramRow.def.type) !== "float"
                                               && String(paramRow.def.type) !== "bool"

            Label {
                visible: paramRow.needsLabel
                width: parent.width
                text: paramRow.needsLabel ? String(paramRow.def.label) : ""
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textSecondary
                elide: Text.ElideRight
            }

            // 未知类型：如实呈现，不生成控件也不进 currentParams（Worker 端
            // 以 FilterDef 默认值合并，缺键等价于默认）。
            Label {
                visible: !paramRow.supported
                width: parent.width
                text: qsTr("暂不支持的参数类型：%1（将以默认值提交）")
                      .arg(String(paramRow.def.type))
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.textDisabled
                wrapMode: Text.WordWrap
            }

            Loader {
                id: paramLoader
                width: parent.width
                visible: paramRow.supported
                active: paramRow.supported
                sourceComponent: {
                    switch (String(paramRow.def.type)) {
                    case "float": return floatComponent;
                    case "int": return intComponent;
                    case "bool": return boolComponent;
                    case "enum": return enumComponent;
                    case "color": return colorComponent;
                    case "string": return stringComponent;
                    default: return null;
                    }
                }
                onLoaded: item.setup(paramRow.def, root.initialValue(paramRow.def))
            }
        }
    }

    // ---- 六种类型的控件模板 ----------------------------------------------------
    // 统一接口：setup(def, initialValue) / current()（协议形状）/ applyValue(v)。
    // 编辑统一走 root.commitValue(def.name, current())。

    Component {
        id: floatComponent

        AppSliderField {
            id: floatField

            property var def: null

            width: parent.width

            readonly property real lo: root.boundMin(def)
            readonly property real hi:
                Math.max(root.boundMax(def), lo + Math.max(root.stepOf(def), 0.01))

            label: def ? String(def.label) : ""
            from: lo
            to: hi
            step: root.stepOf(def)
            defaultValue: def ? Number(root.normalizeDefault(def)) : 0
            onValueModified: root.commitValue(def.name, floatField.current())

            function setup(defObject, initialValue) {
                floatField.def = defObject;
                floatField.applyValue(initialValue);
            }

            function current() {
                const n = Number(floatField.value);
                return Number.isFinite(n) ? n : 0.0;
            }

            function applyValue(v) {
                const n = Number(v);
                floatField.value = Number.isFinite(n) ? n : floatField.defaultValue;
            }
        }
    }

    Component {
        id: intComponent

        Column {
            id: intRow

            property var def: null

            width: parent.width
            spacing: Theme.spacingXs

            function setup(defObject, initialValue) {
                intRow.def = defObject;
                intRow.applyValue(initialValue);
            }

            function current() {
                const n = Math.round(Number(intField.value));
                return Number.isFinite(n) ? n : 0;
            }

            function applyValue(v) {
                const n = Math.round(Number(v));
                intField.value = Number.isFinite(n) ? n : Math.round(Number(root.normalizeDefault(intRow.def)));
            }

            readonly property real lo: root.boundMin(def)
            readonly property real hi:
                Math.max(root.boundMax(def), lo + Math.max(root.stepOf(def), 1))

            AppNumberField {
                id: intField
                width: parent.width
                from: intRow.lo
                to: intRow.hi
                step: Math.max(1, Math.round(root.stepOf(intRow.def)))
                decimals: 0
                onValueModified: root.commitValue(intRow.def.name, intRow.current())
            }
        }
    }

    Component {
        id: boolComponent

        AppToggleField {
            id: boolField

            property var def: null

            width: parent.width
            text: def ? String(def.label) : ""

            function setup(defObject, initialValue) {
                boolField.def = defObject;
                boolField.applyValue(initialValue);
            }

            function current() {
                return boolField.checked;
            }

            function applyValue(v) {
                boolField.checked = v === true;
            }

            onToggled: root.commitValue(boolField.def.name, boolField.current())
        }
    }

    Component {
        id: enumComponent

        Column {
            id: enumRow

            property var def: null
            property var valueList: []
            property var labelList: []

            width: parent.width
            spacing: Theme.spacingXs

            function setup(defObject, initialValue) {
                enumRow.def = defObject;
                enumRow.valueList = root.enumValueList(defObject);
                enumRow.labelList = root.enumLabelList(defObject);
                enumRow.applyValue(initialValue);
            }

            function current() {
                if (enumSelect.currentIndex >= 0
                        && enumSelect.currentIndex < enumRow.valueList.length)
                    return enumRow.valueList[enumSelect.currentIndex];
                return String(root.normalizeDefault(enumRow.def));
            }

            function applyValue(v) {
                // 值不在 choices 时 currentIndex = -1（显示为空，由用户重选；
                // current() 回落 default——不伪造选中态）。
                enumSelect.currentIndex = enumRow.valueList.indexOf(String(v));
            }

            AppSelectField {
                id: enumSelect
                width: parent.width
                model: enumRow.labelList
                onActivated: (index) => {
                    if (index >= 0 && index < enumRow.valueList.length)
                        root.commitValue(enumRow.def.name, enumRow.valueList[index]);
                }
            }
        }
    }

    Component {
        id: colorComponent

        Column {
            id: colorRow

            property var def: null

            width: parent.width
            spacing: Theme.spacingXs

            function setup(defObject, initialValue) {
                colorRow.def = defObject;
                colorRow.applyValue(initialValue);
            }

            function current() {
                return root.hexOf(colorField.value);
            }

            function applyValue(v) {
                if (typeof v === "string" && v.charAt(0) === "#") {
                    colorField.value = Qt.color(v);
                    return;
                }
                colorField.value = Qt.color(root.colorToHex(v));
            }

            AppColorField {
                id: colorField
                width: parent.width
                onValueModified: root.commitValue(colorRow.def.name, colorRow.current())
            }
        }
    }

    Component {
        id: stringComponent

        Column {
            id: stringRow

            property var def: null

            width: parent.width
            spacing: Theme.spacingXs

            function setup(defObject, initialValue) {
                stringRow.def = defObject;
                stringRow.applyValue(initialValue);
            }

            function current() {
                return String(textField.text);
            }

            function applyValue(v) {
                textField.text = String(v);
            }

            AppTextField {
                id: textField
                width: parent.width
                onTextEdited: root.commitValue(stringRow.def.name, stringRow.current())
            }
        }
    }
}
