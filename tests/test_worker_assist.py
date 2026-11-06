"""assist.list 与 assist 动作族测试（docs/ipc-protocol.md §3.8，Phase 7）。

参照 tests/test_worker_generate.py 的进程内风格（不启动 QProcess，CI 直接
执行）：Dispatcher + TaskRuntime(max_workers=1, emitter=...)，轮询事件列表
等待终态。外部依赖（pytesseract/tesseract、pdf2image/poppler、qrcode、
pystrich、pyzbar、magick、ffmpeg、rembg/onnxruntime/模型文件）在 CI 机器
上不假设装/不装——依赖缺失路径一律用 mock 强制（patch
python_worker.adapters.assist_adapter.missing_deps_*，与
test_worker_generate 的 gmic 注入方式一致，结果确定性不随环境漂移），
成功路径 mock 到 processors 资产函数（只锁协议接线与结果形状，不锁依赖
本体效果）；OpenCV/Pillow/pypdf 等核心依赖路径走真实执行。

锁定行为：assist.list 目录形状（与 filter.list 同构、key 即动作名、
available 与 optional_deps 如实互斥）、DEPENDENCY_MISSING 提交前同步返回
且 details.missing 同源、参数校验先于依赖判定、PDF 七资产函数往返、
§4 临时 PNG 通道（path/sha256）、AI 模型注册表 installed 如实（无模型
文件即 false）与模型路径配置读取、compare 指标非有限值 → null。
"""
from __future__ import annotations

import base64
import collections
import hashlib
import importlib.util
import json
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from python_worker import protocol, task_runtime
from python_worker.adapters import assist_adapter
from python_worker.dispatcher import Dispatcher, WorkerContext

ASSIST = 'python_worker.adapters.assist_adapter'


def _request(action: str, params: dict | None = None, request_id: str = 'req-a') -> dict:
    return {'protocol': protocol.PROTOCOL_VERSION, 'request_id': request_id,
            'action': action, 'params': params or {}}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


