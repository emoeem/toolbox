import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
import numpy as np

from app.main_window import MainWindow, TOOL_ITEMS
from processors.filters import ALL_FILTERS

app = QApplication(sys.argv)
mw = MainWindow()
mw.preview.set_image(np.random.randint(50, 200, (400, 500, 3), dtype=np.uint8))

print(f"面板总数: {len(TOOL_ITEMS)}")
print(f"滤镜总数: {len(ALL_FILTERS)}\n")

all_ok = True
for i in range(len(TOOL_ITEMS)):
    icon, name = TOOL_ITEMS[i]
    try:
        mw._select_tool(i)
        print(f"  ✅ [{i:>2}] {icon} {name}")
    except Exception as e:
        print(f"  ❌ [{i:>2}] {icon} {name}: {e}")
        all_ok = False

print("\n滤镜抽样测试:")
sample = ["lomo","polaroid","thermal","pixelate","emboss","kaleidoscope","duo_tone",
          "hdr_tone_mapping","posterize","barrel_distortion","cyberpunk","ascii_filter",
          "silhouette","neon_glow","bokeh"]
img = mw.preview.current_image()
if img is None:
    img = np.random.randint(0,255,(200,200,3),dtype=np.uint8)
for n in sample:
    f = ALL_FILTERS.get(n)
    if f:
        try:
            r = f[1](img.copy())
            print(f"  ✅ {n}")
        except Exception as e:
            print(f"  ❌ {n}: {e}")
            all_ok = False

from processors import shapes, compare, checksum, lut, gradients, stitch, barcode, histogram, batch as batch_mod
print("\n核心模块导入 + 调用测试:")
print(f"  ✅ shapes.shape_mask(100,100,'heart') = {shapes.shape_mask(100,100,'heart').shape}")
print(f"  ✅ compare.SSIM(img,img) = {compare.compare(img,img)['ssim']:.3f}")
print(f"  ✅ checksum.sha256('test') = {checksum.sha256('test')[:16]}...")
print(f"  ✅ lut.lut_identity().shape = {lut.lut_identity().shape}")
print(f"  ✅ gradients.linear_gradient(100,50,...) = {gradients.linear_gradient(100,50,(255,0,0),(0,0,255),45).shape}")
print(f"  ✅ barcode.generate_qr('hi',100) = {barcode.generate_qr('hi',100).shape}")
print(f"  ✅ histogram.histogram_rgb(img) R len = {len(histogram.histogram_rgb(img)['R'])}")
print(f"  ✅ batch.SOCIAL_PRESETS 数量 = {len(batch_mod.SOCIAL_PRESETS)}")

print(f"\n{'🎉 ALL OK' if all_ok else '❌ 有错误'}")
