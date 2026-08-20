from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    lang: str = "ko"
    place_id: list[str] | None = None
    drama_title: list[str] | None = None
    region: list[str] | None = None
    city: list[str] | None = None
    season: list[str] | None = None
    time_of_day: list[str] | None = None
    top_k: int = Field(default=5, ge=1)
    candidate_k: int | None = Field(default=None, ge=1)


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
    latitude: float
    longitude: float
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
    text_score: float | None
    image_score: float | None
    text_rank: int | None
    image_rank: int | None
    final_score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    fallback_used: bool = False
    fallback_reason: str | None = None
