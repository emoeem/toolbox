"""批处理协议化：batch.start / batch.cancel（docs/ipc-protocol.md §3.5）。

复用 1.0 资产，不重写：
- `processors/batch_filter_chain.py` `run_batch_filter_chain`：逐文件
  load → 链 → save 与逐项成功/失败/取消记账（本批仅为其补 quality /
  output_name_fn 两个可选参数，缺省行为不变）。
- `processors/batch.py` `batch_rename` 的 pattern 占位符语义
  （{name}/{ext}/{i}/{index}，start=1、padding=3）。
- `processors/utils.py` `SUPPORTED_READ` / `SUPPORTED_WRITE` / `save_image`。
- 取消走 TaskRuntime 的 CancelToken（`processors/cancellation.py`），任务体
  返回后 `raise_if_cancelled()` 归一为 task.failed(CANCELLED)（§7）。

1.0 批量面板（app/main_window.py `_run_batch`）的扫描/命名/转换/链处理循环
由此协议化：可在提交前判定的错误（参数形状、路径不存在、链非法）在
`build_batch_plan` 同步抛出 WorkerError，不产生 task_id（先例同
filter.preview 的链校验）。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from processors.batch_filter_chain import run_batch_filter_chain
from processors.filter_chain import FilterChain, FilterStep
from processors.utils import SUPPORTED_READ, SUPPORTED_WRITE

from .image_adapter import WorkerError

# naming 三态（§3.5）；suffix 固定标签与 pattern 序号规则取自 batch_rename 缺省。
NAMING_MODES = ('keep', 'suffix', 'pattern')
SUFFIX_TAG = '_batch'
PATTERN_PADDING = 3
PATTERN_START = 1


@dataclass
class BatchPlan:
    """提交前同步校验的产物；任务体只执行，不再做参数判定。"""
    files: list[Path]
    chain: FilterChain
    output_dir: str
    out_ext: str  # 含点，JPEG 已规范化为 .jpg（§3.5）
    quality: int | None
    name_fn: Callable[[Path, int], str]


def build_batch_plan(params: dict) -> BatchPlan:
    """batch.start 参数校验 + 输入扫描 + 链构造（提交前同步，§3.5）。"""
    if not isinstance(params, dict):
        raise WorkerError('INVALID_PARAMS', 'params 必须是对象')
    files = scan_inputs(params.get('paths'))
    out_dir = params.get('output_dir')
    if not isinstance(out_dir, str) or not out_dir.strip():
        raise WorkerError('INVALID_PARAMS', '缺少 output_dir')
    out_ext = _validate_format(params.get('format'))
    quality = _validate_quality(params.get('quality'))
    naming, pattern = _validate_naming(params.get('naming'), params.get('pattern'))
    chain = _build_chain(params.get('steps'))
    return BatchPlan(files=files, chain=chain, output_dir=out_dir,
                     out_ext=out_ext, quality=quality,
                     name_fn=_make_output_name(naming, pattern, out_ext))


def scan_inputs(raw_paths: Any) -> list[Path]:
    """paths 展开：目录递归扫描，仅 SUPPORTED_READ 扩展名入批；去重 + 排序。

    不存在的路径 → FILE_NOT_FOUND；展开后无可处理文件 → FILE_NOT_FOUND
    （§3.5，提交前同步返回）。
    """
    if not isinstance(raw_paths, list) or not raw_paths:
        raise WorkerError('INVALID_PARAMS', 'paths 必须是非空数组')
    files: list[Path] = []
    seen: set[str] = set()
    for i, raw in enumerate(raw_paths):
        if not isinstance(raw, str) or not raw.strip():
            raise WorkerError('INVALID_PARAMS', f'paths[{i}] 必须是非空字符串路径')
        path = Path(raw)
        if not path.exists():
            raise WorkerError('FILE_NOT_FOUND', f'路径不存在: {path}')
        if path.is_dir():
            candidates = (f for f in path.rglob('*')
                          if f.is_file() and f.suffix.lower() in SUPPORTED_READ)
        else:
            # 显式给出的文件与目录内文件同规则：受支持扩展名才纳入。
            candidates = [path] if path.suffix.lower() in SUPPORTED_READ else []
        for f in candidates:
            key = str(f.resolve()).lower()  # Windows 大小写不敏感去重
            if key in seen:
                continue
            seen.add(key)
            files.append(f)
    if not files:
        raise WorkerError('FILE_NOT_FOUND', '输入中没有可处理的图片文件')
    files.sort(key=lambda f: str(f).lower())
    return files


# BatchItemStatus.value → 协议 state（§3.5：done/failed 与 native 侧
# BatchModel 的行状态词汇一致；cancelled/pending 只会出现在不可能随
# task.completed 交付的对账场景，如实映射不虚构）。
_ITEM_STATE = {'succeeded': 'done', 'failed': 'failed', 'cancelled': 'cancelled',
               'pending': 'pending', 'running': 'running'}


def run_batch_plan(plan: BatchPlan, progress_cb: Callable[..., None],
                   cancel_token) -> dict[str, Any]:
    """任务体：run_batch_filter_chain 逐项执行 + 批处理进度字段（§3.5）。

    进度帧为**逐文件帧**（§3.5）：`file` 行键 + 该条目 `state/progress/
    output_path`，同时携带整批聚合字段 `done/total/current`。条目在自身终态
    时发出（run_batch_filter_chain 的 finally 回调）；被取消条目不发帧——
    其呈现归 task.failed(CANCELLED) 与 C++ 侧清扫（native/models/
    batch_model.cpp markActiveAs → skipped）。节流（§7）可能丢弃部分帧，
    终态以 task.completed 的 `items` 全量对账补齐。

    逐项失败不中断批处理（run_batch_filter_chain 记账）；取消经
    run_batch_filter_chain 的 CancelToken 检查点停止剩余项，返回后在此统一
    raise_if_cancelled，由 TaskRuntime 归一为 task.failed(CANCELLED)（§7）。
    """
    files = plan.files
    total = len(files)
    out_dir = Path(plan.output_dir)

    def _progress(done: int, _total: int, status: str) -> None:
        if status not in ('succeeded', 'failed'):
            return  # cancelled：不发帧（呈现归 task.failed + C++ 清扫）
        source = files[done - 1]
        frame: dict[str, Any] = {
            # 聚合字段（§3.5 请求的字段集；current 即最近状态变更的源文件）。
            'done': done, 'total': total, 'current': str(source),
            # 逐文件字段（C++ BatchModel 行键与行状态）。
            'file': str(source), 'state': _ITEM_STATE[status], 'progress': 100,
        }
        if status == 'succeeded':
            # 与 run_batch_filter_chain 落盘同名同径（同一 name_fn/目录）。
            frame['output_path'] = str(out_dir / plan.name_fn(source, done - 1))
        progress_cb(int(done * 100 // max(1, total)), status, frame)

    result = run_batch_filter_chain(
        files, plan.chain,
        output_dir=plan.output_dir,
        output_format=plan.out_ext.lstrip('.').upper(),
        progress_cb=_progress,
        cancel_token=cancel_token,
        overwrite=True,  # §3.5：输出同名覆盖（与 1.0 批量面板缺省一致）
        quality=plan.quality,
        output_name_fn=plan.name_fn,
    )
    cancel_token.raise_if_cancelled()
    items: list[dict[str, Any]] = []
    for item in result.items:
        entry: dict[str, Any] = {'file': str(item.source),
                                 'state': _ITEM_STATE[item.status.value]}
        if item.error:
            entry['error'] = item.error
        if item.output is not None:
            entry['output_path'] = str(item.output)
        items.append(entry)
    return {
        'total': result.total,
        'done': result.succeeded + result.failed,
        'succeeded': result.succeeded,
        'failed': result.failed,
        'current': '',
        'state': 'done',
        'output_dir': str(out_dir.resolve()),
        # 全量对账（§3.5）：补齐被节流丢弃的逐文件帧终态。
        'items': items,
    }


def _validate_format(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise WorkerError('INVALID_PARAMS', 'format 必须是非空字符串')
    ext = '.' + raw.strip().lower().replace('jpeg', 'jpg')
    if ext not in SUPPORTED_WRITE:
        raise WorkerError('INVALID_PARAMS', f'不支持的输出格式: {raw}')
    return ext


def _validate_quality(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not float(raw).is_integer():
        raise WorkerError('INVALID_PARAMS', 'quality 必须是整数')
    quality = int(raw)
    if not 1 <= quality <= 100:
        raise WorkerError('INVALID_PARAMS', 'quality 必须在 1-100 之间')
    return quality


def _validate_naming(raw_naming: Any, raw_pattern: Any) -> tuple[str, str | None]:
    naming = raw_naming if raw_naming is not None else 'keep'
    if not isinstance(naming, str) or naming not in NAMING_MODES:
        raise WorkerError('INVALID_PARAMS', 'naming 必须是 keep / suffix / pattern 之一')
    if naming != 'pattern':
        return naming, None
    if not isinstance(raw_pattern, str) or not raw_pattern.strip():
        raise WorkerError('INVALID_PARAMS', 'naming=pattern 时必须提供非空 pattern')
    try:
        # 占位符拼写在提交前同步校验（format 键错误此时报 INVALID_PARAMS）。
        raw_pattern.format(name='n', ext='.png', i='001', index='001')
    except (KeyError, IndexError, ValueError) as exc:
        raise WorkerError('INVALID_PARAMS', f'pattern 非法: {exc}') from exc
    return naming, raw_pattern


def _make_output_name(naming: str, pattern: str | None,
                      out_ext: str) -> Callable[[Path, int], str]:
    if naming == 'keep':
        # 1.0 既有命名：源文件名 + 输出扩展名（batch_filter_chain.py 缺省分支同款）。
        return lambda src, _i: src.stem + out_ext
    if naming == 'suffix':
        return lambda src, _i: src.stem + SUFFIX_TAG + out_ext

    def _pattern_name(src: Path, index: int) -> str:
        seq = str(PATTERN_START + index).zfill(PATTERN_PADDING)
        name = pattern.format(name=src.stem, ext=out_ext, i=seq, index=seq)
        if not name.endswith(out_ext):
            name += out_ext
        return name

    return _pattern_name


def _build_chain(raw_steps: Any) -> FilterChain:
    """steps → FilterChain（协议 §3.5）。校验同 filter.preview 的 filters
    （FilterStep.from_dict + validate_all），错误消息带 steps 下标；steps
    缺省/空 = 纯格式转换（空链）。"""
    if raw_steps is None:
        raw_steps = []
    if not isinstance(raw_steps, list):
        raise WorkerError('INVALID_PARAMS', 'steps 必须是数组')
    chain = FilterChain()
    for i, raw in enumerate(raw_steps):
        try:
            chain.add_step(FilterStep.from_dict(raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkerError('INVALID_PARAMS', f'steps[{i}]: {exc}') from exc
    ok, errors = chain.validate_all()
    if not ok:
        raise WorkerError('INVALID_PARAMS', '; '.join(errors))
    return chain
