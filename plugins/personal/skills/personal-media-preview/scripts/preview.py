#!/usr/bin/env python3
"""Make phone-sized previews of what a session produced, per standards/media.md.

Each mode writes its output and prints one JSON line of facts about it (path,
size, duration, resolution, codec, and whether the MP4 index comes first). It
makes no judgement about the content; the agent decides what to send where.

Usage:
    preview.py clip SRC [-o OUT]       # <=10 s, <=8 MB, 720p H.264 (--max-mb to tighten)
    preview.py flyover SRC [-o OUT]    # <=60 s, <=15 MB, named *-flyover.mp4
    preview.py stills SRC... [-d DIR]  # <=2048 px JPEG, one per input
    preview.py sheet SRC [-o OUT]      # contact sheet of evenly spaced frames
    preview.py glb SRC [-o OUT]        # decimated GLB <=15 MB (needs gltfpack; --max-mb to tighten)
    preview.py probe FILE...           # facts only, no output written

Needs ffmpeg and ffprobe on PATH; glb also needs gltfpack.
"""

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path

MB = 1_000_000
VIDEO_BOX = (1280, 720)  # 720p: long edge 1280, short edge 720, either orientation
LONG_EDGE_STILL = 2048
MAX_FPS = 30
JPEG_QUALITY = 3  # ffmpeg mjpeg scale, 2 (best) to 31; 3 is about quality 85
H264_QUALITY = 23  # CRF / NVENC CQ; the bitrate ceiling does the size work
CAP_HEADROOM = 0.9  # aim under the cap; VBV can overshoot a little
MAX_ENCODES = 3
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
        if args.max_mb is not None:
            limits = replace(limits, max_bytes=min(limits.max_bytes, int(args.max_mb * MB)))
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
        cap = GLB_MAX_BYTES if args.max_mb is None else min(GLB_MAX_BYTES, int(args.max_mb * MB))
        return _emit(make_glb(Path(args.src), out, cap))
    status = 0
    for path in args.src:
        status |= _emit(probe(Path(path)))
    return status


def make_video(src: Path, out: Path, limits: VideoLimits, encoder: str) -> dict:
    """Encode src to an H.264 preview within limits, in one pass when it can.

    Quality is constant (CRF) with a bitrate ceiling worked out from the size
    cap, so an easy source stays small and a hard one is held under the cap in
    the same encode. VBV can overshoot slightly, so an output over the cap is
    re-encoded with the ceiling scaled down, at most twice. NVENC has a rate
    floor that a very noisy source can sit above, so one still over the cap
    after its retries is encoded again with x264, which holds the cap.
    """
    source = probe(src)
    duration = source.get("durationSeconds") or 0.0
    speed = max(1.0, duration / limits.max_seconds) if duration else 1.0
    out_seconds = min(duration / speed, limits.max_seconds) if duration else limits.max_seconds
    # Drop frames before scaling, so only the frames kept get scaled.
    filters = [f"setpts=PTS/{speed:.6f}", f"fps={MAX_FPS}", _video_scale_filter(*VIDEO_BOX)]
    out.parent.mkdir(parents=True, exist_ok=True)
    encoder = _pick_encoder(encoder)
    first_maxrate_kbps = int(limits.max_bytes * 8 * CAP_HEADROOM / out_seconds / 1000)
    facts, maxrate_kbps, encodes = _encode_to_cap(
        src, out, filters, limits, encoder, first_maxrate_kbps)
    if "nvenc" in encoder and facts["sizeBytes"] > limits.max_bytes:
        encoder = "libx264"
        facts, maxrate_kbps, more = _encode_to_cap(
            src, out, filters, limits, encoder, first_maxrate_kbps)
        encodes += more
    facts.update(
        kind=limits.kind,
        source=str(src),
        sourceDurationSeconds=duration,
        speedFactor=round(speed, 3),
        encoder=encoder,
        maxrateKbps=maxrate_kbps,
        encodes=encodes,
        capBytes=limits.max_bytes,
        withinCap=facts["sizeBytes"] <= limits.max_bytes,
    )
    return facts