class DispatcherAssistTestBase(unittest.TestCase):
    """公共底座：临时目录 + 单线程 TaskRuntime + 事件轮询（同 test_worker_generate）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.events: list[dict] = []
        self.ctx = WorkerContext(temp_dir=Path(self.tmp.name))
        self.ctx.runtime = task_runtime.TaskRuntime(max_workers=1, emitter=self.events.append)
        self.addCleanup(self.ctx.runtime.shutdown)
        self.dispatcher = Dispatcher(self.ctx)

    # ---- 工具 ---------------------------------------------------------------
    def _make_image(self, name: str = 'src.png', size: tuple[int, int] = (32, 24),
                    color: tuple | None = None) -> Path:
        path = self.root / name
        if color is None:
            arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
            arr[..., 0] = np.linspace(0, 255, size[0], dtype=np.uint8)[None, :]
            arr[..., 1] = 80
            arr[..., 2] = 160
        else:
            arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
            arr[..., :] = np.array(color, dtype=np.uint8)
        Image.fromarray(arr).save(path, format='PNG')
        return path

    def _make_pdf(self, name: str, pages: int = 2, size: tuple[int, int] = (64, 48)) -> Path:
        path = self.root / name
        imgs = [Image.new('RGB', size, (n * 40, 100, 200)) for n in range(pages)]
        imgs[0].save(path, format='PDF', save_all=True, append_images=imgs[1:])
        return path

    def _make_text_pdf(self, name: str, text: str) -> Path:
        if not _module_available('reportlab'):
            self.skipTest('reportlab 未安装（文本 PDF 夹具不可用）')
        from reportlab.pdfgen import canvas
        path = self.root / name
        pdf = canvas.Canvas(str(path))
        pdf.drawString(72, 700, text)
        pdf.save()
        return path

    def _wait_for_terminal(self, task_id: str, timeout: float = 60.0) -> dict | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for event in self.events:
                if event.get('task_id') == task_id and event.get('type') in (
                        'task.completed', 'task.failed'):
                    return event
            time.sleep(0.02)
        return None

    def _run(self, action: str, params: dict, request_id: str = 'req-run') -> dict:
        """提交 async 动作并等待完成，返回 completed 事件的 result。"""
        response = self.dispatcher.handle(_request(action, params, request_id))
        self.assertTrue(response['success'], response)
        self.assertEqual(response['result']['status'], 'queued')  # §2.3 受理回执
        event = self._wait_for_terminal(response['result']['task_id'])
        self.assertIsNotNone(event, f'{action} 任务未在超时前完成')
        self.assertEqual(event['type'], 'task.completed', event)
        return event['result']

    def _submit_error(self, action: str, params: dict, code: str) -> dict:
        """提交即被拒绝（无 task_id、无任务事件），返回 error 对象。"""
        response = self.dispatcher.handle(_request(action, params))
        self.assertFalse(response['success'], response)
        self.assertEqual(response['error']['code'], code, response)
        self.assertNotIn('result', response)
        task_events = [e for e in self.events if str(e.get('type', '')).startswith('task')]
        self.assertEqual(task_events, [], '被拒绝的请求不得产生任务事件')
        return response['error']

    def _patch_missing(self, deps_fn: str, missing: list[str]):
        return mock.patch(f'{ASSIST}.{deps_fn}', return_value=list(missing))


class AssistListTests(DispatcherAssistTestBase):
    """assist.list 目录形状与依赖诚实性（§3.8，模式对齐 filter.list/generate.list）。"""

    def setUp(self):
        super().setUp()
        response = self.dispatcher.handle(_request('assist.list', {}))
        self.assertTrue(response['success'], response)
        self.tools = response['result']['tools']
        self.by_key = {t['key']: t for t in self.tools}

    def test_actions_are_registered(self):
        caps = self.dispatcher.handle(_request('capabilities.list', {}))
        self.assertTrue(caps['success'], caps)
        actions = caps['result']['actions']
        self.assertIn('assist.list', actions)
        for tool in self.tools:
            self.assertIn(tool['key'], actions, f"目录条目 {tool['key']} 未注册为动作")

    def test_entry_shape_and_sorting(self):
        self.assertTrue(self.tools, '工具目录为空')
        keys = [t['key'] for t in self.tools]
        self.assertEqual(len(keys), len(set(keys)), '目录条目 key 重复')
        self.assertEqual(keys, sorted(keys, key=lambda k: (self.by_key[k]['category'], k)))
        for tool in self.tools:
            for field in ('key', 'name', 'category', 'category_label', 'description',
                          'type', 'available', 'optional_deps'):
                self.assertIn(field, tool, f"{tool['key']} 缺少字段 {field}")
            self.assertIn(tool['type'], ('sync', 'async'))
            self.assertIsInstance(tool['available'], bool)
            self.assertIsInstance(tool['optional_deps'], list)

    def test_response_is_json_encodable(self):
        response = self.dispatcher.handle(_request('assist.list', {}))
        protocol.encode(response)  # 不抛即通过

    def test_available_is_negation_of_optional_deps(self):
        for tool in self.tools:
            self.assertEqual(tool['available'], not tool['optional_deps'],
                             f"{tool['key']} 的 available 与 optional_deps 不一致")

    def test_family_coverage(self):
        """Phase 7 清单覆盖：OCR/PDF/条形码/ASCII/对比/校验和/直方图/LUT/
        媒体/EXIF/水印/归档/加密/Base64/AI 每族至少一个条目。"""
        categories = {t['category'] for t in self.tools}
        for category in ('ocr', 'pdf', 'barcode', 'ascii', 'compare', 'checksum',
                         'base64', 'histogram', 'lut', 'media', 'exif', 'watermark',
                         'archive', 'crypto', 'ai'):
            self.assertIn(category, categories, f'目录缺少类别 {category}')

    def test_dependency_probe_shared_with_catalog(self):
        """目录探测与提交判定同一函数：强制 ocr 依赖缺失 → 条目置灰且
        optional_deps 与提交时 details.missing 同源。"""
        image = self._make_image()
        with self._patch_missing('missing_deps_ocr', ['tesseract']):
            response = self.dispatcher.handle(_request('assist.list', {}))
            tool = {t['key']: t for t in response['result']['tools']}['ocr.run']
            self.assertFalse(tool['available'])
            self.assertEqual(tool['optional_deps'], ['tesseract'])
            self._submit_error('ocr.run', {'path': str(image)},
                               protocol.ERR_DEPENDENCY_MISSING)

    def test_env_honesty_conditional(self):
        """真实环境条件断言（确定性）：qrcode 模块缺失时该条目必须置灰。"""
        if _module_available('qrcode'):
            self.skipTest('本机已安装 qrcode，缺失路径不适用')
        self.assertFalse(self.by_key['barcode.qr.generate']['available'])
        self.assertIn('qrcode', self.by_key['barcode.qr.generate']['optional_deps'])


class OcrTests(DispatcherAssistTestBase):
    """ocr.run：依赖缺失路径 + 成功接线（mock pytesseract 资产）。"""

    def test_dependency_missing_rejected_before_task(self):
        with self._patch_missing('missing_deps_ocr', ['pytesseract', 'tesseract']):
            error = self._submit_error('ocr.run', {'path': str(self._make_image())},
                                       protocol.ERR_DEPENDENCY_MISSING)
        self.assertEqual(error['details']['missing'], ['pytesseract', 'tesseract'])

    def test_invalid_params_beats_dependency_missing(self):
        """参数校验优先：path 缺失时即使依赖也缺失，仍报 INVALID_PARAMS。"""
        with self._patch_missing('missing_deps_ocr', ['tesseract']):
            self._submit_error('ocr.run', {}, protocol.ERR_INVALID_PARAMS)

    def test_run_success_mocked(self):
        image = self._make_image()
        with self._patch_missing('missing_deps_ocr', []), \
                mock.patch('processors.parity.ocr_image', return_value='识别文本') as ocr:
            result = self._run('ocr.run', {'path': str(image), 'lang': 'chi_sim', 'psm': 6})
        self.assertEqual(result, {'text': '识别文本'})
        self.assertEqual(ocr.call_args.kwargs.get('lang'), 'chi_sim')
        self.assertEqual(ocr.call_args.kwargs.get('psm'), 6)


class PdfTests(DispatcherAssistTestBase):
    """pdf.* 七资产函数往返 + pdf.to_images 依赖双路径（§3.8）。"""

    def test_merge(self):
        a, b = self._make_pdf('a.pdf', pages=2), self._make_pdf('b.pdf', pages=2)
        out = self.root / 'merged.pdf'
        result = self._run('pdf.merge', {'paths': [str(a), str(b)], 'output': str(out)})
        self.assertEqual(Path(result['path']), out)
        from pypdf import PdfReader
        self.assertEqual(len(PdfReader(str(out)).pages), 4)

    def test_split(self):
        src = self._make_pdf('split-src.pdf', pages=3)
        result = self._run('pdf.split', {'path': str(src)})
        self.assertEqual(len(result['files']), 3)
        self.assertTrue(all(Path(f).exists() for f in result['files']))
        from pypdf import PdfReader
        for file in result['files']:
            self.assertEqual(len(PdfReader(file).pages), 1)

    def test_rotate(self):
        src = self._make_pdf('rot-src.pdf', pages=1)
        out = self.root / 'rotated.pdf'
        self._run('pdf.rotate', {'path': str(src), 'output': str(out), 'degrees': 90})
        from pypdf import PdfReader
        self.assertEqual(PdfReader(str(out)).pages[0].rotation, 90)

    def test_rotate_invalid_degrees(self):
        src = self._make_pdf('rot-bad.pdf', pages=1)
        self._submit_error('pdf.rotate', {'path': str(src), 'output': str(self.root / 'x.pdf'),
                                          'degrees': 45}, protocol.ERR_INVALID_PARAMS)

    def test_merge_paths_must_be_nonempty_array(self):
        """§3.8：paths 必须是非空数组——缺失或空数组提交前 INVALID_PARAMS。"""
        out = str(self.root / 'merged-nothing.pdf')
        self._submit_error('pdf.merge', {'output': out}, protocol.ERR_INVALID_PARAMS)
        self._submit_error('pdf.merge', {'paths': [], 'output': out},
                           protocol.ERR_INVALID_PARAMS)

    def test_remove_pages(self):
        src = self._make_pdf('rm-src.pdf', pages=3)
        out = self.root / 'removed.pdf'
        self._run('pdf.remove_pages', {'path': str(src), 'output': str(out), 'pages': [2]})
        from pypdf import PdfReader
        self.assertEqual(len(PdfReader(str(out)).pages), 2)

    def test_extract_text(self):
        src = self._make_text_pdf('text-src.pdf', 'TOOLBOX-ASSIST-MARKER')
        result = self._run('pdf.extract_text', {'path': str(src)})
        self.assertIn('TOOLBOX-ASSIST-MARKER', result['text'])

    def test_set_metadata(self):
        src = self._make_pdf('meta-src.pdf', pages=1)
        out = self.root / 'meta.pdf'
        self._run('pdf.set_metadata', {'path': str(src), 'output': str(out),
                                       'metadata': {'Title': '工具箱测试'}})
        from pypdf import PdfReader
        self.assertEqual(PdfReader(str(out)).metadata.title, '工具箱测试')

    def test_protect(self):
        src = self._make_pdf('enc-src.pdf', pages=1)
        out = self.root / 'protected.pdf'
        self._run('pdf.protect', {'path': str(src), 'output': str(out), 'password': 'secret'})
        from pypdf import PdfReader
        self.assertTrue(PdfReader(str(out)).is_encrypted)

    def test_output_parent_missing_rejected(self):
        src = self._make_pdf('parent-src.pdf', pages=1)
        self._submit_error('pdf.merge', {
            'paths': [str(src)],
            'output': str(self.root / 'no-such-dir' / 'out.pdf')},
            protocol.ERR_INVALID_PARAMS)

    def test_to_images_dependency_missing(self):
        src = self._make_pdf('img-src.pdf', pages=1)
        with self._patch_missing('missing_deps_pdf_to_images', ['poppler']):
            error = self._submit_error('pdf.to_images', {'path': str(src)},
                                       protocol.ERR_DEPENDENCY_MISSING)
        self.assertEqual(error['details']['missing'], ['poppler'])

    def test_to_images_success_mocked(self):
        if not _module_available('pdf2image'):
            self.skipTest('pdf2image 未安装（成功路径夹具不可用）')
        src = self._make_pdf('img-ok.pdf', pages=1)
        pages = [Image.new('RGB', (64, 48), (10, 20, 30)),
                 Image.new('RGB', (64, 48), (40, 50, 60))]
        with self._patch_missing('missing_deps_pdf_to_images', []), \
                mock.patch('pdf2image.convert_from_path', return_value=pages) as convert:
            result = self._run('pdf.to_images', {'path': str(src), 'dpi': 200})
        self.assertEqual(result['pages'], 2)
        self.assertEqual(result['dpi'], 200)
        self.assertTrue(all(Path(f).exists() for f in result['files']))
        self.assertEqual(convert.call_args.args, (str(src),))
        self.assertEqual(convert.call_args.kwargs.get('dpi'), 200)


class BarcodeTests(DispatcherAssistTestBase):
    """barcode.*：三个动作的依赖缺失路径与成功接线。"""

    def test_qr_dependency_missing(self):
        with self._patch_missing('missing_deps_qr', ['qrcode']):
            self._submit_error('barcode.qr.generate', {'data': 'hello'},
                               protocol.ERR_DEPENDENCY_MISSING)

    def test_qr_generate_success_mocked(self):
        image = np.full((300, 300, 3), 255, dtype=np.uint8)
        with self._patch_missing('missing_deps_qr', []), \
                mock.patch('processors.barcode.generate_qr', return_value=image) as gen:
            result = self._run('barcode.qr.generate',
                               {'data': 'https://toolbox.example', 'size': 300,
                                'error_correction': 'H'})
        self.assertEqual(gen.call_args.kwargs.get('error_correction'), 'H')
        path = Path(result['path'])
        self.assertTrue(path.exists())
        self.assertEqual(result['sha256'], _sha256_file(path))
        self.assertEqual((result['width'], result['height']), (300, 300))

    def test_ean13_dependency_missing(self):
        with self._patch_missing('missing_deps_ean13', ['pystrich']):
            self._submit_error('barcode.ean13.generate', {'data': '4006381333931'},
                               protocol.ERR_DEPENDENCY_MISSING)

    def test_ean13_invalid_data_beats_dependency(self):
        """12/13 位数字校验先于依赖判定（§3.8 参数校验优先）。"""
        with self._patch_missing('missing_deps_ean13', ['pystrich']):
            self._submit_error('barcode.ean13.generate', {'data': 'abc'},
                               protocol.ERR_INVALID_PARAMS)

    def test_ean13_generate_success_mocked(self):
        """EAN-13 成功接线（资产 mock，锁 §4 通道）：pystrich 探测放行 →
        generate_barcode_ean13 按 (data, height=) 调用 → 临时 PNG 交付。"""
        image = np.full((120, 360, 3), 255, dtype=np.uint8)
        with self._patch_missing('missing_deps_ean13', []), \
                mock.patch('processors.barcode.generate_barcode_ean13',
                           return_value=image) as gen:
            result = self._run('barcode.ean13.generate',
                               {'data': '4006381333931', 'height': 120})
        self.assertEqual(gen.call_args.args, ('4006381333931',))
        self.assertEqual(gen.call_args.kwargs.get('height'), 120)
        path = Path(result['path'])
        self.assertTrue(path.exists())
        self.assertEqual(result['sha256'], _sha256_file(path))
        self.assertEqual((result['width'], result['height']), (360, 120))

    def test_decode_dependency_missing(self):
        image = self._make_image()
        with self._patch_missing('missing_deps_decode', ['pyzbar']):
            self._submit_error('barcode.decode', {'path': str(image)},
                               protocol.ERR_DEPENDENCY_MISSING)

    def test_decode_success_mocked(self):
        image = self._make_image()
        Rect = collections.namedtuple('Rect', ['x', 'y', 'width', 'height'])
        decoded = [{'data': 'HELLO-42', 'type': 'QRCODE', 'rect': Rect(1, 2, 30, 40)}]
        with self._patch_missing('missing_deps_decode', []), \
                mock.patch('processors.barcode.decode_qr', return_value=decoded):
            response = self.dispatcher.handle(_request('barcode.decode', {'path': str(image)}))
        self.assertTrue(response['success'], response)
        result = response['result']['results'][0]
        self.assertEqual(result['data'], 'HELLO-42')
        self.assertEqual(result['type'], 'QRCODE')
        self.assertEqual(result['rect'], {'x': 1, 'y': 2, 'width': 30, 'height': 40})


class SmallToolTests(DispatcherAssistTestBase):
    """checksum.file / histogram.compute / ascii.render / compare.images（小工具）。"""

    def test_checksum_matches_hashlib(self):
        payload = self.root / 'payload.bin'
        payload.write_bytes(b'toolbox-assist-checksum')
        response = self.dispatcher.handle(_request('checksum.file', {'path': str(payload)}))
        self.assertTrue(response['success'], response)
        result = response['result']
        self.assertEqual(result['md5'], hashlib.md5(b'toolbox-assist-checksum').hexdigest())
        self.assertEqual(result['sha256'], hashlib.sha256(b'toolbox-assist-checksum').hexdigest())
        self.assertEqual(result['crc32'], format(
            __import__('zlib').crc32(b'toolbox-assist-checksum') & 0xFFFFFFFF, '08x'))
        self.assertEqual(result['size'], 23)

    def test_checksum_file_not_found(self):
        self._submit_error('checksum.file', {'path': str(self.root / 'nope.bin')},
                           protocol.ERR_FILE_NOT_FOUND)

    def test_histogram_rgb_sums_to_pixel_count(self):
        image = self._make_image('hist.png')
        response = self.dispatcher.handle(
            _request('histogram.compute', {'path': str(image), 'mode': 'rgb'}))
        self.assertTrue(response['success'], response)
        histogram = response['result']['histogram']
        self.assertEqual(set(histogram), {'R', 'G', 'B'})
        for channel in 'RGB':
            self.assertEqual(sum(histogram[channel]), 32 * 24)

    def test_histogram_hsv_shape(self):
        image = self._make_image('hist-hsv.png')
        response = self.dispatcher.handle(
            _request('histogram.compute', {'path': str(image), 'mode': 'hsv'}))
        histogram = response['result']['histogram']
        self.assertEqual(len(histogram['H']), 180)
        self.assertEqual(len(histogram['S']), 256)
        self.assertEqual(len(histogram['V']), 256)

    def test_histogram_luma_shape(self):
        """luma → 256 bin 数组（§3.8：luma 为数组形状，与 rgb/hsv 的字典不同）。"""
        image = self._make_image('hist-luma.png')
        response = self.dispatcher.handle(
            _request('histogram.compute', {'path': str(image), 'mode': 'luma'}))
        self.assertTrue(response['success'], response)
        self.assertEqual(response['result']['mode'], 'luma')
        histogram = response['result']['histogram']
        self.assertIsInstance(histogram, list)
        self.assertEqual(len(histogram), 256)
        self.assertEqual(sum(histogram), 32 * 24)

    def test_histogram_invalid_mode(self):
        image = self._make_image('hist-bad.png')
        self._submit_error('histogram.compute', {'path': str(image), 'mode': 'cmyk'},
                           protocol.ERR_INVALID_PARAMS)

    def test_ascii_render(self):
        image = self._make_image('ascii.png')
        response = self.dispatcher.handle(
            _request('ascii.render', {'path': str(image), 'cols': 20}))
        self.assertTrue(response['success'], response)
        result = response['result']
        self.assertIsInstance(result['text'], str)
        self.assertEqual(result['rows'], result['text'].count('\n') + 1)
        self.assertGreater(result['rows'], 0)
        self.assertEqual(result['cols'], 20)

    def test_ascii_cols_out_of_range(self):
        image = self._make_image('ascii-bad.png')
        self._submit_error('ascii.render', {'path': str(image), 'cols': 5},
                           protocol.ERR_INVALID_PARAMS)

    def test_compare_different_images(self):
        a = self._make_image('cmp-a.png')
        b = self._make_image('cmp-b.png', color=(250, 10, 10))
        result = self._run('compare.images', {'path_a': str(a), 'path_b': str(b)})
        self.assertEqual(set(result), {'mae', 'rmse', 'mse', 'psnr', 'ncc', 'ssim'})
        self.assertGreater(result['mae'], 0.0)
        self.assertIsNotNone(result['psnr'])

    def test_compare_identical_images_psnr_null(self):
        """图像全同 → PSNR 无穷大、NCC 无定义：协议面以 null 表示（§3.8）。"""
        a = self._make_image('cmp-same.png')
        result = self._run('compare.images', {'path_a': str(a), 'path_b': str(a)})
        self.assertIsNone(result['psnr'])
        self.assertEqual(result['mse'], 0.0)

    def test_compare_missing_param(self):
        a = self._make_image('cmp-c.png')
        self._submit_error('compare.images', {'path_a': str(a)}, protocol.ERR_INVALID_PARAMS)


class LutTests(DispatcherAssistTestBase):
    """lut.apply：.cube 往返 + 解析失败提交前拒绝。"""

    def _write_cube(self, name: str, body: str) -> Path:
        path = self.root / name
        path.write_text(body, encoding='ascii')
        return path

    def test_apply_success(self):
        image = self._make_image('lut-src.png')
        cube = self._write_cube('identity.cube',
                                'LUT_3D_SIZE 2\n' + '\n'.join(
                                    f'{r} {g} {b}' for b in (0, 1) for g in (0, 1)
                                    for r in (0, 1)) + '\n')
        result = self._run('lut.apply', {'path': str(image), 'cube_path': str(cube)})
        self.assertTrue(Path(result['path']).exists())
        self.assertEqual(result['sha256'], _sha256_file(Path(result['path'])))

    def test_unparsable_cube_rejected_before_task(self):
        image = self._make_image('lut-bad-src.png')
        cube = self._write_cube('broken.cube', 'not a lut at all\n')
        self._submit_error('lut.apply', {'path': str(image), 'cube_path': str(cube)},
                           protocol.ERR_INVALID_PARAMS)


class MediaTests(DispatcherAssistTestBase):
    """media.*：外部二进制依赖缺失路径（magick/ffmpeg）。"""

    def test_extract_frames_dependency_missing(self):
        image = self._make_image('anim-src.png')
        with self._patch_missing('missing_deps_media', ['magick']):
            error = self._submit_error('media.extract_frames', {'path': str(image)},
                                       protocol.ERR_DEPENDENCY_MISSING)
        self.assertEqual(error['details']['missing'], ['magick'])

    def test_convert_animation_jxl_needs_ffmpeg(self):
        frame = self._make_image('frame-000.png')
        with self._patch_missing('missing_deps_media', ['ffmpeg']):
            self._submit_error('media.convert_animation', {
                'paths': [str(frame)], 'output': str(self.root / 'out.jxl'), 'fmt': 'jxl'},
                protocol.ERR_DEPENDENCY_MISSING)

    def test_convert_animation_success_mocked(self):
        """合成动画成功接线（资产 mock）：fmt 缺省取 output 扩展名（§3.8），
        fps 缺省 12 透传，result 为 {path}。"""
        frame = self._make_image('conv-frame.png')
        out = self.root / 'conv-out.gif'
        with self._patch_missing('missing_deps_media', []), \
                mock.patch('processors.media.convert_animation',
                           return_value=str(out)) as convert:
            result = self._run('media.convert_animation',
                               {'paths': [str(frame)], 'output': str(out)})
        self.assertEqual(result, {'path': str(out)})
        self.assertEqual(convert.call_args.args, ([str(frame)], str(out), 'gif'))
        self.assertEqual(convert.call_args.kwargs.get('fps'), 12.0)

    def test_extract_frames_success_mocked(self):
        image = self._make_image('anim-ok.png')
        with self._patch_missing('missing_deps_media', []), \
                mock.patch('processors.media.extract_frames',
                           return_value=[str(self.root / 'anim-ok_0001.png')]) as extract:
            result = self._run('media.extract_frames', {'path': str(image), 'fmt': 'png'})
        self.assertEqual(result['files'], [str(self.root / 'anim-ok_0001.png')])
        self.assertEqual(extract.call_args.args[2], 'png')

    def test_invalid_fmt_rejected(self):
        image = self._make_image('anim-bad.png')
        self._submit_error('media.extract_frames', {'path': str(image), 'fmt': '../evil'},
                           protocol.ERR_INVALID_PARAMS)


class ExifWatermarkTests(DispatcherAssistTestBase):
    """exif.extract / exif.strip / watermark.text（parity.py 资产）。"""

    def _jpeg_with_exif(self) -> tuple[Path, Path]:
        path = self.root / 'exif.jpg'
        image = Image.new('RGB', (16, 16), (200, 10, 10))
        exif = image.getexif()
        exif[0x010E] = 'toolbox-test'  # ImageDescription
        image.save(path, format='JPEG', exif=exif.tobytes())
        return path, self.root / 'clean.jpg'

    def test_exif_extract(self):
        src, _ = self._jpeg_with_exif()
        response = self.dispatcher.handle(_request('exif.extract', {'path': str(src)}))
        self.assertTrue(response['success'], response)
        self.assertEqual(response['result']['exif'].get('270'), 'toolbox-test')

    def test_exif_strip(self):
        src, out = self._jpeg_with_exif()
        result = self._run('exif.strip', {'path': str(src), 'output': str(out)})
        self.assertTrue(Path(result['path']).exists())
        self.assertEqual(len(Image.open(out).getexif()), 0)

    def test_watermark_text(self):
        src = self._make_image('wm-src.png')
        out = self.root / 'wm-out.png'
        self._run('watermark.text', {'path': str(src), 'output': str(out), 'text': 'toolbox',
                                     'opacity': 200, 'position': 'center'})
        self.assertTrue(out.exists())
        self.assertEqual(Image.open(out).size, (32, 24))

    def test_watermark_invalid_position(self):
        src = self._make_image('wm-bad.png')
        self._submit_error('watermark.text', {
            'path': str(src), 'output': str(self.root / 'wm-bad-out.png'),
            'text': 'x', 'position': 'middle'}, protocol.ERR_INVALID_PARAMS)


class ArchiveCryptoBase64Tests(DispatcherAssistTestBase):
    """archive.create / crypto.* / base64.*（parity.py 资产，Phase 7 清单
    "压缩、归档、加密和 Base64"）。"""

    def _sources(self) -> list[Path]:
        return [self._make_image('zip-a.png'), self._make_image('zip-b.png')]

    def test_archive_create(self):
        sources = self._sources()
        out = self.root / 'bundle.zip'
        result = self._run('archive.create', {'paths': [str(p) for p in sources],
                                              'output': str(out)})
        self.assertTrue(Path(result['path']).exists())
        with zipfile.ZipFile(out) as bundle:
            self.assertEqual(sorted(Path(n).name for n in bundle.namelist()),
                             ['zip-a.png', 'zip-b.png'])

    def test_crypto_roundtrip(self):
        if not _module_available('cryptography'):
            self.skipTest('cryptography 未安装')
        src = self.root / 'secret.txt'
        src.write_bytes(b'top secret payload')
        encrypted, decrypted = self.root / 'secret.enc', self.root / 'secret.dec'
        self._run('crypto.encrypt', {'path': str(src), 'output': str(encrypted),
                                     'password': 'pw'})
        self.assertNotEqual(encrypted.read_bytes(), b'top secret payload')
        self._run('crypto.decrypt', {'path': str(encrypted), 'output': str(decrypted),
                                     'password': 'pw'})
        self.assertEqual(decrypted.read_bytes(), b'top secret payload')

    def test_crypto_dependency_missing(self):
        src = self._make_image('crypto-src.png')
        with self._patch_missing('missing_deps_crypto', ['cryptography']):
            self._submit_error('crypto.encrypt', {
                'path': str(src), 'output': str(self.root / 'x.enc'), 'password': 'pw'},
                protocol.ERR_DEPENDENCY_MISSING)

    def test_base64_roundtrip(self):
        src = self.root / 'b64-src.bin'
        src.write_bytes(b'roundtrip-\xff-payload')
        encoded, decoded = self.root / 'b64.txt', self.root / 'b64-out.bin'
        self._run('base64.encode', {'path': str(src), 'output': str(encoded)})
        self.assertEqual(encoded.read_text(encoding='ascii'),
                         base64.b64encode(b'roundtrip-\xff-payload').decode('ascii'))
        self._run('base64.decode', {'path': str(encoded), 'output': str(decoded)})
        self.assertEqual(decoded.read_bytes(), b'roundtrip-\xff-payload')


class AiAssistTests(DispatcherAssistTestBase):
    """AI 能力：模型注册表如实降级 + 模型路径配置 + 动作依赖双路径（§3.8）。"""

    def test_models_list_uninstalled_when_no_model_files(self):
        """无模型文件 → installed 全 false（重模型能力默认降级，不谎报）。"""
        from processors import ai_models
        with mock.patch.object(ai_models, 'is_installed', return_value=False), \
                mock.patch(f'{ASSIST}.model_path_config', return_value={}):
            response = self.dispatcher.handle(_request('ai.models.list', {}))
        self.assertTrue(response['success'], response)
        result = response['result']
        self.assertTrue(result['models'], '模型注册表为空')
        for model in result['models']:
            self.assertFalse(model['installed'], f"{model['id']} 未安装却报 installed")
            self.assertIn('size', model)
        self.assertIn('CPU', result['backends'])
        self.assertEqual(result['model_paths'], {})
        self.assertIsInstance(result['cache_root'], str)

    def test_models_list_task_filter_with_alias(self):
        from processors import ai_models
        with mock.patch.object(ai_models, 'is_installed', return_value=False):
            zh = self.dispatcher.handle(_request('ai.models.list', {'task': '超分'}))
            en = self.dispatcher.handle(_request('ai.models.list', {'task': 'upscale'}))
        self.assertTrue(zh['success'] and en['success'])
        self.assertTrue(zh['result']['models'])
        self.assertEqual({m['task'] for m in zh['result']['models']}, {'超分'})
        self.assertEqual(zh['result']['models'], en['result']['models'])

    def test_model_path_config_settings_and_env(self):
        """模型路径配置读取：settings.json model_paths 优先，其次
        TOOLBOX_AI_MODEL_DIR 环境目录；显式配置覆盖环境同名键。"""
        from processors import ai_models
        cache = self.root / 'ai-cache'
        env_dir = self.root / 'env-models'
        env_dir.mkdir()
        (env_dir / 'EDSR_x4.pb').write_bytes(b'dummy')
        (env_dir / 'edsr-local.pb').write_bytes(b'local')
        with mock.patch.dict(os.environ, {'TOOLBOX_AI_MODEL_DIR': str(env_dir)}), \
                mock.patch.object(ai_models, 'CACHE_ROOT', cache):
            # 仅环境目录：文件名去扩展名为键。
            config = assist_adapter.model_path_config()
            self.assertEqual(config.get('EDSR_x4'), str(env_dir / 'EDSR_x4.pb'))
            self.assertEqual(config.get('edsr-local'), str(env_dir / 'edsr-local.pb'))
            # settings.json 同键覆盖环境目录。
            settings_file = ai_models.cache_root() / 'settings.json'
            settings_file.write_text(json.dumps(
                {'model_paths': {'EDSR_x4': str(self.root / 'explicit.pb')}}), encoding='utf-8')
            config = assist_adapter.model_path_config()
            self.assertEqual(config.get('EDSR_x4'), str(self.root / 'explicit.pb'))
            self.assertEqual(config.get('edsr-local'), str(env_dir / 'edsr-local.pb'))
            # ai.models.list 面上同样可见。
            with mock.patch.object(ai_models, 'is_installed', return_value=False):
                response = self.dispatcher.handle(_request('ai.models.list', {}))
        self.assertEqual(response['result']['model_paths'].get('edsr-local'),
                         str(env_dir / 'edsr-local.pb'))
        self.assertEqual(response['result']['model_paths'].get('EDSR_x4'),
                         str(self.root / 'explicit.pb'))

    def test_background_remove_dependency_missing(self):
        image = self._make_image('ai-bg.png')
        with self._patch_missing('missing_deps_ai_background', ['rembg', 'model:u2net']):
            error = self._submit_error('ai.background.remove', {'path': str(image)},
                                       protocol.ERR_DEPENDENCY_MISSING)
        self.assertEqual(error['details']['missing'], ['rembg', 'model:u2net'])

    def test_background_remove_unknown_model(self):
        image = self._make_image('ai-bg-model.png')
        self._submit_error('ai.background.remove', {'path': str(image), 'model': 'nope'},
                           protocol.ERR_INVALID_PARAMS)

    def test_background_remove_success_mocked(self):
        image = self._make_image('ai-bg-ok.png')
        cutout = np.zeros((16, 16, 4), dtype=np.uint8)
        cutout[..., 3] = 128
        with self._patch_missing('missing_deps_ai_background', []), \
                mock.patch('processors.ai.remove_background', return_value=cutout) as remove:
            result = self._run('ai.background.remove',
                               {'path': str(image), 'model': 'u2net', 'background': [0, 255, 0]})
        self.assertEqual(remove.call_args.kwargs.get('model'), 'u2net')
        path = Path(result['path'])
        self.assertTrue(path.exists())
        self.assertEqual(result['sha256'], _sha256_file(path))

    def test_upscale_dependency_missing_without_model(self):
        image = self._make_image('ai-up.png')
        with self._patch_missing('missing_deps_ai_upscale',
                                 ['upscayl', 'model:realesrgan-x4plus']), \
                mock.patch(f'{ASSIST}.model_path_config', return_value={}):
            self._submit_error('ai.upscale', {'path': str(image)},
                               protocol.ERR_DEPENDENCY_MISSING)

    def test_upscale_explicit_model_path_missing_rejected(self):
        """显式 model_path 指向不存在的文件 → 参数错误（用户输入问题）。"""
        image = self._make_image('ai-up-missing.png')
        self._submit_error('ai.upscale', {'path': str(image),
                                          'model_path': str(self.root / 'no-such.pb')},
                           protocol.ERR_INVALID_PARAMS)

    def test_upscale_with_configured_model_path(self):
        """显式模型路径命中（真实探测通过：文件存在即可用）→ 接线
        upscale_sr，不要求 upscayl。"""
        image = self._make_image('ai-up-ok.png')
        model_file = self.root / 'EDSR_x4.pb'
        model_file.write_bytes(b'dummy model')
        upscaled = np.zeros((32, 32, 3), dtype=np.uint8)
        with mock.patch('processors.ai.upscale_sr', return_value=upscaled) as sr:
            result = self._run('ai.upscale', {'path': str(image), 'scale': 4,
                                              'model_path': str(model_file)})
        self.assertEqual(sr.call_args.kwargs.get('model_path'), str(model_file))
        self.assertEqual(sr.call_args.kwargs.get('scale'), 4)
        self.assertTrue(Path(result['path']).exists())

    def test_denoise_real(self):
        """核心依赖真实执行（OpenCV NLM，无外部依赖）：小图往返。"""
        image = self._make_image('ai-denoise.png')
        result = self._run('ai.denoise', {'path': str(image), 'strength': 5.0})
        path = Path(result['path'])
        self.assertTrue(path.exists())
        self.assertEqual(result['sha256'], _sha256_file(path))

    def test_denoise_invalid_strength(self):
        image = self._make_image('ai-denoise-bad.png')
        self._submit_error('ai.denoise', {'path': str(image), 'strength': 999},
                           protocol.ERR_INVALID_PARAMS)

    def test_colorize_real(self):
        image = self._make_image('ai-color.png')
        for mode, style in (('simple', None), ('transfer', 'cool')):
            params = {'path': str(image), 'mode': mode}
            if style:
                params['style'] = style
            result = self._run('ai.colorize', params, request_id=f'req-color-{mode}')
            self.assertTrue(Path(result['path']).exists())

    def test_colorize_invalid_style(self):
        image = self._make_image('ai-color-bad.png')
        self._submit_error('ai.colorize', {'path': str(image), 'mode': 'transfer',
                                           'style': 'neon'}, protocol.ERR_INVALID_PARAMS)


if __name__ == '__main__':
    unittest.main()
