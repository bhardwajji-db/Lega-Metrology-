# OCR engine benchmark: PaddleOCR on MetrCheck synthetic labels
# Run from project root: venv/Scripts/python.exe test_data/bench_ocr.py
import asyncio, os, sys, time, traceback
from pathlib import Path

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from PIL import Image, ImageDraw, ImageFont
from ocr.paddle_engine import PaddleOCREngine

IMG_DIR = os.path.join(os.path.dirname(__file__), "ocr_bench")
os.makedirs(IMG_DIR, exist_ok=True)

lines = [
    ("Tata Salt 500g", 40),
    ("MRP Rs 24.00 incl. of all taxes", 30),
    ("Mfg Date: 12/08/2026", 26),
    ("Best Before: 12 months", 26),
    ("Mfg by Tata Chemicals Ltd", 26),
    ("Mumbai - 400001", 26),
    ("Customer Care: 1800-266-0012", 26),
    ("Country of Origin: India", 26),
]
font_path = r"C:\Windows\Fonts\arial.ttf"
imgs = []
for i in range(2):
    img = Image.new("RGB", (640, 420), "white")
    d = ImageDraw.Draw(img)
    y = 30
    for text, size in lines:
        try:
            f = ImageFont.truetype(font_path, size)
        except Exception:
            f = ImageFont.load_default()
        d.text((30, y), text, fill="black", font=f)
        y += size + 12
    p = os.path.join(IMG_DIR, f"label_{i+1}.png")
    img.save(p)
    imgs.append(p)
    print("saved", p)

async def bench(name, engine, path):
    t0 = time.time()
    try:
        res = await asyncio.wait_for(engine.extract(path), timeout=240)
        dt = time.time() - t0
        text = (res.full_text or "")[:120].replace("\n", " | ")
        print(f"[{name}] OK in {dt:.1f}s  engine={res.engine}  len={len(res.full_text or '')}  conf={res.average_confidence:.2f}")
        print(f"    text: {text}")
        return True
    except asyncio.TimeoutError:
        print(f"[{name}] TIMEOUT after 240s (frozen)")
        return False
    except Exception as e:
        dt = time.time() - t0
        print(f"[{name}] FAILED in {dt:.1f}s: {type(e).__name__}: {str(e)[:200]}")
        return False

async def main():
    print("=== TESTING PADDLEOCR (Sole Engine) ===")
    t0 = time.time()
    p_ok = False
    try:
        p = PaddleOCREngine()
        print(f"PaddleOCR engine constructed in {time.time()-t0:.1f}s")
        print(f"PaddleOCR is_available: {p.is_available()}")
        p_ok = await bench("PADDLE", p, imgs[0])
    except Exception as e:
        print(f"[PADDLE] construct FAILED ({time.time()-t0:.1f}s): {type(e).__name__}: {str(e)[:200]}")

    print()
    print("=== VERDICT ===")
    print(f"paddle_ok={p_ok}")

if __name__ == "__main__":
    asyncio.run(main())