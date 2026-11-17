---
name: personal-media-preview
description: >-
  Make phone-sized previews of what a session produced before showing them:
  a 720p H.264 clip of 10 seconds or less (a labelled flyover up to 60
  seconds), stills at 2048 px or less, a contact sheet of a video's frames,
  and a decimated GLB for an interactive 3D artifact, each within the size
  caps in standards/media.md, with a JSON fact line per output. Use before
  sending any render, turntable, flyover, screenshot, point cloud or mesh to
  chat or an artifact, when a video or image is too big or too long to view
  on a phone, or for "make a preview", "make a clip", "contact sheet",
  "flyover", or "show me the result".
---

# personal-media-preview

The canonical rules are in
[`../personal-standards/standards/media.md`](../personal-standards/standards/media.md).
The essentials:

- **Chat gets a preview, never an original.** Originals go to object storage
  and chat gets a link.
- **Video:** H.264, `yuv420p`, `+faststart`, 720p (1280×720, or 720×1280 portrait), no audio.
  A clip is 10 seconds and 8 MB or less; a flyover, the labelled exception for
  a camera path that needs the time, is 60 seconds and 15 MB or less.
- **Stills:** 2048 px or less on the long edge, JPEG. A contact sheet for
  anything with frames.
- **3D:** a decimated GLB of 15 MB or less for an artifact viewer, plus a
  turntable clip.

## Make the preview

```bash
python3 scripts/preview.py clip render.mp4 -o render-clip.mp4
python3 scripts/preview.py flyover sweep.mp4            # writes sweep-flyover.mp4
python3 scripts/preview.py sheet render.mp4 --frames 12
python3 scripts/preview.py stills frame-*.png -d stills
python3 scripts/preview.py glb mesh.glb -o mesh-preview.glb   # needs gltfpack
python3 scripts/preview.py probe anything.mp4           # facts only
```

`scripts/` is relative to this skill's folder (`${CLAUDE_PLUGIN_ROOT}/skills/personal-media-preview/scripts/` in an installed plugin).

A source longer than the cap is sped up to fit, never cut, so a 30-second
turntable becomes a 10-second clip at 3×; a shorter one keeps its length. If
the file is over the size cap, the script re-encodes at lower quality until it
fits. `--encoder h264_nvenc` uses the GPU encoder on a runner that has one.

Each output prints one JSON line: `path`, `sizeBytes`, `codec`, `width`,
`height`, `pixFmt`, and for video `durationSeconds`, `fps`, `speedFactor`,
`moovBeforeMdat`, `capBytes` and `withinCap`. The exit code is 1 when an
output couldn't be brought under its cap. The script decides nothing else:
which preview to make, whether a flyover is warranted, and what the frames
show are yours to judge.

## Check before you send

Read the contact sheet (or a still) yourself before reporting success: it's
the cheap way to catch a black frame, a broken camera path, holes or floaters,
and you can't watch a video. Then say what you saw in one line.

## Send it

| What | How |
| --- | --- |
| Clip, flyover, still, contact sheet | `SendUserFile`, `display: render` |
| Interactive 3D | An Artifact page with `<model-viewer>` or three.js and the GLB as a supporting file |
| Originals | Leave them where the pipeline wrote them (object storage) and give the link, saying when a signed link expires |

Write previews to the working directory or the scratchpad, since the Claude
app can open files only there, and keep them out of commits: `.scratch/` or a
gitignored output folder.
