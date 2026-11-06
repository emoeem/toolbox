"""generate.list / generate.render 动作测试（docs/ipc-protocol.md §3.7）。

参照 tests/test_worker_batch.py 的进程内风格（不启动 QProcess，CI 直接执行）：
Dispatcher + TaskRuntime(max_workers=1, emitter=...)，轮询事件列表等待终态。
渲染一律用小尺寸（≤48 边）保证 CI 时长；G'MIC 依赖路径用 mock（patch
processors.gmic.available + reset_registry_cache），不要求 CI 机器装/不装
G'MIC。锁定行为：fractal/texture/gradient 小尺寸渲染往返（请求尺寸原样落盘
+ sha256 一致）、参数校验错误路径（提交前同步 INVALID_PARAMS、不产生任务）、
依赖缺失生成器 available:false（texture:gmic:* 与恒不可用的 shader:preview）。

Phase 6C 覆盖核对后补齐（本批，见 CHANGELOG 同日条目）：颜色参数两种协议
形状（[r,g,b] 数组与 #RGB/#RRGGBB hex 文本——UI 侧 AppFilterParameterGroup
发送 hex 文本）、完成 result 形状与 §4 按生成器 key 覆盖命名、texture:gmic 系
渲染通道（可用性 mock 后经 1.0 既有 generate() 的 numpy 降级实现往返，锁定
协议通道不是 gmic 本体效果）、取消路径（texture 族任务体边界检查 →
task.failed(CANCELLED)；分形 cancel_token 直通 render_fractal 的装配锁定）。
"""
from __future__ import annotations

import hashlib
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from processors import fractal as fractal_processor
from processors import gmic as gmic_processor
from processors.texture_studio import generators as texture_generators
from python_worker import task_runtime
from python_worker.adapters import generate_adapter
from python_worker.dispatcher import Dispatcher, WorkerContext
from python_worker.protocol import PROTOCOL_VERSION


def _request(action: str, params: dict | None = None, request_id: str = 'req-g') -> dict:
    return {'protocol': PROTOCOL_VERSION, 'request_id': request_id,
            'action': action, 'params': params or {}}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b''):
            digest.update(chunk)
    return digest.hexdigest()


