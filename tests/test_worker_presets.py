"""filter.presets.* 动作测试（docs/ipc-protocol.md §3.4）。

进程内直接调 dispatcher（模式同 tests/test_worker_protocol.py 的
DispatcherSyncTests），不启动 QProcess。预设存储路径重定向到临时目录
（patch processors.filter_presets._preset_store_path）——"list 空初始"
不依赖真实用户数据，也不触碰 ~/.toolbox/filter_presets 与 QSettings。
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import processors  # noqa: F401  触发滤镜注册（FilterDefRegistry 填充）
import python_worker.protocol as protocol
import processors.filter_presets as preset_store
from python_worker import task_runtime
from python_worker.dispatcher import Dispatcher, WorkerContext


def _request(action: str, params: dict | None = None, request_id: str = 'req-p') -> dict:
    return {'protocol': protocol.PROTOCOL_VERSION, 'request_id': request_id,
            'action': action, 'params': params or {}}


class DispatcherPresetTests(unittest.TestCase):
    """filter.presets.list / save / load / delete（sync，协议 §3.4）。"""

    @classmethod
    def setUpClass(cls):
        from processors.filter_defs import FilterDefRegistry
        keys = FilterDefRegistry.instance().keys()
        assert keys, '滤镜注册表为空——processors 注册异常'
        # 滤镜 key 以注册表实际内容为准，不猜测名字（同 test_worker_protocol.py）。
        cls.key_a = 'grayscale_standard' if 'grayscale_standard' in keys else keys[0]
        cls.key_b = next((k for k in keys if k != cls.key_a), cls.key_a)

    def setUp(self):
        # 存储重定向：每个用例独立空目录；_preset_file_path/save/load/list/delete
        # 都经该函数取路径，单点 patch 即全覆盖。
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(preset_store, '_preset_store_path',
                                    return_value=Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)

        self.ctx = WorkerContext()
        self.ctx.runtime = task_runtime.TaskRuntime(max_workers=1)
        self.dispatcher = Dispatcher(self.ctx)

    def tearDown(self):
        self.ctx.runtime.shutdown()

    def test_list_starts_empty(self):
        response = self.dispatcher.handle(_request('filter.presets.list', {}))
        self.assertTrue(response['success'], response)
        self.assertEqual(response['result']['presets'], [])

    def test_save_two_then_list_counts(self):
        saved = self.dispatcher.handle(_request('filter.presets.save', {
            'name': '链 A',
            'steps': [
                {'filter_key': self.key_a, 'params': {'strength': 0.5}, 'enabled': True},
                {'filter_key': self.key_b, 'params': {}, 'enabled': False},
            ]}))
        self.assertTrue(saved['success'], saved)
        self.assertEqual(saved['result'], {'saved': True, 'name': '链 A'})

        saved_b = self.dispatcher.handle(_request('filter.presets.save', {
            'name': '链 B',
            'steps': [{'filter_key': self.key_a, 'params': {}}]}))  # enabled 缺省 True
        self.assertTrue(saved_b['success'], saved_b)

        listing = self.dispatcher.handle(_request('filter.presets.list', {}))
        self.assertTrue(listing['success'], listing)
        presets = listing['result']['presets']
        self.assertEqual(len(presets), 2)
        by_name = {p['name']: p for p in presets}
        self.assertEqual(by_name['链 A']['step_count'], 2)
        self.assertEqual(by_name['链 B']['step_count'], 1)
        for item in presets:  # 协议只暴露 name/step_count（§3.4）
            self.assertEqual(set(item.keys()), {'name', 'step_count'})

    def test_load_roundtrip_filter_step_fields(self):
        steps = [
            {'filter_key': self.key_a, 'params': {'strength': 0.5}, 'enabled': True},
            {'filter_key': self.key_b, 'params': {}, 'enabled': False},
        ]
        saved = self.dispatcher.handle(_request('filter.presets.save',
                                                {'name': 'roundtrip', 'steps': steps}))
        self.assertTrue(saved['success'], saved)

        loaded = self.dispatcher.handle(_request('filter.presets.load', {'name': 'roundtrip'}))
        self.assertTrue(loaded['success'], loaded)
        self.assertEqual(loaded['result']['name'], 'roundtrip')
        loaded_steps = loaded['result']['steps']
        self.assertEqual(len(loaded_steps), len(steps))
        for want, got in zip(steps, loaded_steps):  # FilterStep 字段一致（§3.4）
            self.assertEqual(got['filter_key'], want['filter_key'])
            self.assertEqual(got['params'], want['params'])
            self.assertEqual(got['enabled'], want['enabled'])

    def test_save_invalid_steps_is_invalid_params(self):
        for bad_steps in (
            'not-a-list',                                  # steps 非数组
            [{'params': {}}],                              # 缺 filter_key
            [{'filter_key': self.key_a, 'params': 123}],   # params 形状非法
        ):
            response = self.dispatcher.handle(_request('filter.presets.save', {
                'name': 'bad', 'steps': bad_steps}))
            self.assertFalse(response['success'])
            self.assertEqual(response['error']['code'], protocol.ERR_INVALID_PARAMS)

    def test_save_empty_name_is_invalid_params(self):
        for bad_name in ('', '   '):
            response = self.dispatcher.handle(_request('filter.presets.save', {
                'name': bad_name, 'steps': []}))
            self.assertFalse(response['success'])
            self.assertEqual(response['error']['code'], protocol.ERR_INVALID_PARAMS)

    def test_load_missing_is_file_not_found(self):
        response = self.dispatcher.handle(_request('filter.presets.load',
                                                   {'name': 'no_such_preset'}))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], protocol.ERR_FILE_NOT_FOUND)

    def test_delete_then_list_decrements(self):
        for name, key in (('doomed', self.key_a), ('keeper', self.key_b)):
            saved = self.dispatcher.handle(_request('filter.presets.save', {
                'name': name,
                'steps': [{'filter_key': key, 'params': {}, 'enabled': True}]}))
            self.assertTrue(saved['success'], saved)

        deleted = self.dispatcher.handle(_request('filter.presets.delete', {'name': 'doomed'}))
        self.assertTrue(deleted['success'], deleted)
        self.assertEqual(deleted['result'], {'deleted': True})

        listing = self.dispatcher.handle(_request('filter.presets.list', {}))
        self.assertTrue(listing['success'], listing)
        names = [p['name'] for p in listing['result']['presets']]
        self.assertNotIn('doomed', names)
        self.assertEqual(names, ['keeper'])  # 2 → 1（list 递减）

    def test_delete_missing_is_file_not_found(self):
        response = self.dispatcher.handle(_request('filter.presets.delete',
                                                   {'name': 'no_such_preset'}))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], protocol.ERR_FILE_NOT_FOUND)

    # ---- 覆盖缺口补齐（对照 filter_adapter.py 四动作全路径逐一核对）----------

    def test_save_nonstring_name_is_invalid_params(self):
        # _require_preset_name（filter_adapter.py:182-185）：非字符串先拒。
        for bad_name in (None, 123, ['链']):
            response = self.dispatcher.handle(_request('filter.presets.save', {
                'name': bad_name, 'steps': []}))
            self.assertFalse(response['success'], bad_name)
            self.assertEqual(response['error']['code'], protocol.ERR_INVALID_PARAMS)

    def test_save_same_name_overwrites(self):
        # 协议 §3.4：同名预设直接覆盖（存储层 overwrite=True 语义），不返回
        # FileExists 类错误；list 条目数不变、step_count 跟随新链。
        first = self.dispatcher.handle(_request('filter.presets.save', {
            'name': 'overwritten',
            'steps': [{'filter_key': self.key_a, 'params': {}, 'enabled': True},
                      {'filter_key': self.key_b, 'params': {}, 'enabled': True}]}))
        self.assertTrue(first['success'], first)

        second = self.dispatcher.handle(_request('filter.presets.save', {
            'name': 'overwritten',
            'steps': [{'filter_key': self.key_b, 'params': {}, 'enabled': True}]}))
        self.assertTrue(second['success'], second)
        self.assertEqual(second['result'], {'saved': True, 'name': 'overwritten'})

        listing = self.dispatcher.handle(_request('filter.presets.list', {}))
        presets = listing['result']['presets']
        self.assertEqual(len(presets), 1)  # 覆盖而非新增
        self.assertEqual(presets[0]['name'], 'overwritten')
        self.assertEqual(presets[0]['step_count'], 1)

    def test_save_non_dict_step_is_invalid_params(self):
        # FilterStep.from_dict 需要 dict（processors/filter_chain.py:59-60）：
        # 数组元素本身不是对象同样归一 INVALID_PARAMS。
        for bad_steps in ([42], ['step'], [None]):
            response = self.dispatcher.handle(_request('filter.presets.save', {
                'name': 'bad', 'steps': bad_steps}))
            self.assertFalse(response['success'], bad_steps)
            self.assertEqual(response['error']['code'], protocol.ERR_INVALID_PARAMS)

    def test_load_invalid_name_is_invalid_params(self):
        # load 与 delete 共用 _require_preset_name：空白/非字符串本地拒绝。
        for bad_name in ('', '   ', None, 42):
            for action in ('filter.presets.load', 'filter.presets.delete'):
                response = self.dispatcher.handle(_request(action, {'name': bad_name}))
                self.assertFalse(response['success'], (action, bad_name))
                self.assertEqual(response['error']['code'], protocol.ERR_INVALID_PARAMS)

    def _preset_file(self, name: str) -> Path:
        # _preset_store_path 已在 setUp patch 到 self.tmp.name；
        # 文件名净化沿用存储层 _preset_filename（filter_presets.py:37-41）。
        return Path(self.tmp.name) / preset_store._preset_filename(name)

    def test_load_corrupt_file_is_engine_error(self):
        # 文件损坏（非 JSON）→ ENGINE_ERROR（filter_adapter.py:165-166；
        # json.JSONDecodeError 是 ValueError 子类）。
        self._preset_file('broken').write_text('{not json', encoding='utf-8')
        response = self.dispatcher.handle(_request('filter.presets.load',
                                                   {'name': 'broken'}))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], protocol.ERR_ENGINE_ERROR)
        self.assertIn('预设文件无法解析', response['error']['message'])

    def test_load_future_schema_version_is_engine_error(self):
        # schema_version 高于当前支持 → ENGINE_ERROR（filter_presets.py:134-136），
        # 内容问题而非请求参数问题（协议 §3.4）。
        self._preset_file('future').write_text(
            json.dumps({'schema_version': 999, 'name': 'future',
                        'chain': {'steps': []}}),
            encoding='utf-8')
        response = self.dispatcher.handle(_request('filter.presets.load',
                                                   {'name': 'future'}))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], protocol.ERR_ENGINE_ERROR)
        self.assertIn('schema_version', response['error']['message'])

    def test_delete_storage_error_is_engine_error(self):
        # 存储层 OSError（权限等）如实归一 ENGINE_ERROR，不谎报删除成功
        # （filter_adapter.py:174-176 的防御分支）。
        with mock.patch.object(preset_store, 'delete_preset',
                               side_effect=OSError('permission denied')):
            response = self.dispatcher.handle(_request('filter.presets.delete',
                                                       {'name': 'io_error'}))
        self.assertFalse(response['success'])
        self.assertEqual(response['error']['code'], protocol.ERR_ENGINE_ERROR)
        self.assertIn('预设删除失败', response['error']['message'])


if __name__ == '__main__':
    unittest.main()
