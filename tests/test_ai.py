import unittest
from unittest.mock import patch
import numpy as np
from processors.ai import remove_background

class TestBackgroundRemoval(unittest.TestCase):
    def test_missing_rembg_is_clear_error(self):
        with patch.dict("sys.modules", {"rembg": None}):
            with self.assertRaisesRegex(RuntimeError, "rembg 后端不可用"):
                remove_background(np.zeros((8, 8, 3), dtype=np.uint8))
