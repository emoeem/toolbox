"""batch.start / batch.cancel / gmic.check 动作测试（docs/ipc-protocol.md §3.5/§3.6）。

参照 tests/test_worker_edit.py 的进程内风格（不启动 QProcess，CI 直接执行）：
Dispatcher + TaskRuntime(max_workers=1, emitter=...)，轮询事件列表等待终态。
图片由 PIL 现场生成小图，不依赖 tests/fixtures；gmic.check 用 mock 模拟
"无 gmic 环境"（patch available + sys.modules['gmic']=None），不要求 CI 机器
真的装/不装 G'MIC。
"""
from __future__ import annotations

import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import processors  # noqa: F401  触发滤镜注册（FilterDefRegistry 填充）
import processors.gmic as gmic_processor
from processors.filter_defs import FilterDefRegistry
from processors.utils import load_image
from python_worker import task_runtime
from python_worker.dispatcher import Dispatcher, WorkerContext
from python_worker.protocol import PROTOCOL_VERSION


def _request(action: str, params: dict | None = None, request_id: str = 'req-b') -> dict:
    return {'protocol': PROTOCOL_VERSION, 'request_id': request_id,
            'action': action, 'params': params or {}}


def _write_image(path: Path, color=(200, 30, 30), size=(16, 12)) -> Path:
    arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color
    path.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    Image.fromarray(arr, 'RGB').save(path, format='PNG')
    return path


def _registry_keys() -> list[str]:
    keys = FilterDefRegistry.instance().keys()
    assert keys, '滤镜注册表为空——processors 注册异常'
    return keys


def _pick_keys() -> tuple[str, str]:
    """(灰度滤镜, 一个异于它的滤镜)，以注册表实际内容为准，不猜测名字。"""
    keys = _registry_keys()
    key_a = 'grayscale_standard' if 'grayscale_standard' in keys else keys[0]
    # sepia 是彩色滤镜：禁用它后输出仍应为灰度，可证明 disabled 步骤未执行。
    key_b = 'sepia' if 'sepia' in keys and 'sepia' != key_a else next(
        (k for k in keys if k != key_a), key_a)
    return key_a, key_b


