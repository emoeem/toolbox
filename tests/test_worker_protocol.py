"""Worker 协议与任务运行时测试（docs/ipc-protocol.md）。

这些测试纯进程内运行（不启动 QProcess），CI 可直接执行；
跨进程端到端验收由 docs/phase3-acceptance.md 的清单在 Linux 环境执行。
"""
from __future__ import annotations

import json
import unittest

import python_worker.protocol as protocol
from python_worker import task_runtime
from python_worker.adapters import filter_adapter
from python_worker.adapters.image_adapter import DocumentStore, WorkerError
from python_worker.dispatcher import Dispatcher, WorkerContext


def _request(action: str, params: dict | None = None, request_id: str = 'req-t') -> dict:
    return {'protocol': protocol.PROTOCOL_VERSION, 'request_id': request_id,
            'action': action, 'params': params or {}}


class CodecTests(unittest.TestCase):
    def test_encode_decode_roundtrip(self):
        req = _request('image.open', {'path': '/tmp/a.png'}, 'req-1')
        line = protocol.encode(req)
        self.assertTrue(line.endswith('\n'))
        decoded = protocol.decode(line)
        self.assertEqual(decoded['request_id'], 'req-1')
        self.assertEqual(decoded['action'], 'image.open')

    def test_decode_rejects_bad_json(self):
        with self.assertRaises(protocol.ProtocolError) as ctx:
            protocol.decode('{not json')
        self.assertEqual(ctx.exception.code, protocol.ERR_PARSE)

    def test_decode_rejects_wrong_protocol_version(self):
        with self.assertRaises(protocol.ProtocolError) as ctx:
            protocol.decode(protocol.encode({**_request('worker.hello'), 'protocol': 99}))
        self.assertEqual(ctx.exception.code, protocol.ERR_PROTOCOL_MISMATCH)

    def test_decode_rejects_missing_fields(self):
        for bad in (
            json.dumps({'protocol': 1, 'action': 'a'}),               # 缺 request_id
            json.dumps({'protocol': 1, 'request_id': 'r'}),           # 缺 action
            json.dumps({'request_id': 'r', 'action': 'a'}),           # 缺 protocol
        ):
            with self.assertRaises(protocol.ProtocolError):
                protocol.decode(bad)

    def test_events_skip_request_validation(self):
        progress = protocol.make_progress('task-1', 50)
        self.assertIsNone(protocol.validate_request(progress))


class DispatcherSyncTests(unittest.TestCase):
    def setUp(self):
        self.ctx = WorkerContext()
        self.ctx.runtime = task_runtime.TaskRuntime(max_workers=1)
        self.dispatcher = Dispatcher(self.ctx)

    def tearDown(self):
        self.ctx.runtime.shutdown()

    def test_hello(self):
        response = self.dispatcher.handle(_request('worker.hello', {}, 'h1'))
        self.assertTrue(response['success'])
        self.assertEqual(response['result']['protocol'], protocol.PROTOCOL_VERSION)
        self.assertIn('engine', response['result'])

    def test_unknown_action(self):
        response = self.dispatcher.handle(_request('no.such.action', {}, 'u1'))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], protocol.ERR_UNKNOWN_ACTION)

    def test_invalid_params_shape(self):
        request = _request('image.open', {'path': 123}, 'p1')
        response = self.dispatcher.handle(request)
        self.assertFalse(response['success'])
        self.assertIn(response['error']['code'], {protocol.ERR_INVALID_PARAMS, protocol.ERR_FILE_NOT_FOUND})

    def test_open_missing_file(self):
        response = self.dispatcher.handle(_request('image.open', {'path': '/nonexistent/x.png'}))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], protocol.ERR_FILE_NOT_FOUND)

    def test_image_open_close_metadata_roundtrip(self):
        from tools.make_test_samples import generate
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            generate(Path(tmp), force=True)
            sample = str(Path(tmp) / 'gradient.png')

            opened = self.dispatcher.handle(_request('image.open', {'path': sample}))
            self.assertTrue(opened['success'], opened)
            document_id = opened['result']['document_id']

            meta = self.dispatcher.handle(_request('image.metadata', {'document_id': document_id}))
            self.assertTrue(meta['success'])
            self.assertEqual(meta['result']['width'], 64)
            self.assertEqual(meta['result']['height'], 64)

            closed = self.dispatcher.handle(_request('image.close', {'document_id': document_id}))
            self.assertTrue(closed['success'])
            after = self.dispatcher.handle(_request('image.metadata', {'document_id': document_id}))
            self.assertEqual(after['error']['code'], protocol.ERR_UNKNOWN_DOCUMENT)

    def test_filter_list_nonempty_with_params(self):
        response = self.dispatcher.handle(_request('filter.list', {}))
        self.assertTrue(response['success'])
        filters = response['result']['filters']
        self.assertGreater(len(filters), 0)
        first = filters[0]
        for field in ('key', 'name', 'category', 'params', 'available'):
            self.assertIn(field, first)


class DispatcherAsyncTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path

        from tools.make_test_samples import generate

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        generate(Path(self.tmp.name), force=True)
        self.sample = str(Path(self.tmp.name) / 'gradient.png')

        self.ctx = WorkerContext(temp_dir=Path(self.tmp.name))
        self.events: list[dict] = []
        self.ctx.runtime = task_runtime.TaskRuntime(max_workers=1, emitter=self.events.append)
        self.dispatcher = Dispatcher(self.ctx)

        opened = self.dispatcher.handle(_request('image.open', {'path': self.sample}))
        self.assertTrue(opened['success'], opened)
        self.document_id = opened['result']['document_id']

        from processors.filter_defs import FilterDefRegistry
        registry_keys = FilterDefRegistry.instance().keys()
        # 滤镜 key 以注册表实际内容为准，不猜测名字。
        self.filter_key = 'grayscale_standard' if 'grayscale_standard' in registry_keys else registry_keys[0]

    def tearDown(self):
        self.ctx.runtime.shutdown()

    def _wait_for_terminal(self, task_id: str, timeout: float = 15.0) -> dict | None:
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for event in self.events:
                if event.get('task_id') == task_id and event.get('type') in ('task.completed', 'task.failed'):
                    return event
            time.sleep(0.02)
        return None

    def test_filter_preview_produces_temp_file(self):
        from pathlib import Path

        request = _request('filter.preview', {
            'document_id': self.document_id,
            'filters': [{'filter_key': self.filter_key, 'params': {}}],
            'max_side': 64,
        })
        response = self.dispatcher.handle(request)
        self.assertTrue(response['success'], response)
        task_id = response['result']['task_id']

        event = self._wait_for_terminal(task_id)
        self.assertIsNotNone(event, '预览任务未在超时前完成')
        self.assertEqual(event['type'], 'task.completed', event)
        self.assertTrue(Path(event['result']['path']).is_file())
        self.assertLessEqual(max(event['result']['width'], event['result']['height']), 64)

    def test_filter_apply_updates_document(self):
        meta_before = self.dispatcher.handle(_request('image.metadata', {'document_id': self.document_id}))
        request = _request('filter.apply', {
            'document_id': self.document_id,
            'filters': [{'filter_key': self.filter_key, 'params': {}}],
        })
        response = self.dispatcher.handle(request)
        self.assertTrue(response['success'], response)
        event = self._wait_for_terminal(response['result']['task_id'])
        self.assertIsNotNone(event)
        self.assertEqual(event['type'], 'task.completed', event)
        self.assertEqual(event['result']['width'], meta_before['result']['width'])

        meta_after = self.dispatcher.handle(_request('image.metadata', {'document_id': self.document_id}))
        self.assertTrue(meta_after['result']['modified'])

    def test_task_cancel_reaches_terminal_state(self):
        import time

        request = _request('filter.preview', {
            'document_id': self.document_id,
            'filters': [{'filter_key': self.filter_key, 'params': {}}],
            'max_side': 32,
        })
        response = self.dispatcher.handle(request)
        task_id = response['result']['task_id']
        self.dispatcher.handle(_request('task.cancel', {'task_id': task_id}))
        event = self._wait_for_terminal(task_id)
        self.assertIsNotNone(event)
        # 取消是协作式的：极小图可能先于取消检查完成，两种终结都合法。
        if event['type'] == 'task.failed':
            self.assertEqual(event['error']['code'], protocol.ERR_CANCELLED)
        else:
            self.assertEqual(event['type'], 'task.completed')