class DispatcherGenerateTestBase(unittest.TestCase):
    """公共底座：临时目录 + 单线程 TaskRuntime + 事件轮询（同 test_worker_batch）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.events: list[dict] = []
        self.ctx = WorkerContext(temp_dir=Path(self.tmp.name))  # 结果落盘在临时目录
        self.ctx.runtime = task_runtime.TaskRuntime(max_workers=1, emitter=self.events.append)
        self.addCleanup(self.ctx.runtime.shutdown)
        self.dispatcher = Dispatcher(self.ctx)
        # 依赖可用性在注册表构建时探测并缓存；每个用例结束后按真实环境重建。
        self.addCleanup(generate_adapter.reset_registry_cache)

    def _wait_for_terminal(self, task_id: str, timeout: float = 60.0) -> dict | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for event in self.events:
                if event.get('task_id') == task_id and event.get('type') in (
                        'task.completed', 'task.failed'):
                    return event
            time.sleep(0.02)
        return None

    def _render(self, params: dict, request_id: str = 'req-render') -> dict:
        """提交 generate.render 并等待完成，返回 completed 事件的 result。"""
        response = self.dispatcher.handle(_request('generate.render', params, request_id))
        self.assertTrue(response['success'], response)
        self.assertIn('task_id', response['result'])
        self.assertEqual(response['result']['status'], 'queued')  # §2.3 受理回执
        event = self._wait_for_terminal(response['result']['task_id'])
        self.assertIsNotNone(event, 'generate.render 任务未在超时前完成')
        self.assertEqual(event['type'], 'task.completed', event)
        return event['result']

    def _task_events(self) -> list[dict]:
        return [e for e in self.events if str(e.get('type', '')).startswith('task')]


class GenerateListTests(DispatcherGenerateTestBase):
    """generate.list 目录形状与注册表来源（§3.7，模式对齐 filter.list）。"""

    def setUp(self):
        super().setUp()
        response = self.dispatcher.handle(_request('generate.list', {}))
        self.assertTrue(response['success'], response)
        self.list_response = response
        self.generators = response['result']['generators']
        self.by_key = {g['key']: g for g in self.generators}

    def test_actions_are_registered(self):
        caps = self.dispatcher.handle(_request('capabilities.list', {}))
        self.assertTrue(caps['success'], caps)
        for name in ('generate.list', 'generate.render'):
            self.assertIn(name, caps['result']['actions'])

    def test_list_response_is_json_encodable(self):
        # 目录条目含参数定义（default 可能是列表/数值），必须能走 JSON Lines 通道。
        from python_worker import protocol
        protocol.encode(self.list_response)  # 不抛即通过

    def test_entry_shape_matches_filter_list_vocabulary(self):
        self.assertTrue(self.generators, '生成器目录为空')
        seen_keys = set()
        for entry in self.generators:
            for field in ('key', 'name', 'category', 'category_label',
                          'available', 'optional_deps', 'params'):
                self.assertIn(field, entry, entry)
            self.assertTrue(entry['key'])
            self.assertTrue(entry['name'])
            self.assertIn(entry['category'], ('fractal', 'texture', 'gradient', 'shader'))
            self.assertTrue(entry['category_label'])
            self.assertIsInstance(entry['available'], bool)
            self.assertIsInstance(entry['optional_deps'], list)
            self.assertIsInstance(entry['params'], list)
            seen_keys.add(entry['key'])
        self.assertEqual(len(seen_keys), len(self.generators), 'key 必须唯一')

    def test_param_descriptors_use_filter_param_vocabulary(self):
        valid_types = {'int', 'float', 'bool', 'enum', 'color', 'string'}
        for entry in self.generators:
            for param in entry['params']:
                for field in ('name', 'label', 'type', 'default'):
                    self.assertIn(field, param, param)
                self.assertIn(param['type'], valid_types, param)
                if param['type'] == 'enum':
                    self.assertTrue(param['choices'], param)

    def test_all_fractal_formulae_registered(self):
        for formula in fractal_processor.formula_keys():
            self.assertIn(f'fractal:{formula}', self.by_key, formula)
        self.assertIn('fractal:mandelbulb', self.by_key)

    def test_texture_and_gradient_generators_registered(self):
        for key in ('texture:perlin', 'texture:simplex', 'texture:value',
                    'texture:worley', 'texture:cellular',
                    'texture:pattern:stripes', 'texture:pattern:rings',
                    'texture:pattern:checker', 'texture:pattern:dots',
                    'texture:pattern:grid',
                    'texture:gmic:paper', 'texture:gmic:canvas',
                    'texture:gmic:grunge', 'texture:gmic:noise_blend',
                    'texture:raymarch:orb',
                    'gradient:linear', 'gradient:radial', 'gradient:mesh'):
            self.assertIn(key, self.by_key, key)

    def test_fractal_param_sets_follow_formula_capabilities(self):
        # 裁剪逻辑与 processors/fractal.py register_fractal_filters 一致。
        mandelbrot = {p['name'] for p in self.by_key['fractal:mandelbrot']['params']}
        self.assertIn('power', mandelbrot)
        self.assertIn('bailout', mandelbrot)
        self.assertNotIn('julia_c_x', mandelbrot)

        julia = {p['name'] for p in self.by_key['fractal:julia']['params']}
        self.assertIn('julia_c_x', julia)
        self.assertIn('julia_c_y', julia)

        phoenix = {p['name'] for p in self.by_key['fractal:phoenix']['params']}
        self.assertIn('phoenix_c_x', phoenix)
        self.assertIn('phoenix_c_y', phoenix)

        nova = {p['name'] for p in self.by_key['fractal:nova']['params']}
        self.assertIn('nova_relaxation', nova)
        self.assertNotIn('bailout', nova)  # nova 注册时 can_bailout=False

        magnet = {p['name'] for p in self.by_key['fractal:magnet_i']['params']}
        self.assertNotIn('power', magnet)  # magnet_i 注册时 can_power=False

        mandelbulb = {p['name'] for p in self.by_key['fractal:mandelbulb']['params']}
        self.assertEqual(mandelbulb, {'power', 'iterations'})

    def test_mesh_gradient_exposes_preset_choices(self):
        param = next(p for p in self.by_key['gradient:mesh']['params'] if p['name'] == 'preset')
        self.assertEqual(param['choices'], ['piretti', 'sunset', 'ocean'])
        self.assertEqual(param['default'], 'piretti')

    def test_noise_defaults_come_from_builtin_presets(self):
        seed = next(p for p in self.by_key['texture:perlin']['params'] if p['name'] == 'seed')
        self.assertEqual(seed['default'], 42)  # presets.py 'Perlin Default'

    def test_shader_preview_unavailable_with_dep_reason(self):
        shader = self.by_key['shader:preview']
        self.assertFalse(shader['available'])  # Worker 无 OpenGL 运行时，恒不可用
        self.assertIn('opengl', shader['optional_deps'])


class GmicAvailabilityTests(unittest.TestCase):
    """texture:gmic:* 的 available 跟随 G'MIC CLI 真实状态（§3.7）。"""

    def tearDown(self):
        generate_adapter.reset_registry_cache()

    def _gmic_entries(self) -> dict[str, dict]:
        return {g['key']: g for g in generate_adapter.list_generators()
                if g['key'].startswith('texture:gmic:')}

    def test_missing_gmic_cli_marks_generators_unavailable(self):
        with mock.patch.object(gmic_processor, 'available', return_value=False):
            generate_adapter.reset_registry_cache()
            entries = self._gmic_entries()
        self.assertEqual(set(entries), {'texture:gmic:paper', 'texture:gmic:canvas',
                                        'texture:gmic:grunge', 'texture:gmic:noise_blend'})
        for key, entry in entries.items():
            self.assertFalse(entry['available'], key)
            self.assertEqual(entry['optional_deps'], ['gmic'], key)

    def test_present_gmic_cli_marks_generators_available(self):
        with mock.patch.object(gmic_processor, 'available', return_value=True):
            generate_adapter.reset_registry_cache()
            entries = self._gmic_entries()
        for key, entry in entries.items():
            self.assertTrue(entry['available'], key)
            self.assertEqual(entry['optional_deps'], [], key)


