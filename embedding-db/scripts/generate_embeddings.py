import json
from pathlib import Path

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor


MODEL_NAME = "openai/clip-vit-base-patch32"


def unique_strings(values: list) -> list[str]:
    """문자열 목록의 빈 값, unknown, 중복을 제거한다."""
    result = []
    seen = set()

    for value in values:
        if not isinstance(value, str):
            continue

        cleaned = value.strip()

        if not cleaned or cleaned.lower() == "unknown":
            continue

        key = cleaned.lower()

        if key not in seen:
            seen.add(key)
            result.append(cleaned)

    return result


def valid_text(value) -> str:
    """사용 가능한 문자열만 반환한다."""
    if not isinstance(value, str):
        return ""

    cleaned = value.strip()

    if not cleaned or cleaned.lower() == "unknown":
        return ""

    return cleaned


def build_search_text(item: dict) -> str:
    """CLIP 77-token 제한을 고려해 SCENE 구별 정보를 우선 배치한다."""
    description = valid_text(
        item.get("description")
    )

    scene_elements = unique_strings(
        item.get("scene_elements") or []
    )

    activities = unique_strings(
        item.get("activity") or []
    )

    mood = unique_strings(
        item.get("mood") or []
    )

    k_culture_elements = unique_strings(
        item.get("k_culture_elements") or []
    )

    season = valid_text(
        item.get("season")
    )

    time_of_day = valid_text(
        item.get("time_of_day")
    )

    place_name = (
        valid_text(item.get("place_name"))
        or valid_text(item.get("spot_name"))
    )

    drama_title = valid_text(
        item.get("drama_title")
    )

    region = valid_text(
        item.get("region")
    )

    city = valid_text(
        item.get("city")
    )

    parts = []

    # 1. SCENE별로 달라지는 정보를 가장 앞에 배치
    if description:
        parts.append(description)

    if scene_elements:
        parts.append(
            "Scene: "
            + ", ".join(scene_elements[:8])
        )

    if activities:
        parts.append(
            "Activities: "
            + ", ".join(activities[:5])
        )

    if mood:
        parts.append(
            "Mood: "
            + ", ".join(mood[:5])
        )

    if k_culture_elements:
        parts.append(
            "K-culture: "
            + ", ".join(k_culture_elements[:5])
        )

    # 2. 계절/시간 정보
    season_time = " ".join(
        value
        for value in [season, time_of_day]
        if value
    )

    if season_time:
        parts.append(season_time)

    # 3. 장소/작품 정보
    if place_name:
        parts.append(place_name)

    if drama_title:
        parts.append(drama_title)

    # 4. 지역 정보는 마지막에 배치
    if region:
        parts.append(region)

    # region과 city가 같으면 중복 삽입하지 않음
    if city and city != region:
        parts.append(city)

    return ". ".join(parts)

def build_keyframe_id(item: dict) -> str:
    """팀 검색 규격에 따라 keyframe_id는 segment_id와 동일하게 사용한다."""
    return item["segment_id"]
    keyframe_stem = Path(item["keyframe_path"]).stem

    return f"{segment_id}__{keyframe_stem}"


def resolve_keyframe_path(
    repo_root: Path,
    keyframe_path: str,
) -> Path:
    """실데이터 keyframe의 실제 파일 경로를 반환한다."""
    return (
        repo_root
        / "K-contents_preprocessed"
        / "preprocessed_output"
        / keyframe_path
    )


def group_metadata_by_segment(
    metadata: list[dict],
) -> dict[str, list[dict]]:
    """metadata를 segment_id별로 묶되 모든 keyframe을 보존한다."""
    grouped = {}

    for item in metadata:
        segment_id = item["segment_id"]

        grouped.setdefault(
            segment_id,
            [],
        ).append(item)

    return grouped

def build_segment_search_text(
    items: list[dict],
) -> str:
    """같은 segment의 모든 keyframe metadata를 하나의 검색 텍스트로 합친다."""
    texts = []

    for item in items:
        text = build_search_text(item)

        if text:
            texts.append(text)

    return ". ".join(unique_strings(texts))