def _encode_to_cap(src: Path, out: Path, filters: list[str], limits: VideoLimits,
                   encoder: str, maxrate_kbps: int) -> tuple[dict, int, int]:
    """Encode until the file fits the cap or MAX_ENCODES are spent.

    Returns the output's facts, the bitrate ceiling the file was made at, and
    the number of encodes run.
    """
    # On a GPU runner, decode on the card too: decoding a 4K source is most of the time.
    decode = ["-hwaccel", "auto"] if "nvenc" in encoder else []
    facts: dict = {}
    for encodes in range(1, MAX_ENCODES + 1):
        args = [*decode, "-i", str(src), "-an", "-vf", ",".join(filters), "-t", str(limits.max_seconds)]
        tail = ["-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
        _ffmpeg(*args, *_encoder_args(encoder, maxrate_kbps), *tail)
        facts = probe(out)
        if facts["sizeBytes"] <= limits.max_bytes or encodes == MAX_ENCODES:
            break  # past the last try, keep the rate this file was made at
        maxrate_kbps = int(maxrate_kbps * limits.max_bytes / facts["sizeBytes"] * CAP_HEADROOM)
    return facts, maxrate_kbps, encodes


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


def make_glb(src: Path, out: Path, max_bytes: int = GLB_MAX_BYTES) -> dict:
    """Decimate with gltfpack, halving the kept ratio until the file fits."""
    ratio = GLB_RATIOS[0]
    for ratio in GLB_RATIOS:
        _run("gltfpack", "-i", str(src), "-o", str(out), "-cc", "-si", str(ratio))
        if out.stat().st_size <= max_bytes:
            break
    size = out.stat().st_size
    return {
        "path": str(out), "kind": "glb", "source": str(src),
        "sizeBytes": size, "simplifyRatio": ratio,
        "capBytes": max_bytes, "withinCap": size <= max_bytes,
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
    if limits.kind == "flyover" and not out.stem.endswith("-flyover"):
        out = out.with_name(f"{out.stem}-flyover{out.suffix or '.mp4'}")
    return out


def _scale_filter(long_edge: int) -> str:
    # Fit the long edge, never upscale, keep both sides even for yuv420p.
    return (
        f"scale=w='if(gt(iw,ih),min({long_edge},iw),-2)'"
        f":h='if(gt(iw,ih),-2,min({long_edge},ih))'"
    )


def _video_scale_filter(long_edge: int, short_edge: int) -> str:
    # Fit inside a long_edge x short_edge box turned to match the source, so
    # landscape lands at 1280x720 and portrait at 720x1280. Never upscale;
    # keep both sides even for yuv420p.
    return (
        f"scale=w='if(gte(iw,ih),min({long_edge},iw),min({short_edge},iw))'"
        f":h='if(gte(iw,ih),min({short_edge},ih),min({long_edge},ih))'"
        ":force_original_aspect_ratio=decrease:force_divisible_by=2"
    )


def _encoder_args(encoder: str, maxrate_kbps: int) -> list[str]:
    rate = ["-maxrate", f"{maxrate_kbps}k", "-bufsize", f"{maxrate_kbps}k"]
    if "nvenc" in encoder:
        return ["-c:v", encoder, "-preset", "p4", "-rc", "vbr", "-cq", str(H264_QUALITY), *rate]
    return ["-c:v", encoder, "-preset", "veryfast", "-crf", str(H264_QUALITY), *rate]


def _pick_encoder(requested: str) -> str:
    """auto: NVENC when this ffmpeg has it (a GPU runner), else libx264."""
    if requested != "auto":
        return requested
    if " h264_nvenc " not in _run("ffmpeg", "-hide_banner", "-encoders").stdout:
        return "libx264"
    # Listed isn't usable: a build can have NVENC with no GPU or driver here.
    probe_encode = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=256x144:d=0.1",
         "-c:v", "h264_nvenc", "-f", "null", "-"],
        capture_output=True, stdin=subprocess.DEVNULL,
    )
    return "h264_nvenc" if probe_encode.returncode == 0 else "libx264"


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
        mode.add_argument("--encoder", default="auto",
                          help="auto (NVENC if ffmpeg has it), libx264 or h264_nvenc")
        mode.add_argument("--max-mb", type=float,
                          help="size cap in MB, below the mode's default (for a tighter channel)")
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
    glb.add_argument("--max-mb", type=float, help="size cap in MB, below the 15 MB default")
    probe_mode = modes.add_parser("probe")
    probe_mode.add_argument("src", nargs="+")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