class GenerateRenderFractalTests(DispatcherGenerateTestBase):
    """fractal 小尺寸渲染往返（§3.7：请求尺寸原样落盘 + §4 path/sha256）。"""

    def test_mandelbrot_render_roundtrip(self):
        result = self._render({'generator_key': 'fractal:mandelbrot',
                               'params': {'iterations': 32},
                               'width': 48, 'height': 32})
        self.assertEqual(result['generator_key'], 'fractal:mandelbrot')
        self.assertEqual(result['width'], 48)
        self.assertEqual(result['height'], 32)
        path = Path(result['path'])
        self.assertTrue(path.is_file(), result['path'])
        self.assertEqual(result['sha256'], _sha256_file(path))  # 校验与文件一致
        with Image.open(path) as img:
            self.assertEqual(img.format, 'PNG')
            self.assertEqual(img.size, (48, 32))
            arr = np.asarray(img.convert('RGB'))
        # 集内既有逃逸点（着色）也有内部点（黑色）：证明渲染真实发生。
        self.assertTrue(arr.any())
        self.assertFalse(arr.all())

    def test_julia_render_honours_julia_constants(self):
        result = self._render({'generator_key': 'fractal:julia',
                               'params': {'iterations': 32, 'julia_c_x': -0.8,
                                          'julia_c_y': 0.156},
                               'width': 32, 'height': 32})
        self.assertEqual((result['width'], result['height']), (32, 32))
        self.assertTrue(Path(result['path']).is_file())

    def test_mandelbulb_render_roundtrip(self):
        result = self._render({'generator_key': 'fractal:mandelbulb',
                               'params': {'iterations': 16, 'power': 8.0},
                               'width': 24, 'height': 24})
        self.assertEqual((result['width'], result['height']), (24, 24))
        with Image.open(result['path']) as img:
            self.assertEqual(img.size, (24, 24))
            arr = np.asarray(img.convert('RGB'))
        self.assertTrue(arr.any())  # 背景之外的命中像素被着色

    def test_generator_alias_is_accepted(self):
        result = self._render({'generator': 'fractal:mandelbrot',  # generator_key 别名
                               'params': {'iterations': 16},
                               'width': 24, 'height': 24})
        self.assertEqual(result['generator_key'], 'fractal:mandelbrot')


