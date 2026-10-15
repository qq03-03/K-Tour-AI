# 프론트엔드 ↔ 실제 검색 백엔드 연결 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the client-side, mock-data search/detail flow with calls to the real Railway-hosted search backend, while keeping every existing component/util (`ResultCard`, `dedupeByPlace`, `dedupeByDrama`, `getMapMarkers`, `localizeSegment`) unchanged by making the new API layer produce objects in the exact shape those already expect.

**Architecture:** A single new module, `src/lib/api.js`, is the only place that calls `fetch`. It maps backend response fields onto the field names the rest of the app already uses (`segment_id` → `uid`, `final_score` → `similarity`, everything else passes through unchanged). `SearchResults.jsx` and `Detail.jsx` become async (loading/error state) but keep their existing render logic for dedup, localization, and the map.

**Tech Stack:** React 19, Vite, vitest + @testing-library/react (already in use). No new dependencies — `fetch` is available natively in the browser/jsdom test environment this project already uses.

## Global Constraints

- Backend base URL: `https://k-tour-ai-production.up.railway.app` (Railway-hosted, already deployed and verified working).
- Backend request/response contract (already implemented and deployed, do not change): `POST /api/search` body `{ query: string (required, min 1 char), lang?, place_id?, drama_title?, region?, city?, season?, time_of_day?, top_k?, candidate_k? }` (all filter fields are `string[] | null`), response `{ results: [...], fallback_used: bool, fallback_reason: string | null }`. Each result item has exactly these fields: `rank, source_segment_id, segment_id, keyframe_id, keyframe_path, video_id, place_id, place_name, region, city, latitude, longitude, drama_title, start_time, end_time, season, time_of_day, description, mood, activity, scene_elements, k_culture_elements, text_score, image_score, text_rank, image_rank, final_score`.
- `GET /api/segments/{id}` returns exactly these fields (confirmed from `search-service/src/segment_row.py`'s `segment_from_row`, the shared row-mapper this endpoint uses): `segment_id, source_segment_id, video_id, place_id, place_name, region, city, drama_title, start_time, end_time, description, season, time_of_day, keyframe_path, mood, activity, scene_elements, k_culture_elements`. No `latitude`/`longitude`, no `rank`/scores — those only exist on search result items. 404 (`{"detail": "..."}`) if not found.
- Never invent a fallback to local mock search on API failure — show an error state instead (explicit product decision).
- `uid` in existing components/tests always refers to `segment_id` going forward (there is no separate `uid` field from the backend).
- Existing files NOT to modify: `src/lib/dedupeByPlace.js`, `src/lib/dedupeByDrama.js`, `src/lib/getMapMarkers.js`, `src/lib/localizeSegment.js`, `src/components/ResultCard.jsx` — the whole point of the mapping layer is that these keep working unchanged.
- `src/lib/searchSegments.js` and `src/data/mockSegments517.js` / `src/data/mockSegments.js` are NOT deleted by this plan (out of scope — they may still be referenced elsewhere, e.g. by `themes.js`'s keyword-authoring comments; leave them in place).

---

### Task 1: `src/lib/mapSearchResponse.js` — pure response-mapping function

**Files:**
- Create: `src/lib/mapSearchResponse.js`
- Test: `src/lib/mapSearchResponse.test.js`

**Interfaces:**
- Produces: `mapSearchResponse(results: BackendResultItem[]): MappedSegment[]` — a pure function, no network. `BackendResultItem` is exactly the `SearchResultItem` shape from the Global Constraints. `MappedSegment` is every field from `BackendResultItem` EXCEPT `rank`/`source_segment_id`/`keyframe_id`/`text_score`/`image_score`/`text_rank`/`image_rank`/`final_score` are dropped, PLUS two added fields: `uid` (copy of `segment_id`) and `similarity` (see below). This is the shape `ResultCard`, `dedupeByPlace`, `dedupeByDrama`, `getMapMarkers`, and `localizeSegment` already expect (same fields as today's `mockSegments517.js` entries plus `place_id`/`video_id`, which those utils already tolerate on their input objects today — confirm by re-reading `src/lib/localizeSegment.js`, it only reads/writes the fields in `LOCALIZABLE_FIELDS` and copies everything else through via `{ ...segment }`).
- Consumed by: `src/lib/api.js` (Task 2).

- [ ] **Step 1: Write the failing tests**

```javascript
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- src/lib/mapSearchResponse.test.js`
Expected: FAIL with "Failed to resolve import" or similar (file doesn't exist yet).

- [ ] **Step 3: Write the implementation**

```javascript
export function mapSearchResponse(results) {
  const maxFinalScore = results.reduce((max, item) => Math.max(max, item.final_score), 0)

  return results.map((item) => ({
    uid: item.segment_id,
    segment_id: item.segment_id,
    video_id: item.video_id,
    place_id: item.place_id,
    place_name: item.place_name,
    region: item.region,
    city: item.city,
    drama_title: item.drama_title,
    start_time: item.start_time,
    end_time: item.end_time,
    season: item.season,
    time_of_day: item.time_of_day,
    description: item.description,
    mood: item.mood,
    activity: item.activity,
    scene_elements: item.scene_elements,
    keyframe_path: item.keyframe_path,
    similarity: maxFinalScore > 0 ? item.final_score / maxFinalScore : 0,
  }))
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/lib/mapSearchResponse.test.js`
Expected: PASS, all 5 tests green.

- [ ] **Step 5: Commit**

```bash
git add src/lib/mapSearchResponse.js src/lib/mapSearchResponse.test.js
git commit -m "feat: add pure mapper from backend search results to frontend segment shape"
```

---

### Task 2: `src/lib/api.js` — the fetch layer

**Files:**
- Create: `src/lib/api.js`
- Test: `src/lib/api.test.js`

**Interfaces:**
- Consumes: `mapSearchResponse` from Task 1 (`src/lib/mapSearchResponse.js`).
- Produces:
  - `searchSegmentsApi({ query, filters })` → `Promise<MappedSegment[]>`. `filters` is an optional object whose keys may include `place_id`, `drama_title`, `region`, `city`, `season`, `time_of_day` (each `string[]`), forwarded as-is into the request body alongside `query`. Throws an `Error` with a message starting `"검색 요청 실패"` on any non-2xx response or network failure.
  - `getSegmentByIdApi(segmentId)` → `Promise<MappedSegment | undefined>`. Returns `undefined` on a 404 specifically (so callers can render a "not found" state without a try/catch). Throws on any other non-2xx or network failure.
- Consumed by: `SearchResults.jsx` and `Detail.jsx` (Tasks 3 and 4).

- [ ] **Step 1: Write the failing tests**

```javascript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { searchSegmentsApi, getSegmentByIdApi } from './api.js'

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
        body: JSON.stringify({ query: '가을 단풍길' }),
      }),
    )
    expect(result).toEqual([])
  })

  it('includes filter fields in the request body when provided', async () => {
    fetch.mockResolvedValueOnce(jsonResponse(200, { results: [], fallback_used: false, fallback_reason: null }))
    await searchSegmentsApi({ query: '여름', filters: { season: ['여름'] } })
    const [, options] = fetch.mock.calls[0]
    expect(JSON.parse(options.body)).toEqual({ query: '여름', season: ['여름'] })
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
```

Note: adjust `getSegmentByIdApi`'s test fixture and `mapSearchResponse`-based mapping in the implementation once Step 0's re-read of the backend confirms the real single-segment response shape — the fixture above assumes it matches `SearchResultItem` minus the rank/score fields, per the Global Constraints note.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- src/lib/api.test.js`
Expected: FAIL (module doesn't exist).

- [ ] **Step 3: Write the implementation**

```javascript
import { mapSearchResponse } from './mapSearchResponse.js'

function baseUrl() {
  const url = import.meta.env.VITE_API_BASE_URL
  if (!url) throw new Error('VITE_API_BASE_URL이 설정되어 있지 않아요.')
  return url
}

export async function searchSegmentsApi({ query, filters = {} }) {
  const response = await fetch(`${baseUrl()}/api/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, ...filters }),
  }).catch(() => {
    throw new Error('검색 요청 실패: 네트워크 오류')
  })

  if (!response.ok) {
    throw new Error(`검색 요청 실패: ${response.status}`)
  }

  const data = await response.json()
  return mapSearchResponse(data.results)
}

export async function getSegmentByIdApi(segmentId) {
  const response = await fetch(`${baseUrl()}/api/segments/${encodeURIComponent(segmentId)}`)

  if (response.status === 404) return undefined
  if (!response.ok) {
    throw new Error(`상세 정보 요청 실패: ${response.status}`)
  }

  const data = await response.json()
  return {
    uid: data.segment_id,
    segment_id: data.segment_id,
    video_id: data.video_id,
    place_id: data.place_id,
    place_name: data.place_name,
    region: data.region,
    city: data.city,
    drama_title: data.drama_title,
    start_time: data.start_time,
    end_time: data.end_time,
    season: data.season,
    time_of_day: data.time_of_day,
    description: data.description,
    mood: data.mood,
    activity: data.activity,
    scene_elements: data.scene_elements,
    keyframe_path: data.keyframe_path,
  }
}
```

`getSegmentByIdApi` does not go through `mapSearchResponse` — `GET /api/segments/{id}` has no `final_score` to normalize (there's nothing to normalize against with only one item), so it maps directly. This is a second small mapper living in the same file; do not try to unify it with `mapSearchResponse` into one function, they handle genuinely different input shapes (a list with scores vs. a single item without).

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/lib/api.test.js`
Expected: PASS, all 7 tests green.

- [ ] **Step 5: Commit**

```bash
git add src/lib/api.js src/lib/api.test.js
git commit -m "feat: add fetch client for the real search backend"
```

---

### Task 3: `SearchResults.jsx` — async search + theme/season query translation

**Files:**
- Modify: `src/pages/SearchResults.jsx`
- Modify: `src/pages/SearchResults.test.jsx` (rewrite to mock `src/lib/api.js` instead of exercising real local mock data)

**Interfaces:**
- Consumes: `searchSegmentsApi` from `src/lib/api.js` (Task 2).
- Produces: no exported interface (page component), but the theme→query and season→query translation logic must be usable as-written by Task 5's plain-language description if a later task needs it (no follow-up task references it here — flag this if it changes).

- [ ] **Step 1: Read current `SearchResults.jsx` and `SearchResults.test.jsx` in full** (both already reproduced during design — re-read from disk before editing, they are the source of truth for exact current behavior).

- [ ] **Step 2: Rewrite `SearchResults.jsx`**

```jsx
import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import Header from '../components/Header.jsx'
import SearchBar from '../components/SearchBar.jsx'
import ResultCard from '../components/ResultCard.jsx'
import EmptyState from '../components/EmptyState.jsx'
import Footer from '../components/Footer.jsx'
import KakaoMap from '../components/KakaoMap.jsx'
import { themes } from '../data/themes.js'
import { placeCoordinates } from '../data/placeCoordinates.js'
import { searchSegmentsApi } from '../lib/api.js'
import { dedupeByPlace } from '../lib/dedupeByPlace.js'
import { dedupeByDrama } from '../lib/dedupeByDrama.js'
import { getMapMarkers } from '../lib/getMapMarkers.js'
import { localizeSegment } from '../lib/localizeSegment.js'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function SearchResults() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [showMap, setShowMap] = useState(false)
  const [results, setResults] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const { lang, t } = useLanguage()

  const query = searchParams.get('q') || ''
  const season = searchParams.get('season')
  const themeId = searchParams.get('theme')
  const theme = themeId ? themes.find((t2) => t2.id === themeId) : null
  const isBrowsing = Boolean(season || themeId)

  useEffect(() => {
    let cancelled = false

    async function run() {
      setError(null)

      if (theme && theme.keywords.length === 0) {
        setResults([])
        setIsLoading(false)
        return
      }

      const effectiveQuery = query || (theme ? theme.keywords.join(' ') : season)
      if (!effectiveQuery) {
        setResults([])
        setIsLoading(false)
        return
      }

      setIsLoading(true)
      try {
        const filters = season ? { season: [season] } : {}
        const searchResults = await searchSegmentsApi({ query: effectiveQuery, filters })
        if (!cancelled) setResults(searchResults)
      } catch {
        if (!cancelled) setError(t('search_error_message'))
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    run()
    return () => { cancelled = true }
  }, [query, season, themeId])

  const displayResults = isBrowsing ? dedupeByDrama(dedupeByPlace(results)) : results
  const localizedResults = displayResults.map((segment) => localizeSegment(segment, lang))

  function handleSearch(newQuery) {
    navigate(`/search?q=${encodeURIComponent(newQuery)}`)
  }

  return (
    <div>
      <Header />
      <div style={{ padding: '16px 24px' }}>
        <SearchBar initialValue={query} onSearch={handleSearch} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 24px' }}>
        <span style={{ fontSize: 12.5, color: '#64748b' }}>{t('results_count', { n: displayResults.length })}</span>
        <button
          onClick={() => setShowMap((v) => !v)}
          style={{ background: 'var(--color-primary)', color: 'white', border: 'none', borderRadius: 20, padding: '8px 16px', fontSize: 12.5, fontWeight: 700 }}
        >
          🗺️ {showMap ? t('view_as_list') : t('view_as_map')}
        </button>
      </div>
      {showMap && (
        <div style={{ margin: '14px 24px' }}>
          <KakaoMap markers={getMapMarkers(displayResults, placeCoordinates)} />
        </div>
      )}
      <div style={{ padding: '14px 24px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {isLoading ? (
          <p style={{ textAlign: 'center', color: '#94a3b8' }}>{t('search_loading_message')}</p>
        ) : error ? (
          <EmptyState message={error} />
        ) : localizedResults.length === 0 ? (
          <EmptyState message={t('empty_results_message')} />
        ) : (
          localizedResults.map((segment) => <ResultCard key={segment.uid} segment={segment} />)
        )}
      </div>
      <Footer />
    </div>
  )
}
```

Add the two new translation keys (`search_loading_message`, `search_error_message`) to whatever i18n dictionary file backs `t(...)` (find it via `grep -rn "empty_results_message" src/i18n/` — add the new keys alongside it, in every language the file already covers, matching that file's existing structure). `search_error_message` text: "검색 결과를 불러오지 못했어요. 잠시 후 다시 시도해주세요." (ko) and natural equivalents for the other languages already present in that dictionary. `search_loading_message`: "검색 중이에요..." (ko) and equivalents.

- [ ] **Step 3: Rewrite `SearchResults.test.jsx`**

Mock `src/lib/api.js`'s `searchSegmentsApi` with `vi.mock('../lib/api.js')`. Re-implement each existing test's intent against small controlled fixtures instead of the real 517-item dataset, using `mapSearchResponse`'s output shape (i.e. fixtures already have `uid`, `similarity`, etc. — construct them as the mapped shape directly, `searchSegmentsApi` is mocked so it never runs `mapSearchResponse` for real):

- "shows matching results for a query" → mock `searchSegmentsApi` to resolve with one fixture segment for `query=canola`-equivalent, assert its `place_name` renders.
- "shows the empty state for a query that matches nothing" → mock resolves `[]`, assert empty-state message.
- "shows an error state when the API call fails" (NEW test replacing implicit coverage) → mock rejects, assert `error` text renders.
- "filters by season" / dedup-by-place / dedup-by-drama under season → mock `searchSegmentsApi` to resolve with several fixture segments sharing a `place_id` or `drama_title`, assert only one card renders for the repeated one. Assert the mock was called with `filters: { season: ['summer'] }` (or whatever value is in the URL) to confirm the hard filter is actually sent.
- theme dedup tests → same pattern, but assert `searchSegmentsApi` was called with `query` equal to the theme's `keywords.join(' ')` (pick an existing theme from `src/data/themes.js` with non-empty keywords, e.g. `traditional`).
- "theme with empty keywords shows empty results without calling the API" (NEW test) → pick `cherry-blossom` (empty keywords per `themes.js`), assert `searchSegmentsApi` was NOT called and the empty state renders.
- "does not dedupe for a plain text query" → same as today, mocked results with a repeated `place_id`, assert all render.
- map markers test → same as today, mocked results feed `getMapMarkers` exactly as before (unchanged function).
- language switching test → use a fixture segment whose `segment_id` has a REAL entry in `src/data/segmentTranslations517.json` (read that file to find one, e.g. reuse the 고창 학원농장 segment from Task 1/2's fixtures if it has a translation entry — confirm by grepping the file for its `segment_id`; if it doesn't, pick any `segment_id` key that does exist in that file and mirror its `ko` fields into the mocked API fixture so the initial Korean render matches, then assert the English fields after switching).

Keep the `beforeEach` block that stubs `window.kakao.maps` — that's testing `KakaoMap`, unrelated to this change.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/pages/SearchResults.test.jsx`
Expected: PASS, all tests green (count will differ from the original 9 given the 2 new tests added above).

- [ ] **Step 5: Commit**

```bash
git add src/pages/SearchResults.jsx src/pages/SearchResults.test.jsx src/i18n/
git commit -m "feat: wire SearchResults to the real search API with loading/error states"
```

---

### Task 4: `Detail.jsx` — async segment lookup

**Files:**
- Modify: `src/pages/Detail.jsx`
- Modify: `src/pages/Detail.test.jsx`

**Interfaces:**
- Consumes: `getSegmentByIdApi` from `src/lib/api.js` (Task 2).

- [ ] **Step 1: Read current `Detail.jsx` and `Detail.test.jsx` in full** from disk before editing.

- [ ] **Step 2: Rewrite `Detail.jsx`**

```jsx
import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import Header from '../components/Header.jsx'
import Footer from '../components/Footer.jsx'
import KakaoMap from '../components/KakaoMap.jsx'
import { placeCoordinates } from '../data/placeCoordinates.js'
import { getMapMarkers } from '../lib/getMapMarkers.js'
import { localizeSegment } from '../lib/localizeSegment.js'
import { buildVideoUrl } from '../lib/buildVideoUrl.js'
import { deriveVideoUrlFromVideoId } from '../lib/deriveVideoUrlFromVideoId.js'
import { getSegmentByIdApi } from '../lib/api.js'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function Detail() {
  const { segmentId: uid } = useParams()
  const { lang, t } = useLanguage()
  const [found, setFound] = useState(undefined)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    getSegmentByIdApi(uid)
      .then((result) => { if (!cancelled) setFound(result) })
      .catch(() => { if (!cancelled) setFound(undefined) })
      .finally(() => { if (!cancelled) setIsLoading(false) })
    return () => { cancelled = true }
  }, [uid])

  const segment = found ? localizeSegment(found, lang) : undefined
  const placeCoord = segment ? placeCoordinates[segment.place_id] : undefined
  const locationLabel = placeCoord?.address || segment?.region
  const videoUrl = segment ? deriveVideoUrlFromVideoId(segment.video_id) : undefined

  if (isLoading) {
    return (
      <div>
        <Header />
        <div style={{ padding: 48, textAlign: 'center', color: '#94a3b8' }}>
          <p>{t('search_loading_message')}</p>
        </div>
        <Footer />
      </div>
    )
  }

  if (!segment) {
    return (
      <div>
        <Header />
        <div style={{ padding: 48, textAlign: 'center', color: '#94a3b8' }}>
          <p>{t('detail_not_found')}</p>
          <Link to="/search" style={{ color: 'var(--color-primary)' }}>{t('detail_back_to_search')}</Link>
        </div>
        <Footer />
      </div>
    )
  }

  return (
    <div>
      <Header />
      <div style={{ padding: '20px 24px' }}>
        <h2 style={{ margin: 0, fontSize: 19 }}>{segment.place_name}</h2>
        <p style={{ fontSize: 12.5, color: '#64748b', margin: '4px 0 14px' }}>
          📍 {locationLabel} · ⏱ {segment.start_time.toFixed(2)}s–{segment.end_time.toFixed(2)}s
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
          {segment.mood.slice(0, 3).map((tag) => (
            <span key={tag} style={{ background: '#EFF6FF', color: 'var(--color-primary)', borderRadius: 16, padding: '6px 12px', fontSize: 12, fontWeight: 600 }}>
              {tag}
            </span>
          ))}
        </div>
        <p style={{ fontSize: 13.5, color: '#334155', lineHeight: 1.6, marginBottom: 20 }}>{segment.description}</p>
        <div style={{ background: '#fff', borderRadius: 16, padding: 16, boxShadow: '0 4px 14px rgba(15,23,42,.05)' }}>
          <h4 style={{ margin: '0 0 10px', fontSize: 13 }}>🎬 {t('detail_drama_heading')}</h4>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 700 }}>{segment.drama_title}</p>
          {videoUrl && (
            <a
              href={buildVideoUrl(videoUrl, segment.start_time)}
              target="_blank"
              rel="noopener noreferrer"
              style={{ display: 'inline-block', marginTop: 12, background: 'var(--color-primary)', color: 'white', borderRadius: 20, padding: '8px 16px', fontSize: 12.5, fontWeight: 700, textDecoration: 'none' }}
            >
              ▶ {t('detail_play_original')}
            </a>
          )}
        </div>
      </div>
      <div className="detail-media-row">
        <div className="detail-media-row__image">
          <img
            src={`${import.meta.env.BASE_URL}${segment.keyframe_path}`}
            alt={segment.place_name}
            onError={(event) => { event.currentTarget.style.visibility = 'hidden' }}
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', background: '#e2e8f0' }}
          />
        </div>
        <div className="detail-media-row__map" style={{ background: '#fff', borderRadius: 16, padding: 16, boxShadow: '0 4px 14px rgba(15,23,42,.05)' }}>
          <h4 style={{ margin: '0 0 10px', fontSize: 13 }}>📍 {t('detail_location_heading')}</h4>
          <KakaoMap markers={getMapMarkers([segment], placeCoordinates)} />
        </div>
      </div>
      <Footer />
    </div>
  )
}
```

- [ ] **Step 3: Rewrite `Detail.test.jsx`**

Mock `src/lib/api.js`'s `getSegmentByIdApi`. Cases: resolves with a fixture segment → renders its `place_name`/`description`/etc.; resolves `undefined` (the 404 case) → renders `detail_not_found`; rejects → also renders `detail_not_found` (per the design spec's explicit decision not to distinguish 404 from network errors here).

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/pages/Detail.test.jsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pages/Detail.jsx src/pages/Detail.test.jsx
git commit -m "feat: wire Detail page to the real segment-lookup API"
```

---

### Task 5: Environment config + backend CORS for local dev

**Files:**
- Modify: `.env.example`
- Modify: `.env`
- Modify: `search-service/app/main.py` (in the backend worktree, `C:\Users\human\Desktop\K-Tour-AI\.worktrees\backend-search-api`)
- Test: `search-service/tests/app/test_health.py` (CORS is already tested there for the GitHub Pages origin — add the equivalent case for localhost)

**Interfaces:**
- None (config + one backend line change).

- [ ] **Step 1: Add the env var**

`.env.example`, append:
```
VITE_API_BASE_URL=https://k-tour-ai-production.up.railway.app
```

`.env` (the real one, not committed... check whether this project's `.env` is gitignored before editing — if it's tracked in git as seen earlier in this session, it's fine to edit directly), append the same line.

- [ ] **Step 2: Write the failing backend test**

In `search-service/tests/app/test_health.py`, add (mirroring the existing `test_cors_allows_the_frontend_origin` test):

```python
def test_cors_allows_local_dev_origin():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
```

- [ ] **Step 3: Run test to verify it fails**

Run (from `search-service/`): `.venv/Scripts/python.exe -m pytest tests/app/test_health.py -v`
Expected: the new test FAILs (localhost not yet in `allow_origins`).

- [ ] **Step 4: Update CORS config**

In `search-service/app/main.py`, change:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://qq03-03.github.io"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```
to:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://qq03-03.github.io", "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/app/test_health.py -v`
Expected: PASS, both CORS tests green. Then run the full backend suite once (`.venv/Scripts/python.exe -m pytest -q`) to confirm no regressions — baseline at time of writing: 264 passed.

- [ ] **Step 6: Commit (two separate repos — commit each)**

Frontend repo (`C:\Users\human\Desktop\K-Tour-AI`):
```bash
git add .env.example .env
git commit -m "feat: add VITE_API_BASE_URL pointing at the deployed search backend"
```

Backend repo/worktree (`C:\Users\human\Desktop\K-Tour-AI\.worktrees\backend-search-api`):
```bash
git add search-service/app/main.py search-service/tests/app/test_health.py
git commit -m "feat: allow local dev origin in CORS for frontend integration testing"
```

The backend commit lands on the `backend-search-api` branch (already pushed once this session) — push it again after this task, same manual-token method used earlier in this session, or ask the user.

---

## After All Tasks

Run the full frontend suite (`npm test`) and confirm everything passes together, not just per-file. Then manually verify in a real browser: `npm run dev`, visit the local dev server, run a text search, browse by season, browse by theme (including one with empty keywords), open a detail page, and confirm results/images/map all render — this is a UI project and per this project's own standing conventions, a passing test suite is necessary but not sufficient proof it works end-to-end.
