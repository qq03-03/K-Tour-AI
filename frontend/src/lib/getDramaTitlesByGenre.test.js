import { describe, it, expect } from 'vitest'
import { getDramaTitlesByGenre } from './getDramaTitlesByGenre.js'

describe('getDramaTitlesByGenre', () => {
  it('returns every drama title tagged with any of the requested genre ids (OR)', () => {
    const titles = getDramaTitlesByGenre(['horror'])
    expect(titles).toContain('악귀')
    expect(titles).not.toContain('사랑의 불시착')
  })

  it('unions titles across multiple requested genre ids without duplicates', () => {
    const titles = getDramaTitlesByGenre(['horror', 'fantasy'])
    expect(titles).toContain('악귀')
    expect(titles).toContain('도깨비')
    expect(new Set(titles).size).toBe(titles.length)
  })

  it('returns an empty array for no requested genres', () => {
    expect(getDramaTitlesByGenre([])).toEqual([])
    expect(getDramaTitlesByGenre(null)).toEqual([])
  })
})
