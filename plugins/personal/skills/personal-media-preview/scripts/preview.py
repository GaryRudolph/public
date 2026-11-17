#!/usr/bin/env python3
"""Make phone-sized previews of what a session produced, per standards/media.md.

Each mode writes its output and prints one JSON line of facts about it (path,
size, duration, resolution, codec, and whether the MP4 index comes first). It
makes no judgement about the content; the agent decides what to send where.

Usage:
    preview.py clip SRC [-o OUT]       # <=10 s, <=8 MB, 720p H.264
    preview.py flyover SRC [-o OUT]    # <=60 s, <=15 MB, named *-flyover.mp4
    preview.py stills SRC... [-d DIR]  # <=2048 px JPEG, one per input
    preview.py sheet SRC [-o OUT]      # contact sheet of evenly spaced frames
    preview.py glb SRC [-o OUT]        # decimated GLB <=15 MB (needs gltfpack)
    preview.py probe FILE...           # facts only, no output written

Needs ffmpeg and ffprobe on PATH; glb also needs gltfpack.
"""

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MB = 1_000_000
LONG_EDGE_VIDEO = 720
LONG_EDGE_STILL = 2048
MAX_FPS = 30
JPEG_QUALITY = 3  # ffmpeg mjpeg scale, 2 (best) to 31; 3 is about quality 85
H264_QUALITY_STEPS = (23, 26, 29, 32, 35, 38)
GLB_MAX_BYTES = 15 * MB
GLB_RATIOS = (0.5, 0.25, 0.1, 0.05, 0.02)
SHEET_COLUMNS = 4
SHEET_TILE_WIDTH = 480
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
MP4_SUFFIXES = (".mp4", ".mov", ".m4v")


@dataclass(frozen=True)
class VideoLimits:
    kind: str
    max_seconds: float
    max_bytes: int


CLIP = VideoLimits(kind="clip", max_seconds=10, max_bytes=8 * MB)
FLYOVER = VideoLimits(kind="flyover", max_seconds=60, max_bytes=15 * MB)


def main() -> int:
    args = _parse_args()
    _require("ffmpeg", "ffprobe")
    if args.mode in ("clip", "flyover"):
        limits = CLIP if args.mode == "clip" else FLYOVER
        return _emit(make_video(Path(args.src), _video_out(args, limits), limits, args.encoder))
    if args.mode == "stills":
        out_dir = Path(args.dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        status = 0
        for src in args.src:
            status |= _emit(make_still(Path(src), out_dir / f"{Path(src).stem}.jpg"))
        return status
    if args.mode == "sheet":
        out = Path(args.out or f"{Path(args.src).stem}-sheet.jpg")
        return _emit(make_sheet(Path(args.src), out, args.frames))
    if args.mode == "glb":
        _require("gltfpack")
        out = Path(args.out or f"{Path(args.src).stem}-preview.glb")
        return _emit(make_glb(Path(args.src), out))
    status = 0
    for path in args.src:
        status |= _emit(probe(Path(path)))
    return status


def make_video(src: Path, out: Path, limits: VideoLimits, encoder: str) -> dict:
    """Encode src to an H.264 preview within limits, raising quality steps until it fits."""
    source = probe(src)
    duration = source.get("durationSeconds") or 0.0
    speed = max(1.0, duration / limits.max_seconds) if duration else 1.0
    filters = [f"setpts=PTS/{speed:.6f}", _scale_filter(LONG_EDGE_VIDEO), f"fps={MAX_FPS}"]
    out.parent.mkdir(parents=True, exist_ok=True)
    facts: dict = {}
    for quality in H264_QUALITY_STEPS:
        _ffmpeg(
            "-i", str(src), "-an",
            "-vf", ",".join(filters),
            "-t", str(limits.max_seconds),
            *_encoder_args(encoder, quality),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out),
        )
        facts = probe(out)
        if facts["sizeBytes"] <= limits.max_bytes:
            break
    facts.update(
        kind=limits.kind,
        source=str(src),
        sourceDurationSeconds=duration,
        speedFactor=round(speed, 3),
        quality=quality,
        capBytes=limits.max_bytes,
        withinCap=facts["sizeBytes"] <= limits.max_bytes,
    )
    return facts


def make_still(src: Path, out: Path) -> dict:
    _ffmpeg("-i", str(src), "-vf", _scale_filter(LONG_EDGE_STILL), "-frames:v", "1",
            "-q:v", str(JPEG_QUALITY), str(out))
    return probe(out) | {"kind": "still", "source": str(src)}


