from pydantic import BaseModel, Field, model_validator


class SearchRequest(BaseModel):
    # Free text is optional: a pure filter/theme-button request (no natural
    # language) sends q="" -- README_BACKEND_APPLY.md's own example request
    # is exactly {"query": "", "theme": ["flower"]}. The model validator
    # below still rejects q="" when no filter is set either, since that
    # would be a meaningless, totally unconstrained request.
    q: str = ""
    lang: str = "ko"
    theme: list[str] | None = None
    place_id: list[str] | None = None
    drama_title: list[str] | None = None
    region: list[str] | None = None
    city: list[str] | None = None
    season: list[str] | None = None
    time_of_day: list[str] | None = None
    top_k: int = Field(default=5, ge=1)
    candidate_k: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _require_query_or_a_filter(self) -> "SearchRequest":
        has_query = bool(self.q.strip())
        has_filter = any(
            [
                self.theme,
                self.place_id,
                self.drama_title,
                self.region,
                self.city,
                self.season,
                self.time_of_day,
            ]
        )
        if not has_query and not has_filter:
            raise ValueError("q(자연어 검색어) 또는 필터(theme/region/season 등) 중 하나는 있어야 합니다.")
        return self


class SearchResultItem(BaseModel):
    rank: int
    source_segment_id: str
    segment_id: str
    keyframe_id: str
    keyframe_path: str
    video_id: str
    place_id: str
    place_name: str
    region: str
    city: str
    latitude: float | None = None
    longitude: float | None = None
    drama_title: str
    start_time: float
    end_time: float
    season: str
    time_of_day: str
    description: str
    mood: list[str]
    activity: list[str]
    scene_elements: list[str]
    k_culture_elements: list[str]
    themes: list[str] = []
    text_score: float | None
    image_score: float | None
    text_rank: int | None
    image_rank: int | None
    final_score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    fallback_used: bool = False
    fallback_reason: str | None = None
