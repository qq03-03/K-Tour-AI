import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "search_embeddings.py"
)


def load_search_module():
    spec = importlib.util.spec_from_file_location(
        "search_embeddings",
        SCRIPT_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError("search_embeddings.py 모듈을 불러올 수 없습니다.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_top_k_accepts_positive_integer():
    module = load_search_module()

    assert module.validate_top_k(1) == 1
    assert module.validate_top_k(5) == 5


def test_validate_top_k_rejects_zero():
    module = load_search_module()

    with pytest.raises(ValueError, match="top-k"):
        module.validate_top_k(0)


def test_validate_query_vector_accepts_512_dimension():
    module = load_search_module()
    vector = np.ones(512, dtype=np.float32)

    result = module.validate_query_vector(vector)

    assert result.shape == (512,)
    assert result.dtype == np.float32


def test_validate_query_vector_rejects_wrong_dimension():
    module = load_search_module()
    vector = np.ones(384, dtype=np.float32)

    with pytest.raises(ValueError, match="512"):
        module.validate_query_vector(vector)


def test_validate_query_vector_rejects_nan():
    module = load_search_module()
    vector = np.ones(512, dtype=np.float32)
    vector[0] = np.nan

    with pytest.raises(ValueError, match="NaN|무한대"):
        module.validate_query_vector(vector)


def test_cosine_distance_to_similarity():
    module = load_search_module()

    assert module.distance_to_similarity(0.0) == pytest.approx(1.0)
    assert module.distance_to_similarity(0.25) == pytest.approx(0.75)
    assert module.distance_to_similarity(1.0) == pytest.approx(0.0)

def test_parse_arguments_accepts_text_mode():
    module = load_search_module()

    args = module.parse_arguments(
        ["--text", "가을 숲길"]
    )

    assert args.text == "가을 숲길"
    assert args.image is None
    assert args.top_k == 5


def test_parse_arguments_accepts_image_mode_and_top_k():
    module = load_search_module()

    args = module.parse_arguments(
        ["--image", "sample.jpg", "--top-k", "3"]
    )

    assert args.text is None
    assert args.image == "sample.jpg"
    assert args.top_k == 3


def test_parse_arguments_rejects_text_and_image_together():
    module = load_search_module()

    with pytest.raises(SystemExit):
        module.parse_arguments(
            [
                "--text",
                "숲길",
                "--image",
                "sample.jpg",
            ]
        )


def test_parse_arguments_requires_search_input():
    module = load_search_module()

    with pytest.raises(SystemExit):
        module.parse_arguments([])

def test_build_connection_string_uses_environment_variables(monkeypatch):
    module = load_search_module()

    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "15432")
    monkeypatch.setenv("POSTGRES_USER", "ktour")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "ktour_ai")

    result = module.build_connection_string()

    assert "host=localhost" in result
    assert "port=15432" in result
    assert "user=ktour" in result
    assert "password=secret" in result
    assert "dbname=ktour_ai" in result


def test_build_connection_string_rejects_missing_variable(monkeypatch):
    module = load_search_module()

    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "15432")
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "ktour_ai")

    with pytest.raises(ValueError, match="POSTGRES_USER"):
        module.build_connection_string()

def test_normalize_vector_returns_unit_vector():
    module = load_search_module()
    vector = np.array([3.0, 4.0], dtype=np.float32)

    result = module.normalize_vector(vector)

    assert np.linalg.norm(result) == pytest.approx(1.0)
    assert result.dtype == np.float32


def test_normalize_vector_rejects_zero_vector():
    module = load_search_module()
    vector = np.zeros(512, dtype=np.float32)

    with pytest.raises(ValueError, match="0 벡터"):
        module.normalize_vector(vector)


def test_validate_image_path_accepts_existing_file(tmp_path):
    module = load_search_module()
    image_path = tmp_path / "sample.jpg"
    image_path.write_bytes(b"test")

    result = module.validate_image_path(str(image_path))

    assert result == image_path


def test_validate_image_path_rejects_missing_file(tmp_path):
    module = load_search_module()
    image_path = tmp_path / "missing.jpg"

    with pytest.raises(FileNotFoundError, match="이미지"):
        module.validate_image_path(str(image_path))

