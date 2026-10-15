import { describe, it, expect } from 'vitest'
import { dedupeByDrama } from './dedupeByDrama.js'

describe('dedupeByDrama', () => {
  it('keeps only the first segment for each unique drama_title', () => {
    const segments = [
      { drama_title: '도깨비', segment_id: 'a' },
      { drama_title: '도깨비', segment_id: 'b' },
      { drama_title: '킹덤', segment_id: 'c' },
    ]
    expect(dedupeByDrama(segments)).toEqual([
      { drama_title: '도깨비', segment_id: 'a' },
      { drama_title: '킹덤', segment_id: 'c' },
    ])
  })

  it('preserves the input order of first occurrences', () => {
    const segments = [
      { drama_title: '킹덤', segment_id: 'a' },
      { drama_title: '도깨비', segment_id: 'b' },
      { drama_title: '킹덤', segment_id: 'c' },
    ]
    const result = dedupeByDrama(segments)
    expect(result.map((s) => s.drama_title)).toEqual(['킹덤', '도깨비'])
  })

  it('returns an empty array for empty input', () => {
    expect(dedupeByDrama([])).toEqual([])
  })
})