class GenerateRenderTextureTests(DispatcherGenerateTestBase):
    """texture 小尺寸渲染往返 + 种子可重复（总纲 §9.7）。"""

    def test_perlin_render_roundtrip_and_seed_repeatability(self):
        params = {'generator_key': 'texture:perlin', 'params': {'seed': 7},
                  'width': 32, 'height': 24}
        first = self._render(dict(params), 'req-t1')
        self.assertEqual(first['generator_key'], 'texture:perlin')
        self.assertEqual((first['width'], first['height']), (32, 24))
        with Image.open(first['path']) as img:
            self.assertEqual(img.size, (32, 24))
            arr = np.asarray(img.convert('RGB'))
        self.assertEqual(arr.shape, (24, 32, 3))
        second = self._render(dict(params), 'req-t2')  # 同种子 → 同输出
        self.assertEqual(first['sha256'], second['sha256'])

    def test_pattern_checker_render_roundtrip(self):
        result = self._render({'generator_key': 'texture:pattern:checker',
                               'params': {'size': 8, 'spacing': 0},
                               'width': 16, 'height': 16})
        self.assertEqual((result['width'], result['height']), (16, 16))
        with Image.open(result['path']) as img:
            arr = np.asarray(img.convert('RGB'))
        self.assertEqual(arr.shape, (16, 16, 3))
        self.assertTrue(arr.any())

    def test_raymarch_render_roundtrip(self):
        result = self._render({'generator_key': 'texture:raymarch:orb',
                               'params': {'steps': 16},
                               'width': 24, 'height': 24})
        self.assertEqual((result['width'], result['height']), (24, 24))
        with Image.open(result['path']) as img:
            self.assertEqual(img.size, (24, 24))


class GenerateRenderGradientTests(DispatcherGenerateTestBase):
    """gradient 渲染往返 + 像素语义（线性渐变两端 = color_a/color_b）。"""

    def test_linear_gradient_endpoints_match_colors(self):
        result = self._render({'generator_key': 'gradient:linear', 'width': 24, 'height': 16})
        self.assertEqual((result['width'], result['height']), (24, 16))
        with Image.open(result['path']) as img:
            arr = np.asarray(img.convert('RGB')).astype(int)
        # 默认色 color_a=[255,0,128] / color_b=[0,255,255]，angle=0：
        # 左端 t=0 精确等于 color_a，右端 t≈1 趋近 color_b（u8 截断）。
        self.assertEqual(list(arr[0, 0]), [255, 0, 128])
        self.assertLessEqual(int(arr[0, -1][0]), 5)
        self.assertGreaterEqual(int(arr[0, -1][1]), 250)
        self.assertGreaterEqual(int(arr[0, -1][2]), 250)

    def test_radial_gradient_with_explicit_colors(self):
        result = self._render({'generator_key': 'gradient:radial',
                               'params': {'color_a': [10, 20, 30],
                                          'color_b': [200, 210, 220]},
                               'width': 16, 'height': 16})
        with Image.open(result['path']) as img:
            arr = np.asarray(img.convert('RGB')).astype(int)
        # 中心 (0.5,0.5) 距离 0 → t=0 → color_a 精确。
        self.assertEqual(list(arr[8, 8]), [10, 20, 30])

    def test_mesh_gradient_preset_render(self):
        result = self._render({'generator_key': 'gradient:mesh',
                               'params': {'preset': 'sunset'},
                               'width': 24, 'height': 24})
        self.assertEqual((result['width'], result['height']), (24, 24))
        with Image.open(result['path']) as img:
            arr = np.asarray(img.convert('RGB'))
        self.assertTrue(arr.any())


