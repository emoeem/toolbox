import sys, time, numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

app = QApplication(sys.argv)
from app.main_window import MainWindow


def wait_apply(window, timeout=15.0):
    """_apply_adjust_full_res() now runs on the task queue, not inline."""
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)
        if not window._apply_in_progress:
            app.processEvents()
            return
    raise AssertionError("full-resolution apply did not finish")

w = MainWindow()
orig_img = np.random.randint(30, 230, (300, 300, 3), dtype=np.uint8)
w.preview.set_image(orig_img)
w._build_adjust_panel()

assert w.preview.original_image() is not None
assert w._applied_image is None
assert len(w._history) == 0
print("[OK] init")

c0 = w._adjust_controls[0]
for i in range(8):
    c0["slider"].setValue(c0["slider"].minimum() + (c0["slider"].maximum() - c0["slider"].minimum()) * (i + 1) * 0.12)
    QTest.qWait(15)
QTest.qWait(500)
print("[OK] quick drag")

w._apply_adjust_full_res()
wait_apply(w)

assert len(w._history) == 1, f"history={len(w._history)}"
assert w._applied_image is not None
assert np.array_equal(w.preview.original_image(), orig_img)
print("[OK] Apply + Original preserved")

w.undo()
QTest.qWait(200)
assert len(w._history) == 0
assert np.array_equal(w._applied_image, orig_img)
assert np.array_equal(w.preview.current_image(), orig_img)
print("[OK] Undo")

c1 = w._adjust_controls[1]
c1["slider"].setValue(c1["slider"].minimum() + (c1["slider"].maximum() - c1["slider"].minimum()) * 0.5)
QTest.qWait(50)
w._apply_adjust_full_res()
wait_apply(w)
assert len(w._history) == 1
print("[OK] 2nd Apply")

w.reset_all()
QTest.qWait(200)
assert len(w._history) == 0
assert w._applied_image is None
assert np.array_equal(w.preview.original_image(), orig_img)
print("[OK] Reset")

print("\n=== ALL SMOKE TEST PASSED ===")
w.close()
