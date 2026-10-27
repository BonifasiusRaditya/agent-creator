import pytest

from trendforge.models import Segment, allocate_segments, validate_cues
from trendforge.media import srt_time, write_srt
from trendforge.integrations import duration_seconds, validate_base_url


def test_allocation_respects_short_clips_and_preserves_frames():
    assets = [{"id": "a", "duration_seconds": 3.1}, {"id": "b", "duration_seconds": 40}, {"id": "c", "duration_seconds": 20}]
    segments = allocate_segments(assets, 45)
    assert sum(round(s["out_seconds"] * 30) for s in segments) == 45 * 30
    assert segments[0]["out_seconds"] <= 3.1
    assert {s["asset_id"] for s in segments} == {"a", "b", "c"}


@pytest.mark.parametrize("lengths,target", [([5, 5, 5], 30), ([30, 30], 30), ([10]*6, 30)])
def test_allocation_rejects_invalid_footage(lengths, target):
    with pytest.raises(ValueError):
        allocate_segments([{"id": str(i), "duration_seconds": n} for i, n in enumerate(lengths)], target)


def test_cue_times_and_no_speech_are_not_interchangeable():
    valid = [{"id": "c1", "start_seconds": 0, "end_seconds": 2, "text": "One line"}]
    validate_cues(valid, 30)
    validate_cues([], 30, no_speech=True)
    for cues, silent in (([], False), (valid, True), ([*valid, {"id": "c2", "start_seconds": 1, "end_seconds": 3, "text": "Overlap"}], False)):
        with pytest.raises(ValueError):
            validate_cues(cues, 30, silent)


def test_srt_preserves_reviewed_words(tmp_path):
    path = tmp_path / "captions.srt"
    write_srt([{"start_seconds": 1.25, "end_seconds": 3.5, "text": "Nama dan angka: 27."}], path)
    text = path.read_text(encoding="utf-8")
    assert "00:00:01,250 --> 00:00:03,500" in text
    assert "Nama dan angka: 27." in text
    assert srt_time(3661.1) == "01:01:01,100"


def test_provider_url_and_source_duration():
    assert validate_base_url("http://localhost:11434/v1") == "http://localhost:11434/v1"
    assert duration_seconds("PT1H2M3S") == 3723
    for url in ("http://remote.example/v1", "https://user:secret@example.com/v1", "file:///tmp"):
        with pytest.raises(Exception):
            validate_base_url(url)

