"""Render a silent walkthrough of the built pages from real output (needs Chrome and ffmpeg):
.venv/bin/python -m http.server 8765 --directory dist --bind 127.0.0.1 &
.venv/bin/python scripts/render_demo.py submission/demo.mp4"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SERVER = "http://127.0.0.1:8765"
WIDTH, HEIGHT, FPS = 1440, 900, 30
CAPTURE_HEIGHT = 8000
SCROLL = 1.2
FADE = 0.5

# Each page is a list of (viewport top in CSS pixels, seconds held there); scrolls ease between stops.
SHOTS: list[tuple[str, list[tuple[int, float]]]] = [
    ("index", [(0, 4), (680, 7), (1800, 5)]),
    ("PTBA", [(0, 6), (1330, 9), (2050, 6), (2580, 5)]),
    ("BBTN", [(0, 4), (1330, 9)]),
    ("ADRO", [(0, 4), (1330, 7), (2540, 6)]),
    ("BMRI", [(0, 3), (1960, 7)]),
    ("methodology", [(0, 5), (2130, 5), (2460, 6), (3700, 6)]),
]


def capture(page: str, folder: Path) -> Path:
    out = folder / f"{page}.png"
    chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                               "--force-device-scale-factor=1", f"--user-data-dir={folder / ('profile-' + page)}",
                               "--virtual-time-budget=3000", f"--window-size={WIDTH},{CAPTURE_HEIGHT}",
                               f"--screenshot={out}", f"{SERVER}/{page}.html"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Headless Chrome can linger after writing the screenshot, so wait for the file rather than the process.
    for _ in range(60):
        if out.exists() and out.stat().st_size:
            break
        time.sleep(1)
    time.sleep(1)
    chrome.kill()
    if not out.exists():
        raise SystemExit(f"No capture for {page}; is the dist server running on {SERVER}?")
    return out


def y_expression(stops: list[tuple[int, float]]) -> tuple[str, float]:
    """A piecewise ffmpeg expression in t: hold at each stop, then ease (smoothstep) to the next."""
    pieces, start = [], 0.0
    for (y, hold), (next_y, _) in zip(stops, stops[1:]):
        pieces.append((start + hold, str(y)))
        s = f"((t-{start + hold})/{SCROLL})"
        pieces.append((start + hold + SCROLL, f"({y}+({next_y}-{y})*{s}*{s}*(3-2*{s}))"))
        start += hold + SCROLL
    last_y, last_hold = stops[-1]
    expr = str(last_y)
    for until, value in reversed(pieces):
        expr = f"if(lt(t,{until}),{value},{expr})"
    return expr, start + last_hold


def render(page: str, stops: list[tuple[int, float]], image: Path, out: Path) -> float:
    expr, duration = y_expression(stops)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-t", str(duration),
                    "-i", str(image), "-vf", f"crop={WIDTH}:{HEIGHT}:0:'{expr}',format=yuv420p",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", str(FPS), str(out)], check=True)
    return duration


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "submission/demo.mp4")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        clips = []
        for page, stops in SHOTS:
            clip = folder / f"{page}.mp4"
            clips.append((clip, render(page, stops, capture(page, folder), clip)))
        inputs = [arg for clip, _ in clips for arg in ("-i", str(clip))]
        chain, label, offset = [], "[0:v]", 0.0
        for index, (_, duration) in enumerate(clips[1:], start=1):
            offset += clips[index - 1][1] - FADE
            chain.append(f"{label}[{index}:v]xfade=transition=fade:duration={FADE}:offset={offset:.3f}[v{index}]")
            label = f"[v{index}]"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(chain),
                        "-map", label, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", str(target)], check=True)
    print(f"Wrote {target}, {offset + clips[-1][1]:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
