import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SearchResults from './SearchResults.jsx'
import { LanguageProvider } from '../i18n/LanguageContext.jsx'
import { searchSegmentsApi, listSegmentsByDramaApi } from '../lib/api.js'

vi.mock('../lib/api.js')

function renderAt(path) {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/search" element={<SearchResults />} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
}

// Header always renders its own "K-Tour AI" home Link (href="/"), so raw
// getAllByRole('link') queries also include it. Scope link assertions to the
// ResultCard links (href starts with /segment/) to test dedup logic only.
function resultLinks() {
  return screen.getAllByRole('link').filter((link) => link.getAttribute('href')?.startsWith('/segment/'))
}

// Small controlled fixtures in the shape mapSearchResponse.js produces
// (uid, similarity, etc. already present) -- searchSegmentsApi is mocked so
// mapSearchResponse never actually runs.
function makeSegment(overrides = {}) {
  return {
    uid: 'V900_P900_S001_SCENE_001',
    segment_id: 'V900_P900_S001_SCENE_001',
    video_id: 'V900_testvideo',
    place_id: 'P900',
    place_name: '테스트 장소',
    region: '서울특별시',
    city: '종로구',
    drama_title: '테스트 드라마',
    start_time: 0,
    end_time: 10,
    season: '여름',
    time_of_day: '낮',
    description: '테스트 설명입니다.',
    mood: ['평화로운'],
    activity: ['걷기'],
    scene_elements: ['길'],
    keyframe_path: 'keyframes/test.jpg',
    similarity: 0.9,
    ...overrides,
  }
}

