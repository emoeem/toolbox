
import numpy as np
from processors.filters import apply_filter

def test_night_vision_runs_and_returns_rgb():
    img = np.full((32, 32, 3), 120, dtype=np.uint8)
    out = apply_filter('night_vision', img)
    assert out.shape == img.shape
    assert out.dtype == np.uint8
    assert not np.array_equal(out, img)