class GenerateRenderValidationTests(DispatcherGenerateTestBase):
    """提交前同步 INVALID_PARAMS（§3.7；均不产生任务）。"""

    def _assert_rejected(self, params: dict, message_part: str | None = None):
        response = self.dispatcher.handle(_request('generate.render', params))
        self.assertFalse(response['success'], params)
        self.assertEqual(response['error']['code'], 'INVALID_PARAMS', params)
        if message_part:
            self.assertIn(message_part, response['error']['message'])
        self.assertEqual(self._task_events(), [])  # 提交前拒绝：无任务

    def test_generator_key_required(self):
        base = {'width': 16, 'height': 16}
        for params in ({}, {'generator_key': ''}, {'generator_key': '   '},
                       {'generator_key': 42}, {**base, 'generator_key': None}):
            self._assert_rejected(params, 'generator_key')

    def test_unknown_generator(self):
        self._assert_rejected({'generator_key': 'no:such', 'width': 16, 'height': 16},
                              '未知生成器')

    def test_unavailable_generator_rejected(self):
        # shader:preview 恒不可用（Worker 无 OpenGL 运行时）：置灰条目不得渲染。
        self._assert_rejected({'generator_key': 'shader:preview',
                               'width': 16, 'height': 16}, '可选依赖')

    def test_unavailable_gmic_generator_rejected(self):
        with mock.patch.object(gmic_processor, 'available', return_value=False):
            generate_adapter.reset_registry_cache()
            self._assert_rejected({'generator_key': 'texture:gmic:paper',
                                   'width': 16, 'height': 16}, 'gmic')

    def test_size_validation(self):
        base = {'generator_key': 'gradient:linear'}
        for width, height in ((0, 16), (-1, 16), (4097, 16), (16, 0), (16, -5),
                              (16, 4097), (32.5, 16), (True, 16), (16, 'big')):
            self._assert_rejected({**base, 'width': width, 'height': height})
        self._assert_rejected({**base, 'height': 16})  # 缺 width
        self._assert_rejected({**base, 'width': 16})   # 缺 height
        self._assert_rejected({'generator_key': 'gradient:linear', 'height': 16,
                               'width': None})

    def test_params_shape_validation(self):
        base = {'generator_key': 'gradient:linear', 'width': 16, 'height': 16}
        for params in ([], 'x', 42, True):
            self._assert_rejected({**base, 'params': params}, 'params')

    def test_param_value_validation_uses_filter_param_ranges(self):
        cases = [
            {'generator_key': 'fractal:mandelbrot', 'params': {'iterations': 0},
             'width': 16, 'height': 16},            # FilterParam 下界
            {'generator_key': 'fractal:mandelbrot', 'params': {'iterations': 2049},
             'width': 16, 'height': 16},            # FilterParam 上界（2048）
            {'generator_key': 'fractal:mandelbrot', 'params': {'power': 0},
             'width': 16, 'height': 16},            # power ≥ 1
            {'generator_key': 'fractal:mandelbrot', 'params': {'scale': 0},
             'width': 16, 'height': 16},            # scale ≥ 0.01
            {'generator_key': 'fractal:mandelbrot', 'params': {'coloring': 'nope'},
             'width': 16, 'height': 16},            # enum 取值域
            {'generator_key': 'gradient:linear', 'params': {'color_a': 'red'},
             'width': 16, 'height': 16},            # color 类型：非 hex 词汇非法
            {'generator_key': 'gradient:mesh', 'params': {'preset': 'nope'},
             'width': 16, 'height': 16},            # mesh 预设枚举
        ]
        for params in cases:
            self._assert_rejected(params)

    def test_valid_params_produce_task(self):
        # 与上面被拒用例同键合法值：证明拒绝来自取值域而非键本身。
        result = self._render({'generator_key': 'fractal:mandelbrot',
                               'params': {'iterations': 16, 'coloring': 'banded'},
                               'width': 16, 'height': 16})
        self.assertEqual(result['generator_key'], 'fractal:mandelbrot')


