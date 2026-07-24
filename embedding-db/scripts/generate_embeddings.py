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


def normalize(features: torch.Tensor) -> torch.Tensor:
    """코사인 유사도 검색을 위해 벡터를 L2 정규화한다."""
    denominator = features.norm(dim=-1, keepdim=True).clamp(min=1e-12)
    return features / denominator


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
