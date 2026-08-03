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
    """메타데이터에서 CLIP 텍스트 임베딩용 문장을 만든다."""
    parts = []

    spot_name = valid_text(item.get("spot_name"))
    place_name = valid_text(item.get("place_name"))
    region = valid_text(item.get("region"))
    drama_title = valid_text(item.get("drama_title"))
    season = valid_text(item.get("season"))
    time_of_day = valid_text(item.get("time_of_day"))
    description = valid_text(item.get("description"))

    mood = unique_strings(item.get("mood", []))
    scene_elements = unique_strings(item.get("scene_elements", []))
    activities = unique_strings(item.get("activity", []))

    if spot_name:
        parts.append(spot_name)

    if place_name:
        parts.append(place_name)

    if region:
        parts.append(region)

    if drama_title:
        parts.append(drama_title)

    if season or time_of_day:
        parts.append(" ".join(value for value in [season, time_of_day] if value))

    if description:
        parts.append(description)

    if mood:
        parts.append("Mood: " + ", ".join(mood[:5]))

    if scene_elements:
        parts.append("Scene: " + ", ".join(scene_elements[:8]))

    if activities:
        parts.append("Activities: " + ", ".join(activities[:5]))

    return ". ".join(parts)

def build_keyframe_id(item: dict) -> str:
    """segment_id와 keyframe 파일명으로 고유 keyframe_id를 만든다."""
    segment_id = item["segment_id"]
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
                "segment_id": segment_id,
                "video_id": first_item["video_id"],
                "place_name": first_item.get("place_name"),
                "spot_name": first_item.get("spot_name"),
                "region": first_item.get("region"),
                "drama_title": first_item.get("drama_title"),
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
                    "keyframe_id": keyframe_id,
                    "segment_id": segment_id,
                    "keyframe_path": item["keyframe_path"],
                    "place_name": item.get("place_name"),
                    "region": item.get("region"),
                    "drama_title": item.get("drama_title"),
                    "description": item.get("description"),
                    "metadata": item,
                    "embedding_model": MODEL_NAME,
                    "image_embedding": image_embedding,
                }
            )

    return {
        "segment_embeddings": segment_embeddings,
        "keyframe_embeddings": keyframe_embeddings,
    }

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

def main() -> None:
    embedding_root = Path(__file__).resolve().parent.parent
    metadata_path = embedding_root / "metadata" / "metadata.json"
    output_dir = embedding_root / "output" / "embeddings"
    output_path = output_dir / "segment_embeddings.json"

    output_dir.mkdir(parents=True, exist_ok=True)

    with metadata_path.open("r", encoding="utf-8-sig") as file:
        metadata = json.load(file)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"사용 장치: {device}")
    print("CLIP 모델 로딩 중...")

    model = CLIPModel.from_pretrained(MODEL_NAME).to(device)
    processor = CLIPProcessor.from_pretrained(MODEL_NAME)
    model.eval()

    print("CLIP 모델 로딩 완료")
    print(f"처리할 데이터: {len(metadata)}건")
    print("-" * 60)

    results = []

    for index, item in enumerate(metadata, start=1):
        segment_id = item["segment_id"]
        image_path = embedding_root / item["keyframe_path"]

        if not image_path.exists():
            raise FileNotFoundError(
                f"{segment_id} 이미지 파일이 없습니다: {image_path}"
            )

        search_text = build_search_text(item)

        if not search_text:
            raise ValueError(f"{segment_id} 검색용 텍스트가 비어 있습니다.")

        with Image.open(image_path) as source_image:
            image = source_image.convert("RGB")

            text_inputs = processor(
                text=[search_text],
                return_tensors="pt",
                padding=True,
                truncation=True,
            )

            image_inputs = processor(
                images=image,
                return_tensors="pt",
            )

        text_inputs = {
            key: value.to(device)
            for key, value in text_inputs.items()
        }

        image_inputs = {
            key: value.to(device)
            for key, value in image_inputs.items()
        }

        with torch.no_grad():
            outputs = model(
                input_ids=text_inputs["input_ids"],
                attention_mask=text_inputs.get("attention_mask"),
                pixel_values=image_inputs["pixel_values"],
                return_dict=True,
             )

            text_features = outputs.text_embeds
            image_features = outputs.image_embeds

        text_features = normalize(text_features)
        image_features = normalize(image_features)

        text_embedding = text_features[0].cpu().tolist()
        image_embedding = image_features[0].cpu().tolist()

        if len(text_embedding) != 512:
            raise ValueError(
                f"{segment_id} 텍스트 임베딩 차원 오류: "
                f"{len(text_embedding)}"
            )

        if len(image_embedding) != 512:
            raise ValueError(
                f"{segment_id} 이미지 임베딩 차원 오류: "
                f"{len(image_embedding)}"
            )

        results.append(
            {
                "segment_id": segment_id,
                "video_id": item["video_id"],
                "place_name": item.get("place_name"),
                "spot_name": item.get("spot_name"),
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time"),
                "keyframe_path": item["keyframe_path"],
                "description": item.get("description"),
                "search_text": search_text,
                "embedding_model": MODEL_NAME,
                "text_embedding": text_embedding,
                "image_embedding": image_embedding,
            }
        )

        print(f"[{index}/{len(metadata)}] 완료: {segment_id}")

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    print("-" * 60)
    print(f"임베딩 생성 완료: {len(results)}건")
    print(f"저장 위치: {output_path}")


if __name__ == "__main__":
    main()
