-- =========================================================
-- K-Tour AI Embedding DB Schema
-- 담당: 텍스트·이미지 임베딩 및 DB 구축
-- DB: PostgreSQL + pgvector
-- =========================================================

-- 1. pgvector 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- =========================================================
-- 2. 관광지 테이블
-- 관광지, 촬영지, 장소 정보를 저장
-- =========================================================
CREATE TABLE IF NOT EXISTS spots (
    spot_id SERIAL PRIMARY KEY,

    spot_name TEXT NOT NULL,
    region TEXT,
    address TEXT,

    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,

    description TEXT,
    source_url TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 3. 영상 테이블
-- 원본 관광 영상 정보를 저장
-- =========================================================
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,

    title TEXT NOT NULL,
    description TEXT,

    video_path TEXT,
    source_url TEXT,
    language TEXT DEFAULT 'ko',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 4. 영상 구간 테이블
-- 검색의 핵심 단위
-- 한 영상 안에서 특정 장면/구간을 저장
-- =========================================================
CREATE TABLE IF NOT EXISTS video_segments (
    segment_id TEXT PRIMARY KEY,

    video_id TEXT NOT NULL REFERENCES videos(video_id)
        ON DELETE CASCADE,

    spot_id INTEGER REFERENCES spots(spot_id)
        ON DELETE SET NULL,

    start_time DOUBLE PRECISION NOT NULL,
    end_time DOUBLE PRECISION NOT NULL,

    caption TEXT,
    summary TEXT,

    tags TEXT[],
    mood_tags TEXT[],
    season_tags TEXT[],

    source_segment_id TEXT,

    place_id TEXT,
    place_name TEXT,
    region TEXT,
    city TEXT,
    drama_title TEXT,
    season TEXT,
    time_of_day TEXT,
    spot_name TEXT,

    activity_tags TEXT[],
    scene_elements TEXT[],
    k_culture_elements TEXT[],

    keyframe_path TEXT,

    metadata JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- 기존 DB 호환용 컬럼 마이그레이션
ALTER TABLE video_segments
ADD COLUMN IF NOT EXISTS place_id TEXT;

ALTER TABLE video_segments
ADD COLUMN IF NOT EXISTS drama_title TEXT;

-- =========================================================
-- 기존 DB 호환용 SCENE 검색 컬럼 마이그레이션
-- =========================================================

ALTER TABLE video_segments
ADD COLUMN IF NOT EXISTS source_segment_id TEXT;

ALTER TABLE video_segments
ADD COLUMN IF NOT EXISTS place_id TEXT;

ALTER TABLE video_segments
ADD COLUMN IF NOT EXISTS place_name TEXT;

ALTER TABLE video_segments
ADD COLUMN IF NOT EXISTS region TEXT;

ALTER TABLE video_segments
ADD COLUMN IF NOT EXISTS city TEXT;

ALTER TABLE video_segments
ADD COLUMN IF NOT EXISTS drama_title TEXT;

ALTER TABLE video_segments
ADD COLUMN IF NOT EXISTS season TEXT;

ALTER TABLE video_segments
ADD COLUMN IF NOT EXISTS time_of_day TEXT;

ALTER TABLE video_segments
ADD COLUMN IF NOT EXISTS activity_tags TEXT[];

ALTER TABLE video_segments
ADD COLUMN IF NOT EXISTS scene_elements TEXT[];

ALTER TABLE video_segments
ADD COLUMN IF NOT EXISTS k_culture_elements TEXT[];
-- =========================================================
-- 5. 임베딩 테이블
-- 텍스트 임베딩과 이미지 임베딩 저장
--
-- CLIP ViT-B/32 text embedding: 512차원
-- CLIP ViT-B/32 image embedding: 512차원
-- 우선 768차원으로 설정하고, 실제 모델 확정 후 수정 가능
-- =========================================================
CREATE TABLE IF NOT EXISTS segment_embeddings (
    segment_id TEXT PRIMARY KEY REFERENCES video_segments(segment_id)
        ON DELETE CASCADE,

    text_embedding vector(512),
    image_embedding vector(512),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 6. Segment Keyframes
-- 하나의 segment에 여러 keyframe을 저장
-- =========================================================
CREATE TABLE IF NOT EXISTS segment_keyframes (
    keyframe_id TEXT PRIMARY KEY,

    segment_id TEXT NOT NULL REFERENCES video_segments(segment_id)
        ON DELETE CASCADE,

    keyframe_path TEXT NOT NULL,

    description TEXT,
    time_of_day TEXT,
    mood TEXT[],
    activity TEXT[],
    scene_elements TEXT[],
    k_culture_elements TEXT[],

    metadata JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 기존 DB 호환용 keyframe 구조화 metadata 컬럼 마이그레이션
ALTER TABLE segment_keyframes
ADD COLUMN IF NOT EXISTS description TEXT;

ALTER TABLE segment_keyframes
ADD COLUMN IF NOT EXISTS time_of_day TEXT;

ALTER TABLE segment_keyframes
ADD COLUMN IF NOT EXISTS mood TEXT[];

ALTER TABLE segment_keyframes
ADD COLUMN IF NOT EXISTS activity TEXT[];

ALTER TABLE segment_keyframes
ADD COLUMN IF NOT EXISTS scene_elements TEXT[];

ALTER TABLE segment_keyframes
ADD COLUMN IF NOT EXISTS k_culture_elements TEXT[];

CREATE INDEX IF NOT EXISTS idx_segment_keyframes_segment_id
ON segment_keyframes(segment_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_segment_keyframes_path
ON segment_keyframes(keyframe_path);

-- =========================================================
-- 7. Keyframe Embeddings
-- keyframe별 image embedding 저장
-- =========================================================
CREATE TABLE IF NOT EXISTS keyframe_embeddings (
    keyframe_id TEXT PRIMARY KEY REFERENCES segment_keyframes(keyframe_id)
        ON DELETE CASCADE,

    image_embedding vector(512),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 8. 일반 검색용 인덱스
-- 지역, 태그, 감성, 계절 필터 검색을 빠르게 하기 위함
-- =========================================================
CREATE INDEX IF NOT EXISTS idx_video_segments_source_segment_id
ON video_segments(source_segment_id);

CREATE INDEX IF NOT EXISTS idx_video_segments_place_id
ON video_segments(place_id);

CREATE INDEX IF NOT EXISTS idx_video_segments_drama_title
ON video_segments(drama_title);

CREATE INDEX IF NOT EXISTS idx_video_segments_city
ON video_segments(city);

CREATE INDEX IF NOT EXISTS idx_video_segments_season
ON video_segments(season);

CREATE INDEX IF NOT EXISTS idx_video_segments_time_of_day
ON video_segments(time_of_day);

CREATE INDEX IF NOT EXISTS idx_video_segments_video_id
ON video_segments(video_id);

CREATE INDEX IF NOT EXISTS idx_video_segments_region
ON video_segments(region);

CREATE INDEX IF NOT EXISTS idx_video_segments_tags
ON video_segments USING GIN(tags);

CREATE INDEX IF NOT EXISTS idx_video_segments_mood_tags
ON video_segments USING GIN(mood_tags);

CREATE INDEX IF NOT EXISTS idx_video_segments_season_tags
ON video_segments USING GIN(season_tags);

-- =========================================================
-- 9. 벡터 검색용 인덱스
-- cosine distance 기반 유사도 검색
-- =========================================================
CREATE INDEX IF NOT EXISTS idx_segment_text_embedding
ON segment_embeddings
USING hnsw (text_embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_segment_image_embedding
ON segment_embeddings
USING hnsw (image_embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_keyframe_image_embedding
ON keyframe_embeddings
USING hnsw (image_embedding vector_cosine_ops);