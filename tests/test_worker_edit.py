"""Worker 编辑动作测试：image.adjust / image.transform / image.undo / image.redo /
image.reset / image.history（docs/ipc-protocol.md §3.1-§3.3）。

参照 tests/test_worker_protocol.py 的进程内风格（不启动 QProcess，CI 直接执行）；
像素断言用 sha256 对比，预览文件断言落在 --temp-dir。
"""
from __future__ import annotations

import hashlib
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

from python_worker import task_runtime
from python_worker.dispatcher import Dispatcher, WorkerContext
from python_worker.protocol import PROTOCOL_VERSION


def _request(action: str, params: dict | None = None, request_id: str = 'req-e') -> dict:
    return {'protocol': PROTOCOL_VERSION, 'request_id': request_id,
            'action': action, 'params': params or {}}


def _sha256_array(image: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest()


class WorkerEditTests(unittest.TestCase):
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

        opened = self.dispatcher.handle(_request('image.open', {'path': self.sample}))
        self.assertTrue(opened['success'], opened)
        self.document_id = opened['result']['document_id']
        self.source_sha = _sha256_array(self.doc().image)
        # 协议 §3.1：image.open 时 version = 0。
        self.assertEqual(self.doc().version, 0)

    # ---- 公共小工具 --------------------------------------------------------
    def doc(self):
        return self.ctx.store.get(self.document_id)

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

    # ---- 调整：预览 vs 全分辨率 --------------------------------------------
    def test_adjust_preview_writes_temp_file_without_bumping_version(self):
        result = self._run('image.adjust', {
            'document_id': self.document_id,
            'adjustments': {'brightness': 0.2, 'contrast': 0.1},
            'preview': True,
            'max_side': 32,
        })
        self.assertTrue(Path(result['path']).is_file())
        self.assertLessEqual(max(result['width'], result['height']), 32)
        self.assertTrue(result['sha256'])
        self.assertEqual(result['version'], 0)  # 预览携带当前版本但不递增
        # 预览不改文档：version、像素、历史、modified 均不变。
        self.assertEqual(self.doc().version, 0)
        self.assertEqual(_sha256_array(self.doc().image), self.source_sha)
        self.assertEqual(self.doc().undo_stack, [])
        self.assertFalse(self.doc().modified)
        self.assertEqual(self._history()['current'], 0)

    def test_adjust_fullres_undo_redo_reset_roundtrip(self):
        adjusted = self._run('image.adjust', {
            'document_id': self.document_id,
            'adjustments': {'brightness': 0.3},
            'preview': False,
        })
        self.assertEqual(adjusted['version'], 1)  # 全分辨率 → version+1
        self.assertNotIn('path', adjusted)        # 全分辨率不含预览文件字段
        self.assertNotIn('sha256', adjusted)
        self.assertTrue(self.doc().modified)
        adjusted_sha = _sha256_array(self.doc().image)
        self.assertNotEqual(adjusted_sha, self.source_sha)

        history = self._history()
        self.assertEqual([entry['name'] for entry in history['entries']],
                         ['open', 'image.adjust'])
        self.assertEqual(history['current'], 1)
        self.assertTrue(history['canUndo'])
        self.assertFalse(history['canRedo'])

        undone = self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(undone['version'], 2)  # undo 同样递增（§3.1）
        self.assertEqual(_sha256_array(self.doc().image), self.source_sha)  # 回到前态
        self.assertTrue(Path(undone['path']).is_file())  # completed 事件带预览 path
        self.assertTrue(undone['sha256'])
        self.assertEqual(undone['width'], 64)
        self.assertEqual(undone['height'], 64)

        redone = self._run('image.redo', {'document_id': self.document_id})
        self.assertEqual(redone['version'], 3)
        self.assertEqual(_sha256_array(self.doc().image), adjusted_sha)  # redo 前进
        self.assertTrue(Path(redone['path']).is_file())

        reset_result = self._run('image.reset', {'document_id': self.document_id})
        self.assertEqual(reset_result['version'], 4)
        self.assertEqual(_sha256_array(self.doc().image), self.source_sha)  # reset 回源图
        self.assertFalse(self.doc().modified)
        self.assertEqual(self.doc().undo_stack, [])
        self.assertEqual(self.doc().redo_stack, [])
        final = self._history()
        self.assertEqual(final['entries'], [{'index': 0, 'name': 'open'}])
        self.assertEqual(final['current'], 0)
        self.assertFalse(final['canUndo'])
        self.assertFalse(final['canRedo'])

    # ---- 变换 ---------------------------------------------------------------
    def test_transform_fullres_changes_dimensions_and_pushes_history(self):
        result = self._run('image.transform', {
            'document_id': self.document_id,
            'op': 'crop',
            'params': {'x': 8, 'y': 8, 'w': 32, 'h': 16},
            'preview': False,
        })
        self.assertEqual(result['width'], 32)   # rotate/scale/crop 改变尺寸
        self.assertEqual(result['height'], 16)
        self.assertEqual(result['version'], 1)
        # 通道数不锁定：文档以 RGBA 载入（processors/utils.py pil_to_np），
        # crop 保持通道不变，断言只看尺寸。
        self.assertEqual(self.doc().image.shape[:2], (16, 32))
        history = self._history()
        self.assertEqual([entry['name'] for entry in history['entries']],
                         ['open', 'image.transform'])
        self.assertTrue(history['canUndo'])

    def test_transform_preview_keeps_document_untouched(self):
        result = self._run('image.transform', {
            'document_id': self.document_id,
            'op': 'scale',
            'params': {'sx': 0.5},
            'preview': True,
            'max_side': 40,
        })
        self.assertLessEqual(max(result['width'], result['height']), 40)
        self.assertTrue(Path(result['path']).is_file())
        self.assertEqual(result['version'], 0)
        self.assertEqual(self.doc().image.shape[:2], (64, 64))  # 文档像素不变
        self.assertEqual(self.doc().version, 0)

    # ---- 变换：rotate（五个 op 中此前唯一未覆盖的一个）-----------------------
    def test_transform_rotate_fullres_changes_pixels_and_is_undoable(self):
        result = self._run('image.transform', {
            'document_id': self.document_id,
            'op': 'rotate',
            'params': {'angle': 90},
            'preview': False,
        })
        self.assertEqual(result['version'], 1)
        # 90° 旋转方形样本：尺寸不变、像素改变（rotate90 输出由引擎基线锁定，
        # tests/baselines/engine_baseline.json）。
        self.assertEqual(result['width'], 64)
        self.assertEqual(result['height'], 64)
        self.assertEqual(self.doc().image.shape[:2], (64, 64))
        rotated_sha = _sha256_array(self.doc().image)
        self.assertNotEqual(rotated_sha, self.source_sha)

        undone = self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(undone['version'], 2)
        self.assertEqual(_sha256_array(self.doc().image), self.source_sha)
        history = self._history()
        self.assertEqual([entry['name'] for entry in history['entries']],
                         ['open', 'image.transform'])
        self.assertEqual(history['current'], 0)
        self.assertTrue(history['canRedo'])  # undo 后 redo 分支保留 rotate 结果

    # ---- 栈空错误（提交前同步返回，不产生任务）-----------------------------
    def test_empty_stack_undo_redo_return_unredoable_synchronously(self):
        undo_response = self.dispatcher.handle(
            _request('image.undo', {'document_id': self.document_id}))
        self.assertFalse(undo_response['success'])
        self.assertEqual(undo_response['error']['code'], 'UNREDOABLE')
        redo_response = self.dispatcher.handle(
            _request('image.redo', {'document_id': self.document_id}))
        self.assertFalse(redo_response['success'])
        self.assertEqual(redo_response['error']['code'], 'UNREDOABLE')
        # 提交前拒绝：错误响应（无 result 字段），不产生 task_id，也没有任何任务事件。
        self.assertNotIn('result', undo_response)
        self.assertNotIn('result', redo_response)
        self.assertFalse([e for e in self.events if e.get('type', '').startswith('task')])
        self.assertEqual(self.doc().version, 0)  # 失败的 undo 不改版本

    # ---- 未知文档（UNKNOWN_DOCUMENT）：六动作的错误路径 ---------------------
    # undo/redo/reset/history 在提交任务前同步拒绝（dispatcher 工厂/handler 先取
    # 文档，python_worker/dispatcher.py _image_undo_job/_image_reset_job/
    # _image_history）；adjust / 非 crop transform 的文档存在性检查在任务体内，
    # 走异步 task.failed（任务运行时把一切任务体异常归一为 ENGINE_ERROR ——
    # WorkerError.code 不进事件，任务清单外行为，如实按现状断言）。
    def test_unknown_document_rejected_for_edit_actions(self):
        ghost = 'doc-ghost'
        sync_actions = ('image.undo', 'image.redo', 'image.reset', 'image.history')
        for action in sync_actions:
            response = self.dispatcher.handle(_request(action, {'document_id': ghost}))
            self.assertFalse(response['success'], action)
            self.assertEqual(response['error']['code'], 'UNKNOWN_DOCUMENT', action)
        # 同步拒绝不产生任何任务。
        self.assertFalse([e for e in self.events if e.get('type', '').startswith('task')])

        async_cases = (
            ('image.adjust', {'document_id': ghost, 'adjustments': {'brightness': 0.1},
                              'preview': True}),
            ('image.transform', {'document_id': ghost, 'op': 'flip_h', 'params': {},
                                 'preview': False}),
        )
        for action, params in async_cases:
            response = self.dispatcher.handle(_request(action, params))
            self.assertTrue(response['success'], (action, response))  # 受理成功
            event = self._wait_for_terminal(response['result']['task_id'])
            self.assertIsNotNone(event, action)
            self.assertEqual(event['type'], 'task.failed', (action, event))
            self.assertEqual(event['error']['code'], 'ENGINE_ERROR', (action, event))
            self.assertIn('文档不存在', event['error']['message'], action)

        # crop 的越界判定需要先取文档：未知文档在提交前同步拒绝（无任务）。
        crop = self.dispatcher.handle(_request('image.transform', {
            'document_id': ghost, 'op': 'crop',
            'params': {'x': 0, 'y': 0, 'w': 8, 'h': 8}, 'preview': False}))
        self.assertFalse(crop['success'])
        self.assertEqual(crop['error']['code'], 'UNKNOWN_DOCUMENT')

    # ---- reset：未编辑的文档同样成功（§3.1：reset 同样递增 version）---------
    def test_reset_without_history_succeeds_and_bumps_version(self):
        result = self._run('image.reset', {'document_id': self.document_id})
        self.assertEqual(result['version'], 1)  # 无历史也递增（version 与内容无关）
        self.assertEqual(_sha256_array(self.doc().image), self.source_sha)  # 像素即源图
        self.assertTrue(Path(result['path']).is_file())  # completed 仍带画布刷新文件
        self.assertTrue(result['sha256'])
        self.assertFalse(self.doc().modified)
        final = self._history()
        self.assertEqual(final['entries'], [{'index': 0, 'name': 'open'}])
        self.assertEqual(final['current'], 0)
        self.assertFalse(final['canUndo'])
        self.assertFalse(final['canRedo'])

    # ---- 历史视图随操作变化 -------------------------------------------------
    def test_history_tracks_operations_and_truncates_redo_branch(self):
        initial = self._history()
        self.assertEqual(initial['entries'], [{'index': 0, 'name': 'open'}])
        self.assertEqual(initial['current'], 0)
        self.assertFalse(initial['canUndo'])
        self.assertFalse(initial['canRedo'])

        self._run('image.transform', {
            'document_id': self.document_id, 'op': 'flip_h', 'params': {}, 'preview': False})
        self._run('image.adjust', {
            'document_id': self.document_id, 'adjustments': {'brightness': 0.1},
            'preview': False})
        after_two = self._history()
        self.assertEqual([entry['name'] for entry in after_two['entries']],
                         ['open', 'image.transform', 'image.adjust'])
        self.assertEqual(after_two['current'], 2)
        self.assertTrue(after_two['canUndo'])
        self.assertFalse(after_two['canRedo'])

        self._run('image.undo', {'document_id': self.document_id})
        after_undo = self._history()
        self.assertEqual(after_undo['current'], 1)
        self.assertTrue(after_undo['canUndo'])
        self.assertTrue(after_undo['canRedo'])  # redo 分支保留
        self.assertEqual(len(after_undo['entries']), 3)

        # 非栈顶的新变更：截断 redo 分支并追加新条目（§3.3）。
        self._run('image.transform', {
            'document_id': self.document_id, 'op': 'flip_v', 'params': {}, 'preview': False})
        after_branch = self._history()
        self.assertEqual([entry['name'] for entry in after_branch['entries']],
                         ['open', 'image.transform', 'image.transform'])
        self.assertEqual(after_branch['current'], 2)
        self.assertFalse(after_branch['canRedo'])

    # ---- 历史深度淘汰：§3.3 不变量在任意淘汰深度下保持 ---------------------
    # 预算压到约 2 个快照强制淘汰：验证 entries[0] 恒为 open、undo 到底像素
    # 回到源图、条目名与可达状态一一对齐（HistoryModel 点击跳转依赖此契约；
    # 底条目钉在源图上，被淘汰的动作名进 dropped_names，条目名绝不错位）。
    def test_history_trimming_keeps_open_floor_and_aligned_names(self):
        from python_worker.adapters.image_adapter import HistoryMixin

        self.assertEqual(HistoryMixin.HISTORY_BUDGET_BYTES, 512 * 1024 * 1024)
        store_cls = type(self.ctx.store)
        # 64×64 样本单快照 = image.nbytes；预算 2 快照 → 第 3 次 push 起淘汰。
        # 预算按类属性打补丁（DocumentStore 遮蔽 HistoryMixin），结束即删。
        store_cls.HISTORY_BUDGET_BYTES = 2 * self.doc().image.nbytes
        self.addCleanup(delattr, store_cls, 'HISTORY_BUDGET_BYTES')

        sha_after = {}
        for step, op in enumerate(('flip_h', 'flip_v', 'flip_h', 'flip_v'), start=1):
            result = self._run('image.transform', {
                'document_id': self.document_id, 'op': op, 'params': {}, 'preview': False})
            self.assertEqual(result['version'], step)
            sha_after[step] = _sha256_array(self.doc().image)

        history = self._history()
        self.assertEqual(history['entries'][0], {'index': 0, 'name': 'open'})
        # 底条目钉在源图，第 2/3 次快照被淘汰并记名：entries 只列可达状态，
        # 最后被淘汰的动作名对齐最旧幸存快照（第 3 次 flip 的产物）。
        self.assertEqual([entry['name'] for entry in history['entries']],
                         ['open', 'image.transform', 'image.transform'])
        self.assertEqual(history['current'], 2)
        self.assertTrue(history['canUndo'])
        self.assertFalse(history['canRedo'])

        undone1 = self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(undone1['version'], 5)
        self.assertEqual(_sha256_array(self.doc().image), sha_after[3])  # 最旧幸存快照

        undone2 = self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(undone2['version'], 6)
        self.assertEqual(_sha256_array(self.doc().image), self.source_sha)  # 钉住的 open 态

        final = self._history()
        self.assertEqual([entry['name'] for entry in final['entries']],
                         ['open', 'image.transform', 'image.transform'])  # redo 分支对齐
        self.assertEqual(final['current'], 0)
        self.assertFalse(final['canUndo'])
        self.assertTrue(final['canRedo'])

        # 重做按条目顺序逐级前进：先最旧幸存快照，再淘汰前栈顶。
        self._run('image.redo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), sha_after[3])
        self._run('image.redo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), sha_after[4])

    # ---- filter.apply 与历史的衔接（§3.3：filter.apply 也产生 undo 条目）----
    def test_filter_apply_pushes_history_version_and_is_undoable(self):
        from processors.filter_defs import FilterDefRegistry

        registry_keys = FilterDefRegistry.instance().keys()
        # 滤镜 key 以注册表实际内容为准，不猜测名字。
        filter_key = ('grayscale_standard' if 'grayscale_standard' in registry_keys
                      else registry_keys[0])
        result = self._run('filter.apply', {
            'document_id': self.document_id,
            'filters': [{'filter_key': filter_key, 'params': {}}],
        })
        self.assertEqual(result['version'], 1)  # filter.apply 结果新增 version（§3.1）
        history = self._history()
        self.assertEqual([entry['name'] for entry in history['entries']],
                         ['open', 'filter.apply'])
        self.assertTrue(history['canUndo'])

        self._run('image.undo', {'document_id': self.document_id})
        self.assertEqual(_sha256_array(self.doc().image), self.source_sha)

    # ---- 参数校验：提交前同步 INVALID_PARAMS --------------------------------
    def test_invalid_params_rejected_synchronously(self):
        cases = [
            ('image.adjust', {'document_id': self.document_id,
                              'adjustments': {}, 'preview': True}),
            ('image.adjust', {'document_id': self.document_id,
                              'adjustments': {'nope': 1.0}, 'preview': True}),
            ('image.adjust', {'document_id': self.document_id,
                              'adjustments': {'brightness': 'x'}, 'preview': True}),
            ('image.adjust', {'document_id': self.document_id,
                              'adjustments': {'brightness': 0.1}}),  # 缺 preview
            ('image.transform', {'document_id': self.document_id,
                                 'op': 'shear', 'params': {}, 'preview': False}),
            ('image.transform', {'document_id': self.document_id,
                                 'op': 'crop', 'params': {'x': 0, 'y': 0, 'w': 9999, 'h': 10},
                                 'preview': False}),  # 越界
            ('image.transform', {'document_id': self.document_id,
                                 'op': 'crop', 'params': {'x': 0, 'y': 0, 'w': 8},
                                 'preview': False}),  # 缺 h
            ('image.transform', {'document_id': self.document_id,
                                 'op': 'scale', 'params': {'sx': 0}, 'preview': False}),
        ]
        for action, params in cases:
            response = self.dispatcher.handle(_request(action, params))
            self.assertFalse(response['success'], (action, params))
            self.assertEqual(response['error']['code'], 'INVALID_PARAMS', (action, params))


if __name__ == '__main__':
    unittest.main()
