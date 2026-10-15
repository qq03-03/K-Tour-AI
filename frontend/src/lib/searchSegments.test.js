import { describe, it, expect } from 'vitest'
import { searchSegments } from './searchSegments.js'

const fixtures = [
  {
    segment_id: 'A',
    season: 'summer',
    place_name: '연꽃 정원과 오리',
    drama_title: '연못이야기',
    description: 'A serene pond with lotus blossoms and ducks.',
    mood: ['calm', 'serene'],
    scene_elements: ['lotus_pond', 'ducks', 'water'],
    activity: ['bird_watching'],
  },
  {
    segment_id: 'B',
    season: 'summer',
    place_name: '숲속 정자',
    drama_title: '선재 업고 튀어',
    description: 'Two people walking through a forested pathway.',
    mood: ['refreshing', 'vibrant'],
    scene_elements: ['trees', 'pathway'],
    activity: ['walking'],
  },
  {
    segment_id: 'C',
    season: 'autumn, winter',
    place_name: '가을 단풍길',
    drama_title: '킹덤',
    description: 'A quiet autumn trail covered in red leaves.',
    mood: ['peaceful'],
    scene_elements: ['leaves', 'trail'],
    activity: ['walking'],
  },
  {
    segment_id: 'D',
    season: 'summer',
    place_name: '충주 중앙탑공원',
    region: '충청북도',
    city: '충주시',
    drama_title: '사랑의 불시착',
    description: 'A lit bridge at night.',
    mood: ['peaceful'],
    scene_elements: ['bridge'],
    activity: ['walking'],
  },
]

describe('searchSegments', () => {
  it('returns all segments when called with no query or filters', () => {
    const result = searchSegments(fixtures, {})
    expect(result).toHaveLength(4)
  })

  it('excludes segments with no matching query terms', () => {
    const result = searchSegments(fixtures, { query: 'lotus pond' })
    expect(result.map((s) => s.segment_id)).toEqual(['A'])
  })

  it('matches on drama_title as well as description/scene fields', () => {
    const result = searchSegments(fixtures, { query: '선재 업고 튀어' })
    expect(result.map((s) => s.segment_id)).toEqual(['B'])
  })

  it('ranks a segment matching more query terms above one matching fewer', () => {
    const result = searchSegments(fixtures, { query: 'walking forested' })
    expect(result[0].segment_id).toBe('B')
  })

  it('filters by season', () => {
    const result = searchSegments(fixtures, { season: 'summer' })
    expect(result.map((s) => s.segment_id)).toEqual(['A', 'B', 'D'])
  })

  it('matches on region and city, not just place_name/drama_title/description', () => {
    const result = searchSegments(fixtures, { query: '충청북도' })
    expect(result.map((s) => s.segment_id)).toEqual(['D'])
    const cityResult = searchSegments(fixtures, { query: '충주시' })
    expect(cityResult.map((s) => s.segment_id)).toEqual(['D'])
  })

  it('matches a broader colloquial region group (e.g. 충청도/충청권) against a segment\'s specific region', () => {
    const provinceResult = searchSegments(fixtures, { query: '충청도' })
    expect(provinceResult.map((s) => s.segment_id)).toEqual(['D'])
    const districtResult = searchSegments(fixtures, { query: '충청권' })
    expect(districtResult.map((s) => s.segment_id)).toEqual(['D'])
  })

  it('filters by season when the segment lists multiple comma-separated seasons', () => {
    const result = searchSegments(fixtures, { season: 'winter' })
    expect(result.map((s) => s.segment_id)).toEqual(['C'])
  })

  it('filters by theme keywords, matching if any keyword is present', () => {
    const result = searchSegments(fixtures, { themeKeywords: ['pond', 'water'] })
    expect(result.map((s) => s.segment_id)).toEqual(['A'])
  })

  it('does not filter by theme when themeKeywords is not provided', () => {
    const result = searchSegments(fixtures, {})
    expect(result).toHaveLength(4)
  })

  it('matches nothing when a theme is selected but has no known keywords yet', () => {
    const result = searchSegments(fixtures, { themeKeywords: [] })
    expect(result).toEqual([])
  })

  it('returns an empty array when nothing matches', () => {
    const result = searchSegments(fixtures, { query: 'skyscraper subway' })
    expect(result).toEqual([])
  })

  it('attaches a similarity score to every result', () => {
    const result = searchSegments(fixtures, { query: 'lotus' })
    expect(result[0].similarity).toBeGreaterThan(0)
    expect(result[0].similarity).toBeLessThanOrEqual(1)
  })
})
