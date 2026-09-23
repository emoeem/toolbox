"""ImageToolbox parity helpers for the desktop Toolbox.

Optional dependencies are detected at runtime so the core app remains usable.
"""
from __future__ import annotations
import base64, io, json, math, os, zipfile, hashlib, subprocess, shutil, wave, struct, re
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageColor
import numpy as np


def base64_encode(path: str, output: str) -> str:
    Path(output).write_text(base64.b64encode(Path(path).read_bytes()).decode(), encoding="utf-8")
    return output


def base64_decode(path: str, output: str) -> str:
    Path(output).write_bytes(base64.b64decode(Path(path).read_text(encoding="utf-8")))
    return output


def archive_images(paths, output: str) -> str:
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            z.write(p, Path(p).name)
    return output


def image_info(path: str) -> dict:
    with Image.open(path) as im:
        return {"format": im.format, "mode": im.mode, "width": im.width, "height": im.height,
                "frames": getattr(im, "n_frames", 1), "bytes": os.path.getsize(path)}


def split_grid(path: str, output_dir: str, rows: int, cols: int, fmt="PNG") -> list[str]:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    im = Image.open(path).convert("RGBA")
    w, h = im.size; out=[]
    for r in range(rows):
        for c in range(cols):
            box=(c*w//cols, r*h//rows, (c+1)*w//cols, (r+1)*h//rows)
            p=Path(output_dir)/f"tile_{r+1:02d}_{c+1:02d}.{fmt.lower()}"; im.crop(box).save(p); out.append(str(p))
    return out


def stack_images(paths, output: str, direction="vertical", spacing=0, background=(0,0,0,0)) -> str:
    ims=[Image.open(p).convert("RGBA") for p in paths]
    if not ims: raise ValueError("no images")
    if direction=="horizontal":
        size=(sum(i.width for i in ims)+spacing*(len(ims)-1), max(i.height for i in ims))
        pos=lambda i,off:(off,(size[1]-i.height)//2)
    else:
        size=(max(i.width for i in ims), sum(i.height for i in ims)+spacing*(len(ims)-1))
        pos=lambda i,off:((size[0]-i.width)//2,off)
    canvas=Image.new("RGBA",size,background); off=0
    for im in ims: canvas.alpha_composite(im,pos(im,off)); off += (im.width if direction=="horizontal" else im.height)+spacing
    canvas.save(output); return output
def auto_crop(path: str, output: str, tolerance=8) -> str:
    im=Image.open(path).convert("RGBA"); bg=Image.new("RGBA", im.size, im.getpixel((0,0)))
    diff=ImageChops.difference(im,bg); diff=diff.convert("L").point(lambda p: 255 if p>tolerance else 0)
    box=diff.getbbox(); im.crop(box or (0,0,*im.size)).save(output); return output


def add_border(path: str, output: str, width: int, color="#ffffff") -> str:
    ImageOps.expand(Image.open(path), border=width, fill=color).save(output); return output


def resize_by_weight(path: str, output: str, target_kb: int, quality_min=25) -> str:
    if int(target_kb) < 1:
        raise ValueError("target_kb must be at least 1")
    im=Image.open(path).convert("RGB"); lo,hi=quality_min,95; best=None
    while lo<=hi:
        q=(lo+hi)//2; b=io.BytesIO(); im.save(b,"JPEG",quality=q,optimize=True)
        if len(b.getvalue())<=target_kb*1024: best=b.getvalue(); lo=q+1
        else: hi=q-1
    if best is None: im.save(output,"JPEG",quality=quality_min,optimize=True)
    else: Path(output).write_bytes(best)
    return output


def add_noise(path: str, output: str, amount=12.0) -> str:
    im=np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    noise=np.random.normal(0,amount,im.shape[:2]+(1,)); arr=np.clip(im+noise,0,255).astype(np.uint8)
    Image.fromarray(arr).save(output); return output


def grayscale(path: str, output: str) -> str:
    Image.open(path).convert("L").save(output); return output


def invert(path: str, output: str) -> str:
    im=Image.open(path).convert("RGBA"); r,g,b,a=im.split(); Image.merge("RGBA",(ImageOps.invert(r),ImageOps.invert(g),ImageOps.invert(b),a)).save(output); return output


def watermark(path: str, output: str, text: str, opacity=128, position="bottom-right") -> str:
    im=Image.open(path).convert("RGBA"); layer=Image.new("RGBA",im.size,(0,0,0,0)); d=ImageDraw.Draw(layer)
    box=d.textbbox((0,0),text); tw,th=box[2]-box[0],box[3]-box[1]; pad=24
    pos={"top-left":(pad,pad),"top-right":(im.width-tw-pad,pad),"bottom-left":(pad,im.height-th-pad),"bottom-right":(im.width-tw-pad,im.height-th-pad),"center":((im.width-tw)//2,(im.height-th)//2)}.get(position,(pad,pad))
    d.text(pos,text,fill=(255,255,255,int(opacity))); im.alpha_composite(layer); im.save(output); return output


def find_duplicates(paths) -> dict[str,list[str]]:
    groups={}
    for p in paths:
        try: h=hashlib.sha256(Path(p).read_bytes()).hexdigest(); groups.setdefault(h,[]).append(p)
        except OSError: pass
    return {k:v for k,v in groups.items() if len(v)>1}
def dominant_palette(path: str, count=8) -> list[str]:
    im=Image.open(path).convert("RGB").resize((256,256)); arr=np.asarray(im).reshape(-1,3)
    # Fast histogram-based palette; deterministic and dependency-free.
    q=(arr//32)*32; vals,cnt=np.unique(q,axis=0,return_counts=True); idx=np.argsort(cnt)[::-1][:count]
    return ["#%02x%02x%02x"%tuple(int(x) for x in vals[i]) for i in idx]


def to_svg(path: str, output: str) -> str:
    im=Image.open(path).convert("RGBA"); buf=io.BytesIO(); im.save(buf,"PNG"); data=base64.b64encode(buf.getvalue()).decode()
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{im.width}" height="{im.height}" viewBox="0 0 {im.width} {im.height}"><image width="100%" height="100%" href="data:image/png;base64,{data}"/></svg>'
    Path(output).write_text(svg,encoding="utf-8"); return output


def convert_format(path: str, output: str, fmt: str) -> str:
    im=Image.open(path)
    if fmt.upper() in {"JPG","JPEG"} and im.mode in {"RGBA","LA","P"}: im=im.convert("RGB")
    im.save(output,format=fmt.upper()); return output


def compress_image(path: str, output: str, quality=82) -> str:
    im=Image.open(path)
    suffix = Path(output).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        if im.mode in {"RGBA", "LA", "P"}: im=im.convert("RGB")
        im.save(output, quality=int(quality), optimize=True)
    elif suffix == ".webp":
        im.save(output, format="WEBP", quality=int(quality), optimize=True)
    else:
        im.save(output, optimize=True)
    return output


def jpeg_to_webp(path: str, output: str, quality=85) -> str:
    im=Image.open(path).convert("RGB")
    im.save(output, "WEBP", quality=int(quality), method=6)
    return output


def make_contact_sheet(paths, output: str, columns=4, thumb=240, spacing=12) -> str:
    ims=[]
    for p in paths:
        try: ims.append(ImageOps.contain(Image.open(p).convert("RGB"),(thumb,thumb)))
        except Exception: pass
    rows=math.ceil(len(ims)/columns); canvas=Image.new("RGB",(columns*thumb+(columns+1)*spacing,rows*thumb+(rows+1)*spacing),"#202020")
    for n,im in enumerate(ims): x=spacing+(n%columns)*(thumb+spacing); y=spacing+(n//columns)*(thumb+spacing); canvas.paste(im,(x+(thumb-im.width)//2,y+(thumb-im.height)//2))
    canvas.save(output); return output


def encrypt_file(path: str, output: str, password: str) -> str:
    from cryptography.fernet import Fernet
    import base64, hashlib
    key=base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest()); Path(output).write_bytes(Fernet(key).encrypt(Path(path).read_bytes())); return output


def decrypt_file(path: str, output: str, password: str) -> str:
    from cryptography.fernet import Fernet
    import base64, hashlib
    key=base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest()); Path(output).write_bytes(Fernet(key).decrypt(Path(path).read_bytes())); return output
PARITY_FEATURES = {
"ai-tools":"AI 工具","apng-tools":"APNG 工具","archive-tools":"归档/打包","ascii-art":"ASCII 艺术","audio-cover-extractor":"音频封面提取",
"base64-tools":"Base64","batch-rename":"批量重命名","checksum-tools":"校验和","cipher":"文件加密","code-preview":"代码预览","collage-maker":"拼贴制作",
"color-library":"颜色库","color-tools":"颜色工具","compression-lab":"压缩实验室","curves":"曲线","delete-exif":"删除 EXIF","document-scanner":"文档扫描",
"draw":"绘图标注","duplicate-finder":"重复图片","edit-exif":"编辑 EXIF","fractal-generation":"分形生成","image-cutting":"图片切割","image-splitting":"图片分割",
"image-stacking":"图片堆叠","jxl-tools":"JPEG XL","limits-resize":"限制尺寸","load-net-image":"网络图片","markup-layers":"标注图层","mesh-gradients":"网格渐变",
"multi-frame-fusion":"多帧融合","noise-generation":"噪声生成","palette-pdf":"调色板 PDF","palette-tools":"调色板","photomosaic":"照片马赛克","pick-color":"取色器",
"quick-tiles":"快速拼图","recognize-text":"文字识别","resize-convert":"尺寸/转换","scan-qr-code":"二维码扫描","shader-studio":"Shader Studio","single-edit":"单图编辑",
"svg-maker":"SVG 制作","texture-generation":"纹理生成","wallpapers-export":"壁纸导出","webp-tools":"WebP 工具","weight-resize":"按体积缩放","watermarking":"水印",
"app-logs":"应用日志","compare":"图像比较","crop":"裁剪","easter-egg":"彩蛋","erase-background":"背景擦除","filters":"滤镜","format-conversion":"格式转换",
"gif-tools":"GIF 工具","gradient-maker":"渐变制作","help":"帮助","image-preview":"图片预览","image-stitch":"图片拼接","libraries-info":"库信息",
"library-details":"库详情","main":"主界面","media-picker":"媒体选择","pdf-tools":"PDF 工具","root":"核心模块","settings":"设置","usage-statistics":"使用统计"}

# ---- ImageToolbox desktop implementations ----
def resize_with_limits(path, output, max_width=4096, max_height=4096, mode="contain"):
    if int(max_width) <= 0 or int(max_height) <= 0:
        raise ValueError("max_width and max_height must be greater than 0")
    im=Image.open(path)
    ratio=min(max_width/im.width, max_height/im.height, 1.0)
    if mode == "stretch": size=(max_width,max_height)
    elif mode == "cover":
        ratio=max(max_width/im.width,max_height/im.height); size=(round(im.width*ratio),round(im.height*ratio))
    else: size=(max(1,round(im.width*ratio)),max(1,round(im.height*ratio)))
    if size != im.size: im=im.resize(size,Image.Resampling.LANCZOS)
    im.save(output); return output

def cut_image(path, output, x=0, y=0, width=None, height=None):
    im=Image.open(path); width=width or im.width-x; height=height or im.height-y
    im.crop((x,y,x+width,y+height)).save(output); return output

def create_gradient(output, width=1200, height=800, start="#8b5cf6", end="#22d3ee", angle=0):
    a=np.array(ImageColor.getrgb(start),dtype=np.float32); b=np.array(ImageColor.getrgb(end),dtype=np.float32)
    yy,xx=np.mgrid[0:height,0:width]; rad=np.deg2rad(angle); t=(xx*np.cos(rad)+yy*np.sin(rad)); t=(t-t.min())/(t.max()-t.min() or 1)
    arr=np.clip(a[None,None,:]*(1-t[...,None])+b[None,None,:]*t[...,None],0,255).astype(np.uint8)
    Image.fromarray(arr,"RGB").save(output); return output

def generate_noise(output,width=1024,height=1024,amount=1.0,kind="gaussian"):
    allowed={"gaussian","uniform"}
    if kind not in allowed:
        raise ValueError(f"unsupported noise kind: {kind!r}; expected one of {sorted(allowed)}")
    if kind=="uniform": arr=np.random.uniform(0,255,(height,width,3))
    else: arr=np.random.normal(127,70*amount,(height,width,3))
    Image.fromarray(np.clip(arr,0,255).astype(np.uint8)).save(output); return output

def generate_fractal(output,width=1024,height=768,iterations=80,center=(-0.7435,0.1314),scale=3.0):
    x0,y0=center; xs=np.linspace(x0-scale/2,x0+scale/2,width); ys=np.linspace(y0-scale/2*height/width,y0+scale/2*height/width,height)
    X,Y=np.meshgrid(xs,ys); C=X+1j*Y; Z=np.zeros_like(C); out=np.zeros(C.shape,dtype=np.uint16); alive=np.ones(C.shape,bool)
    for i in range(iterations):
        Z[alive]=Z[alive]**2+C[alive]; escaped=np.abs(Z)>2; out[escaped & alive]=i; alive &= ~escaped
    v=np.clip(out/ max(1,iterations-1)*255,0,255).astype(np.uint8); rgb=np.stack([v,np.roll(v,32,1),np.roll(v,64,0)],axis=2); Image.fromarray(rgb).save(output); return output

def apply_curves(path, output, points=((0,0),(64,48),(128,150),(192,220),(255,255))):
    pts=np.asarray(points,dtype=float); lut=np.interp(np.arange(256),pts[:,0],pts[:,1]).astype(np.uint8)
    im=Image.open(path); arr=np.asarray(im); out=lut[arr] if arr.dtype==np.uint8 else arr; Image.fromarray(out).save(output); return output

def strip_exif(path, output):
    im=Image.open(path)
    data=list(im.getdata()); clean=Image.new(im.mode,im.size); clean.putdata(data)
    fmt=(im.format or Path(output).suffix.lstrip('.')).upper()
    if fmt in {'JPG','JPEG'} and clean.mode in {'RGBA','LA','P'}: clean=clean.convert('RGB')
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    clean.save(output,format=fmt); return output

def extract_exif(path):
    im=Image.open(path); ex=im.getexif(); return {str(k):v for k,v in ex.items()}

def find_similar_images(paths, threshold=8):
    def dhash(p):
        a=np.asarray(Image.open(p).convert('L').resize((9,8),Image.Resampling.LANCZOS)); return (a[:,1:]>a[:,:-1]).flatten()
    hashes=[]
    for p in paths:
        try: hashes.append((p,dhash(p)))
        except Exception: pass
    groups=[]; used=set()
    for i,(p,h) in enumerate(hashes):
        if p in used: continue
        g=[p]
        for q,h2 in hashes[i+1:]:
            if int(np.count_nonzero(h!=h2))<=threshold: g.append(q); used.add(q)
        if len(g)>1: groups.append(g)
    return groups

def make_collage(paths, output, columns=3, cell_width=400, cell_height=300, spacing=16, background="#202020"):
    ims=[ImageOps.contain(Image.open(p).convert("RGB"),(cell_width,cell_height)) for p in paths]
    rows=max(1,math.ceil(len(ims)/columns)); canvas=Image.new("RGB",(columns*cell_width+(columns+1)*spacing,rows*cell_height+(rows+1)*spacing),background)
    for n,im in enumerate(ims):
        x=spacing+n%columns*(cell_width+spacing); y=spacing+n//columns*(cell_height+spacing); canvas.paste(im,(x+(cell_width-im.width)//2,y+(cell_height-im.height)//2))
    canvas.save(output); return output

def image_to_ascii(path, output, width=100, chars="@%#*+=-:. "):
    im=Image.open(path).convert('L'); h=max(1,round(im.height*width/im.width*0.48)); im=im.resize((width,h)); a=np.asarray(im); idx=(a/255*(len(chars)-1)).astype(int)
    Path(output).write_text('\n'.join(''.join(chars[i] for i in row) for row in idx),encoding='utf-8'); return output

def make_palette_pdf(path, output, count=8):
    from reportlab.pdfgen import canvas
    colors=dominant_palette(path,count); c=canvas.Canvas(str(output),pagesize=(600,450)); c.setFont('Helvetica-Bold',18); c.drawString(40,410,'Image Palette')
    for i,h in enumerate(colors):
        rgb=tuple(int(h[j:j+2],16)/255 for j in (1,3,5)); c.setFillColorRGB(*rgb); c.rect(40+i*65,300,55,80,fill=1,stroke=0); c.setFillColorRGB(0,0,0); c.drawCentredString(67+i*65,280,h)
    c.save(); return output

def make_gif(paths, output, duration=100, loop=0):
    ims=[Image.open(p).convert('RGBA') for p in paths]
    if not ims: raise ValueError('no frames')
    ims[0].save(output,save_all=True,append_images=ims[1:],duration=duration,loop=loop,disposal=2); return output

def extract_gif_frames(path, output_dir, prefix='frame'):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    im=Image.open(path); out=[]
    for i in range(getattr(im,'n_frames',1)):
        im.seek(i); p=Path(output_dir)/f'{prefix}_{i:04d}.png'; im.convert('RGBA').save(p); out.append(str(p))
    return out

def scan_qr(path):
    try:
        import cv2
        det=cv2.QRCodeDetector(); data,points,_=det.detectAndDecode(cv2.imread(path)); return [data] if data else []
    except Exception: return []

def document_scan(path, output, threshold=160):
    import cv2
    img=cv2.imread(path); gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY); blur=cv2.GaussianBlur(gray,(5,5),0); bw=cv2.adaptiveThreshold(blur,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,threshold-160 if threshold>=160 else 0); cv2.imwrite(output,bw); return output

def add_text(path, output, text, x=32, y=32, size=48, color="#ffffff"):
    im=Image.open(path).convert('RGBA'); d=ImageDraw.Draw(im); d.text((x,y),text,fill=color,stroke_width=0); im.save(output); return output

def merge_animation_files(paths, output, duration=100):
    frames=[]
    for p in paths:
        im=Image.open(p)
        for i in range(getattr(im,'n_frames',1)):
            im.seek(i); frames.append(im.convert('RGBA').copy())
    if not frames: raise ValueError('no animation frames')
    frames[0].save(output,save_all=True,append_images=frames[1:],duration=duration,loop=0,disposal=2); return output

def photomosaic(target_path: str, tile_paths, output: str, columns=40, repeat_distance=2, color_blend=0.12, max_tiles=300) -> str:
    """Create a photo mosaic using tile average colors in CIE Lab space."""
    target = Image.open(target_path).convert("RGB")
    columns = max(10, min(int(columns), 100, target.width))
    tiles = []
    for p in list(dict.fromkeys(tile_paths))[:max(10, min(int(max_tiles), 500))]:
        try:
            im = Image.open(p).convert("RGB")
            side = max(16, min(192, target.width // columns))
            tile = ImageOps.fit(im, (side, side), method=Image.Resampling.LANCZOS)
            arr = np.asarray(tile, dtype=np.float32).reshape(-1, 3).mean(axis=0)
            tiles.append((tile, _rgb_to_lab(arr)))
        except Exception:
            continue
    if not tiles:
        raise ValueError("没有可用的马赛克素材图片")
    rows = max(1, round(target.height / (target.width / columns)))
    cell_w = target.width / columns
    cell_h = target.height / rows
    target_arr = np.asarray(target, dtype=np.float32)
    result = target.copy()
    draw = ImageDraw.Draw(result)
    chosen = []
    for r in range(rows):
        for c in range(columns):
            x0, y0 = int(c * cell_w), int(r * cell_h)
            x1, y1 = int((c + 1) * cell_w), int((r + 1) * cell_h)
            sample = target_arr[y0:y1, x0:x1]
            lab = _rgb_to_lab(sample.reshape(-1, 3).mean(axis=0))
            best_i, best_d = 0, float("inf")
            for i, (_, tlab) in enumerate(tiles):
                if repeat_distance and i in chosen[-repeat_distance:]:
                    continue
                d = sum((a - b) ** 2 for a, b in zip(lab, tlab))
                if d < best_d:
                    best_i, best_d = i, d
            chosen.append(best_i)
            tile = tiles[best_i][0].resize((max(1, x1-x0), max(1, y1-y0)), Image.Resampling.LANCZOS)
            result.paste(tile, (x0, y0))
    if color_blend > 0:
        result = Image.blend(result, target, max(0.0, min(float(color_blend), 0.6)))
    result.save(output)
    return output


def batch_rename(paths, pattern="{original}_{sequence}", start=1, padding=3, prefix="", suffix="") -> list[tuple[str, str]]:
    """Preview/execute a safe batch rename; supports common ImageToolbox-style tokens."""
    import datetime, re, uuid
    files = [Path(p) for p in paths]
    result = []
    for i, p in enumerate(files, start=start):
        stat = p.stat()
        stem, ext = p.stem, p.suffix
        name = pattern
        tokens = {
            "{original}": stem, "{ext}": ext.lstrip("."), "{width}": "", "{height}": "",
            "{parent}": p.parent.name, "{size}": str(stat.st_size), "{uuid}": str(uuid.uuid4()),
            "{date}": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
            "{prefix}": prefix, "{suffix}": suffix,
        }
        for k, v in tokens.items(): name = name.replace(k, v)
        name = re.sub(r"\{sequence(?::(\d+))?\}", lambda m: str(i).zfill(int(m.group(1) or padding)), name)
        result.append((str(p), str(p.with_name(name + (ext if "." not in Path(name).name else "")))))
    return result


def apply_batch_rename(paths, pattern="{original}_{sequence}", start=1, padding=3, prefix="", suffix="") -> list[str]:
    import uuid
    plan = batch_rename(paths, pattern, start, padding, prefix, suffix)
    sources = {Path(a).resolve() for a, _ in plan}
    targets = [Path(b) for _, b in plan]
    if len({t.resolve() for t in targets}) != len(targets):
        raise ValueError("重命名结果存在重复文件名")
    for t in targets:
        if t.exists() and t.resolve() not in sources:
            raise FileExistsError(f"目标已存在: {t}")
    temp = []
    for n, (src, _) in enumerate(plan):
        s = Path(src)
        tmp = s.with_name(f".toolbox-rename-{n}-{uuid.uuid4().hex}{s.suffix}")
        s.rename(tmp)
        temp.append(tmp)
    outputs = []
    for tmp, (_, dst) in zip(temp, plan):
        d = Path(dst)
        tmp.rename(d)
        outputs.append(str(d))
    return outputs


def _rgb_to_lab(rgb) -> tuple[float, float, float]:
    v = np.asarray(rgb, dtype=np.float64) / 255.0
    v = np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)
    r, g, b = v
    x = (r*0.4124564 + g*0.3575761 + b*0.1804375) / 0.95047
    y = (r*0.2126729 + g*0.7151522 + b*0.0721750)
    z = (r*0.0193339 + g*0.1191920 + b*0.9503041) / 1.08883
    def f(q): return np.cbrt(q) if q > 0.008856 else 7.787*q + 16/116
    fx, fy, fz = f(x), f(y), f(z)
    return (116*fy-16, 500*(fx-fy), 200*(fy-fz))


def convert_animation_format(path: str, output: str, fmt="WEBP", fps=None) -> str:
    with Image.open(path) as im:
        frames=[]; durations=[]
        for i in range(getattr(im,"n_frames",1)):
            im.seek(i); frames.append(im.convert("RGBA").copy()); durations.append(im.info.get("duration",100))
        if fps: durations=[max(1,int(1000/float(fps)))]*len(frames)
        savefmt=fmt.upper()
        frames[0].save(output,format=savefmt,save_all=True,append_images=frames[1:],duration=durations,loop=0,lossless=(savefmt=="WEBP"))
    return output


def jxl_convert(path: str, output: str, quality=90) -> str:
    try:
        import pillow_jxl
        im=Image.open(path)
        im.save(output,format="JXL",quality=int(quality))
        return output
    except Exception:
        exe=shutil.which("cjxl") or shutil.which("djxl")
        if not exe:
            raise RuntimeError("JXL 后端不可用：当前优先使用 pillow-jxl-plugin；若仍失败，请安装系统 libjxl-tools。")
        if Path(exe).name=="cjxl":
            subprocess.run([exe,path,output,"-q",str(quality)],check=True)
        else:
            subprocess.run([exe,path,output],check=True)
        return output


def ocr_image(path: str, lang="eng", psm=3) -> str:
    import pytesseract
    im=Image.open(path)
    return pytesseract.image_to_string(im,lang=lang,config=f"--psm {int(psm)}")


def ocr_to_file(path: str, output: str, lang="eng", psm=3) -> str:
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    text=ocr_image(path,lang,psm)
    Path(output).write_text(text,encoding="utf-8")
    return output


def multi_frame_fusion(paths, output: str, method="median") -> str:
    imgs=[Image.open(p).convert("RGB") for p in paths]
    size=(min(i.width for i in imgs),min(i.height for i in imgs))
    arr=np.stack([np.asarray(ImageOps.fit(i,size)) for i in imgs]).astype(np.float32)
    if method=="mean": out=arr.mean(axis=0)
    elif method=="max": out=arr.max(axis=0)
    elif method=="min": out=arr.min(axis=0)
    else: out=np.median(arr,axis=0)
    Image.fromarray(np.uint8(np.clip(out,0,255))).save(output)
    return output


def color_sample(path: str, x: int, y: int) -> dict:
    im=Image.open(path).convert("RGB")
    r,g,b=im.getpixel((max(0,min(x,im.width-1)),max(0,min(y,im.height-1))))
    def hx(v): return f"{v:02X}"
    return {"rgb":[r,g,b],"hex":f"#{hx(r)}{hx(g)}{hx(b)}","hsv":list(ImageColor.getrgb(f"#{hx(r)}{hx(g)}{hx(b)}"))}


def color_replace(path: str, output: str, source: str, target: str, tolerance=30) -> str:
    im=Image.open(path).convert("RGBA"); a=np.asarray(im).copy()
    s=np.array(ImageColor.getrgb(source),dtype=np.int16); t=np.array(ImageColor.getrgb(target),dtype=np.uint8)
    d=np.linalg.norm(a[:,:,:3].astype(np.int16)-s,axis=2)
    a[d<=float(tolerance),:3]=t
    Image.fromarray(a).save(output); return output


def colorize_gradient(path: str, output: str, start="#6d5dfc", end="#ff5ca8") -> str:
    im=Image.open(path).convert("L"); a=np.asarray(im,dtype=np.float32)/255
    s=np.array(ImageColor.getrgb(start),dtype=np.float32); e=np.array(ImageColor.getrgb(end),dtype=np.float32)
    rgb=(s[None,None,:]*(1-a[:,:,None])+e[None,None,:]*a[:,:,None]).astype(np.uint8)
    Image.fromarray(rgb).save(output); return output


def svg_make(output: str, width=1024, height=1024, background="#ffffff", shapes=None) -> str:
    shapes=shapes or []
    body=[f'<rect width="100%" height="100%" fill="{background}"/>']
    for s in shapes:
        typ=s.get("type","rect")
        if typ=="circle":
            cx=float(s.get("cx",width/2)); cy=float(s.get("cy",height/2)); r=max(0.0,float(s.get("r",min(width,height)/4)))
            body.append(f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="{s.get("fill","#000")}"/>')
        elif typ=="rect":
            x=float(s.get("x",0)); y=float(s.get("y",0)); w=float(s.get("w",s.get("width",width-x))); h=float(s.get("h",s.get("height",height-y)))
            if w<=0 or h<=0: raise ValueError("SVG rect width and height must be positive")
            body.append(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{float(s.get("rx",0)):g}" fill="{s.get("fill","#000")}"/>')
        elif s.get("type")=="text": body.append(f'<text x="{s.get("x", 0)}" y="{s.get("y", 0)}" font-size="{s.get("size",48)}" fill="{s.get("fill","#000")}">{s.get("text","")}</text>')
    Path(output).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">{"".join(body)}</svg>',encoding="utf-8")
    return output


def texture_generate(output: str, width=1024, height=1024, kind="noise", scale=8, seed=0) -> str:
    rng=np.random.default_rng(seed)
    if kind=="noise": a=rng.random((height,width))
    elif kind=="cloud": 
        small=rng.random((max(2,height//scale),max(2,width//scale))); a=np.asarray(Image.fromarray(np.uint8(small*255)).resize((width,height),Image.Resampling.BICUBIC))/255
    elif kind=="stripes":
        x=np.arange(width)[None,:]; a=np.tile((np.sin(x/scale)+1)/2,(height,1))
    else:
        y,x=np.mgrid[0:height,0:width]; a=(np.sin(np.hypot(x-width/2,y-height/2)/max(1,scale))+1)/2
    Image.fromarray(np.uint8(np.clip(a,0,1)*255)).convert("L").save(output); return output


def mesh_gradient(output: str, width=1024, height=1024, colors=None) -> str:
    colors=colors or ["#6d5dfc","#ff5ca8","#35d0ba","#ffd166"]
    cs=np.array([ImageColor.getrgb(c) for c in colors],dtype=np.float32).reshape(2,2,3)
    yy,xx=np.mgrid[0:height,0:width]; u=xx/max(1,width-1); v=yy/max(1,height-1)
    a=cs[0,0]*(1-u[...,None])*(1-v[...,None])+cs[0,1]*u[...,None]*(1-v[...,None])+cs[1,0]*(1-u[...,None])*v[...,None]+cs[1,1]*u[...,None]*v[...,None]
    Image.fromarray(np.uint8(np.clip(a,0,255))).save(output); return output


def shader_cpu(path: str, output: str, effect="invert", strength=1.0) -> str:
    im=Image.open(path).convert("RGB"); a=np.asarray(im,dtype=np.float32)/255
    if effect=="invert": b=1-a
    elif effect=="posterize": b=np.round(a*4)/4
    elif effect=="scanlines": b=a*(0.75+0.25*((np.arange(a.shape[0])[:,None]%4)<2))
    elif effect=="vignette":
        y,x=np.mgrid[0:a.shape[0],0:a.shape[1]]; d=np.sqrt(((x-a.shape[1]/2)/(a.shape[1]/2))**2+((y-a.shape[0]/2)/(a.shape[0]/2))**2); b=a*np.clip(1-d*0.65,0.25,1)[...,None]
    else: b=a
    out=a*(1-float(strength))+b*float(strength)
    Image.fromarray(np.uint8(np.clip(out,0,1)*255)).save(output); return output


def extract_audio_cover(path: str, output: str) -> str:
    try:
        from mutagen import File
        f=File(path)
        if f and f.tags:
            for key in ("APIC:","covr"):
                if key in f.tags:
                    data=f.tags[key].data if hasattr(f.tags[key],"data") else bytes(f.tags[key][0])
                    Path(output).write_bytes(data); return output
            for v in f.tags.values():
                if hasattr(v,"data") and isinstance(v.data,(bytes,bytearray)):
                    Path(output).write_bytes(v.data); return output
    except ImportError:
        raise RuntimeError("音频封面提取需要 Python 包 mutagen；请用项目 .venv 的 uv 安装。")
    raise ValueError("音频文件没有找到嵌入封面")


def wallpaper_export(path: str, output: str, width=None, height=None, fit="cover") -> str:
    im=Image.open(path).convert("RGB")
    if width and height:
        im=ImageOps.fit(im,(int(width),int(height)),method=Image.Resampling.LANCZOS,centering=(0.5,0.5)) if fit=="cover" else ImageOps.contain(im,(int(width),int(height)))
    im.save(output); return output


def annotate(path: str, output: str, items=None) -> str:
    im=Image.open(path).convert("RGBA"); d=ImageDraw.Draw(im)
    for it in items or []:
        typ=it.get("type","rect")
        if typ=="rect": d.rectangle(tuple(it.get("box", (0,0,im.width-1,im.height-1))),outline=it.get("color","#ff4d6d"),width=int(it.get("width",4)))
        elif typ=="ellipse": d.ellipse(tuple(it.get("box", (0,0,im.width-1,im.height-1))),outline=it.get("color","#ff4d6d"),width=int(it.get("width",4)))
        elif typ=="line": d.line(tuple(it.get("xy", (0,0,im.width-1,im.height-1))),fill=it.get("color","#ff4d6d"),width=int(it.get("width",4)))
        elif typ=="text": d.text(tuple(it.get("xy", (0,0,im.width-1,im.height-1))),it.get("text",""),fill=it.get("color","#ffffff"))
    im.save(output); return output


def erase_background(path: str, output: str, model="u2net", backend="auto") -> str:
    from .ai import remove_background
    from .utils import np_to_pil
    result = remove_background(np.asarray(Image.open(path).convert("RGBA")), model=model, backend=backend)
    np_to_pil(result).save(output)
    return output


def run_parity_tool(tool: str, **kwargs):
    mapping={
        "duplicate-finder":find_duplicates,"image-info":image_info,"base64-encode":base64_encode,"base64-decode":base64_decode,"archive":archive_images,
        "split-grid":split_grid,"stack":stack_images,"auto-crop":auto_crop,"border":add_border,
        "weight-resize":resize_by_weight,"noise":add_noise,"grayscale":grayscale,"invert":invert,
        "watermark":watermark,"palette":dominant_palette,"svg":to_svg,"convert":convert_format,
        "compress":compress_image,"contact-sheet":make_contact_sheet,"encrypt":encrypt_file,"decrypt":decrypt_file,
        "limits-resize":resize_with_limits,"cut":cut_image,"gradient":create_gradient,"noise-generate":generate_noise,
        "fractal":generate_fractal,"curves":apply_curves,"strip-exif":strip_exif,"exif":extract_exif,"similar":find_similar_images,
        "collage":make_collage,"ascii":image_to_ascii,"palette-pdf":make_palette_pdf,"gif":make_gif,"gif-frames":extract_gif_frames,
        "qr":scan_qr,"document-scan":document_scan,"text":add_text,"merge-animation":merge_animation_files,
        "photomosaic":photomosaic,"batch-rename":batch_rename,
        "animation-format":convert_animation_format,"jxl":jxl_convert,"ocr":ocr_to_file,
        "fusion":multi_frame_fusion,"color-sample":color_sample,"color-replace":color_replace,
        "colorize":colorize_gradient,"svg-make":svg_make,"texture":texture_generate,"mesh-gradient":mesh_gradient,
        "shader":shader_cpu,"audio-cover":extract_audio_cover,"wallpaper":wallpaper_export,"annotate":annotate,"background-remove":erase_background,
    }
    fn=mapping.get(tool)
    if fn is None: raise KeyError(tool)
    return fn(**kwargs)


# ---- Remaining ImageToolbox desktop parity primitives ---------------------
def checksum_file(path, algorithms=None):
    import hashlib, zlib
    algorithms = algorithms or ["md5", "sha1", "sha256", "sha512", "crc32", "blake2b", "blake2s"]
    data = Path(path).read_bytes()
    out = {}
    for name in algorithms:
        if name == "crc32":
            out[name] = f"{zlib.crc32(data) & 0xffffffff:08x}"
        else:
            out[name] = hashlib.new(name, data).hexdigest()
    return out


def make_apng(paths, output, duration=100, loop=0):
    ims = [Image.open(p).convert("RGBA") for p in paths]
    if not ims:
        raise ValueError("至少需要一个帧")
    ims[0].save(output, format="PNG", save_all=True, append_images=ims[1:],
                duration=duration, loop=loop, disposal=2)
    return output


def edit_exif(path, output, metadata):
    im = Image.open(path)
    exif = im.getexif()
    for key, value in metadata.items():
        try:
            exif[int(key)] = value
        except (ValueError, TypeError):
            continue
    kwargs = {"exif": exif.tobytes()}
    if im.format == "JPEG" and im.mode not in {"RGB", "L"}:
        im = im.convert("RGB")
    im.save(output, format=im.format or Path(output).suffix.lstrip("."), **kwargs)
    return output


def load_net_image(url, output):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Toolbox/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        data = response.read()
    Path(output).write_bytes(data)
    return output


def quick_tiles(paths, output, columns=4, tile=256):
    return make_contact_sheet(paths, output, columns=columns, thumb=tile, spacing=8)


def webp_convert(path, output, quality=90, lossless=False):
    im = Image.open(path).convert("RGBA")
    im.save(output, "WEBP", quality=int(quality), lossless=bool(lossless), method=6)
    return output


def code_preview(path, output=None):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    if output:
        Path(output).write_text(text, encoding="utf-8")
        return output
    return text


# Desktop-native equivalents for Android-only modules. These are deliberately
# explicit: no fake Android APIs are exposed.
DESKTOP_NATIVE_FEATURES = {
    "app-logs", "help", "libraries-info", "library-details", "main", "root",
    "settings", "usage-statistics", "media-picker", "image-preview", "single-edit",
}


FEATURE_LEVELS = {'ai-tools': 'usable', 'apng-tools': 'usable', 'archive-tools': 'usable', 'ascii-art': 'usable', 'audio-cover-extractor': 'usable', 'base64-tools': 'usable', 'batch-rename': 'usable', 'checksum-tools': 'usable', 'cipher': 'usable', 'code-preview': 'usable', 'collage-maker': 'usable', 'color-library': 'usable', 'color-tools': 'usable', 'compression-lab': 'usable', 'curves': 'usable', 'delete-exif': 'usable', 'document-scanner': 'usable', 'draw': '未验证', 'duplicate-finder': 'usable', 'edit-exif': 'usable', 'fractal-generation': 'usable', 'image-cutting': 'usable', 'image-splitting': 'usable', 'image-stacking': 'usable', 'jxl-tools': 'usable', 'limits-resize': 'usable', 'load-net-image': 'usable', 'markup-layers': '未验证', 'mesh-gradients': 'usable', 'multi-frame-fusion': 'usable', 'noise-generation': 'usable', 'palette-pdf': 'usable', 'palette-tools': 'usable', 'photomosaic': 'usable', 'pick-color': 'usable', 'quick-tiles': 'usable', 'recognize-text': 'usable', 'resize-convert': 'usable', 'scan-qr-code': 'usable', 'shader-studio': '未验证', 'single-edit': 'usable', 'svg-maker': 'usable', 'texture-generation': 'usable', 'wallpapers-export': 'usable', 'webp-tools': 'usable', 'weight-resize': 'usable', 'watermarking': 'usable', 'app-logs': 'usable', 'compare': 'usable', 'crop': 'usable', 'easter-egg': 'placeholder', 'erase-background': 'usable', 'filters': '未验证', 'format-conversion': 'usable', 'gif-tools': 'usable', 'gradient-maker': 'usable', 'help': '未验证', 'image-preview': 'usable', 'image-stitch': 'usable', 'libraries-info': '未验证', 'library-details': '未验证', 'main': '未验证', 'media-picker': '未验证', 'pdf-tools': 'usable', 'root': '未验证', 'settings': 'usable', 'usage-statistics': 'placeholder'}

FEATURE_STATUS = {key: ("native" if key in DESKTOP_NATIVE_FEATURES else "implemented")
                  for key in PARITY_FEATURES}
FEATURE_STATUS.update({
    "ai-tools": "implemented",
    "erase-background": "implemented",
    "filters": "implemented",
    "compare": "implemented",
    "crop": "implemented",
    "draw": "implemented",
    "edit-exif": "implemented",
    "apng-tools": "implemented",
    "checksum-tools": "implemented",
    "code-preview": "implemented",
    "color-library": "implemented",
    "load-net-image": "implemented",
    "quick-tiles": "implemented",
    "webp-tools": "implemented",
})


def parity_audit():
    return {
        "total": len(PARITY_FEATURES),
        "levels": {level: sum(v == level for v in FEATURE_LEVELS.values()) for level in ("placeholder", "usable", "equivalent", "未验证")},
        "implemented": sum(v == "implemented" for v in FEATURE_STATUS.values()),
        "native": sum(v == "native" for v in FEATURE_STATUS.values()),
        "pending": [k for k, v in FEATURE_STATUS.items() if v == "pending"],
        "features": [
            {"id": k, "title": title, "status": FEATURE_STATUS.get(k, "pending"), "level": FEATURE_LEVELS.get(k, "未验证")}
            for k, title in PARITY_FEATURES.items()
        ],
    }


def run_parity_tool(tool: str, **kwargs):
    mapping = {
        "duplicate-finder": find_duplicates, "image-info": image_info,
        "checksum": checksum_file, "apng": make_apng, "edit-exif": edit_exif,
        "load-net-image": load_net_image, "quick-tiles": quick_tiles,
        "webp": webp_convert, "code-preview": code_preview,
        "base64-encode": base64_encode, "base64-decode": base64_decode, "archive": archive_images,
        "split-grid": split_grid, "stack": stack_images, "auto-crop": auto_crop, "border": add_border,
        "weight-resize": resize_by_weight, "noise": add_noise, "grayscale": grayscale, "invert": invert,
        "watermark": watermark, "palette": dominant_palette, "svg": to_svg, "convert": convert_format,
        "compress": compress_image, "contact-sheet": make_contact_sheet, "encrypt": encrypt_file, "decrypt": decrypt_file,
        "limits-resize": resize_with_limits, "cut": cut_image, "gradient": create_gradient, "noise-generate": generate_noise,
        "fractal": generate_fractal, "curves": apply_curves, "strip-exif": strip_exif, "exif": extract_exif,
        "similar": find_similar_images, "collage": make_collage, "ascii": image_to_ascii,
        "palette-pdf": make_palette_pdf, "gif": make_gif, "gif-frames": extract_gif_frames,
        "qr": scan_qr, "document-scan": document_scan, "text": add_text, "merge-animation": merge_animation_files,
        "photomosaic": photomosaic, "batch-rename": batch_rename, "animation-format": convert_animation_format,
        "jxl": jxl_convert, "ocr": ocr_to_file, "fusion": multi_frame_fusion,
        "color-sample": color_sample, "color-replace": color_replace, "colorize": colorize_gradient,
        "svg-make": svg_make, "texture": texture_generate, "mesh-gradient": mesh_gradient,
        "shader": shader_cpu, "audio-cover": extract_audio_cover, "wallpaper": wallpaper_export, "annotate": annotate, "background-remove": erase_background, "erase-background": erase_background, "background-remove": erase_background, "erase-background": erase_background,
    }
    fn = mapping.get(tool)
    if fn is None:
        raise KeyError(tool)
    return fn(**kwargs)
