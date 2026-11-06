"""参数化 undo 与滑杆命令合并测试（docs/competitive-analysis.md §4 行动项 1/2）。

参数化 undo（ipc-protocol.md §3.3）：filter.apply 的历史条目只存链 steps 参数
（不存像素快照），undo/redo 从基线/最近快照锚点重放链；像素快照仅保留给
不可参数化操作（transform/crop 类，重放屏障）。合并（coalescing）：连续的
全分辨率 image.adjust 并作单条历史。

进程内风格（不启动 QProcess，CI 直接执行），参照 tests/test_worker_edit.py；
像素断言用 sha256 对比。链重放的确定性依据：processors 滤镜与 adjust_chain
均为纯函数（同输入 + 同参数 → bitwise 同输出），重放与原应用一致。
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


def _request(action: str, params: dict | None = None, request_id: str = 'req-h') -> dict:
    return {'protocol': PROTOCOL_VERSION, 'request_id': request_id,
            'action': action, 'params': params or {}}


def _sha256_array(image: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest()


class _CancelAfterN:
    """第 N 次 raise_if_cancelled 起抛 CancelledError 的确定性取消令牌：

    覆盖"重放中途取消"路径（真实 CancelToken 只能整段置位，无法在重放步进
    间精确定位）；其余接口与 processors.cancellation.CancelToken 同形。
    """

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


class WorkerParametricHistoryTests(unittest.TestCase):
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
        self.chain = [{'filter_key': self._filter_key(), 'params': {}}]

    # ---- 公共小工具 --------------------------------------------------------
    def doc(self):
        return self.ctx.store.get(self.document_id)

    @staticmethod
    def _filter_key() -> str:
        from processors.filter_defs import FilterDefRegistry

        registry_keys = FilterDefRegistry.instance().keys()
        # 滤镜 key 以注册表实际内容为准，不猜测名字（test_worker_edit 同款）。
        return ('grayscale_standard' if 'grayscale_standard' in registry_keys
                else registry_keys[0])

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

    def _adjust(self, adjustments: dict) -> dict:
        return self._run('image.adjust', {
            'document_id': self.document_id, 'adjustments': adjustments,
            'preview': False})

    def _apply_chain(self) -> dict:
        return self._run('filter.apply', {
            'document_id': self.document_id, 'filters': self.chain})

    def _transform(self, op: str) -> dict:
        return self._run('image.transform', {
            'document_id': self.document_id, 'op': op, 'params': {},
            'preview': False})

    def _undo(self) -> dict:
        return self._run('image.undo', {'document_id': self.document_id})

    def _redo(self) -> dict:
        return self._run('image.redo', {'document_id': self.document_id})

    # ---- 1. 历史条目含 steps 参数而非像素快照 ------------------------------
    def test_chain_entry_stores_steps_not_pixel_snapshot(self):
        self._apply_chain()
        stack = self.doc().undo_stack
        self.assertEqual(len(stack), 1)
        entry = stack[0]
        self.assertEqual(entry.name, 'filter.apply')
        self.assertIsNone(entry.pixels)  # 参数化条目：不保留像素快照
        self.assertEqual(entry.replay, {'kind': 'chain', 'steps': self.chain})
        history = self._history()
        self.assertEqual([e['name'] for e in history['entries']],
                         ['open', 'filter.apply'])
        self.assertTrue(history['canUndo'])

    # ---- 2. 链应用 → undo → 像素与基线一致 ---------------------------------
    def test_chain_undo_restores_baseline_pixels(self):
        self._apply_chain()
        self.assertNotEqual(_sha256_array(self.doc().image), self.source_sha)
        undone = self._undo()
        self.assertEqual(undone['version'], 2)  # undo 同样递增（§3.1）
        self.assertEqual(_sha256_array(self.doc().image), self.source_sha)
        self.assertTrue(Path(undone['path']).is_file())  # completed 仍带画布刷新文件
        self.assertEqual(self.doc().redo_stack[0].replay['steps'], self.chain)

    def test_chain_undo_redo_roundtrip_replays_identical_pixels(self):
        self._apply_chain()
        applied_sha = _sha256_array(self.doc().image)
        self._undo()
        self._redo()
        self.assertEqual(_sha256_array(self.doc().image), applied_sha)

    # ---- 3. 连续链：undo 从基线重放（栈内全程无像素快照）-------------------
    def test_two_chains_undo_replays_from_baseline(self):
        self._apply_chain()
        after_first = _sha256_array(self.doc().image)
        self._apply_chain()
        after_second = _sha256_array(self.doc().image)
        self.assertEqual([e.pixels for e in self.doc().undo_stack], [None, None])

        self._undo()  # 撤销 chain2：基线 + 重放 chain1（无快照可恢复）
        self.assertEqual(_sha256_array(self.doc().image), after_first)
        self._undo()  # 撤销 chain1：直达源图基线
        self.assertEqual(_sha256_array(self.doc().image), self.source_sha)
        self._redo()
        self.assertEqual(_sha256_array(self.doc().image), after_first)
        self._redo()
        self.assertEqual(_sha256_array(self.doc().image), after_second)

    # ---- 4. adjust 锚点：undo 链 = 从 adjust 快照重放 adjust ----------------
    def test_adjust_then_chain_undo_replays_adjust_anchor(self):
        self._adjust({'brightness': 0.3})
        post_adjust_sha = _sha256_array(self.doc().image)
        self.assertEqual(self.doc().undo_stack[0].replay,
                         {'kind': 'adjust', 'applies': [{'brightness': 0.3}]})
        self._apply_chain()
        self.assertNotEqual(_sha256_array(self.doc().image), post_adjust_sha)

        self._undo()  # 撤销链：从 adjust 快照重放 adjust（快照存的是 adjust 前）
        self.assertEqual(_sha256_array(self.doc().image), post_adjust_sha)
        self._undo()  # 撤销 adjust：快照直达基线
        self.assertEqual(_sha256_array(self.doc().image), self.source_sha)

    # ---- 5. transform 重放屏障：链条目退化为快照，undo 直达 ----------------
    def test_transform_barrier_pins_chain_entry_to_snapshot(self):
        self._transform('flip_h')
        post_transform_sha = _sha256_array(self.doc().image)
        self._apply_chain()
        stack = self.doc().undo_stack
        self.assertEqual([e.name for e in stack], ['image.transform', 'filter.apply'])
        self.assertIsNotNone(stack[1].pixels)  # 屏障之上链条目退化为快照条目
        self.assertIsNone(stack[1].replay)
        self._undo()
        self.assertEqual(_sha256_array(self.doc().image), post_transform_sha)

    # ---- 6. 滑杆命令合并（coalescing）---------------------------------------
    def test_consecutive_adjusts_coalesce_into_single_entry(self):
        self._adjust({'brightness': 0.2})
        self._adjust({'contrast': 0.3})
        compounded_sha = _sha256_array(self.doc().image)

        stack = self.doc().undo_stack
        self.assertEqual(len(stack), 1)  # 两次应用一条历史
        self.assertEqual(stack[0].replay,
                         {'kind': 'adjust',
                          'applies': [{'brightness': 0.2}, {'contrast': 0.3}]})
        history = self._history()
        self.assertEqual([e['name'] for e in history['entries']],
                         ['open', 'image.adjust'])
        self.assertEqual(history['current'], 1)

        self._undo()  # 一次 undo 越过两次应用，直达基线
        self.assertEqual(_sha256_array(self.doc().image), self.source_sha)
        self._redo()  # 重做按快照像素精确复原合并后的状态
        self.assertEqual(_sha256_array(self.doc().image), compounded_sha)

    def test_merge_breaks_on_intervening_action(self):
        self._adjust({'brightness': 0.2})
        self._transform('flip_h')
        self._adjust({'contrast': 0.1})
        stack = self.doc().undo_stack
        self.assertEqual([e.name for e in stack],
                         ['image.adjust', 'image.transform', 'image.adjust'])
        self.assertEqual(stack[0].replay['applies'], [{'brightness': 0.2}])
        self.assertEqual(stack[2].replay['applies'], [{'contrast': 0.1}])

    def test_merge_not_applied_after_undo(self):
        # undo 后 redo 栈非空：新 adjust 不并入已撤销的条目（否则条目内重放
        # 序列与实况像素不一致），redo 分支按 §3.3 截断。
        self._adjust({'brightness': 0.2})
        self._undo()
        self._adjust({'contrast': 0.1})
        stack = self.doc().undo_stack
        self.assertEqual(len(stack), 1)
        self.assertEqual(stack[0].replay['applies'], [{'contrast': 0.1}])
        self.assertFalse(self._history()['canRedo'])
        self._undo()
        self.assertEqual(_sha256_array(self.doc().image), self.source_sha)

    def test_merged_adjust_replays_exactly_through_chain_undo(self):
        # 合并条目作为锚点：其上链条目 undo 时按 applies 顺序重放两段调整，
        # 必须逐位复原"两段依次应用"的复合状态（而非单段参数的一次应用）。
        self._adjust({'brightness': 0.2})
        self._adjust({'contrast': 0.3})
        compounded_sha = _sha256_array(self.doc().image)
        self._apply_chain()
        self._undo()
        self.assertEqual(_sha256_array(self.doc().image), compounded_sha)

    # ---- 7. 字节预算只计快照条目；参数段整段淘汰保持重放完整性 --------------
    def test_budget_counts_snapshots_only(self):
        store_cls = type(self.ctx.store)
        store_cls.HISTORY_BUDGET_BYTES = 2 * self.doc().image.nbytes
        self.addCleanup(delattr, store_cls, 'HISTORY_BUDGET_BYTES')

        self._adjust({'brightness': 0.2})  # 1 快照
        self._apply_chain()
        self._apply_chain()
        after_two_chains_sha = _sha256_array(self.doc().image)
        self._apply_chain()  # 链条目零像素：预算不淘汰（快照仍只有 1 份）
        self.assertEqual(len(self.doc().undo_stack), 4)
        self.assertEqual([e.pixels is None for e in self.doc().undo_stack],
                         [False, True, True, True])

        self._undo()  # 撤销 chain3：从 adjust 锚点重放 adjust + chain1 + chain2
        self.assertEqual(_sha256_array(self.doc().image), after_two_chains_sha)
        history = self._history()
        self.assertEqual([e['name'] for e in history['entries']],
                         ['open', 'image.adjust', 'filter.apply', 'filter.apply',
                          'filter.apply'])
        self.assertEqual(history['current'], 3)

    def test_trim_drops_replay_run_intactly_and_keeps_invariants(self):
        store_cls = type(self.ctx.store)
        store_cls.HISTORY_BUDGET_BYTES = 2 * self.doc().image.nbytes
        self.addCleanup(delattr, store_cls, 'HISTORY_BUDGET_BYTES')

        sha_after = {}
        self._apply_chain()                                    # E0 参数化（0 快照）
        self._adjust({'brightness': 0.2})                      # E1 快照（第 1）
        self._apply_chain()                                    # E2 参数化
        self._apply_chain()                                    # E3 参数化
        sha_after['chain3'] = _sha256_array(self.doc().image)
        self._transform('flip_h')                              # E4 快照（第 2，触顶）
        sha_after['flip1'] = _sha256_array(self.doc().image)
        self._transform('flip_v')                              # E5 快照（第 3 → 淘汰）

        # 淘汰：底为参数化条目（无像素可钉）→ 弹出 E1（adjust 快照）时其上
        # 参数段 E2/E3 整段随行；E4 快照次步弹出。可达状态只剩 S0/S4/S5。
        stack = self.doc().undo_stack
        self.assertEqual([e.name for e in stack],
                         ['filter.apply', 'image.transform', 'image.transform'])
        self.assertIsNone(stack[0].pixels)  # E0 参数化条目仍在栈底（undo 底 = 基线重放）
        self.assertEqual(self.doc().dropped_names,
                         ['image.adjust', 'filter.apply', 'filter.apply'])
        history = self._history()
        self.assertEqual([e['name'] for e in history['entries']],
                         ['open', 'filter.apply', 'image.transform', 'image.transform'])

        self._undo()
        self.assertEqual(_sha256_array(self.doc().image), sha_after['flip1'])
        self._undo()  # E4 快照：回到 chain3 后状态
        self.assertEqual(_sha256_array(self.doc().image), sha_after['chain3'])
        self._undo()  # 底部参数化条目：基线（重放范围为空）
        self.assertEqual(_sha256_array(self.doc().image), self.source_sha)
        # 命名职责随改名转移到复合 redo 条目：dropped_names 就此清空，其后新
        # 动作的条目名不会被 history() 的 dropped_names 分支吞掉（§3.3 对齐）。
        self.assertEqual(self.doc().dropped_names, [])
        self._redo()  # 复合 redo 条目：回到最后一个被淘汰动作的产物（快照直达）
        self.assertEqual(_sha256_array(self.doc().image), sha_after['chain3'])
        # 复合 redo 条目必须是无 replay 的重放屏障：其上新推的链退化为快照
        # 条目，undo 逐位一致。若随行底条目的陈旧 replay，此处会以复合快照为
        # 锚点重放底动作的陈旧参数，静默复原出错误像素。
        self.assertIsNone(self.doc().undo_stack[0].replay)
        self._apply_chain()
        # §3.3：新变更加入即截断 redo 分支——此前的 flip 复合 redo 条目在本次
        # 链应用后已不可重做，故本轮 undo/redo 往返的目标态是"本次链应用之后"
        # 的状态（灰度滤镜 float32 截断非幂等，链再应用像素仍会变化），在
        # 应用后立即采集；redo 只须与该状态逐位一致（快照条目 1.0 语义）。
        reapplied_sha = _sha256_array(self.doc().image)
        stack = self.doc().undo_stack
        self.assertEqual([e.name for e in stack], ['filter.apply', 'filter.apply'])
        self.assertIsNotNone(stack[1].pixels)  # 屏障之上退化为快照条目
        self.assertIsNone(stack[1].replay)
        self._undo()
        self.assertEqual(_sha256_array(self.doc().image), sha_after['chain3'])
        self._redo()
        self.assertEqual(_sha256_array(self.doc().image), reapplied_sha)

    # ---- 8. 取消：compute-before-commit，重放中途取消不动文档 ----------------
    def test_cancelled_replay_leaves_document_untouched(self):
        from processors.cancellation import CancelledError

        self._apply_chain()
        self._apply_chain()
        doc = self.doc()
        # 像素基线在调用 undo 前采集：灰度滤镜 float32 截断管线非幂等
        # （L×(0.299f+0.587f+0.114f) 经 float32 舍入后 u8 截断，13/256 灰阶
        # 再应用会 -1），两次链应用位不相等，取消的 undo 应把像素留在
        # "最近一次链应用之后"的状态——本测试锁的是 compute-before-commit
        # （取消既不动栈也不动像素），与滤镜自身的幂等性无关。
        baseline_sha = _sha256_array(doc.image)

        store = self.ctx.store
        with self.assertRaises(CancelledError):  # 第一步重放前即取消
            store.undo(doc, cancel_token=_CancelAfterN(1))
        self.assertEqual(len(doc.undo_stack), 2)  # 栈未动
        self.assertEqual(_sha256_array(doc.image), baseline_sha)  # 像素未动
        self.assertEqual(doc.redo_stack, [])

        with self.assertRaises(CancelledError):  # 重放第一步的步进边界取消
            store.undo(doc, cancel_token=_CancelAfterN(2))
        self.assertEqual(len(doc.undo_stack), 2)
        self.assertEqual(_sha256_array(doc.image), baseline_sha)
        self.assertEqual(doc.redo_stack, [])


if __name__ == '__main__':
    unittest.main()