describe('SearchResults', () => {
  beforeEach(() => {
    window.kakao = {
      maps: {
        LatLng: vi.fn(function LatLng() {}),
        LatLngBounds: vi.fn(function LatLngBounds() {
          this.extend = vi.fn()
        }),
        Map: vi.fn(function Map() {
          this.setBounds = vi.fn()
          this.setCenter = vi.fn()
          this.relayout = vi.fn()
        }),
        Marker: vi.fn(function Marker() {
          this.setMap = vi.fn()
        }),
        InfoWindow: vi.fn(function InfoWindow() {
          this.open = vi.fn()
          this.close = vi.fn()
        }),
        event: { addListener: vi.fn() },
        load: (callback) => callback(),
      },
    }
    vi.mocked(searchSegmentsApi).mockReset()
    vi.mocked(listSegmentsByDramaApi).mockReset()
  })

  it('shows matching results for a query', async () => {
    vi.mocked(searchSegmentsApi).mockResolvedValueOnce([
      makeSegment({ place_name: '고창 학원농장' }),
    ])

    renderAt('/search?q=canola')

    expect(await screen.findByText('고창 학원농장')).toBeInTheDocument()
  })

  it('shows the empty state for a query that matches nothing', async () => {
    vi.mocked(searchSegmentsApi).mockResolvedValueOnce([])

    renderAt('/search?q=submarine spaceship dinosaur')

    expect(await screen.findByText(/검색 결과가 없어요/)).toBeInTheDocument()
  })

  it('shows an error state when the API call fails', async () => {
    vi.mocked(searchSegmentsApi).mockRejectedValueOnce(new Error('network down'))

    renderAt('/search?q=canola')

    expect(await screen.findByText(/검색 결과를 불러오지 못했어요/)).toBeInTheDocument()
  })

  it('shows loading message while the API call is in flight', async () => {
    let resolve
    const apiPromise = new Promise((r) => {
      resolve = r
    })

    vi.mocked(searchSegmentsApi).mockReturnValueOnce(apiPromise)

    renderAt('/search?q=test')

    // Assert loading text is visible BEFORE resolving
    expect(screen.getByText('검색 중이에요...')).toBeInTheDocument()

    // Resolve the API call with results
    resolve([makeSegment({ place_name: '테스트 검색 결과' })])

    // Wait for results to appear
    expect(await screen.findByText('테스트 검색 결과')).toBeInTheDocument()

    // Assert loading text is now gone
    expect(screen.queryByText('검색 중이에요...')).not.toBeInTheDocument()
  })

  it('does not flash "검색 결과 0건" in the count badge while a search is still loading', async () => {
    // Regression test: the count badge used to read straight from `results`
    // (which starts at []), rendering unconditionally regardless of
    // isLoading -- so on first load it briefly said "검색 결과 0건" even
    // though the request hadn't come back yet.
    let resolve
    const apiPromise = new Promise((r) => {
      resolve = r
    })

    vi.mocked(searchSegmentsApi).mockReturnValueOnce(apiPromise)

    renderAt('/search?q=test')

    expect(screen.queryByText('검색 결과 0건')).not.toBeInTheDocument()

    resolve([makeSegment({ place_name: '테스트 검색 결과' })])

    expect(await screen.findByText('검색 결과 1건')).toBeInTheDocument()
  })

  it('filters by season from the URL and sends the season filter to the API', async () => {
    vi.mocked(searchSegmentsApi).mockResolvedValueOnce([makeSegment({ place_id: 'P001' })])

    renderAt('/search?season=summer')

    await screen.findByText('테스트 장소')
    expect(searchSegmentsApi).toHaveBeenCalledWith({
      query: 'summer',
      filters: { season: ['summer'] },
    })
  })

  it('shows only one card per place when filtering by season, even if the place has many matching segments', async () => {
    vi.mocked(searchSegmentsApi).mockResolvedValueOnce([
      makeSegment({ uid: 'a', segment_id: 'a', place_id: 'P001' }),
      makeSegment({ uid: 'b', segment_id: 'b', place_id: 'P001' }),
      makeSegment({ uid: 'c', segment_id: 'c', place_id: 'P001' }),
    ])

    renderAt('/search?season=summer')

    await screen.findByText('테스트 장소')
    expect(resultLinks()).toHaveLength(1)
  })

  it('shows only one card per drama when filtering by season, even if the drama was filmed at several different places', async () => {
    vi.mocked(searchSegmentsApi).mockResolvedValueOnce([
      makeSegment({ uid: 'a', segment_id: 'a', place_id: 'P001', drama_title: '그 해 우리는' }),
      makeSegment({ uid: 'b', segment_id: 'b', place_id: 'P002', drama_title: '그 해 우리는' }),
      makeSegment({ uid: 'c', segment_id: 'c', place_id: 'P003', drama_title: '그 해 우리는' }),
    ])

    renderAt('/search?season=summer')

    await waitFor(() => {
      expect(screen.getAllByText(/그 해 우리는/)).toHaveLength(1)
    })
  })

  it('shows only one card per place when filtering by theme, even if the place has many matching segments', async () => {
    vi.mocked(searchSegmentsApi).mockResolvedValueOnce([
      makeSegment({ uid: 'a', segment_id: 'a', place_id: 'P001' }),
      makeSegment({ uid: 'b', segment_id: 'b', place_id: 'P001' }),
    ])

    renderAt('/search?theme=traditional')

    await screen.findByText('테스트 장소')
    expect(resultLinks()).toHaveLength(1)
    // Theme is a real backend hard filter now (see theme_mapping.py's
    // source_segment_id -> themes mapping), not a bag of keywords joined
    // into a free-text CLIP query -- so q stays empty and the theme id is
    // sent as its own filter.
    expect(searchSegmentsApi).toHaveBeenCalledWith({
      query: '',
      filters: { theme: ['traditional'] },
    })
  })

  it('normalizes a legacy dash-separated theme id from an old bookmarked URL to its canonical id', async () => {
    vi.mocked(searchSegmentsApi).mockResolvedValueOnce([makeSegment({ place_id: 'P001' })])

    renderAt('/search?theme=beach')

    await screen.findByText('테스트 장소')
    expect(searchSegmentsApi).toHaveBeenCalledWith({
      query: '',
      filters: { theme: ['sea'] },
    })
  })

  it('shows only one card per drama when filtering by theme, even if the drama was filmed at several different places', async () => {
    vi.mocked(searchSegmentsApi).mockResolvedValueOnce([
      makeSegment({ uid: 'a', segment_id: 'a', place_id: 'P001', drama_title: '그 해 우리는' }),
      makeSegment({ uid: 'b', segment_id: 'b', place_id: 'P002', drama_title: '그 해 우리는' }),
      makeSegment({ uid: 'c', segment_id: 'c', place_id: 'P003', drama_title: '그 해 우리는' }),
      makeSegment({ uid: 'd', segment_id: 'd', place_id: 'P004', drama_title: '그 해 우리는' }),
    ])

    renderAt('/search?theme=traditional')

    await waitFor(() => {
      expect(screen.getAllByText(/그 해 우리는/)).toHaveLength(1)
    })
  })

  it('an unrecognized theme id shows empty results without calling the API', async () => {
    // A theme id that doesn't match anything in themes.js (even after legacy
    // normalization) -- e.g. a stale bookmark -- must not be sent to the
    // backend as a filter, since it's not one of the confirmed canonical ids.
    renderAt('/search?theme=does-not-exist')

    expect(await screen.findByText(/검색 결과가 없어요/)).toBeInTheDocument()
    expect(searchSegmentsApi).not.toHaveBeenCalled()
  })

  it('drama browsing calls listSegmentsByDramaApi (not the ranked/deduped search endpoint)', async () => {
    // POST /api/search always collapses to one result per source_segment_id,
    // so a drama with 53 curated SCENE entries across only 4 distinct shots
    // would only ever return 4 rows there. Drama browsing needs the plain
    // segment-listing endpoint instead, which returns every SCENE.
    vi.mocked(listSegmentsByDramaApi).mockResolvedValueOnce([makeSegment()])

    renderAt(`/search?drama=${encodeURIComponent('호텔 델루나')}`)

    await waitFor(() => {
      expect(listSegmentsByDramaApi).toHaveBeenCalledWith('호텔 델루나')
    })
    expect(searchSegmentsApi).not.toHaveBeenCalled()
  })

  it('drama browsing dedupes by place -- many scenes at the same spot collapse to one card', async () => {
    // listSegmentsByDramaApi returns every individual SCENE (e.g. 53 for
    // 호텔 델루나), but most of those are the same handful of physical
    // locations shot many times over. Showing all 53 cards meant the same
    // place name repeating dozens of times, so results are deduped by
    // place -- one card per distinct location, same as season/theme
    // browsing already does.
    vi.mocked(listSegmentsByDramaApi).mockResolvedValueOnce([
      makeSegment({ uid: 'a', segment_id: 'a', place_id: 'P001', drama_title: '호텔 델루나' }),
      makeSegment({ uid: 'b', segment_id: 'b', place_id: 'P001', drama_title: '호텔 델루나' }),
      makeSegment({ uid: 'c', segment_id: 'c', place_id: 'P002', drama_title: '호텔 델루나' }),
    ])

    renderAt(`/search?drama=${encodeURIComponent('호텔 델루나')}`)

    await waitFor(() => {
      expect(resultLinks()).toHaveLength(2)
    })
  })

  it('shows an error state when listSegmentsByDramaApi fails', async () => {
    vi.mocked(listSegmentsByDramaApi).mockRejectedValueOnce(new Error('network down'))

    renderAt(`/search?drama=${encodeURIComponent('호텔 델루나')}`)

    expect(await screen.findByText(/검색 결과를 불러오지 못했어요/)).toBeInTheDocument()
  })

  it('shows a trailer panel with a new-tab YouTube link when browsing a drama with known trailer data', async () => {
    vi.mocked(listSegmentsByDramaApi).mockResolvedValueOnce([
      makeSegment({ drama_title: '호텔 델루나' }),
    ])

    renderAt(`/search?drama=${encodeURIComponent('호텔 델루나')}`)

    await screen.findByText('테스트 장소')

    expect(screen.getByRole('heading', { name: '호텔 델루나' })).toBeInTheDocument()
    const trailerLink = screen.getByRole('link', { name: /예고편/ })
    expect(trailerLink).toHaveAttribute('href', 'https://www.youtube.com/watch?v=wi6kzEHVqRk')
    expect(trailerLink).toHaveAttribute('target', '_blank')
  })

  it('localizes the trailer link accessible name instead of always appending Korean "예고편 보기"', async () => {
    // Bug report: the drama title in the trailer thumbnail's alt text was
    // localized, but the " 예고편 보기" suffix was a hardcoded Korean literal
    // appended in every language -- so an English-mode screen reader still
    // heard Korean words tacked onto the English drama title.
    window.localStorage.setItem('ktourai_lang', 'en')
    vi.mocked(listSegmentsByDramaApi).mockResolvedValueOnce([
      makeSegment({ drama_title: '호텔 델루나' }),
    ])

    renderAt(`/search?drama=${encodeURIComponent('호텔 델루나')}`)

    await screen.findByText('테스트 장소')

    const trailerLink = screen.getByRole('link', { name: /Hotel del Luna/ })
    const alt = trailerLink.querySelector('img').getAttribute('alt')
    expect(alt).not.toMatch(/[가-힣]/)
  })

  it('does not show a trailer panel when browsing a drama with no trailer data', async () => {
    vi.mocked(listSegmentsByDramaApi).mockResolvedValueOnce([
      makeSegment({ drama_title: '테스트 드라마' }),
    ])

    renderAt(`/search?drama=${encodeURIComponent('테스트 드라마')}`)

    await screen.findByText('테스트 장소')

    expect(screen.queryByRole('link', { name: /예고편/ })).not.toBeInTheDocument()
  })

  it('does not dedupe by place for a plain text search with no season filter', async () => {
    vi.mocked(searchSegmentsApi).mockResolvedValueOnce([
      makeSegment({ uid: 'a', segment_id: 'a', place_id: 'P001' }),
      makeSegment({ uid: 'b', segment_id: 'b', place_id: 'P001' }),
    ])

    renderAt('/search?q=%EA%B2%BD%EB%B3%B5%EA%B6%81')

    await waitFor(() => {
      expect(resultLinks()).toHaveLength(2)
    })
  })

  it('adds a region hard filter when the query contains a colloquial region grouping', async () => {
    // "경상도" isn't a literal administrative region, so CLIP semantic
    // matching alone can surface unrelated results (e.g. Seoul). Recognized
    // groupings get sent as an additional region hard filter alongside the
    // original free-text query.
    vi.mocked(searchSegmentsApi).mockResolvedValueOnce([])

    renderAt(`/search?q=${encodeURIComponent('경상도')}`)

    await waitFor(() => {
      expect(searchSegmentsApi).toHaveBeenCalledWith({
        query: '경상도',
        filters: { region: ['부산광역시', '대구광역시', '울산광역시', '경상북도', '경상남도'] },
      })
    })
  })

  it('does not add a region filter for a query with no recognized region grouping', async () => {
    vi.mocked(searchSegmentsApi).mockResolvedValueOnce([])

    renderAt(`/search?q=${encodeURIComponent('가을 단풍길')}`)

    await waitFor(() => {
      expect(searchSegmentsApi).toHaveBeenCalledWith({
        query: '가을 단풍길',
        filters: {},
      })
    })
  })

  it('shows a map with markers when "지도로 보기" is clicked', async () => {
    const user = userEvent.setup()
    vi.mocked(searchSegmentsApi).mockResolvedValueOnce([makeSegment({ place_id: 'P001' })])

    renderAt('/search?q=palace')
    await screen.findByText('테스트 장소')

    await user.click(screen.getByText('🗺️ 지도로 보기'))

    expect(window.kakao.maps.Map).toHaveBeenCalledTimes(1)
    expect(window.kakao.maps.Marker).toHaveBeenCalled()
  })

  it('shows results in English when the language is switched to en', async () => {
    const user = userEvent.setup()
    // Real segment_id with a real entry in segmentTranslations517.json
    // (keyframeId `${segment_id}__${segment_id}`), mirrored ko fields so the
    // initial Korean render matches, then verified against its en fields.
    vi.mocked(searchSegmentsApi).mockResolvedValueOnce([
      makeSegment({
        uid: 'V002_P004_S001_SCENE_001',
        segment_id: 'V002_P004_S001_SCENE_001',
        video_id: 'V002_Q6qUEvQfjRs',
        place_id: 'P004',
        place_name: '고창 학원농장',
        region: '전북특별자치도',
        city: '고창군',
        drama_title: '폭싹 속았수다',
        season: '봄',
        time_of_day: '낮',
        description: '구름 낀 하늘 아래 노란 꽃이 활짝 핀 생생한 들판과 그 사이로 구불구불 이어지는 길이 보인다.',
        mood: ['평화로운', '생기 넘치는', '자연적인'],
        activity: ['서 있기', '걷기'],
        scene_elements: ['들판', '노란 꽃', '길', '하늘', '구름', '나무', '땅'],
      }),
    ])

    renderAt('/search?q=canola')

    expect(await screen.findByText('고창 학원농장')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '메뉴' }))
    await user.click(screen.getByRole('button', { name: 'EN' }))

    expect(await screen.findByText('Gochang Hakwon Farm')).toBeInTheDocument()
  })

  describe('combined filter panel', () => {
    it('toggles the filter panel open and closed', async () => {
      const user = userEvent.setup()
      vi.mocked(searchSegmentsApi).mockResolvedValueOnce([])
      renderAt('/search?q=test')

      expect(screen.queryByText('선택 조건으로 찾기')).not.toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: '☰ 검색 조건' }))
      expect(screen.getByText('선택 조건으로 찾기')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: '닫기' }))
      expect(screen.queryByText('선택 조건으로 찾기')).not.toBeInTheDocument()
    })

    it('opens the panel when the URL carries an openFilter signal (desktop entry via the header hamburger menu)', async () => {
      vi.mocked(searchSegmentsApi).mockResolvedValueOnce([])

      renderAt('/search?seasons=summer&openFilter=1735689600000')

      expect(await screen.findByText('선택 조건으로 찾기')).toBeInTheDocument()
    })

    it('applying the panel navigates to a combined-filter URL and searches with season+theme+drama_title', async () => {
      const user = userEvent.setup()
      vi.mocked(searchSegmentsApi).mockResolvedValue([])

      renderAt('/search')
      await user.click(screen.getByRole('button', { name: '☰ 검색 조건' }))

      await user.click(screen.getByRole('button', { name: '여름' }))
      await user.click(screen.getByRole('button', { name: '야경' }))
      await user.click(screen.getByRole('button', { name: '선재 업고 튀어' }))
      await user.click(screen.getByRole('button', { name: '선택 조건으로 찾기' }))

      await waitFor(() => {
        expect(searchSegmentsApi).toHaveBeenCalledWith({
          query: '',
          filters: {
            season: ['summer'],
            theme: ['night_view'],
            drama_title: ['선재 업고 튀어'],
          },
        })
      })
    })

    it('a genre selection resolves to its matching drama titles as a drama_title filter', async () => {
      const user = userEvent.setup()
      vi.mocked(searchSegmentsApi).mockResolvedValue([])

      renderAt('/search')
      await user.click(screen.getByRole('button', { name: '☰ 검색 조건' }))
      await user.click(screen.getByRole('button', { name: '공포' }))
      await user.click(screen.getByRole('button', { name: '선택 조건으로 찾기' }))

      await waitFor(() => {
        expect(searchSegmentsApi).toHaveBeenCalledWith({
          query: '',
          filters: { drama_title: ['악귀'] },
        })
      })
    })

    it('shows a summary of the active filters from the URL above the results', async () => {
      vi.mocked(searchSegmentsApi).mockResolvedValueOnce([])

      renderAt('/search?seasons=summer&themes=night_view&dramas=선재%20업고%20튀어')

      expect(await screen.findByText(/여름/)).toBeInTheDocument()
      expect(screen.getByText(/야경/)).toBeInTheDocument()
      expect(screen.getByText(/선재 업고 튀어/)).toBeInTheDocument()
    })

    it('a region selection is sent as a region filter alongside the other combined filters', async () => {
      const user = userEvent.setup()
      vi.mocked(searchSegmentsApi).mockResolvedValue([])

      renderAt('/search')
      await user.click(screen.getByRole('button', { name: '☰ 검색 조건' }))
      await user.click(screen.getByRole('button', { name: '서울특별시' }))
      await user.click(screen.getByRole('button', { name: '선택 조건으로 찾기' }))

      await waitFor(() => {
        expect(searchSegmentsApi).toHaveBeenCalledWith({
          query: '',
          filters: { region: ['서울특별시'] },
        })
      })
    })

    it('includes the selected region in the active filter summary', async () => {
      vi.mocked(searchSegmentsApi).mockResolvedValueOnce([])

      renderAt('/search?regions=서울특별시')

      expect(await screen.findByText(/서울특별시/)).toBeInTheDocument()
    })
  })

  describe('browsing summary indicator', () => {
    // Regression coverage: landing on a filtered results page gave no clue
    // what was clicked to get there, especially when it came back empty
    // (e.g. browsing a drama with no matching locations) -- the empty state
    // just says "no results" with nothing to say why you're looking at it.
    // Unlike the combined filter panel's summary (desktop can reopen that
    // panel to see its state), single-click season/theme/drama entries from
    // the home page have no other indicator at all, on any screen size.

    it('shows the season name above the results when browsing by season alone', async () => {
      vi.mocked(searchSegmentsApi).mockResolvedValueOnce([])

      renderAt('/search?season=summer')

      expect(await screen.findByText('여름')).toBeInTheDocument()
    })

    it('shows the theme name above the results when browsing by theme alone', async () => {
      vi.mocked(searchSegmentsApi).mockResolvedValueOnce([])

      renderAt('/search?theme=night_view')

      expect(await screen.findByText('야경')).toBeInTheDocument()
    })

    it('shows the drama name above the results when browsing a drama with no trailer and no results', async () => {
      vi.mocked(listSegmentsByDramaApi).mockResolvedValueOnce([])

      renderAt(`/search?drama=${encodeURIComponent('옥씨부인전')}`)

      expect(await screen.findByText('옥씨부인전')).toBeInTheDocument()
      expect(screen.getByText(/검색 결과가 없어요/)).toBeInTheDocument()
    })

    it('does not duplicate the drama name when a trailer panel already shows it as a heading', async () => {
      vi.mocked(listSegmentsByDramaApi).mockResolvedValueOnce([makeSegment({ drama_title: '호텔 델루나' })])

      renderAt(`/search?drama=${encodeURIComponent('호텔 델루나')}`)

      await screen.findByText('테스트 장소')
      expect(screen.getAllByText('호텔 델루나')).toHaveLength(1)
    })
  })
})
