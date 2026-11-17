# Session Media

How an agent shows me what it made: renders, turntables, flyovers, screenshots,
point clouds and meshes. I'm often reading on a phone, in the Claude app, over a
cellular link, so anything shown in chat or on an artifact is a **preview**: small,
short, and in a format every phone plays. The originals go to object storage and
get a link. The `personal-media-preview` skill makes the previews
(`plugins/personal/skills/personal-media-preview/` in the personal bok).

Contents: [Previews and originals](#previews-and-originals) · [Video](#video) · [Stills](#stills) · [3D](#3d) · [Where each one goes](#where-each-one-goes) · [Why these numbers](#why-these-numbers)

## Previews and originals

- **Never send an original to chat.** A 4K render, a 2 GB point cloud or a
  10-minute capture is the wrong thing to open on a phone, and the upload limits
  below reject most of them anyway. Make a preview, send that, and link the
  original.
- **Make previews with a script, not by hand.** The skill's `preview.py` applies
  the numbers below the same way every time, so a preview from Tuesday's run and
  one from Friday's look alike. A prompt that says "keep it small" drifts.
- **Originals live in object storage** (GCS, S3, Azure Blob), written by the
  pipeline rather than the agent, and the chat gets a link: a signed URL that
  expires, or an authenticated console link. Say which, and when a signed link
  expires.

## Video

| | Clip (default) | Flyover |
| --- | --- | --- |
| Length | 10 seconds or less | 60 seconds or less |
| Size | 8 MB or less | 15 MB or less |
| Resolution | 720 on the long edge | 720 on the long edge |

- **H.264, `yuv420p`, `+faststart`.** That plays inline on every phone and in
  every browser, and `faststart` puts the index first so playback starts before
  the download finishes. Not HEVC or AV1, even though a Blackwell card encodes
  AV1 well: older phones and some browsers won't play them. Encoding with NVENC
  (`h264_nvenc`) is fine; the codec is what matters, not the encoder.
- **No audio** unless the audio is the point.
- **30 fps or less.** A turntable doesn't need more.
- **A clip is the default.** A flyover is the exception, for a camera path that
  needs the time (a site flythrough, a long reconstruction sweep), and it's
  labelled as one in the file name (`*-flyover.mp4`) and in the message, so I know
  before I tap it that it's a minute long.
- **Longer than the cap means speed it up or cut it, not lower the resolution
  further.** A 3-minute capture becomes a 10-second clip at 18× or a 60-second
  flyover at 3×; the script does the speed-up.

## Stills

- **2048 px or less on the long edge,** JPEG (quality 85) or WebP. PNG only when
  the image is a diagram or has text that compression would smear.
- **A contact sheet for anything with frames.** One image, a grid of evenly spaced
  frames, so I can see the whole sequence without playing it. Agents can read a
  contact sheet too, which makes it the cheap way to check a render for floaters,
  holes or a broken camera path before reporting success; an agent can't watch a
  video.

## 3D

- **A decimated GLB, 15 MB or less,** for an artifact viewer (`<model-viewer>` or
  three.js) so I can orbit the result instead of watching a fixed turntable.
  `gltfpack` does the decimation and compression. Gaussian splats get the same
  treatment through a compressed splat format and a splat viewer.
- **Plus a turntable clip,** because not every surface opens an artifact, and a
  clip is what shows up in a notification.

## Where each one goes

| What | Where |
| --- | --- |
| Clip, flyover, still, contact sheet | `SendUserFile` into chat |
| Interactive 3D | An Artifact page with the GLB as a supporting file |
| Originals | Object storage, written by the pipeline; a link in chat |

## Why these numbers

The caps sit under the hard limits with room to spare:

- An Artifact's supporting binary file is limited to 15 MB, an uploaded asset to
  20 MiB and the page itself to 16 MB. A flyover or GLB at 15 MB fits either way.
- `SendUserFile` has no documented cap, so the clip cap is set by what loads
  quickly on a phone over cellular, not by the tool.
- 720p is the largest size that still looks sharp in a chat bubble and stays
  under 8 MB for 10 seconds at a sensible quality.