class TaskRuntimeTests(unittest.TestCase):
    def test_status_transitions_and_progress(self):
        events: list[dict] = []
        runtime = task_runtime.TaskRuntime(max_workers=1, emitter=events.append)

        def job(progress_cb, cancel_token):
            progress_cb(50)
            return {'done': True}

        submitted = runtime.submit('test', job)
        task_id = submitted['task_id']
        # 极小任务可能在 submit 返回前已被线程池跑完：状态是快照而非承诺。
        self.assertIn(submitted['status'],
                      (task_runtime.STATUS_QUEUED, task_runtime.STATUS_RUNNING, task_runtime.STATUS_COMPLETED))

        deadline = __import__('time').monotonic() + 5
        while __import__('time').monotonic() < deadline:
            state = runtime.query(task_id)
            if state and state['status'] == task_runtime.STATUS_COMPLETED:
                break
        self.assertEqual(runtime.query(task_id)['status'], task_runtime.STATUS_COMPLETED)
        progress_events = [e for e in events if e['type'] == 'task.progress']
        self.assertTrue(progress_events)
        completed = [e for e in events if e['type'] == 'task.completed']
        self.assertTrue(completed)
        runtime.shutdown()

    def test_progress_throttled(self):
        events: list[dict] = []
        runtime = task_runtime.TaskRuntime(max_workers=1, emitter=events.append)

        def job(progress_cb, cancel_token):
            for i in range(10):
                progress_cb(i * 10)  # 无间隔连发 → 应被节流
            return {}

        runtime.submit('throttle', job)
        __import__('time').sleep(0.5)
        runtime.shutdown()
        progress_events = [e for e in events if e['type'] == 'task.progress']
        self.assertLessEqual(len(progress_events), 3, '进度事件未按 100ms 节流')


class DocumentStoreTests(unittest.TestCase):
    def test_unknown_document_raises_worker_error(self):
        store = DocumentStore()
        with self.assertRaises(WorkerError) as ctx:
            store.get('doc-nope')
        self.assertEqual(ctx.exception.code, 'UNKNOWN_DOCUMENT')


class FilterAdapterTests(unittest.TestCase):
    def test_build_chain_rejects_unknown_key(self):
        with self.assertRaises(WorkerError) as ctx:
            filter_adapter.build_chain([{'filter_key': 'no-such-filter', 'params': {}}])
        self.assertEqual(ctx.exception.code, 'INVALID_PARAMS')

    def test_build_chain_accepts_real_filter(self):
        import processors  # 注册滤镜

        keys = processors.filter_defs.FilterDefRegistry.instance().keys()
        self.assertTrue(keys)
        chain = filter_adapter.build_chain([{'filter_key': keys[0], 'params': {}}])
        self.assertGreaterEqual(len(chain), 1)

    def test_chain_fingerprint_stable(self):
        steps = [{'filter_key': 'brightness', 'params': {'value': 0.1}}]
        self.assertEqual(filter_adapter.chain_fingerprint(steps),
                         filter_adapter.chain_fingerprint([{'params': {'value': 0.1}, 'filter_key': 'brightness'}]))


if __name__ == '__main__':
    unittest.main()
