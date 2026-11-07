"""image.transform 组合参数与 image.save target_kb 测试（Phase 9，docs/ipc-protocol.md §3.2/§3.9）。

- 既有 op/params 形式兼容回归：五个 op 与 processors/core 直调逐位一致、
  历史条目仍是无 replay 的快照（重放屏障不变）。
- 新式组合参数（crop/rotate_free/perspective/scale）：校验（提交前同步
  INVALID_PARAMS）、执行顺序 crop→rotate→scale、参数化历史（快照 + replay，
  其上参数化条目不再屏障退化）。
- image.save target_kb：二分收敛与下限 30、保 alpha 用 WebP、响应形状
  （无 target_kb 时逐字节不变）。

进程内风格（不启动 QProcess，CI 直接执行），参照 tests/test_worker_edit.py；
像素断言用 sha256 / numpy 逐位对比。
"""
from __future__ import annotations

import hashlib
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

from python_worker import task_runtime
from python_worker.adapters.image_adapter import (SAVE_TARGET_MAX_QUALITY, SAVE_TARGET_MIN_QUALITY,
                                                  apply_composite_transform, encode_image_size,
                                                  search_quality_for_target)
from python_worker.dispatcher import Dispatcher, WorkerContext
from python_worker.protocol import PROTOCOL_VERSION


def _request(action: str, params: dict | None = None, request_id: str = 'req-t') -> dict:
    return {'protocol': PROTOCOL_VERSION, 'request_id': request_id,
            'action': action, 'params': params or {}}