def build_embedding_records(
    metadata: list[dict],
    repo_root: Path,
    encode_text_fn,
    encode_image_fn,
) -> dict[str, list[dict]]:
    """segment 텍스트 임베딩과 keyframe 이미지 임베딩을 분리해 생성한다."""
    grouped = group_metadata_by_segment(metadata)

    segment_embeddings = []
    keyframe_embeddings = []

    for segment_id, items in grouped.items():
        first_item = items[0]

        search_text = build_segment_search_text(items)

        if not search_text:
            raise ValueError(
                f"{segment_id} 검색용 텍스트가 비어 있습니다."
            )

        text_embedding = encode_text_fn(search_text)

        if len(text_embedding) != 512:
            raise ValueError(
                f"{segment_id} 텍스트 임베딩 차원 오류: "
                f"{len(text_embedding)}"
            )

        segment_embeddings.append(
            {
                "source_segment_id": first_item.get("source_segment_id"),
                "segment_id": segment_id,
                "video_id": first_item["video_id"],
                "place_id": first_item.get("place_id"),
                "place_name": first_item.get("place_name"),
                "spot_name": first_item.get("spot_name"),
                "region": first_item.get("region"),
                "city": first_item.get("city"),
                "drama_title": first_item.get("drama_title"),
                "season": first_item.get("season"),
                "time_of_day": first_item.get("time_of_day"),
                "description": first_item.get("description"),
                "mood": first_item.get("mood", []),
                "activity": first_item.get("activity", []),
                "scene_elements": first_item.get("scene_elements", []),
                "k_culture_elements": first_item.get("k_culture_elements"),
                "start_time": first_item.get("start_time"),
                "end_time": first_item.get("end_time"),
                "search_text": search_text,
                "embedding_model": MODEL_NAME,
                "text_embedding": text_embedding,
            }
        )

        for item in items:
            keyframe_id = build_keyframe_id(item)

            image_path = resolve_keyframe_path(
                repo_root,
                item["keyframe_path"],
            )

            image_embedding = encode_image_fn(image_path)

            if len(image_embedding) != 512:
                raise ValueError(
                    f"{keyframe_id} 이미지 임베딩 차원 오류: "
                    f"{len(image_embedding)}"
                )

            keyframe_embeddings.append(
                {
                    "source_segment_id": item.get("source_segment_id"),
                    "segment_id": segment_id,
                    "keyframe_id": keyframe_id,
                    "keyframe_path": item["keyframe_path"],
                    "video_id": item.get("video_id"),
                    "place_id": item.get("place_id"),
                    "place_name": item.get("place_name"),
                    "region": item.get("region"),
                    "city": item.get("city"),
                    "drama_title": item.get("drama_title"),
                    "season": item.get("season"),
                    "time_of_day": item.get("time_of_day"),
                    "description": item.get("description"),
                    "mood": item.get("mood", []),
                    "activity": item.get("activity", []),
                    "scene_elements": item.get("scene_elements", []),
                    "k_culture_elements": item.get("k_culture_elements"),
                    "start_time": item.get("start_time"),
                    "end_time": item.get("end_time"),
                    "metadata": item,
                    "embedding_model": MODEL_NAME,
                    "image_embedding": image_embedding,
                }
            )

    return {
        "segment_embeddings": segment_embeddings,
        "keyframe_embeddings": keyframe_embeddings,
    }

def extract_clip_features(
    features,
    projection,
) -> torch.Tensor:
    """transformers 버전에 따라 달라지는 CLIP 반환형을 Tensor로 통일한다."""
    if not hasattr(features, "pooler_output"):
        return features

    pooled = features.pooler_output

    if pooled.shape[-1] == 512:
        return pooled

    if projection is None:
        raise ValueError(
            "Projection layer is required for non-512-dimensional features."
        )

    return projection(pooled)

def normalize(features: torch.Tensor) -> torch.Tensor:
    """코사인 유사도 검색을 위해 벡터를 L2 정규화한다."""
    denominator = features.norm(dim=-1, keepdim=True).clamp(min=1e-12)
    return features / denominator

def encode_text_embedding(
    text: str,
    model,
    processor,
    device,
) -> list[float]:
    """텍스트를 CLIP 512차원 정규화 벡터로 변환한다."""
    inputs = processor(
        text=[text],
        return_tensors="pt",
        padding=True,
        truncation=True,
    )

    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }

    with torch.no_grad():
        features = model.get_text_features(
            input_ids=inputs["input_ids"],
            attention_mask=inputs.get("attention_mask"),
        )

        features = extract_clip_features(
            features,
            getattr(model, "text_projection", None),
        )

    features = normalize(features)

    embedding = features[0].cpu().tolist()

    if len(embedding) != 512:
        raise ValueError(
            "텍스트 임베딩 차원 오류: "
            f"{len(embedding)}"
        )

    return embedding

