#!/usr/bin/env bash
# Tests for scripts/preview.py against synthetic ffmpeg sources. Needs ffmpeg,
# ffprobe and python3; prints SKIP and passes when ffmpeg is missing. The glb
# mode needs gltfpack and is only checked for its missing-tool error.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
preview="$here/../scripts/preview.py"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failures=0
pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1" >&2; failures=$((failures + 1)); }
expect_eq() { if [ "$2" = "$3" ]; then pass "$1"; else fail "$1: expected '$3', got '$2'"; fi; }
expect_le() { if [ "$2" -le "$3" ]; then pass "$1"; else fail "$1: $2 is over $3"; fi; }
# field <json> <key>: one fact from preview.py's JSON line.
field() { python3 -c 'import json,sys; v=json.loads(sys.argv[1]).get(sys.argv[2]); print(str(v).lower() if isinstance(v,bool) else v)' "$1" "$2"; }

if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
    echo "SKIP: media-preview tests: ffmpeg or ffprobe not on PATH"
    exit 0
fi

cd "$work" || exit 1
# A 30-second 1080p landscape source and a 4-second portrait one, encoded
# fast; the preview's own encode is what's under test.
ffmpeg -v error -f lavfi -i testsrc2=size=1920x1080:rate=60:duration=30 \
    -c:v libx264 -preset ultrafast -pix_fmt yuv420p landscape.mp4
ffmpeg -v error -f lavfi -i testsrc2=size=1080x1920:rate=30:duration=4 \
    -c:v libx264 -preset ultrafast -pix_fmt yuv420p portrait.mp4
ffmpeg -v error -f lavfi -i testsrc2=size=4000x3000 -frames:v 1 big.png
ffmpeg -v error -f lavfi -i testsrc2=size=640x480 -frames:v 1 small.png

echo "clip"
out=$(python3 "$preview" clip landscape.mp4 -o clip.mp4)
expect_eq "clip exits 0" "$?" "0"
expect_eq "clip kind" "$(field "$out" kind)" "clip"
expect_eq "clip is H.264" "$(field "$out" codec)" "h264"
expect_eq "clip is yuv420p" "$(field "$out" pixFmt)" "yuv420p"
expect_eq "clip width 1280" "$(field "$out" width)" "1280"
expect_eq "clip height 720" "$(field "$out" height)" "720"
expect_eq "clip sped up to 10 s" "$(field "$out" durationSeconds)" "10.0"
expect_eq "clip speed factor" "$(field "$out" speedFactor)" "3.0"
expect_eq "clip caps fps at 30" "$(field "$out" fps)" "30.0"
expect_le "clip within 8 MB" "$(field "$out" sizeBytes)" 8000000
expect_eq "clip moov before mdat" "$(field "$out" moovBeforeMdat)" "true"
expect_eq "clip has no audio" "$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 clip.mp4)" ""

echo "portrait and short sources"
out=$(python3 "$preview" clip portrait.mp4 -o portrait-clip.mp4)
expect_eq "portrait height 1280" "$(field "$out" height)" "1280"
expect_eq "portrait width 720" "$(field "$out" width)" "720"
expect_eq "short source not slowed" "$(field "$out" speedFactor)" "1.0"
expect_eq "short source keeps its length" "$(field "$out" durationSeconds)" "4.0"

echo "flyover"
out=$(python3 "$preview" flyover landscape.mp4 -o tour.mp4)
expect_eq "flyover kind" "$(field "$out" kind)" "flyover"
expect_eq "flyover is labelled in the name" "$(field "$out" path)" "tour-flyover.mp4"
expect_eq "flyover keeps 30 s under the 60 s cap" "$(field "$out" durationSeconds)" "30.0"
expect_le "flyover within 15 MB" "$(field "$out" sizeBytes)" 15000000
out=$(python3 "$preview" flyover landscape.mp4)
expect_eq "flyover default name" "$(field "$out" path)" "landscape-flyover.mp4"

echo "stills"
out=$(python3 "$preview" stills big.png small.png -d stills)
expect_eq "stills exits 0" "$?" "0"
big=$(printf '%s\n' "$out" | sed -n 1p)
small=$(printf '%s\n' "$out" | sed -n 2p)
expect_eq "big still fits 2048" "$(field "$big" width)" "2048"
expect_eq "big still keeps aspect" "$(field "$big" height)" "1536"
expect_eq "small still not upscaled" "$(field "$small" width)" "640"
expect_eq "still is JPEG" "$(field "$big" codec)" "mjpeg"

echo "sheet"
out=$(python3 "$preview" sheet landscape.mp4 -o sheet.jpg --frames 12)
expect_eq "sheet is 4 tiles wide" "$(field "$out" width)" "1920"
expect_eq "sheet records frame count" "$(field "$out" frames)" "12"

echo "probe"
out=$(python3 "$preview" probe landscape.mp4)
expect_eq "probe reads duration" "$(field "$out" durationSeconds)" "30.0"
expect_eq "probe reports the default muxer's atom order" "$(field "$out" moovBeforeMdat)" "false"

echo "glb"
if command -v gltfpack >/dev/null; then
    echo "  skip  glb decimation (covered by hand; needs a mesh fixture)"
else
    if python3 "$preview" glb missing.glb >"$work/out" 2>&1; then
        fail "glb without gltfpack should fail"
    else
        if grep -qF "gltfpack" "$work/out"; then pass "glb names the missing tool"; else fail "glb error doesn't name gltfpack"; fi
    fi
fi

if [ "$failures" -gt 0 ]; then
    echo "$failures media-preview test(s) failed" >&2
    exit 1
fi
echo "all media-preview tests passed"
