import hashlib
import json
import os
import shutil
import subprocess
import sys
import textwrap
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import av
import imageio_ffmpeg

from .db import now
from .errors import AppError

MAX_FILE = 100 * 1024 * 1024
MAX_TOTAL = 500 * 1024 * 1024


@lru_cache(maxsize=1)
def ffmpeg():
    return os.environ.get("FFMPEG_BINARY") or shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


def probe(path):
    try:
        with av.open(str(path)) as container:
            if not container.streams.video:
                raise ValueError("No video stream")
            video = container.streams.video[0]
            audio = container.streams.audio[0] if container.streams.audio else None
            duration = float(container.duration / av.time_base) if container.duration else float(video.duration * video.time_base) if video.duration else 0
            return {"duration_seconds": duration, "width": video.width, "height": video.height,
                    "rotation": int(video.metadata.get("rotate", 0)),
                    "video_codec": video.codec_context.name,
                    "pixel_format": video.codec_context.format.name if video.codec_context.format else "unknown",
                    "fps": float(video.average_rate or 0), "has_audio": audio is not None,
                    "audio_codec": audio.codec_context.name if audio else None,
                    "sample_rate": audio.codec_context.sample_rate if audio else None,
                    "audio_channels": audio.codec_context.channels if audio else 0}
    except (av.FFmpegError, ValueError, TypeError, OverflowError):
        raise AppError("This file could not be read as a video. Export it as an H.264 MP4 and try again.", "INVALID_MEDIA")


def validate_upload(path, filename):
    if Path(filename).suffix.lower() not in {".mp4", ".mov"}:
        raise AppError("Upload an MP4 or MOV file with H.264 video.", "UNSUPPORTED_FORMAT")
    metadata = probe(path)
    if metadata["video_codec"] != "h264":
        raise AppError("This video uses an unsupported codec. Convert it to H.264 before uploading.", "UNSUPPORTED_CODEC")
    if metadata["audio_codec"] and not (metadata["audio_codec"] == "aac" or metadata["audio_codec"].startswith("pcm_")):
        raise AppError("Use AAC or PCM audio in your video.", "UNSUPPORTED_AUDIO")
    if not 2.99 <= metadata["duration_seconds"] <= 120.1:
        raise AppError("Each clip must be between 3 and 120 seconds long.", "INVALID_DURATION")
    if min(metadata["width"], metadata["height"]) < 360 or max(metadata["width"], metadata["height"]) > 1920:
        raise AppError("Use clips with a short edge of at least 360 pixels and a long edge no larger than 1920 pixels.", "INVALID_RESOLUTION")
    return metadata


