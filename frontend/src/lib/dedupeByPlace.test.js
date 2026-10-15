import { describe, it, expect } from 'vitest'
import { dedupeByPlace } from './dedupeByPlace.js'

describe('dedupeByPlace', () => {
  it('keeps only the first segment for each unique place_id', () => {
    const segments = [
      { place_id: 'P001', segment_id: 'a' },
      { place_id: 'P001', segment_id: 'b' },
      { place_id: 'P002', segment_id: 'c' },
    ]
    expect(dedupeByPlace(segments)).toEqual([
      { place_id: 'P001', segment_id: 'a' },
      { place_id: 'P002', segment_id: 'c' },
    ])
  })

  it('preserves the input order of first occurrences', () => {
    const segments = [
      { place_id: 'P002', segment_id: 'a' },
      { place_id: 'P001', segment_id: 'b' },
      { place_id: 'P002', segment_id: 'c' },
    ]
    const result = dedupeByPlace(segments)
    expect(result.map((s) => s.place_id)).toEqual(['P002', 'P001'])
  })

  it('returns an empty array for empty input', () => {
    expect(dedupeByPlace([])).toEqual([])
  })

  it('does not merge different place_ids even if the place_name looks the same', () => {
    const segments = [
      { place_id: 'P001', place_name: '경복궁', segment_id: 'a' },
      { place_id: 'N-P016', place_name: '경복궁', segment_id: 'b' },
    ]
    expect(dedupeByPlace(segments)).toHaveLength(2)
  })
})
