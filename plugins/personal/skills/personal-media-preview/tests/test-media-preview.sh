#!/usr/bin/env bash
# Tests for scripts/preview.py against synthetic sources: ffmpeg test patterns,
# temporal noise that H.264 can't compress, and a generated sphere mesh
# (make-mesh.py). Needs ffmpeg, ffprobe and python3, and gltfpack for the glb
# tests; prints SKIP: and passes when one is missing, which CI fails on.
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
# A 30-second landscape source above 720p and a 4-second portrait one, encoded
# fast; the preview's own encode is what's under test. 15 fps keeps the frame
# count low while 3x speed-up still takes it past the 30 fps cap.
ffmpeg -v error -f lavfi -i testsrc2=size=1600x900:rate=15:duration=30 \
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
out=$(python3 "$preview" flyover portrait.mp4)
expect_eq "flyover default name" "$(field "$out" path)" "portrait-flyover.mp4"

echo "size cap"
# Full-frame temporal noise defeats motion prediction, so every frame costs
# nearly its raw size: the worst case for the size cap. Small and short keeps
# the test fast; --max-mb shrinks the cap to match. The bitrate ceiling has to
# hold even full-strength noise under the cap, in one encode or a retry.
ffmpeg -v error -f lavfi -i "color=c=gray:s=320x240:r=30:d=2" -vf "noise=alls=25:allf=t+u" \
    -c:v libx264 -crf 0 -preset ultrafast -pix_fmt yuv420p noise25.mkv
ffmpeg -v error -f lavfi -i "color=c=gray:s=320x240:r=30:d=2" -vf "noise=alls=100:allf=t+u" \
    -c:v libx264 -crf 0 -preset ultrafast -pix_fmt yuv420p noise100.mkv
for strength in 25 100; do
    out=$(python3 "$preview" clip "noise$strength.mkv" -o "noise$strength.mp4" --max-mb 0.1)
    expect_eq "noise $strength exits 0" "$?" "0"
    expect_eq "noise $strength within cap" "$(field "$out" withinCap)" "true"
    expect_le "noise $strength under 0.1 MB" "$(field "$out" sizeBytes)" 100000
    expect_le "noise $strength took at most 3 encodes" "$(field "$out" encodes)" 3
done
expect_eq "noise reports its bitrate ceiling" "$(field "$out" maxrateKbps | grep -cE '^[0-9]+$')" "1"
out=$(python3 "$preview" clip noise25.mkv -o noise-wide.mp4 --max-mb 50)
expect_eq "--max-mb never raises the clip cap" "$(field "$out" capBytes)" "8000000"

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
# A PATH holding only what preview.py needs besides gltfpack.
mkdir -p nogltf
for tool in python3 ffmpeg ffprobe; do ln -s "$(command -v "$tool")" "nogltf/$tool"; done
if PATH="$work/nogltf" python3 "$preview" glb missing.glb >"$work/out" 2>&1; then
    fail "glb without gltfpack should fail"
elif grep -qF "gltfpack" "$work/out"; then
    pass "glb names the missing tool"
else
    fail "glb error doesn't name gltfpack"
fi
if ! command -v gltfpack >/dev/null; then
    echo "SKIP: media-preview glb tests: gltfpack not on PATH (npm install gltfpack)"
else
    python3 "$here/make-mesh.py" sphere.glb
    tris() { python3 "$here/make-mesh.py" --triangles "$1"; }
    expect_eq "fixture has 50,000 triangles" "$(tris sphere.glb)" "50000"
    out=$(python3 "$preview" glb sphere.glb -o sphere-preview.glb)
    expect_eq "glb exits 0" "$?" "0"
    expect_eq "glb output is GLB" "$(head -c 4 sphere-preview.glb)" "glTF"
    expect_eq "glb keeps half the triangles first" "$(field "$out" simplifyRatio)" "0.5"
    if [ "$(tris sphere-preview.glb)" -lt 50000 ]; then pass "glb has fewer triangles"; else fail "glb kept $(tris sphere-preview.glb) triangles"; fi
    expect_le "glb is smaller than its source" "$(field "$out" sizeBytes)" "$(wc -c < sphere.glb)"
    out=$(python3 "$preview" glb sphere.glb -o sphere-tight.glb --max-mb 0.03)
    expect_eq "tight glb fits" "$(field "$out" withinCap)" "true"
    if python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) < 0.5 else 1)' "$(field "$out" simplifyRatio)"; then
        pass "glb loop decimated further to fit"
    else
        fail "glb loop stayed at ratio $(field "$out" simplifyRatio)"
    fi
fi

if [ "$failures" -gt 0 ]; then
    echo "$failures media-preview test(s) failed" >&2
    exit 1
fi
echo "all media-preview tests passed"