def srt_time(seconds):
    ms = int(round(seconds * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def write_srt(cues, path):
    content = "\n\n".join(f"{i + 1}\n{srt_time(c['start_seconds'])} --> {srt_time(c['end_seconds'])}\n{c['text']}" for i, c in enumerate(cues))
    Path(path).write_text(content + "\n", encoding="utf-8")


def write_ass(cues, path, large=False):
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{60 if large else 48},&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,-1,0,0,0,100,100,0,0,1,3,1,2,108,108,340,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def stamp(t):
        cs = round(t * 100)
        return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"
    rows = []
    for cue in cues:
        plain = " ".join(cue["text"].split()).replace("\\", "＼").replace("{", "｛").replace("}", "｝")
        lines = textwrap.wrap(plain, width=32, break_long_words=True, break_on_hyphens=False)
        if len(lines) > 2:
            raise AppError("A subtitle is too long for two lines. Split it into shorter cues before exporting.", "SUBTITLE_TOO_LONG")
        text = r"\N".join(lines)
        rows.append(f"Dialogue: 0,{stamp(cue['start_seconds'])},{stamp(cue['end_seconds'])},Default,,0,0,0,,{text}")
    Path(path).write_text(header + "\n".join(rows) + "\n", encoding="utf-8-sig")


class Cancelled(Exception):
    pass


class MediaWorker:
    def __init__(self, db, settings, directory):
        self.db, self.settings, self.directory = db, settings, Path(directory)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="trendforge-media")
        self.cancel_events = {}
        self.lock = threading.Lock()
        self.db.interrupt_jobs()

    def submit(self, job):
        event = threading.Event()
        with self.lock:
            self.cancel_events[job["id"]] = event
        self.executor.submit(self.run, job["id"], event)

    def cancel(self, jid):
        with self.lock:
            event = self.cancel_events.get(jid)
            if event:
                event.set()
        job = self.db.job(jid)
        if job["status"] in {"queued", "running"}:
            return self.db.update_job(jid, {"status": "cancelling", "stage": "Stopping safely"})
        return job

    def stage(self, jid, text):
        self.db.update_job(jid, {"stage": text, "progress_percent": None})

    def command(self, args, cwd, event, timeout=600):
        if event.is_set():
            raise Cancelled()
        logfile = Path(cwd) / "process.log"
        with logfile.open("wb") as log:
            process = subprocess.Popen([str(x) for x in args], cwd=str(cwd), stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            started = time.monotonic()
            while process.poll() is None:
                if event.wait(0.15) or time.monotonic() - started > timeout:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    if event.is_set():
                        raise Cancelled()
                    raise AppError("This processing step took too long. Your saved clips are safe; try again.", "PROCESS_TIMEOUT")
            if process.returncode:
                # Keep the full diagnostic on the device; never expose commands or private paths to the client.
                raise AppError("This processing step could not finish. Check the local job log, then try again.", "PROCESS_FAILED")

    def run(self, jid, event):
        root = None
        try:
            job = self.db.job(jid)
            if event.is_set():
                raise Cancelled()
            self.db.update_job(jid, {"status": "running", "started_at": now()})
            root = self.directory / "jobs" / jid
            root.mkdir(parents=True, exist_ok=True)
            if job["type"] == "prepare":
                output = self.prepare(job, root, event)
            elif job["type"] == "edited_prepare":
                output = self.prepare_edited(job, root, event)
            elif job["type"] == "export":
                output = self.export(job, root, event)
            elif job["type"] == "transcribe":
                output = self.transcribe(job, root, event)
            elif job["type"] == "model_download":
                self.stage(jid, "Downloading the speech model")
                self.command([sys.executable, "-m", "trendforge.transcribe", "--warmup", "--model",
                    job["input"]["model"], "--cache", self.directory / "models"], root, event, 900)
                (self.directory / "models" / f".ready-{job['input']['model']}").touch()
                output = {"model": job["input"]["model"]}
            else:
                raise AppError("Unknown processing step.")
            with self.db.lock, self.lock:
                if event.is_set():
                    raise Cancelled()
                self.db.update_job(jid, {"status": "succeeded", "stage": "Complete", "progress_percent": 100,
                                        "output": output, "finished_at": now()})
                if job["type"] == "export":
                    self.db.update_project(job["project_id"], {"export_id": output["export_id"],
                        "ready_confirmed_at": None, "phase": "EXPORT_READY"})
            self.db.event(job["project_id"], "job_succeeded", {"job_id": jid})
        except Cancelled:
            self.db.update_job(jid, {"status": "cancelled", "stage": "Cancelled", "finished_at": now()})
        except AppError as exc:
            self.db.update_job(jid, {"status": "failed", "stage": "Needs attention", "finished_at": now(),
                                    "error": {"code": exc.code, "message": exc.message}})
        except Exception:
            import logging
            logging.getLogger("trendforge.media").exception("Media job failed: %s", jid)
            self.db.update_job(jid, {"status": "failed", "stage": "Needs attention", "finished_at": now(),
                                    "error": {"code": "PROCESS_FAILED", "message": "Processing stopped unexpectedly. Your saved inputs are safe; try this step again."}})
        finally:
            with self.lock:
                self.cancel_events.pop(jid, None)
            # Normalized intermediates are never checkpoints; preserve draft/audio referenced by a saved document.
            if root:
                for temp in root.glob("segment_*.mp4"):
                    temp.unlink(missing_ok=True)
                if self.db.job(jid)["status"] in {"failed", "cancelled"}:
                    for filename in ("final.mp4", "export.ass", "export.srt"):
                        (root / filename).unlink(missing_ok=True)

    def encode_args(self):
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-threads", "2",
                "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart"]

    def prepare(self, job, root, event):
        pid, jid = job["project_id"], job["id"]
        plan = self.db.doc(pid, job["input"]["plan_id"], "plan")
        assets = {a["id"]: a for a in self.db.docs(pid, "asset")}
        if shutil.disk_usage(root).free < 1024 ** 3:
            raise AppError("Keep at least 1 GB free for video processing, then try again.", "DISK_SPACE")
        segments = sorted(plan["segments"], key=lambda s: s["order"])
        names = []
        for i, segment in enumerate(segments):
            self.stage(jid, f"Preparing clip {i + 1} of {len(segments)}")
            asset = assets[segment["asset_id"]]
            length = segment["out_seconds"] - segment["in_seconds"]
            args = [ffmpeg(), "-hide_banner", "-loglevel", "warning", "-y", "-ss", str(segment["in_seconds"]), "-i", self.directory / asset["file_ref"]]
            if not asset["has_audio"]:
                args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            args += ["-t", str(length), "-map", "0:v:0", "-map", "0:a:0" if asset["has_audio"] else "1:a:0",
                "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x101216,setsar=1,fps=30,format=yuv420p,setpts=PTS-STARTPTS",
                "-af", f"aresample=48000,apad,atrim=duration={length},asetpts=PTS-STARTPTS"]
            name = f"segment_{i}.mp4"
            self.command(args + self.encode_args() + [name], root, event)
            names.append(name)
        self.stage(jid, "Combining clips and applying finishing effects")
        (root / "clips.txt").write_text("\n".join(f"file '{name}'" for name in names), encoding="utf-8")
        duration = plan["target_duration_seconds"]
        self.command([ffmpeg(), "-hide_banner", "-loglevel", "warning", "-y", "-f", "concat", "-safe", "1", "-i", "clips.txt",
            "-t", str(duration), "-vf", f"fade=t=in:st=0:d=0.3,fade=t=out:st={duration - 0.3}:d=0.3",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000"] + self.encode_args() + ["draft.mp4"], root, event)
        metadata = self.validate_final(root / "draft.mp4", duration, root, event)
        self.command([ffmpeg(), "-hide_banner", "-loglevel", "warning", "-y", "-i", "draft.mp4", "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "audio.wav"], root, event)
        draft = self.db.add_doc(pid, "draft", {"plan_id": plan["id"], "brief_id": plan["brief_revision_id"],
            "job_id": jid, "duration_seconds": duration, "file_ref": str((root / "draft.mp4").relative_to(self.directory)),
            "audio_ref": str((root / "audio.wav").relative_to(self.directory)), "metadata": metadata})
        self.db.update_project(pid, {"draft_id": draft["id"], "subtitle_id": None, "export_id": None, "phase": "DRAFT_READY"})
        self.db.update_job(jid, {"output": {"draft_id": draft["id"]}})
        track = self.speech_track(pid, draft, root, jid, event, job["input"].get("speech_model"))
        return {"draft_id": draft["id"], "subtitle_id": track["id"]}

    def prepare_edited(self, job, root, event):
        pid, jid = job["project_id"], job["id"]
        item = self.db.doc(pid, job["input"]["edited_video_id"], "edited_video")
        metadata = item["metadata"]
        duration = metadata["duration_seconds"]
        if shutil.disk_usage(root).free < 1024 ** 3:
            raise AppError("Keep at least 1 GB free for video processing.", "DISK_SPACE")
        self.stage(jid, "Preparing your finished edit for subtitles")
        args = [ffmpeg(), "-hide_banner", "-loglevel", "warning", "-y", "-i", self.directory / item["file_ref"]]
        if not metadata["has_audio"]:
            args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        args += ["-t", str(duration), "-map", "0:v:0", "-map", "0:a:0" if metadata["has_audio"] else "1:a:0",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x101216,setsar=1,fps=30,format=yuv420p",
            "-af", f"aresample=48000,apad,atrim=duration={duration}"]
        self.command(args + self.encode_args() + ["draft.mp4"], root, event)
        final_metadata = self.validate_final(root / "draft.mp4", duration, root, event)
        self.command([ffmpeg(), "-hide_banner", "-loglevel", "warning", "-y", "-i", "draft.mp4", "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "audio.wav"], root, event)
        draft = self.db.add_doc(pid, "draft", {"plan_id": None, "brief_id": item["brief_id"],
            "source": "external_edit", "edited_video_id": item["id"], "job_id": jid,
            "duration_seconds": duration, "file_ref": str((root / "draft.mp4").relative_to(self.directory)),
            "audio_ref": str((root / "audio.wav").relative_to(self.directory)), "metadata": final_metadata})
        self.db.update_project(pid, {"plan_id": None, "draft_id": draft["id"], "subtitle_id": None,
            "export_id": None, "ready_confirmed_at": None, "phase": "DRAFT_READY"})
        self.db.update_job(jid, {"output": {"draft_id": draft["id"]}})
        track = self.speech_track(pid, draft, root, jid, event, job["input"].get("speech_model"))
        return {"draft_id": draft["id"], "subtitle_id": track["id"]}

    def speech_track(self, pid, draft, root, jid, event, model=None):
        self.stage(jid, "Transcribing Indonesian speech")
        self.command([sys.executable, "-m", "trendforge.transcribe", "--model", model or self.settings.get("speech_model"),
            "--cache", self.directory / "models", "--input", self.directory / draft["audio_ref"],
            "--output", "transcript.json", "--duration", str(draft["duration_seconds"])], root, event, 600)
        result = json.loads((root / "transcript.json").read_text(encoding="utf-8"))
        track = self.db.add_doc(pid, "subtitle", {**result, "draft_id": draft["id"], "language": "id", "source": "asr", "status": "draft"})
        self.db.update_project(pid, {"subtitle_id": track["id"], "export_id": None, "phase": "CAPTIONS_REVIEW"})
        return track

    def transcribe(self, job, root, event):
        draft = self.db.doc(job["project_id"], job["input"]["draft_id"], "draft")
        track = self.speech_track(job["project_id"], draft, root, job["id"], event, job["input"].get("speech_model"))
        return {"draft_id": draft["id"], "subtitle_id": track["id"]}

    def export(self, job, root, event):
        pid, jid = job["project_id"], job["id"]
        draft = self.db.doc(pid, job["input"]["draft_id"], "draft")
        track = self.db.doc(pid, job["input"]["subtitle_id"], "subtitle")
        self.stage(jid, "Rendering your final video")
        source = self.directory / draft["file_ref"]
        if track["cues"]:
            write_ass(track["cues"], root / "export.ass", job["input"].get("large_text", False))
            write_srt(track["cues"], root / "export.srt")
            self.command([ffmpeg(), "-hide_banner", "-loglevel", "warning", "-y", "-i", source,
                "-vf", "ass=export.ass", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-threads", "2",
                "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "copy", "-movflags", "+faststart", "final.mp4"], root, event)
        else:
            self.command([ffmpeg(), "-hide_banner", "-loglevel", "warning", "-y", "-i", source, "-c", "copy", "-movflags", "+faststart", "final.mp4"], root, event)
        self.stage(jid, "Checking video, audio and playback")
        metadata = self.validate_final(root / "final.mp4", draft["duration_seconds"], root, event)
        if event.is_set():
            raise Cancelled()
        with (root / "final.mp4").open("rb") as final_file:
            checksum = hashlib.file_digest(final_file, "sha256").hexdigest()
        export = self.db.add_doc(pid, "export", {"job_id": jid, "draft_id": draft["id"], "plan_id": draft["plan_id"],
            "brief_id": draft["brief_id"], "subtitle_id": track["id"], "duration_seconds": draft["duration_seconds"],
            "mp4_ref": str((root / "final.mp4").relative_to(self.directory)),
            "srt_ref": str((root / "export.srt").relative_to(self.directory)) if track["cues"] else None,
            "bytes": (root / "final.mp4").stat().st_size, "sha256": checksum,
            "metadata": metadata, "validated_at": now()})
        return {"export_id": export["id"]}

    def validate_final(self, path, duration, root, event):
        meta = probe(path)
        if (meta["width"], meta["height"]) != (1080, 1920) or abs(meta["fps"] - 30) > 0.01 or abs(meta["duration_seconds"] - duration) > 0.12 or meta["video_codec"] != "h264" or meta["audio_codec"] != "aac" or meta["pixel_format"] != "yuv420p" or meta["sample_rate"] != 48000 or meta["audio_channels"] != 2:
            raise AppError("The exported file did not pass the video profile checks. Try processing it again.", "OUTPUT_VALIDATION_FAILED")
        self.command([ffmpeg(), "-hide_banner", "-loglevel", "error", "-xerror", "-i", path, "-f", "null", "-"], root, event)
        return meta

    def shutdown(self):
        with self.lock:
            for event in self.cancel_events.values():
                event.set()
        self.executor.shutdown(wait=True, cancel_futures=True)

