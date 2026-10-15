import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { searchSegmentsApi, getSegmentByIdApi, listSegmentsByDramaApi } from './api.js'

const ORIGINAL_ENV = import.meta.env.VITE_API_BASE_URL

beforeEach(() => {
  import.meta.env.VITE_API_BASE_URL = 'https://example-api.test'
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  import.meta.env.VITE_API_BASE_URL = ORIGINAL_ENV
  vi.unstubAllGlobals()
})

function jsonResponse(status, body) {
  return { ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) }
}

describe('searchSegmentsApi', () => {
  it('POSTs to /api/search with the query and returns mapped results', async () => {
    fetch.mockResolvedValueOnce(jsonResponse(200, { results: [], fallback_used: false, fallback_reason: null }))
    const result = await searchSegmentsApi({ query: '가을 단풍길' })
    expect(fetch).toHaveBeenCalledWith(
      'https://example-api.test/api/search',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ q: '가을 단풍길' }),
      }),
    )
    expect(result).toEqual([])
  })

  it('includes filter fields in the request body when provided', async () => {
    fetch.mockResolvedValueOnce(jsonResponse(200, { results: [], fallback_used: false, fallback_reason: null }))
    await searchSegmentsApi({ query: '여름', filters: { season: ['여름'] } })
    const [, options] = fetch.mock.calls[0]
    expect(JSON.parse(options.body)).toEqual({ q: '여름', season: ['여름'] })
  })

  it('throws a Korean error message on a non-2xx response', async () => {
    fetch.mockResolvedValueOnce(jsonResponse(503, { detail: '데이터베이스에 연결할 수 없어요.' }))
    await expect(searchSegmentsApi({ query: '가을' })).rejects.toThrow('검색 요청 실패')
  })

  it('throws on a network failure', async () => {
    fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(searchSegmentsApi({ query: '가을' })).rejects.toThrow()
  })
})

describe('getSegmentByIdApi', () => {
  it('GETs /api/segments/{id} and returns the mapped segment', async () => {
    fetch.mockResolvedValueOnce(jsonResponse(200, {
      segment_id: 'V002_P004_S001_SCENE_001', video_id: 'V002_Q6qUEvQfjRs', place_id: 'P004',
      place_name: '고창 학원농장', region: '전북특별자치도', city: '고창군', drama_title: '폭싹 속았수다',
      start_time: 0, end_time: 10, season: '봄', time_of_day: 'day', description: 'desc',
      mood: [], activity: [], scene_elements: [], keyframe_path: 'keyframes/x.jpg',
    }))
    const result = await getSegmentByIdApi('V002_P004_S001_SCENE_001')
    expect(fetch).toHaveBeenCalledWith('https://example-api.test/api/segments/V002_P004_S001_SCENE_001', expect.anything())
    expect(result.uid).toBe('V002_P004_S001_SCENE_001')
    expect(result.place_name).toBe('고창 학원농장')
  })

  it('returns undefined on a 404', async () => {
    fetch.mockResolvedValueOnce(jsonResponse(404, { detail: '해당 영상 구간을 찾을 수 없어요.' }))
    const result = await getSegmentByIdApi('does-not-exist')
    expect(result).toBeUndefined()
  })

  it('throws on a non-404 non-2xx response', async () => {
    fetch.mockResolvedValueOnce(jsonResponse(503, { detail: 'x' }))
    await expect(getSegmentByIdApi('any')).rejects.toThrow()
  })
})

describe('listSegmentsByDramaApi', () => {
  it('GETs /api/segments filtered by drama_title and returns every raw row, unranked', async () => {
    fetch.mockResolvedValueOnce(jsonResponse(200, [
      {
        segment_id: 'V009_P015_S001_SCENE_001', video_id: 'V009_7ir6-MekfHU', place_id: 'P015',
        place_name: '망상해변', region: '강원특별자치도', city: '동해시', drama_title: '호텔 델루나',
        start_time: 0, end_time: 4.75, season: '여름', time_of_day: 'day', description: 'desc1',
        mood: [], activity: [], scene_elements: [], keyframe_path: 'keyframes/a.jpg',
      },
      {
        segment_id: 'V009_P015_S001_SCENE_002', video_id: 'V009_7ir6-MekfHU', place_id: 'P015',
        place_name: '망상해변', region: '강원특별자치도', city: '동해시', drama_title: '호텔 델루나',
        start_time: 5, end_time: 9, season: '여름', time_of_day: 'day', description: 'desc2',
        mood: [], activity: [], scene_elements: [], keyframe_path: 'keyframes/b.jpg',
      },
    ]))

    const result = await listSegmentsByDramaApi('호텔 델루나')

    expect(fetch).toHaveBeenCalledWith(
      `https://example-api.test/api/segments?drama_title=${encodeURIComponent('호텔 델루나')}`,
      expect.anything(),
    )
    expect(result).toHaveLength(2)
    expect(result[0].uid).toBe('V009_P015_S001_SCENE_001')
    expect(result[1].uid).toBe('V009_P015_S001_SCENE_002')
  })

  it('throws a Korean error message on a non-2xx response', async () => {
    fetch.mockResolvedValueOnce(jsonResponse(503, { detail: 'x' }))
    await expect(listSegmentsByDramaApi('호텔 델루나')).rejects.toThrow('구간 목록 요청 실패')
  })

  it('throws on a network failure', async () => {
    fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(listSegmentsByDramaApi('호텔 델루나')).rejects.toThrow()
  })
})
