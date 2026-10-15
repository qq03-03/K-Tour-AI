import { describe, it, expect } from 'vitest'
import { rawSegments517 } from './mockSegments517.js'

describe('mockSegments517', () => {
  it('has exactly 517 entries', () => {
    expect(rawSegments517).toHaveLength(517)
  })

  it('has unique segment_id values', () => {
    const ids = rawSegments517.map((s) => s.segment_id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('prefixes every place_id with N- to avoid colliding with the original 45-segment dataset', () => {
    for (const segment of rawSegments517) {
      expect(segment.place_id.startsWith('N-'), segment.segment_id).toBe(true)
    }
  })

  it('every entry has the required fields', () => {
    const requiredFields = [
      'place_id', 'place_name', 'region', 'city', 'drama_title', 'season', 'time_of_day',
      'mood', 'scene_elements', 'activity', 'description', 'segment_id',
      'source_segment_id', 'video_id', 'start_time', 'end_time', 'keyframe_path',
    ]
    for (const segment of rawSegments517) {
      for (const field of requiredFields) {
        expect(segment[field], `${segment.segment_id}.${field}`).toBeDefined()
      }
    }
  })

  it('every season is a raw Korean value the SEASON_KO_TO_EN map in mockSegments.js understands', () => {
    const knownSeasons = new Set(['봄', '여름', '가을', '겨울'])
    for (const segment of rawSegments517) {
      expect(knownSeasons.has(segment.season), `${segment.segment_id}: ${segment.season}`).toBe(true)
    }
  })

  it('every keyframe_path is a public/-relative path under keyframes/', () => {
    for (const segment of rawSegments517) {
      expect(segment.keyframe_path.startsWith('keyframes/')).toBe(true)
    }
  })
})
