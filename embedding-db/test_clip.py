from transformers import CLIPModel, CLIPProcessor

MODEL_NAME = "openai/clip-vit-base-patch32"


def main() -> None:
    print("CLIP 모델 로딩을 시작합니다.")
    print(f"모델명: {MODEL_NAME}")

    model = CLIPModel.from_pretrained(MODEL_NAME)
    processor = CLIPProcessor.from_pretrained(MODEL_NAME)

    print("CLIP 모델과 프로세서 로딩 완료")
    print(f"임베딩 차원: {model.config.projection_dim}")
    print(f"프로세서 클래스: {processor.__class__.__name__}")


if __name__ == "__main__":
    main()