def test_encode_text_returns_512_dimension(monkeypatch):
    module = load_search_module()

    class FakeTensor:
        def __init__(self, values):
            self.values = np.asarray(values, dtype=np.float32)

        def to(self, device):
            return self

        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return self.values

    class FakeProcessor:
        def __call__(self, **kwargs):
            return {
                "input_ids": FakeTensor([[1, 2, 3]]),
                "attention_mask": FakeTensor([[1, 1, 1]]),
            }

    class FakeModel:
        def get_text_features(self, **kwargs):
            return FakeTensor(
                np.ones((1, 512), dtype=np.float32)
            )

    result = module.encode_text(
        "가을 숲길",
        FakeModel(),
        FakeProcessor(),
        "cpu",
    )

    assert result.shape == (512,)
    assert np.linalg.norm(result) == pytest.approx(1.0)


def test_encode_image_returns_512_dimension(tmp_path):
    module = load_search_module()

    from PIL import Image

    image_path = tmp_path / "sample.jpg"
    Image.new("RGB", (10, 10)).save(image_path)

    class FakeTensor:
        def __init__(self, values):
            self.values = np.asarray(values, dtype=np.float32)

        def to(self, device):
            return self

        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return self.values

    class FakeProcessor:
        def __call__(self, **kwargs):
            return {
                "pixel_values": FakeTensor(
                    np.ones((1, 3, 224, 224), dtype=np.float32)
                )
            }

    class FakeModel:
        def get_image_features(self, **kwargs):
            return FakeTensor(
                np.ones((1, 512), dtype=np.float32)
            )

    result = module.encode_image(
        image_path,
        FakeModel(),
        FakeProcessor(),
        "cpu",
    )

    assert result.shape == (512,)
    assert np.linalg.norm(result) == pytest.approx(1.0)

def test_search_database_builds_text_search_query(monkeypatch):
    module = load_search_module()

    captured = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            captured["query"] = str(query)
            captured["params"] = params

        def fetchall(self):
            return [
                (
                    "SEG_001",
                    "메타세쿼이아길",
                    "VID_001",
                    0.0,
                    5.0,
                    0.1,
                    "frame.jpg",
                    "조용한 숲길",
                )
            ]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(
        module.psycopg,
        "connect",
        lambda connection_string: FakeConnection(),
    )

    monkeypatch.setattr(
        module,
        "register_vector",
        lambda connection: None,
    )

    monkeypatch.setattr(
        module,
        "build_connection_string",
        lambda: "fake-connection",
    )

    result = module.search_database(
        np.ones(512, dtype=np.float32),
        "text",
        5,
    )

    assert "text_embedding" in captured["query"]
    assert len(result) == 1
    assert result[0]["segment_id"] == "SEG_001"
    assert result[0]["similarity"] == pytest.approx(0.9)


def test_search_database_builds_image_search_query(monkeypatch):
    module = load_search_module()

    captured = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            captured["query"] = str(query)

        def fetchall(self):
            return []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(
        module.psycopg,
        "connect",
        lambda connection_string: FakeConnection(),
    )

    monkeypatch.setattr(
        module,
        "register_vector",
        lambda connection: None,
    )

    monkeypatch.setattr(
        module,
        "build_connection_string",
        lambda: "fake-connection",
    )

    result = module.search_database(
        np.ones(512, dtype=np.float32),
        "image",
        3,
    )

    assert "image_embedding" in captured["query"]
    assert result == []


def test_search_database_rejects_invalid_mode():
    module = load_search_module()

    with pytest.raises(ValueError, match="검색 모드"):
        module.search_database(
            np.ones(512, dtype=np.float32),
            "audio",
            5,
        )

def test_print_results_displays_search_information(capsys):
    module = load_search_module()

    results = [
        {
            "segment_id": "SEG_NAMI_01_01",
            "spot_name": "메타세쿼이아길",
            "video_id": "VID_NAMI_01",
            "start_time": 0.0,
            "end_time": 5.0,
            "similarity": 0.87654,
            "keyframe_path": "frame_001.jpg",
            "summary": "가을 숲길을 걷는 장면",
        }
    ]

    module.print_results(results)

    output = capsys.readouterr().out

    assert "SEG_NAMI_01_01" in output
    assert "메타세쿼이아길" in output
    assert "VID_NAMI_01" in output
    assert "0.8765" in output
    assert "frame_001.jpg" in output
    assert "가을 숲길을 걷는 장면" in output


