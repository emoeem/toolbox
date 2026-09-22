from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from processors import parity


class ParityProcessorTests(unittest.TestCase):
    def test_feature_registry_matches_reference_count(self):
        self.assertEqual(len(parity.PARITY_FEATURES), 67)
        self.assertEqual(parity.parity_audit()["pending"], [])

    def test_generators_create_valid_images(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name, fn in (
                ("fractal.png", lambda p: parity.generate_fractal(str(p), 128, 96, 24)),
                ("texture.png", lambda p: parity.texture_generate(str(p), 128, 96, "cloud", 8, 7)),
                ("mesh.png", lambda p: parity.mesh_gradient(str(p), 128, 96)),
            ):
                out = root / name
                fn(out)
                with Image.open(out) as image:
                    self.assertEqual(image.size, (128, 96))

    def test_fusion_modes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inputs=[]
            for i, value in enumerate((40, 80, 120)):
                p=root/f"{i}.png"; Image.new("RGB",(32,32),(value,value,value)).save(p); inputs.append(str(p))
            for mode in ("median", "mean", "max", "min"):
                out=root/f"{mode}.png"; parity.multi_frame_fusion(inputs,str(out),mode)
                with Image.open(out) as image: self.assertEqual(image.size,(32,32))

    def test_batch_rename_rejects_collisions(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=root/"a.png"; b=root/"b.png"; a.write_bytes(b"a"); b.write_bytes(b"b")
            with self.assertRaises(ValueError):
                parity.apply_batch_rename([str(a),str(b)],"same")


if __name__ == "__main__":
    unittest.main()
