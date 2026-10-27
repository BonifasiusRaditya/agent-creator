import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class ProjectInput(Model):
    niche: str = Field(min_length=2, max_length=100)
    audience: str = Field(min_length=2, max_length=200)
    goal: str = Field(min_length=5, max_length=500)
    platform: Literal["shorts", "reels", "both"] = "both"
    target_duration_seconds: Literal[30, 45, 60] = 30
    language: Literal["id", "en"] = "id"


class ResearchInput(Model):
    query: str = Field(min_length=2, max_length=150)
    period_days: Literal[1, 7, 30] = 7
    source_mode: Literal["search", "chart", "manual"] = "search"
    region: Literal["ID"] = "ID"
    language: Literal["id", "en"] = "id"


class Idea(Model):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=3, max_length=180)
    angle: str = Field(min_length=5, max_length=600)
    hook: str = Field(min_length=3, max_length=400)


class Ideas(Model):
    ideas: list[Idea] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def unique(self):
        if len({i.id for i in self.ideas}) != 3:
            raise ValueError("Idea IDs must be unique")
        return self


class Shot(Model):
    visual: str = Field(min_length=2, max_length=600)
    narration: str = Field(min_length=1, max_length=1000)
    duration_seconds: float = Field(gt=0, le=60)


class BriefContent(Model):
    title: str = Field(min_length=3, max_length=180)
    hook: str = Field(min_length=3, max_length=600)
    angle: str = Field(min_length=5, max_length=1000)
    script: str = Field(min_length=10, max_length=8000)
    cta: str = Field(min_length=2, max_length=600)
    shots: list[Shot] = Field(min_length=3, max_length=5)


class BriefInput(BriefContent):
    source_video_ids: list[str] = Field(default_factory=list, max_length=20)
    selected_idea_id: str | None = None
    expected_project_revision: int = Field(ge=1)


class AgentRequestInput(Model):
    task: Literal["ideas", "brief"]
    source_video_ids: list[str] = Field(default_factory=list, max_length=5)
    idea_id: str | None = Field(default=None, max_length=80)
    expected_project_revision: int = Field(ge=1)


class Segment(Model):
    asset_id: str
    order: int = Field(ge=1, le=5)
    in_seconds: float = Field(ge=0)
    out_seconds: float = Field(gt=0)

    @model_validator(mode="after")
    def range(self):
        if self.out_seconds <= self.in_seconds:
            raise ValueError("The end must be after the start")
        return self


class PlanInput(Model):
    brief_revision_id: str
    target_duration_seconds: Literal[30, 45, 60]
    segments: list[Segment] = Field(min_length=3, max_length=5)
    framing: Literal["fit_pad"] = "fit_pad"
    preset: Literal["simple_fade"] = "simple_fade"
    audio_mode: Literal["original"] = "original"
    expected_project_revision: int = Field(ge=1)


class Cue(Model):
    id: str = Field(min_length=1, max_length=80)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=500)


class SubtitleInput(Model):
    draft_id: str
    cues: list[Cue] = Field(max_length=600)
    speech_status: Literal["speech", "no_speech"] = "speech"
    expected_project_revision: int = Field(ge=1)


class Approval(Model):
    expected_project_revision: int = Field(ge=1)
    confirmation: Literal[True]
    no_speech_decision: bool = False


def allocate_segments(assets, target):
    if not 3 <= len(assets) <= 5:
        raise ValueError("Upload 3–5 valid clips before creating an edit plan.")
    available = [math.floor(a["duration_seconds"] * 30 + 0.001) for a in assets]
    required = target * 30
    if sum(available) < required:
        raise ValueError("Your clips are shorter than the target. Add longer clips or choose a shorter duration.")
    lengths = [0] * len(assets)
    while required:
        eligible = [i for i in range(len(assets)) if lengths[i] < available[i]]
        share = max(1, required // len(eligible))
        for i in eligible:
            take = min(share, available[i] - lengths[i], required)
            lengths[i] += take
            required -= take
            if not required:
                break
    return [{"asset_id": a["id"], "order": i + 1, "in_seconds": 0,
             "out_seconds": lengths[i] / 30} for i, a in enumerate(assets)]


def validate_cues(cues, duration, no_speech=False):
    if not cues and not no_speech:
        raise ValueError("Add subtitles, or explicitly confirm that there is no speech.")
    if cues and no_speech:
        raise ValueError("A no-speech track cannot contain subtitles.")
    previous = 0
    ids = set()
    for cue in cues:
        if cue["id"] in ids:
            raise ValueError("Subtitle IDs must be unique.")
        ids.add(cue["id"])
        if not (previous <= cue["start_seconds"] < cue["end_seconds"] <= duration + 0.01):
            raise ValueError("Subtitle times must be ordered, non-overlapping, and inside the video.")
        previous = cue["end_seconds"]

