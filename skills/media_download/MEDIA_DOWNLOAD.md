---
name: media-download
description: Download user-authorized audio or video from accessible URLs with yt-dlp, including merging separate video and audio streams.
---

# Media Download

Use this workflow when a user asks to download audio or video from a URL.
Only download media the user is authorized to access; do not bypass DRM,
authentication, or platform restrictions.

## Workflow

1. Use `run_python_task` for the whole download. Its virtual environment is
   temporary, so install `yt-dlp` and the FFmpeg provider in the same script.
2. YouTube commonly serves video and audio as separate adaptive streams. Install
   `yt-dlp` and `imageio-ffmpeg` with the task's interpreter, then pass
   `imageio_ffmpeg.get_ffmpeg_exe()` as `ffmpeg_location` to `YoutubeDL`.
   If a system FFmpeg is already available, it may be used instead.
3. Prefer `format: "bestvideo+bestaudio/best"` so yt-dlp can merge the streams.
   Do not fall back to a video-only format just because FFmpeg is unavailable;
   report the dependency error instead.
4. If the user asked for one video, set `noplaylist: True`, especially when the
   URL also has playlist query parameters. Download a playlist only when asked.
5. Use an ASCII ID-based output template such as `%(id)s.%(ext)s` to avoid
   Unicode filenames that are easy to mistype with file tools. Set `quiet` and
   `noprogress` so progress bars do not truncate the final status and path.
6. Save to the task's current directory. After downloading, verify that the
   final output file exists and is non-empty. For an audio/video request, use
   FFmpeg to decode a short portion of the first audio stream to the null
   output; report failure if no audio stream is present.
7. Print the final path, size, and audio-verification result from the same
   script. Do not repeat verification with other tools after the script
   confirms success.

## Example

```python
import os
import shutil
import subprocess
import sys

subprocess.check_call([
    sys.executable, "-m", "pip", "install", "yt-dlp", "imageio-ffmpeg"
])

import imageio_ffmpeg
import yt_dlp

url = "USER_PROVIDED_URL"
ffmpeg_path = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()
options = {
    "format": "bestvideo+bestaudio/best",
    "ffmpeg_location": ffmpeg_path,
    "noplaylist": True,
    "outtmpl": "%(id)s.%(ext)s",
    "quiet": True,
    "noprogress": True,
}

with yt_dlp.YoutubeDL(options) as downloader:
    info = downloader.extract_info(url, download=True)
    output_path = info.get("filepath") or downloader.prepare_filename(info)

if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
    raise RuntimeError(f"Download output is missing or empty: {output_path}")

audio_check = subprocess.run(
    [
        ffmpeg_path, "-v", "error", "-i", output_path,
        "-map", "0:a:0", "-t", "1", "-f", "null", "-"
    ],
    capture_output=True,
    text=True,
)
if audio_check.returncode != 0:
    raise RuntimeError(f"Audio stream verification failed: {audio_check.stderr}")

print(f"Downloaded video with audio: {output_path}")
print(f"Title: {info.get('title', 'Unknown title')}")
print(f"Size: {os.path.getsize(output_path)} bytes")
```