def encode_image_embedding(
    image_path: Path,
    model,
    processor,
    device,
) -> list[float]:
    """이미지를 CLIP 512차원 정규화 벡터로 변환한다."""
    if not image_path.is_file():
        raise FileNotFoundError(
            f"이미지 파일이 없습니다: {image_path}"
        )

    with Image.open(image_path) as source_image:
        image = source_image.convert("RGB")

        inputs = processor(
            images=image,
            return_tensors="pt",
        )

    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }

    with torch.no_grad():
        features = model.get_image_features(
            pixel_values=inputs["pixel_values"],
        )

        features = extract_clip_features(
            features,
            getattr(model, "visual_projection", None),
        )

    features = normalize(features)

    embedding = features[0].cpu().tolist()

    if len(embedding) != 512:
        raise ValueError(
            "이미지 임베딩 차원 오류: "
            f"{len(embedding)}"
        )

    return embedding

def write_embedding_outputs(
    records: dict[str, list[dict]],
    output_dir: Path,
) -> dict[str, Path]:
    """segment/keyframe 임베딩을 각각 별도 JSON 파일로 저장한다."""
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    segment_path = (
        output_dir
        / "segment_embeddings.json"
    )

    keyframe_path = (
        output_dir
        / "keyframe_embeddings.json"
    )

    with segment_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            records["segment_embeddings"],
            file,
            ensure_ascii=False,
            indent=2,
        )

    with keyframe_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            records["keyframe_embeddings"],
            file,
            ensure_ascii=False,
            indent=2,
        )

    return {
        "segment_embeddings": segment_path,
        "keyframe_embeddings": keyframe_path,
    }

def run_embedding_generation(
    metadata: list[dict],
    repo_root: Path,
    output_dir: Path,
    encode_text_fn,
    encode_image_fn,
) -> dict:
    """임베딩 레코드를 생성하고 JSON 파일로 저장한다."""
    records = build_embedding_records(
        metadata=metadata,
        repo_root=repo_root,
        encode_text_fn=encode_text_fn,
        encode_image_fn=encode_image_fn,
    )

    paths = write_embedding_outputs(
        records,
        output_dir,
    )

    return {
        "records": records,
        "paths": paths,
    }

def main() -> None:
    embedding_root = Path(__file__).resolve().parent.parent
    repo_root = embedding_root.parent

    metadata_path = (
        embedding_root
        / "metadata"
        / "metadata.json"
    )

    output_dir = (
        embedding_root
        / "output"
        / "embeddings"
    )

    with metadata_path.open(
        "r",
        encoding="utf-8-sig",
    ) as file:
        metadata = json.load(file)

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(f"사용 장치: {device}")
    print("CLIP 모델 로딩 중...")

    model = CLIPModel.from_pretrained(
        MODEL_NAME
    ).to(device)

    processor = CLIPProcessor.from_pretrained(
        MODEL_NAME
    )

    model.eval()

    print("CLIP 모델 로딩 완료")
    print(
        f"metadata: {len(metadata)}건"
    )

    grouped = group_metadata_by_segment(
        metadata
    )

    print(
        f"segment: {len(grouped)}건"
    )

    print(
        f"keyframe: {len(metadata)}건"
    )

    print("-" * 60)

    def encode_text_fn(text: str) -> list[float]:
        return encode_text_embedding(
            text=text,
            model=model,
            processor=processor,
            device=device,
        )

    def encode_image_fn(
        image_path: Path,
    ) -> list[float]:
        return encode_image_embedding(
            image_path=image_path,
            model=model,
            processor=processor,
            device=device,
        )

    result = run_embedding_generation(
        metadata=metadata,
        repo_root=repo_root,
        output_dir=output_dir,
        encode_text_fn=encode_text_fn,
        encode_image_fn=encode_image_fn,
    )

    segment_records = (
        result["records"]["segment_embeddings"]
    )

    keyframe_records = (
        result["records"]["keyframe_embeddings"]
    )

    print("-" * 60)

    print(
        "segment text embedding 생성 완료: "
        f"{len(segment_records)}건"
    )

    print(
        "keyframe image embedding 생성 완료: "
        f"{len(keyframe_records)}건"
    )

    print(
        "segment 저장 위치: "
        f"{result['paths']['segment_embeddings']}"
    )

    print(
        "keyframe 저장 위치: "
        f"{result['paths']['keyframe_embeddings']}"
    )


if __name__ == "__main__":
    main()