def _sha256_array(image: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest()


class WorkerTransformTests(unittest.TestCase):
    def setUp(self):
        from tools.make_test_samples import generate

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        generate(Path(self.tmp.name), force=True)
        self.sample = str(Path(self.tmp.name) / 'gradient.png')

        self.events: list[dict] = []
        self.ctx = WorkerContext(temp_dir=Path(self.tmp.name))
        self.ctx.runtime = task_runtime.TaskRuntime(max_workers=1, emitter=self.events.append)
        self.addCleanup(self.ctx.runtime.shutdown)
        self.dispatcher = Dispatcher(self.ctx)

        self.document_id = self._open(self.sample)

    # ---- 公共小工具 --------------------------------------------------------
    def _open(self, path: str) -> str:
        opened = self.dispatcher.handle(_request('image.open', {'path': path}))
        self.assertTrue(opened['success'], opened)
        return opened['result']['document_id']

    def doc(self):
        return self.ctx.store.get(self.document_id)

    @property
    def source_arr(self) -> np.ndarray:
        """open 态源图像素（processors 均为函数式，恒不被原地修改）。"""
        return self.doc().source_image

    def _wait_for_terminal(self, task_id: str, timeout: float = 15.0) -> dict | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for event in self.events:
                if event.get('task_id') == task_id and event.get('type') in (
                        'task.completed', 'task.failed'):
                    return event
            time.sleep(0.02)
        return None

    def _run(self, action: str, params: dict) -> dict:
        """提交异步动作并等待完成，返回 completed 事件的 result。"""
        response = self.dispatcher.handle(_request(action, params))
        self.assertTrue(response['success'], response)
        event = self._wait_for_terminal(response['result']['task_id'])
        self.assertIsNotNone(event, f'{action} 任务未在超时前完成')
        self.assertEqual(event['type'], 'task.completed', event)
        return event['result']

    def _history(self) -> dict:
        response = self.dispatcher.handle(
            _request('image.history', {'document_id': self.document_id}))
        self.assertTrue(response['success'], response)
        return response['result']

    def _expect_invalid(self, action: str, params: dict) -> None:
        response = self.dispatcher.handle(_request(action, params))
        self.assertFalse(response['success'], (action, params))
        self.assertEqual(response['error']['code'], 'INVALID_PARAMS', (action, params))

    def _to_rgb(self) -> None:
        """把文档调成 3 通道（image.adjust 走 ensure_rgb）：JPEG 成功路径前置。"""
        self._run('image.adjust', {'document_id': self.document_id,
                                   'adjustments': {'brightness': 0.1}, 'preview': False})
        self.assertEqual(self.doc().image.ndim, 3)
        self.assertEqual(self.doc().image.shape[2], 3)

    # ---- 既有 op/params 形式：兼容回归 --------------------------------------
    def test_legacy_ops_bitwise_match_processors_core(self):
        """既有五个 op 经 dispatcher 的结果与 processors/core 直调逐位一致。"""
        from processors import core as image_core

        source = self.source_arr
        expected_version = 1  # open 后 version=0；每次 op +1、每次 reset 再 +1
        cases = (
            ('rotate', {'angle': 90}, image_core.rotate(source, 90.0)),
            ('flip_h', {}, image_core.flip_h(source)),
            ('flip_v', {}, image_core.flip_v(source)),
            ('scale', {'sx': 2.0}, image_core.scale(source, 2.0)),
            ('crop', {'x': 8, 'y': 8, 'w': 32, 'h': 16},
             image_core.crop(source, 8, 8, 32, 16)),
        )
        for op, params, expected in cases:
            result = self._run('image.transform', {
                'document_id': self.document_id, 'op': op, 'params': params,
                'preview': False})
            self.assertEqual(result['version'], expected_version, op)
            self.assertTrue(np.array_equal(self.doc().image, expected), op)
            self.assertEqual(result['width'], int(expected.shape[1]), op)
            self.assertEqual(result['height'], int(expected.shape[0]), op)
            # 复位到源图，下一个 op 从同一基线开始（reset 同样递增 version，§3.1）。
            self._run('image.reset', {'document_id': self.document_id})
            expected_version += 2

    def test_legacy_transform_entry_stays_replay_barrier(self):
        self._run('image.transform', {
            'document_id': self.document_id, 'op': 'flip_h', 'params': {},
            'preview': False})
        entry = self.doc().undo_stack[0]
        self.assertEqual(entry.name, 'image.transform')
        self.assertIsNotNone(entry.pixels)
        self.assertIsNone(entry.replay)  # 既有形式仍是无 replay 的重放屏障

    def test_legacy_invalid_params_still_synchronous(self):
        for params in (
                {'document_id': self.document_id, 'op': 'crop',
                 'params': {'x': 0, 'y': 0, 'w': 9999, 'h': 10}, 'preview': False},
                {'document_id': self.document_id, 'op': 'scale',
                 'params': {'sx': 0}, 'preview': False},
                {'document_id': self.document_id, 'op': 'shear', 'params': {},
                 'preview': False},
        ):
            self._expect_invalid('image.transform', params)

    # ---- 组合参数：提交前同步校验 -------------------------------------------
    def test_composite_validation_rejected_synchronously(self):
        base = {'document_id': self.document_id, 'preview': False}
        cases = [
            # crop：负值 / 非正尺寸 / 越界 / 缺键 / 非对象
            {'crop': {'x': -1, 'y': 0, 'width': 8, 'height': 8}},
            {'crop': {'x': 0, 'y': 0, 'width': 0, 'height': 8}},
            {'crop': {'x': 0, 'y': 0, 'width': 8, 'height': -8}},
            {'crop': {'x': 0, 'y': 0, 'width': 65, 'height': 8}},
            {'crop': {'x': 0, 'y': 0, 'width': 8, 'height': 65}},
            {'crop': {'x': 0, 'y': 0, 'width': 8}},
            {'crop': 'x'},
            # rotate_free：角度越界 / 非数值 / expand 非布尔 / 缺 angle
            {'rotate_free': {'angle': 180.5}},
            {'rotate_free': {'angle': -181}},
            {'rotate_free': {'angle': 'x'}},
            {'rotate_free': {'angle': 45, 'expand': 'yes'}},
            {'rotate_free': {'expand': True}},
            # perspective：点数 / 点形状 / 非数值 / 与其它组合键并存
            {'perspective': {'corners': [[0, 0], [64, 0], [64, 64]]}},
            {'perspective': {'corners': [[0, 0], [64, 0], [64, 64], [0, 64], [1, 1]]}},
            {'perspective': {'corners': [[0, 0], [64, 0], [64, 64], [0, 64, 1]]}},
            {'perspective': {'corners': [[0, 0], [64, 0], ['x', 64], [0, 64]]}},
            {'perspective': {'corners': [[0, 0], [64, 0], [64, 64], [0, 64]]},
             'crop': {'x': 0, 'y': 0, 'width': 8, 'height': 8}},
            # scale：非正尺寸 / 缺键 / resample 非法
            {'scale': {'width': 0, 'height': 8}},
            {'scale': {'width': 8, 'height': -1}},
            {'scale': {'width': 8}},
            {'scale': {'width': 8, 'height': 8, 'resample': 'bicubicX'}},
            {'scale': {'width': 8, 'height': 8, 'resample': 4}},
            # 与既有 op/params 混用（顶层组合键 + op / + params 键 / 嵌套组合 + op）
            {'op': 'flip_h', 'params': {},
             'crop': {'x': 0, 'y': 0, 'width': 8, 'height': 8}},
            {'crop': {'x': 0, 'y': 0, 'width': 8, 'height': 8}, 'params': {}},
            {'op': 'flip_h', 'params': {'crop': {'x': 0, 'y': 0, 'width': 8, 'height': 8}}},
        ]
        for composite in cases:
            self._expect_invalid('image.transform', {**base, **composite})
        # 嵌套线形（C++ applyTransform 透传形状）的参数校验与顶层线形一致。
        for composite in ({'crop': {'x': -1, 'y': 0, 'width': 8, 'height': 8}},
                          {'rotate_free': {'angle': 181}},
                          {'scale': {'width': 0, 'height': 8}}):
            self._expect_invalid('image.transform', {**base, 'params': composite})

        # 既无 op 也无组合键：仍按既有路径报"未知变换 op"。
        self._expect_invalid('image.transform', dict(base))
        # 组合参数形式的未知文档在提交前同步拒绝（不产生任务）。
        for composite_request in (
                {'document_id': 'doc-ghost',
                 'crop': {'x': 0, 'y': 0, 'width': 8, 'height': 8}, 'preview': False},
                {'document_id': 'doc-ghost',
                 'params': {'crop': {'x': 0, 'y': 0, 'width': 8, 'height': 8}},
                 'preview': False},
        ):
            response = self.dispatcher.handle(_request('image.transform', composite_request))
            self.assertFalse(response['success'], composite_request)
            self.assertEqual(response['error']['code'], 'UNKNOWN_DOCUMENT', composite_request)
        # 以上全部为提交前拒绝：没有任何任务事件。
        self.assertFalse([e for e in self.events if e.get('type', '').startswith('task')])

    def test_nested_composite_form_matches_top_level(self):
        """嵌套线形（params 对象承载组合键）与顶层线形逐位一致——C++
        applyTransform 的透传形状（§3.2 双线形）。"""
        composite = {'crop': {'x': 0, 'y': 0, 'width': 32, 'height': 64},
                     'rotate_free': {'angle': 90.0, 'expand': True}}
        top = self._run('image.transform', {
            'document_id': self.document_id, **composite, 'preview': False})
        top_sha = _sha256_array(self.doc().image)
        self._run('image.reset', {'document_id': self.document_id})
        nested = self._run('image.transform', {
            'document_id': self.document_id, 'params': composite, 'preview': False})
        self.assertEqual((nested['width'], nested['height']),
                         (top['width'], top['height']))
        self.assertEqual(_sha256_array(self.doc().image), top_sha)
        # 嵌套线形同样走组合历史（快照 + replay，spec 与顶层线形同形）。
        entry = self.doc().undo_stack[0]
        self.assertEqual(entry.name, 'image.transform')
        self.assertIsNotNone(entry.pixels)
        self.assertEqual(entry.replay,
                         {'kind': 'transform',
                          'ops': {'crop': composite['crop'],
                                  'rotate_free': composite['rotate_free']}})

    # ---- 组合参数：语义 ------------------------------------------------------
    def test_composite_crop_exact_pixels(self):
        result = self._run('image.transform', {
            'document_id': self.document_id,
            'crop': {'x': 8, 'y': 8, 'width': 32, 'height': 16}, 'preview': False})
        self.assertEqual((result['width'], result['height']), (32, 16))
        self.assertTrue(np.array_equal(self.doc().image, self.source_arr[8:24, 8:40]))

    def test_composite_scale_all_resamples_and_determinism(self):
        for resample in ('lanczos', 'bilinear', 'nearest', 'bicubic'):
            result = self._run('image.transform', {
                'document_id': self.document_id,
                'scale': {'width': 16, 'height': 8, 'resample': resample},
                'preview': False})
            self.assertEqual((result['width'], result['height']), (16, 8), resample)
            self._run('image.reset', {'document_id': self.document_id})
        # 同参数两次应用逐位一致（确定性，参数化重放的前提）。
        spec = {'scale': {'width': 16, 'height': 8, 'resample': 'lanczos'}}
        self._run('image.transform', {'document_id': self.document_id,
                                      **spec, 'preview': False})
        first_sha = _sha256_array(self.doc().image)
        self._run('image.reset', {'document_id': self.document_id})
        self._run('image.transform', {'document_id': self.document_id,
                                      **spec, 'preview': False})
        self.assertEqual(_sha256_array(self.doc().image), first_sha)

    def test_rotate_free_expand_semantics(self):
        # 90°：方形样本尺寸不变、像素改变。
        result = self._run('image.transform', {
            'document_id': self.document_id,
            'rotate_free': {'angle': 90}, 'preview': False})
        self.assertEqual((result['width'], result['height']), (64, 64))
        self.assertNotEqual(_sha256_array(self.doc().image), _sha256_array(self.source_arr))
        self._run('image.reset', {'document_id': self.document_id})
        # 45°：expand=true 画布扩张（> 64 且宽高相等）；expand=false 保持原尺寸。
        result = self._run('image.transform', {
            'document_id': self.document_id,
            'rotate_free': {'angle': 45, 'expand': True}, 'preview': False})
        self.assertEqual(result['width'], result['height'])
        self.assertGreater(result['width'], 64)
        self._run('image.reset', {'document_id': self.document_id})
        result = self._run('image.transform', {
            'document_id': self.document_id,
            'rotate_free': {'angle': 45, 'expand': False}, 'preview': False})
        self.assertEqual((result['width'], result['height']), (64, 64))
        self._run('image.reset', {'document_id': self.document_id})
        # 0°：尺寸不变（恒等变换）。
        result = self._run('image.transform', {
            'document_id': self.document_id,
            'rotate_free': {'angle': 0}, 'preview': False})
        self.assertEqual((result['width'], result['height']), (64, 64))

    def test_rotate_free_exposed_fill_matches_canvas_mode(self):
        """旋转露出的底面：RGBA 透明、RGB 黑（§3.2 参数表约定）。"""
        # RGBA 文档：45° expand 后外接画布角落远离内容（64×64 旋转 45° 时
        # 角点距内容边缘 >30px），必为纯填充 → alpha 0。
        self._run('image.transform', {
            'document_id': self.document_id,
            'rotate_free': {'angle': 45, 'expand': True}, 'preview': False})
        expanded = self.doc().image
        self.assertEqual(expanded.ndim, 3)
        self.assertEqual(expanded.shape[2], 4)
        self.assertEqual(int(expanded[0, 0, 3]), 0)
        self._run('image.reset', {'document_id': self.document_id})
        # RGB 文档（adjust 走 ensure_rgb）：同一角落露出底面为黑。
        self._to_rgb()
        self._run('image.transform', {
            'document_id': self.document_id,
            'rotate_free': {'angle': 45, 'expand': True}, 'preview': False})
        rgb_rotated = self.doc().image
        self.assertEqual(rgb_rotated.shape[2], 3)
        self.assertEqual(list(rgb_rotated[0, 0]), [0, 0, 0])

    def test_perspective_output_is_target_bbox(self):
        base = {'document_id': self.document_id, 'preview': False}
        # 恒等四角：尺寸不变。
        result = self._run('image.transform', {**base, 'perspective': {
            'corners': [[0, 0], [64, 0], [64, 64], [0, 64]]}})
        self.assertEqual((result['width'], result['height']), (64, 64))
        self._run('image.reset', {'document_id': self.document_id})
        # 负坐标外扩：输出 = 目标四点外接矩形（80×80）。
        result = self._run('image.transform', {**base, 'perspective': {
            'corners': [[-8, -8], [72, -8], [72, 72], [-8, 72]]}})
        self.assertEqual((result['width'], result['height']), (80, 80))
        self._run('image.reset', {'document_id': self.document_id})
        # 梯形（底边内收）：外接矩形仍是 64×64。
        result = self._run('image.transform', {**base, 'perspective': {
            'corners': [[0, 0], [64, 0], [40, 64], [24, 64]]}})
        self.assertEqual((result['width'], result['height']), (64, 64))

    def test_composite_chain_executes_in_documented_order(self):
        """顺序锁定 crop → rotate_free → scale：与文档顺序的手工链逐位一致。"""
        from processors import core as image_core

        from python_worker.adapters.image_adapter import _rotate_free

        spec = {'crop': {'x': 0, 'y': 0, 'width': 32, 'height': 64},
                'rotate_free': {'angle': 90.0, 'expand': True},
                'scale': {'width': 16, 'height': 8, 'resample': 'lanczos'}}
        result = self._run('image.transform', {
            'document_id': self.document_id, **spec, 'preview': False})
        self.assertEqual((result['width'], result['height']), (16, 8))
        cropped = image_core.crop(self.source_arr, 0, 0, 32, 64)      # 步骤 1 → 32宽×64高
        rotated = _rotate_free(cropped, spec['rotate_free'])          # 步骤 2 → 64宽×32高
        self.assertEqual(rotated.shape[:2], (32, 64))                 # np 形状 (行, 列)
        expected = image_core.resize(rotated, 16, 8, keep_aspect=False,
                                     interpolation='lanczos')          # 步骤 3 → 16×8
        self.assertTrue(np.array_equal(self.doc().image, expected))
        # 直接函数与 dispatcher 路径一致（接线无参数漂移）。
        self.assertTrue(np.array_equal(self.doc().image,
                                       apply_composite_transform(self.source_arr, spec)))

    def test_composite_preview_keeps_document_untouched(self):
        result = self._run('image.transform', {
            'document_id': self.document_id,
            'crop': {'x': 0, 'y': 0, 'width': 32, 'height': 64},
            'rotate_free': {'angle': 90},
            'preview': True, 'max_side': 40})
        self.assertLessEqual(max(result['width'], result['height']), 40)
        self.assertTrue(Path(result['path']).is_file())
        self.assertEqual(result['version'], 0)  # 预览携带当前版本但不递增
        self.assertEqual(self.doc().version, 0)
        self.assertTrue(np.array_equal(self.doc().image, self.source_arr))
        self.assertEqual(self.doc().undo_stack, [])

    # ---- 组合参数：参数化历史 ------------------------------------------------
    def test_composite_fullres_pushes_replayable_history(self):
        spec = {'crop': {'x': 0, 'y': 0, 'width': 32, 'height': 64},
                'rotate_free': {'angle': 90.0, 'expand': True}}
        result = self._run('image.transform', {
            'document_id': self.document_id, **spec, 'preview': False})
        self.assertEqual(result['version'], 1)

        entry = self.doc().undo_stack[0]
        self.assertEqual(entry.name, 'image.transform')
        self.assertIsNotNone(entry.pixels)  # 快照（undo 直达）
        self.assertEqual(entry.replay, {'kind': 'transform', 'ops': spec})  # 可重放锚点

    def test_composite_anchor_keeps_chain_parametric_and_replays_bitwise(self):
        """组合变换之上 filter.apply 不再屏障退化；undo 链条目时从变换锚点
        重放其 replay（快照像素 + replay 参数），逐位复原变换后状态。"""
        spec = {'crop': {'x': 0, 'y': 0, 'width': 32, 'height': 64},
                'rotate_free': {'angle': 45.0, 'expand': True}}
        self._run('image.transform', {'document_id': self.document_id,
                                      **spec, 'preview': False})
        post_transform_sha = _sha256_array(self.doc().image)
        from processors.filter_defs import FilterDefRegistry
        registry_keys = FilterDefRegistry.instance().keys()
        chain = [{'filter_key': ('grayscale_standard' if 'grayscale_standard' in registry_keys
                                 else registry_keys[0]), 'params': {}}]
        self._run('filter.apply', {'document_id': self.document_id, 'filters': chain})
        after_chain_sha = _sha256_array(self.doc().image)

        stack = self.doc().undo_stack
        self.assertEqual([e.name for e in stack], ['image.transform', 'filter.apply'])
        self.assertIsNone(stack[1].pixels)  # 参数化条目未被屏障退化（Phase 9 前会退化）
        self.assertIsNotNone(stack[1].replay)

        undone = self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(undone['version'], 3)
        self.assertEqual(_sha256_array(self.doc().image), post_transform_sha)  # 锚点重放

        redone = self._run('image.redo', {'document_id': self.document_id})
        self.assertEqual(redone['version'], 4)
        self.assertEqual(_sha256_array(self.doc().image), after_chain_sha)

        self._run('image.undo', {'document_id': self.document_id})  # 链
        self._run('image.undo', {'document_id': self.document_id})  # 变换条目（快照直达）
        self.assertEqual(_sha256_array(self.doc().image), _sha256_array(self.source_arr))

    # ---- image.save target_kb（§3.9）----------------------------------------
    def test_save_target_kb_only_applies_to_jpeg_webp(self):
        for ext in ('.png', '.bmp', ''):
            path = str(Path(self.tmp.name) / f'out{ext}') if ext else str(
                Path(self.tmp.name) / 'noext')
            self._expect_invalid('image.save', {
                'document_id': self.document_id, 'path': path, 'target_kb': 64})

    def test_save_target_kb_alpha_must_use_webp(self):
        # 文档以 RGBA 载入（processors/utils.py pil_to_np）：JPEG 会丢/拒透明度。
        self.assertEqual(self.doc().image.shape[2], 4)
        self._expect_invalid('image.save', {
            'document_id': self.document_id,
            'path': str(Path(self.tmp.name) / 'alpha.jpg'), 'target_kb': 64})
        # 保 alpha 用 WebP：成功且响应带 quality/bytes。
        path = Path(self.tmp.name) / 'alpha.webp'
        result = self._run('image.save', {
            'document_id': self.document_id, 'path': str(path), 'target_kb': 200})
        self.assertTrue(path.is_file())
        self.assertLessEqual(result['bytes'], 200 * 1024)
        self.assertTrue(SAVE_TARGET_MIN_QUALITY <= result['quality'] <= SAVE_TARGET_MAX_QUALITY)
        self.assertEqual(result['bytes'], result['file_size'])
        from PIL import Image
        with Image.open(path) as check:
            self.assertEqual(check.format, 'WEBP')

    def test_save_target_kb_binary_search_converges_on_rgb_jpeg(self):
        self._to_rgb()
        target_kb = 64
        path = Path(self.tmp.name) / 'conv.jpg'
        result = self._run('image.save', {
            'document_id': self.document_id, 'path': str(path), 'target_kb': target_kb})
        self.assertTrue(path.is_file())
        self.assertTrue(SAVE_TARGET_MIN_QUALITY <= result['quality'] <= SAVE_TARGET_MAX_QUALITY)
        self.assertLessEqual(result['bytes'], target_kb * 1024)
        self.assertEqual(result['bytes'], result['file_size'])
        self.assertEqual(result['bytes'], path.stat().st_size)
        from PIL import Image
        with Image.open(path) as check:
            self.assertEqual(check.format, 'JPEG')
        # 二分最优性：返回的 quality 达标，quality+1 超预算（或已到上限）。
        quality = result['quality']
        image = self.doc().image
        self.assertLessEqual(encode_image_size(image, '.jpg', quality), target_kb * 1024)
        if quality < SAVE_TARGET_MAX_QUALITY:
            self.assertGreater(encode_image_size(image, '.jpg', quality + 1), target_kb * 1024)

    def test_search_quality_floor_returns_min_quality(self):
        self._to_rgb()
        # 1 字节预算必然不可达：二分收敛到下限 30，探测大小如实返回（> 预算）。
        quality, size = search_quality_for_target(self.doc().image, '.jpg', 1)
        self.assertEqual(quality, SAVE_TARGET_MIN_QUALITY)
        self.assertEqual(size, encode_image_size(self.doc().image, '.jpg',
                                                 SAVE_TARGET_MIN_QUALITY))
        self.assertGreater(size, 1)  # 下限仍超预算：不谎报达标（§3.9）

    def test_search_quality_cancelled_at_probe_boundary(self):
        """target_kb 二分的取消在探测边界检查点生效（§3.9/§7）。"""
        from processors.cancellation import CancelledError, CancelToken

        class _CancelAtThirdProbe:
            """第 3 次 raise_if_cancelled 起抛 CancelledError 的确定性令牌
            （tests/test_worker_annotate.py _CancelAfterN 同款）。"""

            def __init__(self) -> None:
                self._token = CancelToken()
                self._calls = 0

            def raise_if_cancelled(self) -> None:
                self._calls += 1
                if self._calls >= 3:
                    self._token.cancel()
                self._token.raise_if_cancelled()

        self._to_rgb()
        # [30, 100] 的二分全程 ≥ 6 次探测：第 3 次取消必落在搜索中途。
        with self.assertRaises(CancelledError):
            search_quality_for_target(self.doc().image, '.jpg', 64 * 1024,
                                      _CancelAtThirdProbe())

    def test_save_target_kb_reports_truth_at_floor(self):
        self._to_rgb()
        path = Path(self.tmp.name) / 'floor.jpg'
        result = self._run('image.save', {
            'document_id': self.document_id, 'path': str(path), 'target_kb': 1})
        self.assertTrue(path.is_file())
        # 响应 quality 与重算的二分结果一致；bytes 为落盘真实大小。
        expected_quality, _probe = search_quality_for_target(self.doc().image, '.jpg', 1024)
        self.assertEqual(result['quality'], expected_quality)
        self.assertEqual(result['bytes'], path.stat().st_size)
        self.assertEqual(result['bytes'], result['file_size'])

    def test_save_target_kb_validated_before_task(self):
        for bad in (0, -5, 'x', 64.5, True):
            self._expect_invalid('image.save', {
                'document_id': self.document_id,
                'path': str(Path(self.tmp.name) / 'x.jpg'), 'target_kb': bad})
        response = self.dispatcher.handle(_request('image.save', {
            'document_id': 'doc-ghost', 'path': str(Path(self.tmp.name) / 'x.jpg'),
            'target_kb': 64}))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], 'UNKNOWN_DOCUMENT')
        self.assertFalse([e for e in self.events if e.get('type', '').startswith('task')])

    def test_save_target_kb_takes_precedence_over_quality(self):
        self._to_rgb()
        path = Path(self.tmp.name) / 'prec.jpg'
        result = self._run('image.save', {
            'document_id': self.document_id, 'path': str(path),
            'quality': 5, 'target_kb': 64})
        self.assertTrue(path.is_file())
        self.assertGreaterEqual(result['quality'], SAVE_TARGET_MIN_QUALITY)  # 走二分而非 quality=5

    def test_save_without_target_kb_keeps_response_shape(self):
        path = Path(self.tmp.name) / 'plain.png'
        result = self._run('image.save', {'document_id': self.document_id, 'path': str(path)})
        self.assertEqual(set(result.keys()), {'saved', 'path', 'file_size'})  # 无新字段
        self.assertTrue(path.is_file())


if __name__ == '__main__':
    unittest.main()