def make_sheet(src: Path, out: Path, frames: int) -> dict:
    """Tile `frames` evenly spaced frames of a video into one JPEG."""
    duration = probe(src).get("durationSeconds") or 1.0
    rows = -(-frames // SHEET_COLUMNS)
    filters = [
        f"fps={frames / duration:.6f}",
        f"scale={SHEET_TILE_WIDTH}:-2",
        f"tile={SHEET_COLUMNS}x{rows}",
    ]
    _ffmpeg("-i", str(src), "-vf", ",".join(filters), "-frames:v", "1",
            "-q:v", str(JPEG_QUALITY), str(out))
    return probe(out) | {"kind": "sheet", "source": str(src), "frames": frames}


def make_glb(src: Path, out: Path) -> dict:
    """Decimate with gltfpack, halving the kept ratio until the file fits."""
    ratio = GLB_RATIOS[0]
    for ratio in GLB_RATIOS:
        _run("gltfpack", "-i", str(src), "-o", str(out), "-cc", "-si", str(ratio))
        if out.stat().st_size <= GLB_MAX_BYTES:
            break
    size = out.stat().st_size
    return {
        "path": str(out), "kind": "glb", "source": str(src),
        "sizeBytes": size, "simplifyRatio": ratio,
        "capBytes": GLB_MAX_BYTES, "withinCap": size <= GLB_MAX_BYTES,
    }


def probe(path: Path) -> dict:
    """Facts about a media file from ffprobe, plus MP4 atom order."""
    result = _run(
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,pix_fmt,r_frame_rate,duration"
        ":format=duration",
        "-of", "json", str(path),
    )
    data = json.loads(result.stdout)
    stream = (data.get("streams") or [{}])[0]
    duration = stream.get("duration") or data.get("format", {}).get("duration")
    facts = {
        "path": str(path),
        "sizeBytes": path.stat().st_size,
        "codec": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "pixFmt": stream.get("pix_fmt"),
        "fps": _rate(stream.get("r_frame_rate")),
        "durationSeconds": round(float(duration), 3) if duration not in (None, "N/A") else None,
    }
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        del facts["fps"], facts["durationSeconds"]
    if suffix in MP4_SUFFIXES:
        facts["moovBeforeMdat"] = moov_before_mdat(path)
    return facts


def moov_before_mdat(path: Path) -> bool | None:
    """True when the top-level moov atom precedes mdat (playback can start early)."""
    with path.open("rb") as file:
        while header := file.read(8):
            if len(header) < 8:
                return None
            size = int.from_bytes(header[:4], "big")
            kind = header[4:8]
            if kind in (b"moov", b"mdat"):
                return kind == b"moov"
            if size == 1:
                size = int.from_bytes(file.read(8), "big") - 8
            elif size == 0:
                return None
            file.seek(size - 8, 1)
    return None


def _video_out(args: argparse.Namespace, limits: VideoLimits) -> Path:
    out = Path(args.out or f"{Path(args.src).stem}-{limits.kind}.mp4")
    if limits is FLYOVER and not out.stem.endswith("-flyover"):
        out = out.with_name(f"{out.stem}-flyover{out.suffix or '.mp4'}")
    return out


def _scale_filter(long_edge: int) -> str:
    # Fit the long edge, never upscale, keep both sides even for yuv420p.
    return (
        f"scale=w='if(gt(iw,ih),min({long_edge},iw),-2)'"
        f":h='if(gt(iw,ih),-2,min({long_edge},ih))'"
    )


def _encoder_args(encoder: str, quality: int) -> list[str]:
    if "nvenc" in encoder:
        return ["-c:v", encoder, "-rc", "vbr", "-cq", str(quality), "-b:v", "0"]
    return ["-c:v", encoder, "-preset", "slow", "-crf", str(quality)]


def _rate(value: str | None) -> float | None:
    if not value or "/" not in value:
        return None
    num, den = (int(part) for part in value.split("/"))
    return round(num / den, 3) if den else None


def _ffmpeg(*args: str) -> None:
    _run("ffmpeg", "-y", "-v", "error", *args)


def _run(*command: str) -> subprocess.CompletedProcess:
    result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if result.returncode:
        raise SystemExit(f"{command[0]} failed: {result.stderr.strip()}")
    return result


def _require(*tools: str) -> None:
    missing = [tool for tool in tools if not shutil.which(tool)]
    if missing:
        raise SystemExit(f"not on PATH: {', '.join(missing)}")


def _emit(facts: dict) -> int:
    print(json.dumps(facts))
    return 0 if facts.get("withinCap", True) else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    modes = parser.add_subparsers(dest="mode", required=True)
    for name in ("clip", "flyover"):
        mode = modes.add_parser(name)
        mode.add_argument("src")
        mode.add_argument("-o", "--out")
        mode.add_argument("--encoder", default="libx264", help="libx264 or h264_nvenc")
    stills = modes.add_parser("stills")
    stills.add_argument("src", nargs="+")
    stills.add_argument("-d", "--dir", default=".")
    sheet = modes.add_parser("sheet")
    sheet.add_argument("src")
    sheet.add_argument("-o", "--out")
    sheet.add_argument("--frames", type=int, default=12)
    glb = modes.add_parser("glb")
    glb.add_argument("src")
    glb.add_argument("-o", "--out")
    probe_mode = modes.add_parser("probe")
    probe_mode.add_argument("src", nargs="+")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