class GenerateRenderColorFormatTests(DispatcherGenerateTestBase):
    """颜色参数的两种协议形状（FilterParam._validate_color 词汇，§3.7）：
    [r,g,b] 数组与 #RGB/#RRGGBB hex 文本——UI 侧 AppFilterParameterGroup 对
    color 类型发送 "#rrggbb" 文本（该组件头注：color 存十六进制文本），
    Worker 侧经 generate_adapter._hex_to_rgb 归一为元组后交给 processors。"""

    def test_hex_color_param_accepted(self):
        result = self._render({'generator_key': 'gradient:linear',
                               'params': {'color_a': '#102030'},
                               'width': 24, 'height': 16})
        with Image.open(result['path']) as img:
            arr = np.asarray(img.convert('RGB')).astype(int)
        # 线性渐变 angle=0 时左端 t=0 精确等于 color_a（既有默认色用例同款断言）。
        self.assertEqual(list(arr[0, 0]), [16, 32, 48])

    def test_three_digit_hex_expands(self):
        result = self._render({'generator_key': 'gradient:radial',
                               'params': {'color_a': '#f0b'},
                               'width': 16, 'height': 16})
        with Image.open(result['path']) as img:
            arr = np.asarray(img.convert('RGB')).astype(int)
        # 中心像素 (8,8) 与默认中心 (0.5*w, 0.5*h) 重合 → t=0 → color_a 精确。
        self.assertEqual(list(arr[8, 8]), [255, 0, 187])


class GenerateRenderResultShapeTests(DispatcherGenerateTestBase):
    """完成 result 形状（§2.3/§3.7：path/width/height/sha256/generator_key）
    与 §4 防堆积覆盖命名（preview-generate-<key>.png，按生成器 key 覆盖）。"""

    def test_result_fields_and_overwrite_naming(self):
        first = self._render({'generator_key': 'texture:perlin',
                              'params': {'seed': 1},
                              'width': 24, 'height': 24}, 'req-s1')
        for field in ('path', 'width', 'height', 'sha256', 'generator_key'):
            self.assertIn(field, first, first)
        self.assertTrue(Path(first['path']).name.startswith('preview-generate-texture-perlin'),
                        first['path'])

        # 同一生成器重复渲染：按 key 覆盖同一文件名，尺寸随请求更新。
        second = self._render({'generator_key': 'texture:perlin',
                               'params': {'seed': 2},
                               'width': 32, 'height': 16}, 'req-s2')
        self.assertEqual(Path(first['path']).name, Path(second['path']).name)
        self.assertEqual((second['width'], second['height']), (32, 16))

        # 不同生成器：文件名不同（互不覆盖）。
        linear = self._render({'generator_key': 'gradient:linear',
                               'width': 16, 'height': 16}, 'req-s3')
        self.assertNotEqual(Path(linear['path']).name, Path(first['path']).name)

    def test_gmic_texture_render_channel(self):
        """texture:gmic:* 的渲染通道锁定（可用性 mock 后提交成功）。

        如实边界：CI 机器无 gmic CLI，processors.texture_studio.generators
        .generate → generate_gmic_texture 在 CLI 不可用时走 1.0 既有 numpy
        降级实现（texture_studio/gmic.py _fallback）——本用例锁定的是协议
        通道（受理/完成 result 形状/参数透传），不是 gmic 本体的渲染效果
        （gmic 真实输出归实机验收，phase6c-acceptance.md）。渲染结果像素
        不做断言：装有 gmic 的环境走 CLI 路径、CI 走降级路径，两环境像素
        不同是 1.0 既有行为，协议面语义相同。"""
        with mock.patch.object(gmic_processor, 'available', return_value=True):
            generate_adapter.reset_registry_cache()
            result = self._render({'generator_key': 'texture:gmic:paper',
                                   'params': {'seed': 7},
                                   'width': 24, 'height': 24}, 'req-s4')
        self.assertEqual(result['generator_key'], 'texture:gmic:paper')
        self.assertEqual((result['width'], result['height']), (24, 24))
        path = Path(result['path'])
        self.assertTrue(path.is_file(), result['path'])
        self.assertEqual(result['sha256'], _sha256_file(path))
        with Image.open(path) as img:
            self.assertEqual(img.format, 'PNG')
            self.assertEqual(img.size, (24, 24))