class DispatcherBatchTestBase(unittest.TestCase):
    """公共底座：临时目录 + 单线程 TaskRuntime + 事件轮询（同 test_worker_edit）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.events: list[dict] = []
        self.ctx = WorkerContext()
        self.ctx.runtime = task_runtime.TaskRuntime(max_workers=1, emitter=self.events.append)
        self.addCleanup(self.ctx.runtime.shutdown)
        self.dispatcher = Dispatcher(self.ctx)

    def _wait_for_terminal(self, task_id: str, timeout: float = 30.0) -> dict | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for event in self.events:
                if event.get('task_id') == task_id and event.get('type') in (
                        'task.completed', 'task.failed'):
                    return event
            time.sleep(0.02)
        return None

    def _start_batch(self, params: dict) -> dict:
        response = self.dispatcher.handle(_request('batch.start', params))
        self.assertTrue(response['success'], response)
        self.assertIn('task_id', response['result'])
        self.assertIn('total', response['result'])
        return response['result']

    def _run_batch(self, params: dict) -> dict:
        """提交 batch.start 并等待完成，返回 completed 事件的 result。"""
        started = self._start_batch(params)
        event = self._wait_for_terminal(started['task_id'])
        self.assertIsNotNone(event, 'batch 任务未在超时前完成')
        self.assertEqual(event['type'], 'task.completed', event)
        self.assertEqual(event['result']['total'], started['total'])
        return event['result']

    def _task_events(self) -> list[dict]:
        return [e for e in self.events if str(e.get('type', '')).startswith('task')]


class BatchCapabilitiesTests(DispatcherBatchTestBase):
    def test_new_actions_are_registered(self):
        response = self.dispatcher.handle(_request('capabilities.list', {}))
        self.assertTrue(response['success'], response)
        actions = response['result']['actions']
        for name in ('batch.start', 'batch.cancel', 'gmic.check'):
            self.assertIn(name, actions)


class BatchScanTests(DispatcherBatchTestBase):
    """目录扫描计数（§3.5：目录递归、扩展名过滤、去重、缺失路径）。"""

    def _input_tree(self) -> Path:
        _write_image(self.root / 'in' / 'a.png')
        _write_image(self.root / 'in' / 'sub' / 'b.JPG')  # 扩展名大小写不敏感
        _write_image(self.root / 'in' / 'sub' / 'deep' / 'c.png')
        (self.root / 'in' / 'notes.txt').write_text('not an image', encoding='utf-8')
        return self.root / 'in'

    def test_recursive_dir_scan_counts_supported_images(self):
        in_dir = self._input_tree()
        result = self._run_batch({
            'paths': [str(in_dir)],
            'output_dir': str(self.root / 'out'),
            'format': 'PNG',
        })
        self.assertEqual(result['total'], 3)  # a/b/c 计数，notes.txt 不计
        self.assertEqual(result['state'], 'done')
        self.assertEqual(result['succeeded'], 3)
        self.assertEqual(result['failed'], 0)
        outputs = sorted(p.name for p in (self.root / 'out').glob('*'))
        self.assertEqual(outputs, ['a.png', 'b.png', 'c.png'])  # keep 命名：stem+输出扩展名
        # items 全量对账（§3.5）：file 为扫描序（路径排序）源路径，state 均 done。
        expected_files = sorted([str(in_dir / 'a.png'), str(in_dir / 'sub' / 'b.JPG'),
                                 str(in_dir / 'sub' / 'deep' / 'c.png')],
                                key=str.lower)
        self.assertEqual([item['file'] for item in result['items']], expected_files)
        for item in result['items']:
            self.assertEqual(item['state'], 'done')

    def test_dir_and_inner_file_entries_are_counted_once(self):
        in_dir = self._input_tree()
        result = self._run_batch({
            'paths': [str(in_dir / 'a.png'), str(in_dir)],
            'output_dir': str(self.root / 'out'),
            'format': 'PNG',
        })
        self.assertEqual(result['total'], 3)  # 显式文件与目录重复展开只计一次

    def test_missing_input_path_is_file_not_found_without_task(self):
        response = self.dispatcher.handle(_request('batch.start', {
            'paths': [str(self.root / 'nope')],
            'output_dir': str(self.root / 'out'),
            'format': 'PNG',
        }))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], 'FILE_NOT_FOUND')
        self.assertEqual(self._task_events(), [])  # 提交前同步拒绝：不产生任务

    def test_dir_without_images_is_file_not_found(self):
        (self.root / 'empty').mkdir()
        response = self.dispatcher.handle(_request('batch.start', {
            'paths': [str(self.root / 'empty')],
            'output_dir': str(self.root / 'out'),
            'format': 'PNG',
        }))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], 'FILE_NOT_FOUND')
        self.assertIn('没有可处理', response['error']['message'])

    def test_explicit_unsupported_file_is_not_batched(self):
        """显式给出的文件与目录内文件同规则：受支持扩展名才纳入（§3.5）。"""
        doc = self.root / 'doc.txt'
        doc.write_text('not an image', encoding='utf-8')
        response = self.dispatcher.handle(_request('batch.start', {
            'paths': [str(doc)],
            'output_dir': str(self.root / 'out'),
            'format': 'PNG',
        }))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], 'FILE_NOT_FOUND')
        self.assertIn('没有可处理', response['error']['message'])
        self.assertEqual(self._task_events(), [])


class BatchNamingTests(DispatcherBatchTestBase):
    """命名规则（§3.5 keep / suffix / pattern）。"""

    def setUp(self):
        super().setUp()
        self.in_dir = self.root / 'in'
        # 故意乱序创建：扫描按路径排序，pattern 序号依此序（§3.5）。
        _write_image(self.in_dir / 'photo_c.png')
        _write_image(self.in_dir / 'photo_a.png')
        _write_image(self.in_dir / 'photo_b.png')

    def _names(self, out: Path) -> list[str]:
        return sorted(p.name for p in out.glob('*'))

    def test_keep_naming_uses_source_stem_with_target_ext(self):
        out = self.root / 'out'
        result = self._run_batch({'paths': [str(self.in_dir)], 'output_dir': str(out),
                                  'format': 'PNG', 'naming': 'keep'})
        self.assertEqual(result['total'], 3)
        self.assertEqual(self._names(out),
                         ['photo_a.png', 'photo_b.png', 'photo_c.png'])

    def test_jpeg_format_normalizes_to_jpg_extension(self):
        out = self.root / 'out'
        self._run_batch({'paths': [str(self.in_dir)], 'output_dir': str(out),
                         'format': 'JPEG', 'naming': 'keep'})
        self.assertEqual(self._names(out),
                         ['photo_a.jpg', 'photo_b.jpg', 'photo_c.jpg'])
        from PIL import Image
        with Image.open(out / 'photo_a.jpg') as img:
            self.assertEqual(img.format, 'JPEG')

    def test_suffix_naming_appends_tag(self):
        out = self.root / 'out'
        self._run_batch({'paths': [str(self.in_dir)], 'output_dir': str(out),
                         'format': 'PNG', 'naming': 'suffix'})
        self.assertEqual(self._names(out),
                         ['photo_a_batch.png', 'photo_b_batch.png', 'photo_c_batch.png'])

    def test_pattern_naming_follows_batch_rename_placeholders(self):
        out = self.root / 'out'
        self._run_batch({'paths': [str(self.in_dir)], 'output_dir': str(out),
                         'format': 'PNG', 'naming': 'pattern',
                         'pattern': '{name}_{i}{ext}'})
        # batch_rename 语义（processors/batch.py）：{i}=1 起 3 位补零，按扫描序。
        self.assertEqual(self._names(out),
                         ['photo_a_001.png', 'photo_b_002.png', 'photo_c_003.png'])

    def test_pattern_without_target_ext_gets_ext_appended(self):
        out = self.root / 'out'
        self._run_batch({'paths': [str(self.in_dir)], 'output_dir': str(out),
                         'format': 'PNG', 'naming': 'pattern', 'pattern': '{name}_v{i}'})
        self.assertEqual(self._names(out),
                         ['photo_a_v001.png', 'photo_b_v002.png', 'photo_c_v003.png'])

    def test_pattern_naming_without_pattern_is_invalid_params(self):
        response = self.dispatcher.handle(_request('batch.start', {
            'paths': [str(self.in_dir)], 'output_dir': str(self.root / 'out'),
            'format': 'PNG', 'naming': 'pattern'}))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], 'INVALID_PARAMS')
        self.assertEqual(self._task_events(), [])

    def test_unknown_naming_is_invalid_params(self):
        response = self.dispatcher.handle(_request('batch.start', {
            'paths': [str(self.in_dir)], 'output_dir': str(self.root / 'out'),
            'format': 'PNG', 'naming': 'shout'}))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], 'INVALID_PARAMS')


class BatchConversionTests(DispatcherBatchTestBase):
    """纯格式转换（steps 可空，§3.5）与小图滤镜链批处理。"""

    def test_pure_conversion_without_steps(self):
        src = _write_image(self.root / 'in' / 'red.png')
        out_dir = self.root / 'out'
        result = self._run_batch({'paths': [str(src)], 'output_dir': str(out_dir),
                                  'format': 'JPEG', 'quality': 60})
        self.assertEqual(result['done'], 1)
        self.assertEqual(result['succeeded'], 1)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(result['state'], 'done')
        self.assertEqual(result['current'], '')
        self.assertTrue(Path(result['output_dir']).is_dir())
        outputs = list(out_dir.glob('*.jpg'))
        self.assertEqual([p.name for p in outputs], ['red.jpg'])
        self.assertEqual(result['items'][0]['file'], str(src))
        self.assertEqual(result['items'][0]['state'], 'done')
        self.assertEqual(Path(result['items'][0]['output_path']), outputs[0])
        arr = load_image(outputs[0])[..., :3].astype(int)
        self.assertEqual(arr.shape[:2], (12, 16))  # 尺寸不变
        self.assertGreater(arr[..., 0].min(), 150)  # JPEG 有损：只断言主色保持
        self.assertLess(arr[..., 1].max(), 80)
        self.assertLess(arr[..., 2].max(), 80)

    def test_empty_steps_list_is_pure_conversion(self):
        src = _write_image(self.root / 'in' / 'red.png')
        result = self._run_batch({'paths': [str(src)], 'output_dir': str(self.root / 'out'),
                                  'format': 'PNG', 'steps': []})
        self.assertEqual(result['succeeded'], 1)

    def test_filter_chain_batch_grayscales_small_images(self):
        key_a, key_b = _pick_keys()
        self.in_dir = self.root / 'in'
        _write_image(self.in_dir / 'red.png', color=(200, 30, 30))
        _write_image(self.in_dir / 'green.png', color=(30, 200, 30))
        out_dir = self.root / 'out'
        result = self._run_batch({
            'paths': [str(self.in_dir)], 'output_dir': str(out_dir),
            'format': 'PNG',
            'steps': [
                {'filter_key': key_a, 'params': {}, 'enabled': True},
                {'filter_key': key_b, 'params': {}, 'enabled': False},  # 禁用步骤不生效
            ]})
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['succeeded'], 2)
        self.assertEqual(result['failed'], 0)
        for name in ('red.png', 'green.png'):
            arr = load_image(out_dir / name)[..., :3].astype(int)
            if key_a == 'grayscale_standard':
                # 灰度链 + 禁用的彩色步骤：三通道相等（禁用步骤若被误执行会带色）。
                self.assertTrue((arr[..., 0] == arr[..., 1]).all(), name)
                self.assertTrue((arr[..., 1] == arr[..., 2]).all(), name)

    def test_invalid_steps_rejected_synchronously(self):
        src = _write_image(self.root / 'in' / 'red.png')
        base = {'paths': [str(src)], 'output_dir': str(self.root / 'out'), 'format': 'PNG'}
        for steps in ('not-a-list', 42, ['x'], [{'params': {}}],
                      [{'filter_key': 'no_such_filter', 'params': {}}],
                      [{'filter_key': 'grayscale_standard', 'params': 'oops'}]):
            response = self.dispatcher.handle(_request('batch.start', {**base, 'steps': steps}))
            self.assertFalse(response['success'], steps)
            self.assertEqual(response['error']['code'], 'INVALID_PARAMS', steps)
        self.assertEqual(self._task_events(), [])  # 提交前拒绝：无任务

    def test_failed_file_does_not_interrupt_batch(self):
        """单文件失败只记该项 failed，批处理继续（§3.5：解码失败不中断）。"""
        in_dir = self.root / 'in'
        _write_image(in_dir / 'good.png')
        (in_dir / 'broken.png').write_bytes(b'not an image at all')  # 解码必失败
        out_dir = self.root / 'out'
        result = self._run_batch({'paths': [str(in_dir)], 'output_dir': str(out_dir),
                                  'format': 'PNG'})
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['succeeded'], 1)
        self.assertEqual(result['failed'], 1)
        self.assertEqual(result['done'], 2)  # done = succeeded + failed（§3.5）
        failed = [item for item in result['items'] if item['state'] == 'failed']
        done = [item for item in result['items'] if item['state'] == 'done']
        self.assertEqual(len(failed), 1)
        self.assertEqual(len(done), 1)
        self.assertTrue(failed[0]['error'])  # 失败原因如实上送
        self.assertNotIn('output_path', failed[0])  # failed 条目省略 output_path（§3.5）
        self.assertTrue(Path(done[0]['output_path']).is_file())
        # 失败条目同样有逐文件终态帧（state=failed，无 output_path）。
        failed_frames = [e for e in self.events
                         if e.get('type') == 'task.progress' and e.get('state') == 'failed']
        self.assertEqual(len(failed_frames), 1)
        self.assertNotIn('output_path', failed_frames[0])

    def test_lowercase_format_matches_ui_submission(self):
        """format 大小写不敏感是 UI 契约（§3.5）：AppBatchWizard formatValues
        为小写（ui/components/AppBatchWizard.qml formatValues），JPEG 规范化为
        .jpg 扩展名对两种拼写一致。"""
        src = _write_image(self.root / 'in' / 'red.png')
        result = self._run_batch({'paths': [str(src)], 'output_dir': str(self.root / 'out'),
                                  'format': 'jpeg'})
        self.assertEqual(result['succeeded'], 1)
        outputs = list((self.root / 'out').glob('*'))
        self.assertEqual([p.name for p in outputs], ['red.jpg'])
        from PIL import Image
        with Image.open(outputs[0]) as img:
            self.assertEqual(img.format, 'JPEG')

    def test_quality_is_forwarded_to_save_image_and_defaults_to_it(self):
        """quality 透传（§3.5）：显式值转发 save_image(quality=…)；缺省不注入
        quality，由 save_image 自身缺省（JPEG 92）接管。"""
        import processors.batch_filter_chain as bfc
        src = _write_image(self.root / 'in' / 'red.png')
        seen: list[dict] = []
        real_save = bfc.save_image

        def spy(arr, path, **kwargs):
            seen.append(kwargs)
            return real_save(arr, path, **kwargs)

        with mock.patch.object(bfc, 'save_image', spy):
            self._run_batch({'paths': [str(src)], 'output_dir': str(self.root / 'out60'),
                             'format': 'JPEG', 'quality': 60})
            self.assertEqual(seen, [{'quality': 60}])
            seen.clear()
            self._run_batch({'paths': [str(src)], 'output_dir': str(self.root / 'out'),
                             'format': 'JPEG'})
            self.assertEqual(seen, [{}])  # 缺省：不注入 quality（save_image 缺省 92）


class BatchProgressTests(DispatcherBatchTestBase):
    """批处理进度字段（§3.5：逐文件帧 file/state/progress + 聚合 done/total/current）。"""

    def test_progress_events_carry_batch_fields(self):
        in_dir = self.root / 'in'
        for name in ('x1.png', 'x2.png', 'x3.png'):
            _write_image(in_dir / name)
        result = self._run_batch({'paths': [str(in_dir)], 'output_dir': str(self.root / 'out'),
                                  'format': 'PNG'})
        self.assertEqual(result['state'], 'done')
        batch_events = [e for e in self.events
                        if e.get('type') == 'task.progress' and 'done' in e]
        # 首条进度必发（节流窗口初始为 0）；后续条目可能被 ≥100ms 节流合并（§7）。
        self.assertGreaterEqual(len(batch_events), 1)
        for event in batch_events:
            # 聚合字段（§3.5 字段集）。
            self.assertEqual(event['total'], 3)
            self.assertTrue(1 <= event['done'] <= 3, event)
            self.assertTrue(event['current'])
            # 逐文件字段（C++ BatchModel 行契约）：终态帧 state ∈ done/failed。
            self.assertTrue(event['file'])
            self.assertEqual(event['file'], event['current'])
            self.assertIn(event['state'], ('done', 'failed'))
            self.assertEqual(event['progress'], 100)
            self.assertIn(event['message'], ('succeeded', 'failed'))
            if event['state'] == 'done':
                self.assertTrue(Path(event['output_path']).is_file(), event)
        # completed result：聚合字段 + items 全量对账（补齐被节流丢弃的帧）。
        self.assertEqual(result['total'], 3)
        self.assertEqual(result['done'], 3)
        self.assertEqual(result['succeeded'], 3)
        self.assertEqual(len(result['items']), 3)
        for item in result['items']:
            self.assertEqual(item['state'], 'done')
            self.assertTrue(Path(item['file']).is_file())
            self.assertTrue(Path(item['output_path']).is_file())


class BatchCancelTests(DispatcherBatchTestBase):
    """cancel 中断（§3.5/§7：协作检查点 → task.failed(CANCELLED)）。"""

    def test_batch_cancel_stops_remaining_items(self):
        key_a, _key_b = _pick_keys()
        defn = FilterDefRegistry.instance().get(key_a)
        in_dir = self.root / 'in'
        for name in ('c1.png', 'c2.png', 'c3.png'):
            _write_image(in_dir / name)
        out_dir = self.root / 'out'

        seen_tokens: list = []

        def blocking_apply(image, params=None, cancel_token=None):
            # 首个文件阻塞在滤镜协作检查点，直到测试发出 batch.cancel（§7）。
            if cancel_token is not None:
                seen_tokens.append(cancel_token)
                if cancel_token.event.wait(timeout=30):
                    cancel_token.raise_if_cancelled()
            return image

        patcher = mock.patch.object(defn, 'apply', blocking_apply)
        patcher.start()
        self.addCleanup(patcher.stop)

        started_result = self._start_batch({
            'paths': [str(in_dir)], 'output_dir': str(out_dir),
            'format': 'PNG',
            'steps': [{'filter_key': key_a, 'params': {}, 'enabled': True}]})
        task_id = started_result['task_id']

        deadline = time.monotonic() + 15
        while not seen_tokens and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(seen_tokens, '任务未在超时前进入滤镜检查点')

        cancelled = self.dispatcher.handle(_request('batch.cancel', {'task_id': task_id}))
        self.assertTrue(cancelled['success'], cancelled)
        self.assertEqual(cancelled['result'], {'cancelled': True})

        event = self._wait_for_terminal(task_id)
        self.assertIsNotNone(event, '取消后任务未在超时前终结')
        self.assertEqual(event['type'], 'task.failed', event)
        self.assertEqual(event['error']['code'], 'CANCELLED', event)
        self.assertEqual(list(out_dir.glob('*')), [])  # 首项阻塞在滤镜步骤，未写任何输出

        late = self.dispatcher.handle(_request('batch.cancel', {'task_id': task_id}))
        self.assertTrue(late['success'], late)
        self.assertEqual(late['result'], {'cancelled': False})  # 已终结，不谎报取消成功

    def test_batch_cancel_unknown_task_is_unknown_task_error(self):
        response = self.dispatcher.handle(_request('batch.cancel', {'task_id': 'task-nope'}))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], 'UNKNOWN_TASK')

    def test_batch_cancel_requires_task_id(self):
        response = self.dispatcher.handle(_request('batch.cancel', {}))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], 'INVALID_PARAMS')


class BatchInvalidParamsTests(DispatcherBatchTestBase):
    """提交前同步 INVALID_PARAMS（§3.5；均不产生任务）。"""

    def setUp(self):
        super().setUp()
        self.src = _write_image(self.root / 'in' / 'red.png')
        self.base = {'paths': [str(self.src)],
                     'output_dir': str(self.root / 'out'), 'format': 'PNG'}

    def test_invalid_params_rejected_synchronously(self):
        cases = [
            {'paths': []},                                            # 空 paths
            {'paths': 'not-a-list'},                                  # paths 非数组
            {'paths': [42]},                                          # 元素非字符串
            {'paths': ['   ']},                                       # 元素空白字符串
            {**self.base, 'paths': [str(self.src)], 'output_dir': ''},   # 空 output_dir
            {**self.base, 'format': ''},                              # 空 format
            {**self.base, 'format': 'PSD'},                           # 不支持的格式
            {**self.base, 'quality': 0},                              # quality 下界
            {**self.base, 'quality': 101},                            # quality 上界
            {**self.base, 'quality': 'high'},                         # quality 非数值
            {**self.base, 'quality': 50.5},                           # quality 非整数
            {**self.base, 'quality': True},                           # quality 布尔冒充整数
            {**self.base, 'naming': 'pattern', 'pattern': '{oops}'},  # 占位符拼写非法
        ]
        for params in cases:
            payload = {**self.base, **params}
            response = self.dispatcher.handle(_request('batch.start', payload))
            self.assertFalse(response['success'], params)
            self.assertEqual(response['error']['code'], 'INVALID_PARAMS', params)
        self.assertEqual(self._task_events(), [])


class GmicCheckTests(unittest.TestCase):
    """gmic.check（§3.6）：无 gmic 环境 available:false 不抛错；CLI/python 溯源。"""

    def setUp(self):
        self.dispatcher = Dispatcher(WorkerContext())  # 纯 sync 动作，无需任务运行时

    def _check(self) -> dict:
        response = self.dispatcher.handle(_request('gmic.check', {}))
        self.assertTrue(response['success'], response)  # 探测动作不抛错
        return response['result']

    def test_no_gmic_environment_reports_unavailable(self):
        # sys.modules['gmic']=None 使 import gmic 抛 ImportError（模拟无绑定）。
        with mock.patch.object(gmic_processor, 'available', return_value=False), \
                mock.patch.dict(sys.modules, {'gmic': None}):
            result = self._check()
        self.assertEqual(result, {'available': False, 'version': '', 'source': None})

    def test_cli_available_reports_cli_source(self):
        with mock.patch.object(gmic_processor, 'available', return_value=True), \
                mock.patch.object(gmic_processor, 'version', return_value='3.4.0'):
            result = self._check()
        self.assertEqual(result, {'available': True, 'version': '3.4.0', 'source': 'cli'})

    def test_python_binding_fallback(self):
        fake = types.SimpleNamespace(__version__='2.9.1')
        with mock.patch.object(gmic_processor, 'available', return_value=False), \
                mock.patch.dict(sys.modules, {'gmic': fake}):
            result = self._check()
        self.assertEqual(result, {'available': True, 'version': '2.9.1', 'source': 'python'})

    def test_python_binding_without_version_attribute_is_unknown(self):
        with mock.patch.object(gmic_processor, 'available', return_value=False), \
                mock.patch.dict(sys.modules, {'gmic': types.SimpleNamespace()}):
            result = self._check()
        self.assertEqual(result, {'available': True, 'version': 'unknown', 'source': 'python'})


if __name__ == '__main__':
    unittest.main()