def test_print_results_handles_empty_results(capsys):
    module = load_search_module()

    module.print_results([])

    output = capsys.readouterr().out

    assert "검색 결과가 없습니다" in output

def test_load_clip_model_returns_model_processor_and_device(monkeypatch):
    module = load_search_module()

    class FakeModel:
        def to(self, device):
            self.device = device
            return self

        def eval(self):
            self.is_eval = True
            return self

    fake_model = FakeModel()
    fake_processor = object()

    monkeypatch.setattr(
        module,
        "CLIPModel",
        type(
            "FakeCLIPModel",
            (),
            {
                "from_pretrained": staticmethod(
                    lambda model_name: fake_model
                )
            },
        ),
    )

    monkeypatch.setattr(
        module,
        "CLIPProcessor",
        type(
            "FakeCLIPProcessor",
            (),
            {
                "from_pretrained": staticmethod(
                    lambda model_name: fake_processor
                )
            },
        ),
    )

    monkeypatch.setattr(
        module.torch.cuda,
        "is_available",
        lambda: False,
    )

    model, processor, device = module.load_clip_model()

    assert model is fake_model
    assert processor is fake_processor
    assert device == "cpu"
    assert model.device == "cpu"
    assert model.is_eval is True

def test_main_runs_text_search(monkeypatch):
    module = load_search_module()

    from types import SimpleNamespace

    fake_vector = np.ones(512, dtype=np.float32)
    fake_results = [{"segment_id": "SEG_TEXT"}]
    captured = {}

    monkeypatch.setattr(
        module,
        "parse_arguments",
        lambda argv=None: SimpleNamespace(
            text="가을 숲길",
            image=None,
            top_k=3,
        ),
    )
    monkeypatch.setattr(
        module,
        "load_clip_model",
        lambda: ("model", "processor", "cpu"),
    )
    monkeypatch.setattr(
        module,
        "encode_text",
        lambda text, model, processor, device: fake_vector,
    )

    def fake_search_database(vector, mode, top_k):
        captured["mode"] = mode
        captured["top_k"] = top_k
        return fake_results

    monkeypatch.setattr(
        module,
        "search_database",
        fake_search_database,
    )
    monkeypatch.setattr(
        module,
        "print_results",
        lambda results: captured.update(results=results),
    )

    module.main([])

    assert captured["mode"] == "text"
    assert captured["top_k"] == 3
    assert captured["results"] == fake_results


def test_main_runs_image_search(monkeypatch):
    module = load_search_module()

    from types import SimpleNamespace

    fake_vector = np.ones(512, dtype=np.float32)
    fake_results = [{"segment_id": "SEG_IMAGE"}]
    captured = {}

    monkeypatch.setattr(
        module,
        "parse_arguments",
        lambda argv=None: SimpleNamespace(
            text=None,
            image="sample.jpg",
            top_k=5,
        ),
    )
    monkeypatch.setattr(
        module,
        "load_clip_model",
        lambda: ("model", "processor", "cpu"),
    )
    monkeypatch.setattr(
        module,
        "validate_image_path",
        lambda image_path: Path(image_path),
    )
    monkeypatch.setattr(
        module,
        "encode_image",
        lambda image, model, processor, device: fake_vector,
    )

    def fake_search_database(vector, mode, top_k):
        captured["mode"] = mode
        captured["top_k"] = top_k
        return fake_results

    monkeypatch.setattr(
        module,
        "search_database",
        fake_search_database,
    )
    monkeypatch.setattr(
        module,
        "print_results",
        lambda results: captured.update(results=results),
    )

    module.main([])

    assert captured["mode"] == "image"
    assert captured["top_k"] == 5
    assert captured["results"] == fake_results

def test_extract_clip_features_uses_512_pooler_output_without_projection():
    module = load_search_module()

    class FakeTensor:
        shape = (1, 512)

    class FakeOutput:
        pooler_output = FakeTensor()

    projection_called = False

    def fake_projection(value):
        nonlocal projection_called
        projection_called = True
        return value

    result = module.extract_clip_features(
        FakeOutput(),
        fake_projection,
    )

    assert result is FakeOutput.pooler_output
    assert projection_called is False