class GenerateRenderCancelTests(DispatcherGenerateTestBase):
    """取消路径（§3.7/§7）：texture 族渲染是同步 CPU 计算，取消在任务体
    边界检查（generate_adapter.render_generator 的 _check_cancel 前后点）；
    分形渲染直通 render_fractal / render_mandelbulb 的协作检查点（逐行）。"""

    def test_cancel_during_texture_generation_fails_cancelled(self):
        entered = threading.Event()
        release = threading.Event()

        def blocking_generate(gid, width, height, params):
            # 模拟 texture_studio 生成期间的同步计算段：阻塞直到测试发出取消。
            entered.set()
            release.wait(timeout=30)
            return np.zeros((height, width, 3), dtype=np.uint8)

        patcher = mock.patch.object(texture_generators, 'generate', blocking_generate)
        patcher.start()
        self.addCleanup(patcher.stop)

        response = self.dispatcher.handle(_request(
            'generate.render',
            {'generator_key': 'texture:perlin', 'params': {'seed': 1},
             'width': 24, 'height': 24}, 'req-cancel'))
        self.assertTrue(response['success'], response)
        task_id = response['result']['task_id']

        self.assertTrue(entered.wait(timeout=30), '任务未在超时前进入渲染边界')
        cancelled = self.dispatcher.handle(
            _request('task.cancel', {'task_id': task_id}, 'req-cancel-c'))
        self.assertTrue(cancelled['success'], cancelled)
        self.assertTrue(cancelled['result']['cancelling'])

        release.set()
        event = self._wait_for_terminal(task_id)
        self.assertIsNotNone(event, '取消后任务未在超时前终结')
        self.assertEqual(event['type'], 'task.failed', event)
        self.assertEqual(event['error']['code'], 'CANCELLED', event)
        # 边界检查抛出发生在 write_render 之前：不落任何结果文件（§4）。
        self.assertEqual(list(Path(self.tmp.name).glob('preview-generate-*')), [])

        late = self.dispatcher.handle(_request('task.cancel', {'task_id': task_id}))
        self.assertTrue(late['success'], late)
        self.assertFalse(late['result']['cancelling'])  # 已终结，不谎报取消成功

    def test_fractal_render_forwards_cancel_token_to_processor(self):
        """§3.7"分形渲染直通 render_fractal 的协作检查点"的装配锁定：
        cancel_token 必须真实传入 processors（mock 断言，像素由
        GenerateRenderFractalTests 的真实往返覆盖）。"""
        captured: dict = {}

        def fake_render(width, height, formula_key, params,
                        cancel_token=None, progress_cb=None):
            captured['cancel_token'] = cancel_token
            return mock.Mock(image=np.full((height, width, 3), 7, dtype=np.uint8))

        patcher = mock.patch.object(fractal_processor, 'render_fractal', fake_render)
        patcher.start()
        self.addCleanup(patcher.stop)

        result = self._render({'generator_key': 'fractal:mandelbrot',
                               'params': {'iterations': 16},
                               'width': 16, 'height': 16}, 'req-cancel-f')
        self.assertEqual(result['generator_key'], 'fractal:mandelbrot')
        self.assertIsNotNone(captured.get('cancel_token'), 'cancel_token 未直通 render_fractal')

    def test_progress_wrapper_attaches_message(self):
        # _progress_with：processors 的 int 进度回调 → 协议 (progress, message)。
        sink: list = []
        wrapped = generate_adapter._progress_with(lambda *args: sink.append(args), '渲染分形')
        wrapped(50)
        self.assertEqual(sink, [(50, '渲染分形')])
        self.assertIsNone(generate_adapter._progress_with(None, 'x'))  # 无回调 → 不包装


if __name__ == '__main__':
    unittest.main()
