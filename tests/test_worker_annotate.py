"""image.annotate 测试（Phase 9，docs/ipc-protocol.md §3.9）。

覆盖：八种 op 的小图往返（逐类型像素效应）、ops 提交前同步校验、参数化 undo
对 annotate 的重放一致性（undo 从基线重绘 ops 前缀 / redo 逐位复原）、eraser
的源图基线语义（含几何变换后的降级）、进度与取消对齐既有任务生命周期。

进程内风格（不启动 QProcess，CI 直接执行），参照 tests/test_worker_edit.py；
像素断言用 sha256 / numpy 对比。绘制（PIL）为确定性函数：同输入同参数 →
同输出，重放一致性断言以此为据。
"""
from __future__ import annotations

import hashlib
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

from python_worker import task_runtime
from python_worker.adapters.image_adapter import apply_annotate, validate_annotate_ops
from python_worker.dispatcher import Dispatcher, WorkerContext
from python_worker.protocol import PROTOCOL_VERSION


def _request(action: str, params: dict | None = None, request_id: str = 'req-a') -> dict:
    return {'protocol': PROTOCOL_VERSION, 'request_id': request_id,
            'action': action, 'params': params or {}}


def _sha256_array(image: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest()


class _CancelAfterN:
    """第 N 次 raise_if_cancelled 起抛 CancelledError 的确定性取消令牌
    （tests/test_worker_history_parametric.py 同款；真实 CancelToken 只能整段
    置位，无法在逐 op 检查点间精确定位）。"""

    def __init__(self, n: int) -> None:
        from processors.cancellation import CancelToken
        self._token = CancelToken()
        self._n = n
        self._calls = 0

    def raise_if_cancelled(self) -> None:
        self._calls += 1
        if self._calls >= self._n:
            self._token.cancel()
        self._token.raise_if_cancelled()


class WorkerAnnotateTests(unittest.TestCase):
    def setUp(self):
        from tools.make_test_samples import generate

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        generate(Path(self.tmp.name), force=True)

        self.events: list[dict] = []
        self.ctx = WorkerContext(temp_dir=Path(self.tmp.name))
        self.ctx.runtime = task_runtime.TaskRuntime(max_workers=1, emitter=self.events.append)
        self.addCleanup(self.ctx.runtime.shutdown)
        self.dispatcher = Dispatcher(self.ctx)

        self.document_id = self._open(str(Path(self.tmp.name) / 'gradient.png'))

    # ---- 公共小工具 --------------------------------------------------------
    def _open(self, path: str) -> str:
        opened = self.dispatcher.handle(_request('image.open', {'path': path}))
        self.assertTrue(opened['success'], opened)
        document_id = opened['result']['document_id']
        return document_id

    def doc(self):
        return self.ctx.store.get(self.document_id)

    @property
    def source_arr(self) -> np.ndarray:
        return self.doc().source_image

    def _open_noise(self) -> None:
        """切换到 96×96 噪声样本（高频纹理：模糊/像素化的效应可断言）。"""
        self.document_id = self._open(str(Path(self.tmp.name) / 'noise.png'))
        self.assertEqual(self.doc().image.shape[:2], (96, 96))

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

    def _annotate(self, ops: list[dict]) -> dict:
        return self._run('image.annotate', {'document_id': self.document_id, 'ops': ops})

    def _history(self) -> dict:
        response = self.dispatcher.handle(
            _request('image.history', {'document_id': self.document_id}))
        self.assertTrue(response['success'], response)
        return response['result']

    def _expect_invalid(self, ops, action: str = 'image.annotate') -> None:
        response = self.dispatcher.handle(
            _request(action, {'document_id': self.document_id, 'ops': ops}))
        self.assertFalse(response['success'], ops)
        self.assertEqual(response['error']['code'], 'INVALID_PARAMS', ops)

    # ---- 逐 op 类型：小图往返 ----------------------------------------------
    def test_pen_draws_opaque_stroke(self):
        ops = [{'type': 'pen', 'points': [[10, 32], [54, 32]],
                'color': [255, 0, 0], 'width': 5}]
        result = self._annotate(ops)
        self.assertEqual(result['version'], 1)
        self.assertEqual((result['width'], result['height']), (64, 64))
        image = self.doc().image
        # 笔触中心为纯红（RGBA 文档，alpha 保持 255）。
        self.assertEqual(list(image[32, 32, :3]), [255, 0, 0])
        self.assertEqual(int(image[32, 32, 3]), 255)
        # 远离笔触的像素不变。
        self.assertTrue(np.array_equal(image[0:10, 0:10], self.source_arr[0:10, 0:10]))
        # 参数化条目：只存 ops，不存像素。
        entry = self.doc().undo_stack[0]
        self.assertEqual(entry.name, 'image.annotate')
        self.assertIsNone(entry.pixels)
        self.assertEqual(entry.replay['kind'], 'annotate')
        self.assertEqual(entry.replay['ops'][0]['type'], 'pen')
        self.assertEqual([e['name'] for e in self._history()['entries']],
                         ['open', 'image.annotate'])

    def test_pen_accepts_hex_color(self):
        self._annotate([{'type': 'pen', 'points': [[10, 32], [54, 32]],
                         'color': '#00ff00', 'width': 3}])
        self.assertEqual(list(self.doc().image[32, 32, :3]), [0, 255, 0])

    def test_alpha_color_blends_via_composite(self):
        """alpha 第 4 分量：alpha < 255 经透明图层 alpha_composite 混色（§3.9
        颜色词汇），alpha=0 恒等（不谎称绘制），hex 形式 #RRGGBBAA 等价。"""
        pen = {'type': 'pen', 'points': [[10, 32], [54, 32]], 'width': 5}
        self._annotate([{**pen, 'color': [255, 0, 0]}])
        opaque_sha = _sha256_array(self.doc().image)
        self._run('image.reset', {'document_id': self.document_id})

        # alpha=0：图层全透明 → alpha_composite 结果与画布逐位一致（无绘制）。
        self._annotate([{**pen, 'color': [255, 0, 0, 0]}])
        self.assertEqual(_sha256_array(self.doc().image), _sha256_array(self.source_arr))
        self._run('image.reset', {'document_id': self.document_id})

        # 半透明（数组与 #RRGGBBAA hex 同源）：中心像素既非纯红也非源图。
        self._annotate([{**pen, 'color': [255, 0, 0, 128]}])
        blended_sha = _sha256_array(self.doc().image)
        blended_center = list(self.doc().image[32, 32, :3])
        self.assertNotEqual(blended_sha, _sha256_array(self.source_arr))
        self.assertNotEqual(blended_sha, opaque_sha)
        self.assertNotEqual(blended_center, [255, 0, 0])
        self.assertNotEqual(blended_center, list(self.source_arr[32, 32, :3]))
        self._run('image.reset', {'document_id': self.document_id})
        self._annotate([{**pen, 'color': '#ff000080'}])
        self.assertEqual(_sha256_array(self.doc().image), blended_sha)

    def test_alpha_blend_on_rgb_canvas_after_adjust(self):
        """RGB 画布（adjust 后）上 alpha < 255 仍按 4 元组墨水经 RGBA 图层
        alpha_composite 混色（§3.9 无 RGB 画布例外）：半透明不得退化为
        不透明落笔，alpha=0 恒等。"""
        from PIL import Image, ImageDraw

        # adjust（非全默认）把画布转成 RGB 3ch（image_core.brightness 的
        # ensure_rgb）——先锁定该前置，防止前置失真为平凡通过。
        self._run('image.adjust', {'document_id': self.document_id,
                                   'adjustments': {'brightness': 40},
                                   'preview': False})
        self.assertEqual(self.doc().image.shape[2], 3)
        pre = self.doc().image.copy()

        # alpha=0：空图层合成 → 与画布逐位一致。
        self._annotate([{'type': 'rect', 'x': 16, 'y': 16, 'width': 16, 'height': 16,
                         'color': [255, 0, 0, 0], 'fill': True}])
        self.assertTrue(np.array_equal(self.doc().image, pre))
        self.assertEqual(self.doc().image.shape[2], 3)

        # 半透明：与 PIL 图层混色的期望值逐位一致（4 元组墨水），且既非
        # 源像素也非不透明纯红。
        self._run('image.undo', {'document_id': self.document_id})
        self.assertTrue(np.array_equal(self.doc().image, pre))
        self._annotate([{'type': 'rect', 'x': 16, 'y': 16, 'width': 16, 'height': 16,
                         'color': [255, 0, 0, 128], 'fill': True}])
        image = self.doc().image
        center = list(image[24, 24, :3])
        self.assertNotEqual(center, list(pre[24, 24, :3]))
        self.assertNotEqual(center, [255, 0, 0])
        layer = Image.new('RGBA', (image.shape[1], image.shape[0]), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rectangle([16, 16, 32, 32], fill=(255, 0, 0, 128))
        canvas = Image.fromarray(pre, mode='RGB').convert('RGBA')
        expected = np.array(Image.alpha_composite(canvas, layer).convert('RGB'))
        self.assertTrue(np.array_equal(image, expected))

    def test_rect_outline_vs_fill(self):
        rect = {'type': 'rect', 'x': 10, 'y': 10, 'width': 40, 'height': 30,
                'color': [0, 0, 255], 'stroke_width': 2}
        self._annotate([{**rect, 'fill': False}])
        image = self.doc().image
        self.assertFalse(np.array_equal(image[11, 11], self.source_arr[11, 11]))  # 边框
        self.assertTrue(np.array_equal(image[25, 30], self.source_arr[25, 30]))   # 内部空心
        self._run('image.reset', {'document_id': self.document_id})
        self._annotate([{**rect, 'fill': True}])
        image = self.doc().image
        self.assertFalse(np.array_equal(image[25, 30], self.source_arr[25, 30]))  # 内部实心
        self._run('image.reset', {'document_id': self.document_id})
        # ellipse：外接矩形中心；描边时空心、填充时实心。
        self._annotate([{**rect, 'type': 'ellipse', 'fill': False}])
        self.assertTrue(np.array_equal(self.doc().image[25, 30], self.source_arr[25, 30]))
        self._run('image.reset', {'document_id': self.document_id})
        self._annotate([{**rect, 'type': 'ellipse', 'fill': True}])
        self.assertFalse(np.array_equal(self.doc().image[25, 30], self.source_arr[25, 30]))

    def test_arrow_shaft_and_head(self):
        self._annotate([{'type': 'arrow', 'x1': 8, 'y1': 32, 'x2': 56, 'y2': 32,
                         'color': [255, 0, 0], 'width': 3}])
        image = self.doc().image
        changed = np.any(image[:, :, :3] != self.source_arr[:, :, :3], axis=-1)
        self.assertTrue(changed[32, 32])   # 主线中段
        self.assertTrue(changed[32, 8])    # 起点
        # 头线向后张开（±150°，长度 max(6, 3×3)=9）： tip 后方 4px 之外不变，
        # 头线扫过的区域（tip 左下方）有变化。
        self.assertFalse(changed[32, 60])
        self.assertTrue(np.any(changed[33:39, 46:53]))

    def test_text_draws_pixels_with_font_size(self):
        ops = [{'type': 'text', 'x': 8, 'y': 8, 'text': 'X',
                'font_size': 32, 'color': [0, 0, 0]}]
        result = self._annotate(ops)
        self.assertEqual((result['width'], result['height']), (64, 64))
        region = (self.doc().image[0:56, 0:56, :3] != self.source_arr[0:56, 0:56, :3])
        self.assertTrue(np.any(region))  # 字形像素有变化（字形跨平台差异不断言像素值）
        self._run('image.reset', {'document_id': self.document_id})
        # 小字号同样生效（load_default(size=…) 分支）。
        self._annotate([{'type': 'text', 'x': 8, 'y': 8, 'text': 'X',
                         'font_size': 8, 'color': [0, 0, 0]}])
        self.assertTrue(np.any(self.doc().image[0:40, 0:40, :3]
                               != self.source_arr[0:40, 0:40, :3]))

    def test_blur_rect_blurs_only_region(self):
        self._open_noise()
        ops = [{'type': 'blur_rect', 'x': 16, 'y': 16, 'width': 32, 'height': 32,
                'strength': 4}]
        self._annotate(ops)
        image = self.doc().image
        source = self.source_arr
        self.assertFalse(np.array_equal(image[16:48, 16:48], source[16:48, 16:48]))
        # 区域外逐位不变（含边界行列）。
        self.assertTrue(np.array_equal(image[:16], source[:16]))
        self.assertTrue(np.array_equal(image[48:], source[48:]))
        self.assertTrue(np.array_equal(image[16:48, :16], source[16:48, :16]))
        self.assertTrue(np.array_equal(image[16:48, 48:], source[16:48, 48:]))

    def test_pixelate_rect_makes_uniform_blocks(self):
        self._open_noise()
        ops = [{'type': 'pixelate_rect', 'x': 16, 'y': 16, 'width': 32, 'height': 32,
                'block': 8}]
        self._annotate(ops)
        image = self.doc().image
        source = self.source_arr
        self.assertFalse(np.array_equal(image[16:48, 16:48], source[16:48, 16:48]))
        self.assertTrue(np.array_equal(image[:16], source[:16]))
        # 32×32 区域按 block=8 缩放：每个 8×8 块内部逐位一致。
        for y0 in (16, 24, 32, 40):
            for x0 in (16, 24, 32, 40):
                block = image[y0:y0 + 8, x0:x0 + 8]
                self.assertTrue(np.all(block == block[0, 0]), (y0, x0))

    def test_eraser_restores_source_baseline_and_replays(self):
        """eraser 恢复源图基线像素；undo/redo 经参数化重放逐位一致
        （redo 重放 eraser 条目时源图基线由重放器随行传入）。"""
        self._open_noise()
        pen_ops = [{'type': 'pen', 'points': [[10, 48], [54, 48]],
                    'color': [255, 0, 0], 'width': 5}]
        self._annotate(pen_ops)
        after_pen_sha = _sha256_array(self.doc().image)
        self.assertNotEqual(after_pen_sha, _sha256_array(self.source_arr))

        # 同路径、更宽笔刷的 eraser 完全覆盖笔触 → 回到源图。
        self._annotate([{'type': 'eraser', 'points': [[10, 48], [54, 48]], 'width': 9}])
        self.assertEqual(_sha256_array(self.doc().image), _sha256_array(self.source_arr))

        # undo（弹出 eraser 条目）：从源图基线重绘 pen 前缀 → 回到 pen 后状态。
        undone = self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(undone['version'], 3)
        self.assertEqual(_sha256_array(self.doc().image), after_pen_sha)

        # redo（重放 eraser 条目）：逐位回到源图。
        self._run('image.redo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), _sha256_array(self.source_arr))

    def test_eraser_after_geometry_change_keeps_pre_action_pixels(self):
        """源图与当前画布几何不一致（open 后发生过 crop）时 eraser 不恢复：
        笔画区域保持本动作应用前像素（§3.9 的降级语义，不越界写）。"""
        self._open_noise()
        self._run('image.transform', {
            'document_id': self.document_id,
            'crop': {'x': 0, 'y': 0, 'width': 32, 'height': 64}, 'preview': False})
        pre_sha = _sha256_array(self.doc().image)
        self._annotate([{'type': 'eraser', 'points': [[2, 32], [30, 32]], 'width': 5}])
        self.assertEqual(_sha256_array(self.doc().image), pre_sha)

    def test_eraser_after_adjust_recovers_channel_mismatched_baseline(self):
        """源图基线 RGBA（4ch）与 adjust 后画布 RGB（3ch）通道数不一致但
        几何一致：eraser 按基线前 C 通道恢复**笔画覆盖区**（§3.9 语义；
        降级只限几何不一致）。adjust 改变全图像素，笔画区外画布保持本动作
        应用前像素——整画布回到源图不是 eraser 的语义。undo/redo 经参数化
        重放逐位一致（重放基线同为 RGBA，同款通道裁剪）。"""
        self._open_noise()
        self._run('image.adjust', {'document_id': self.document_id,
                                   'adjustments': {'brightness': 40},
                                   'preview': False})
        self.assertEqual(self.doc().image.shape[2], 3)  # adjust 后画布为 RGB
        pen_ops = [{'type': 'pen', 'points': [[10, 48], [54, 48]],
                    'color': [255, 0, 0], 'width': 5}]
        self._annotate(pen_ops)
        after_pen_sha = _sha256_array(self.doc().image)
        self.assertNotEqual(after_pen_sha,
                            _sha256_array(self.doc().source_image[:, :, :3]))

        # 同路径、更宽笔刷的 eraser：笔画覆盖区恢复源图 RGB 分量（4ch 基线
        # 前 3 通道，RGB 分量逐位对应），笔画区外保持 adjust+pen 后像素，
        # 画布保持 3ch（不越界写、不改变通道形状）。掩膜按实现同款几何复刻
        # （PIL line joint='curve' + 圆头端点，width 9），两类区域都锁定。
        pre_eraser = self.doc().image.copy()
        self._annotate([{'type': 'eraser', 'points': [[10, 48], [54, 48]], 'width': 9}])
        image = self.doc().image
        post_eraser_sha = _sha256_array(image)
        self.assertEqual(image.shape[2], 3)
        from PIL import Image, ImageDraw

        from python_worker.adapters.image_adapter import _draw_round_caps
        eraser_points = [(10, 48), (54, 48)]
        mask_img = Image.new('L', (int(image.shape[1]), int(image.shape[0])), 0)
        mask_draw = ImageDraw.Draw(mask_img)
        mask_draw.line(eraser_points, fill=255, width=9, joint='curve')
        _draw_round_caps(mask_draw, eraser_points, 9, 255)
        stroked = np.asarray(mask_img) > 0
        self.assertTrue(np.array_equal(image[stroked],
                                       self.doc().source_image[:, :, :3][stroked]))
        self.assertTrue(np.array_equal(image[~stroked], pre_eraser[~stroked]))

        # undo（弹出 eraser 条目）：从 adjust 快照锚点重放 pen 前缀 → 回到
        # pen 后状态；redo（重放 eraser 条目，基线随行）→ 逐位回到 eraser 后
        # 状态（重放确定性）。版本 §3.3：undo 也递增
        # （adjust v1 → pen v2 → eraser v3 → undo v4）。
        undone = self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), after_pen_sha)
        self._run('image.redo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), post_eraser_sha)
        self.assertEqual(undone['version'], 4)

    def test_multi_call_undo_redo_replays_ops_prefix(self):
        """多次 annotate：undo 从基线重绘 ops 前缀，redo 逐位复原。"""
        self._annotate([{'type': 'pen', 'points': [[10, 20], [54, 20]],
                         'color': [255, 0, 0], 'width': 3}])
        sha1 = _sha256_array(self.doc().image)
        self._annotate([{'type': 'rect', 'x': 10, 'y': 40, 'width': 20, 'height': 15,
                         'color': [0, 0, 255], 'stroke_width': 2, 'fill': True}])
        sha2 = _sha256_array(self.doc().image)

        self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), sha1)   # 重绘 call-1 ops
        self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), _sha256_array(self.source_arr))
        self._run('image.redo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), sha1)
        self._run('image.redo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), sha2)

    def test_annotate_then_chain_undo_replays_from_baseline(self):
        """annotate + filter.apply 全参数化：undo 链条目时从源图基线重绘
        annotate ops（历史栈内全程无像素快照）。"""
        from processors.filter_defs import FilterDefRegistry

        self._annotate([{'type': 'pen', 'points': [[10, 32], [54, 32]],
                         'color': [255, 0, 0], 'width': 3}])
        sha_after_annotate = _sha256_array(self.doc().image)
        registry_keys = FilterDefRegistry.instance().keys()
        chain = [{'filter_key': ('grayscale_standard' if 'grayscale_standard' in registry_keys
                                 else registry_keys[0]), 'params': {}}]
        self._run('filter.apply', {'document_id': self.document_id, 'filters': chain})
        stack = self.doc().undo_stack
        self.assertEqual([e.name for e in stack], ['image.annotate', 'filter.apply'])
        self.assertEqual([e.pixels for e in stack], [None, None])  # 全程参数化

        self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), sha_after_annotate)
        self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), _sha256_array(self.source_arr))

    def test_annotate_above_composite_transform_stays_parametric(self):
        """组合参数 transform（快照 + replay 锚点）之上 annotate 保持参数化：
        undo 从锚点快照复原（重放空前缀），redo 重放 ops 逐位复原。"""
        self._run('image.transform', {
            'document_id': self.document_id,
            'crop': {'x': 0, 'y': 0, 'width': 32, 'height': 64}, 'preview': False})
        post_transform_sha = _sha256_array(self.doc().image)
        self._annotate([{'type': 'pen', 'points': [[2, 32], [30, 32]],
                         'color': [255, 0, 0], 'width': 3}])
        after_annotate_sha = _sha256_array(self.doc().image)

        stack = self.doc().undo_stack
        self.assertEqual([e.name for e in stack], ['image.transform', 'image.annotate'])
        self.assertIsNotNone(stack[0].pixels)  # 组合变换：快照 + replay 并存（锚点）
        self.assertIsNotNone(stack[0].replay)
        self.assertIsNone(stack[1].pixels)     # annotate 未被屏障退化（§3.9）
        self.assertIsNotNone(stack[1].replay)

        self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), post_transform_sha)
        self._run('image.redo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), after_annotate_sha)

    def test_annotate_after_legacy_transform_degrades_to_snapshot(self):
        """重放屏障不因 annotate 改变：既有 op 形式的 transform 之上，
        annotate 退化为快照条目（undo 直达）。"""
        self._run('image.transform', {'document_id': self.document_id, 'op': 'flip_h',
                                      'params': {}, 'preview': False})
        post_transform_sha = _sha256_array(self.doc().image)
        self._annotate([{'type': 'pen', 'points': [[10, 32], [54, 32]],
                         'color': [255, 0, 0], 'width': 3}])
        stack = self.doc().undo_stack
        self.assertEqual([e.name for e in stack], ['image.transform', 'image.annotate'])
        self.assertIsNotNone(stack[1].pixels)  # 屏障之上退化为快照
        self.assertIsNone(stack[1].replay)
        self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), post_transform_sha)

    # ---- 提交前同步校验 ------------------------------------------------------
    def test_ops_validation_rejected_synchronously(self):
        base = {'document_id': self.document_id}
        pen = {'type': 'pen', 'points': [[10, 32], [54, 32]],
               'color': [255, 0, 0], 'width': 3}
        rect = {'type': 'rect', 'x': 10, 'y': 10, 'width': 20, 'height': 10,
                'color': [0, 0, 255]}
        cases = [
            None,                       # 缺 ops
            [],                         # 空数组
            'pen',                      # 非数组
            [{'type': 'spray', 'points': [[0, 0], [1, 1]]}],  # 未知 type
            [{'type': 'pen', 'points': [[10, 32]], 'color': [255, 0, 0], 'width': 3}],
            [{'type': 'pen', 'points': [[10, 32], [54, 32]], 'width': 3}],    # 缺 color
            [{**pen, 'width': 0}],
            [{**pen, 'color': [256, 0, 0]}],
            [{**pen, 'color': [1, 2]}],
            [{**pen, 'color': '#gggggg'}],
            [{'type': 'text', 'x': 8, 'y': 8, 'text': '', 'font_size': 16,
              'color': [0, 0, 0]}],
            [{'type': 'text', 'x': 8, 'y': 8, 'text': 'X', 'font_size': 0,
              'color': [0, 0, 0]}],
            [{'type': 'text', 'x': 8, 'y': 8, 'text': 'X', 'font_size': 513,
              'color': [0, 0, 0]}],
            [{'type': 'text', 'x': 8, 'y': 8, 'text': 'X', 'font_size': 16.5,
              'color': [0, 0, 0]}],
            [{**rect, 'width': 0}],
            [{**rect, 'height': -1}],
            [{**rect, 'fill': 'yes'}],
            [{**rect, 'stroke_width': 0}],
            [{'type': 'arrow', 'x1': 8, 'y1': 32, 'x2': 56, 'color': [0, 0, 0],
              'width': 3}],           # 缺 y2
            [{'type': 'arrow', 'x1': 8, 'y1': 32, 'x2': 56, 'y2': 32,
              'color': [0, 0, 0], 'width': 0}],
            [{'type': 'blur_rect', 'x': 16, 'y': 16, 'width': 32, 'height': 32,
              'strength': 0}],
            [{'type': 'blur_rect', 'x': 16, 'y': 16, 'width': 32, 'height': 32,
              'strength': 101}],
            [{'type': 'blur_rect', 'x': 200, 'y': 16, 'width': 32, 'height': 32,
              'strength': 4}],        # 完全在图像外
            [{'type': 'pixelate_rect', 'x': 16, 'y': 16, 'width': 32, 'height': 32,
              'block': 1}],
            [{'type': 'pixelate_rect', 'x': 16, 'y': 16, 'width': 32, 'height': 32,
              'block': 1.5}],
            [{'type': 'eraser', 'points': [[10, 32]], 'width': 5}],
            [{'type': 'eraser', 'points': [[10, 32], [54, 32]], 'width': 0}],
        ]
        for ops in cases:
            response = self.dispatcher.handle(
                _request('image.annotate', {**base, 'ops': ops}))
            self.assertFalse(response['success'], ops)
            self.assertEqual(response['error']['code'], 'INVALID_PARAMS', ops)
        # 未知文档在提交前同步拒绝。
        response = self.dispatcher.handle(_request('image.annotate', {
            'document_id': 'doc-ghost', 'ops': [pen]}))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], 'UNKNOWN_DOCUMENT')
        # 全部提交前拒绝：没有任务、版本未动。
        self.assertFalse([e for e in self.events if e.get('type', '').startswith('task')])
        self.assertEqual(self.doc().version, 0)

    # ---- 生命周期：进度 / 取消 ----------------------------------------------
    def test_annotate_lifecycle_matches_standard_tasks(self):
        ops = [
            {'type': 'pen', 'points': [[10, 20], [54, 20]], 'color': [255, 0, 0],
             'width': 3},
            {'type': 'rect', 'x': 10, 'y': 40, 'width': 20, 'height': 15,
             'color': [0, 0, 255], 'stroke_width': 2, 'fill': False},
            {'type': 'ellipse', 'x': 30, 'y': 40, 'width': 20, 'height': 15,
             'color': [0, 255, 0], 'stroke_width': 1, 'fill': True},
        ]
        response = self.dispatcher.handle(_request('image.annotate', {
            'document_id': self.document_id, 'ops': ops}))
        self.assertTrue(response['success'], response)
        task_id = response['result']['task_id']
        event = self._wait_for_terminal(task_id)
        self.assertIsNotNone(event)
        self.assertEqual(event['type'], 'task.completed', event)
        # §2.3 受理回执形状与其它 async 动作一致。
        self.assertEqual(response['result']['status'], 'queued')
        # 进度对齐既有任务：至少一条 task.progress（首条必发，§7 节流只节后续）。
        progress_events = [e for e in self.events
                           if e.get('type') == 'task.progress' and e.get('task_id') == task_id]
        self.assertTrue(progress_events)
        # 完成形状：{version, width, height}，modified 置位。
        self.assertEqual(event['result'], {'version': 1, 'width': 64, 'height': 64})
        self.assertTrue(self.doc().modified)
        # task.cancel 对齐既有任务：新任务可取消，未知任务 UNKNOWN_TASK。
        cancel = self.dispatcher.handle(_request('task.cancel', {'task_id': task_id}))
        self.assertTrue(cancel['success'], cancel)  # 已终结 → {cancelling: false}
        self.assertFalse(cancel['result']['cancelling'])
        ghost = self.dispatcher.handle(_request('task.cancel', {'task_id': 'task-ghost'}))
        self.assertFalse(ghost['success'])
        self.assertEqual(ghost['error']['code'], 'UNKNOWN_TASK')

    def test_cancelled_apply_leaves_document_untouched(self):
        """逐 op 协作取消：第一步前 / 第一步后取消均抛 CancelledError，
        文档像素不动（apply_annotate 为函数式，先算后提交）。"""
        from processors.cancellation import CancelledError

        ops = validate_annotate_ops(
            [{'type': 'pen', 'points': [[10, 32], [54, 32]], 'color': [255, 0, 0],
              'width': 3},
             {'type': 'rect', 'x': 10, 'y': 10, 'width': 20, 'height': 10,
              'color': [0, 0, 255], 'stroke_width': 2}],
            64, 64)
        baseline_sha = _sha256_array(self.doc().image)
        with self.assertRaises(CancelledError):  # 第一个 op 前取消
            apply_annotate(self.doc().image, ops, self.doc().source_image,
                           cancel_token=_CancelAfterN(1))
        with self.assertRaises(CancelledError):  # 第一个 op 的检查点取消
            apply_annotate(self.doc().image, ops, self.doc().source_image,
                           cancel_token=_CancelAfterN(2))
        self.assertEqual(_sha256_array(self.doc().image), baseline_sha)
        self.assertEqual(self.doc().version, 0)
        self.assertEqual(self.doc().undo_stack, [])


if __name__ == '__main__':
    unittest.main()
