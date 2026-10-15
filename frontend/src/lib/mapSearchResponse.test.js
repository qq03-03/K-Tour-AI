import { describe, it, expect } from 'vitest'
import { mapSearchResponse } from './mapSearchResponse.js'

function makeResult(overrides = {}) {
  return {
    rank: 1,
    source_segment_id: 'V002_P004_S001',
    segment_id: 'V002_P004_S001_SCENE_001',
    keyframe_id: 'V002_P004_S001_SCENE_001',
    keyframe_path: 'keyframes/V002_Q6qUEvQfjRs/V002_P004_S001_SCENE_001.jpg',
    video_id: 'V002_Q6qUEvQfjRs',
    place_id: 'P004',
    place_name: '고창 학원농장',
    region: '전북특별자치도',
    city: '고창군',
    latitude: null,
    longitude: null,
    drama_title: '폭싹 속았수다',
    start_time: 0,
    end_time: 10,
    season: '봄',
    time_of_day: 'day',
    description: 'A field of yellow flowers under a clear sky.',
    mood: ['peaceful', 'vibrant', 'natural'],
    activity: [],
    scene_elements: ['field', 'yellow_flowers', 'path', 'sky'],
    k_culture_elements: [],
    text_score: 0.7,
    image_score: null,
    text_rank: 1,
    image_rank: null,
    final_score: 0.0166,
    ...overrides,
  }
}

describe('mapSearchResponse', () => {
  it('returns an empty array for an empty results list', () => {
    expect(mapSearchResponse([])).toEqual([])
  })

  it('copies segment_id into uid', () => {
    const [mapped] = mapSearchResponse([makeResult()])
    expect(mapped.uid).toBe('V002_P004_S001_SCENE_001')
  })

  it('scales similarity relative to the highest final_score in the batch, giving the top result 1', () => {
    const results = [makeResult({ segment_id: 'A', final_score: 0.02 }), makeResult({ segment_id: 'B', final_score: 0.01 })]
    const [a, b] = mapSearchResponse(results)
    expect(a.similarity).toBe(1)
    expect(b.similarity).toBe(0.5)
  })

  it('gives every result similarity 0 when every final_score is 0, without dividing by zero', () => {
    const results = [makeResult({ segment_id: 'A', final_score: 0 }), makeResult({ segment_id: 'B', final_score: 0 })]
    const mapped = mapSearchResponse(results)
    expect(mapped.every((item) => item.similarity === 0)).toBe(true)
  })

  it('passes through the fields ResultCard/localizeSegment/getMapMarkers read, unchanged', () => {
    const [mapped] = mapSearchResponse([makeResult()])
    expect(mapped.place_name).toBe('고창 학원농장')
    expect(mapped.drama_title).toBe('폭싹 속았수다')
    expect(mapped.keyframe_path).toBe('keyframes/V002_Q6qUEvQfjRs/V002_P004_S001_SCENE_001.jpg')
    expect(mapped.region).toBe('전북특별자치도')
    expect(mapped.place_id).toBe('P004')
    expect(mapped.mood).toEqual(['peaceful', 'vibrant', 'natural'])
  })
})
