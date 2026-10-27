"""Isolated speech process: cancellation can stop inference or a model download."""
import argparse
import json
import os
import textwrap
import wave
from pathlib import Path


def make_cues(segments, duration):
    cues = []
    previous = 0.0
    for segment in segments:
        text = " ".join(segment.text.split())
        if not text:
            continue
        start = max(previous, float(segment.start), 0)
        end = min(float(segment.end), duration)
        if end <= start + 0.05:
            continue
        lines = textwrap.wrap(text, width=32, break_long_words=False, break_on_hyphens=False)
        chunks = ["\n".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
        total = sum(len(t) for t in chunks)
        cursor = start
        for index, chunk in enumerate(chunks):
            stop = end if index == len(chunks) - 1 else cursor + (end - start) * len(chunk) / total
            cues.append({"id": f"cue_{len(cues) + 1}", "start_seconds": round(cursor, 3),
                         "end_seconds": round(stop, 3), "text": chunk})
            cursor = stop
        previous = end
    return cues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="base", choices=["tiny", "base", "small"])
    parser.add_argument("--cache", required=True)
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--duration", type=float, default=0)
    parser.add_argument("--warmup", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    if args.input and not args.warmup:
        import numpy as np
        with wave.open(args.input, "rb") as wav:
            samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
        if len(samples) == 0 or int(np.max(np.abs(samples.astype(np.int32)))) < 8:
            Path(args.output).write_text(json.dumps({"cues": [], "speech_status": "no_speech"}), encoding="utf-8")
            return
    from faster_whisper import WhisperModel
    snapshots = Path(args.cache).glob(f"models--Systran--faster-whisper-{args.model}/snapshots/*")
    cached = [p for p in snapshots if (p / "model.bin").is_file()]
    model_location = str(cached[-1]) if cached else args.model
    model = WhisperModel(model_location, device="cpu", compute_type="int8", cpu_threads=4,
                         download_root=args.cache)
    (Path(args.cache) / f".ready-{args.model}").touch()
    if args.warmup:
        return
    segments, _ = model.transcribe(args.input, language="id", beam_size=3, vad_filter=True,
                                  condition_on_previous_text=False)
    cues = make_cues(segments, args.duration)
    Path(args.output).write_text(json.dumps({"cues": cues, "speech_status": "speech" if cues else "no_speech"}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()

