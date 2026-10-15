import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import Header from '../components/Header.jsx'
import SearchBar from '../components/SearchBar.jsx'
import ResultCard from '../components/ResultCard.jsx'
import EmptyState from '../components/EmptyState.jsx'
import Footer from '../components/Footer.jsx'
import KakaoMap from '../components/KakaoMap.jsx'
import { themes } from '../data/themes.js'
import { seasons } from '../data/seasons.js'
import { placeCoordinates } from '../data/placeCoordinates.js'
import { searchSegmentsApi, listSegmentsByDramaApi } from '../lib/api.js'
import { deriveRegionFilterFromQuery } from '../lib/deriveRegionFilterFromQuery.js'
import { normalizeThemeId } from '../lib/normalizeThemeId.js'
import { dedupeByPlace } from '../lib/dedupeByPlace.js'
import { dedupeByDrama } from '../lib/dedupeByDrama.js'
import { getMapMarkers } from '../lib/getMapMarkers.js'
import { localizeSegment } from '../lib/localizeSegment.js'
import { getDramaTrailer } from '../lib/getDramaTrailer.js'
import { getDramaTitlesByGenre } from '../lib/getDramaTitlesByGenre.js'
import { localizeDramaTitle } from '../lib/localizeDramaTitle.js'
import { genres } from '../data/dramaGenres.js'
import { regions } from '../data/regions.js'
import SearchFilterPanel from '../components/SearchFilterPanel.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'

function splitParam(value) {
  return value ? value.split(',').filter(Boolean) : []
}

export default function SearchResults() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [showMap, setShowMap] = useState(false)
  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [results, setResults] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const { lang, t } = useLanguage()

  const query = searchParams.get('q') || ''
  const season = searchParams.get('season')
  const rawThemeId = searchParams.get('theme')
  const dramaTitle = searchParams.get('drama')
  const theme = rawThemeId ? themes.find((t2) => t2.id === normalizeThemeId(rawThemeId)) : null

  // Combined filter panel (season+theme+genre+drama, all multi-select) --
  // a separate opt-in path from the single-value season/theme/drama entry
  // points the home page still uses (see SearchFilterPanel.jsx).
  const rawSeasonsParam = searchParams.get('seasons') || ''
  const rawThemesParam = searchParams.get('themes') || ''
  const rawGenresParam = searchParams.get('genres') || ''
  const rawRegionsParam = searchParams.get('regions') || ''
  const rawDramasParam = searchParams.get('dramas') || ''
  const selectedSeasons = splitParam(rawSeasonsParam)
  const selectedThemeIds = splitParam(rawThemesParam)
  const selectedGenres = splitParam(rawGenresParam)
  const selectedRegions = splitParam(rawRegionsParam)
  const selectedDramas = splitParam(rawDramasParam)
  const hasCombinedFilters = Boolean(
    selectedSeasons.length || selectedThemeIds.length || selectedGenres.length || selectedRegions.length || selectedDramas.length,
  )

  const isBrowsing = Boolean(season || rawThemeId || hasCombinedFilters)
  const isDramaBrowsing = Boolean(dramaTitle)

  // Desktop opens the filter panel from the header's hamburger menu (see
  // Header.jsx) instead of the on-page toggle button mobile uses. That link
  // sets a fresh openFilter value every time, so this fires (and reopens
  // the panel) even if the user had since closed it manually.
  const openFilterSignal = searchParams.get('openFilter')
  useEffect(() => {
    if (openFilterSignal) setIsFilterPanelOpen(true)
  }, [openFilterSignal])

  useEffect(() => {
    let cancelled = false

    async function run() {
      setError(null)

      if (dramaTitle) {
        setIsLoading(true)
        try {
          // Not searchSegmentsApi: POST /api/search always collapses results
          // to one representative SCENE per source_segment_id (its fixed
          // "same shot -> one result" rule), so a drama filmed at 4 distinct
          // locations across 53 curated SCENE entries would only ever
          // return 4 rows there. listSegmentsByDramaApi hits the plain,
          // unranked segment-listing endpoint instead, which returns every
          // individual SCENE the team split out, even ones sharing a shot.
          const segments = await listSegmentsByDramaApi(dramaTitle)
          if (!cancelled) setResults(segments)
        } catch {
          if (!cancelled) setError(t('search_error_message'))
        } finally {
          if (!cancelled) setIsLoading(false)
        }
        return
      }

      if (hasCombinedFilters) {
        setIsLoading(true)
        try {
          const genreDramas = getDramaTitlesByGenre(selectedGenres)
          const dramaTitles = [...new Set([...selectedDramas, ...genreDramas])]
          const filters = {
            ...(selectedSeasons.length ? { season: selectedSeasons } : {}),
            ...(selectedThemeIds.length ? { theme: selectedThemeIds } : {}),
            ...(selectedRegions.length ? { region: selectedRegions } : {}),
            ...(dramaTitles.length ? { drama_title: dramaTitles } : {}),
          }
          const searchResults = await searchSegmentsApi({ query: '', filters })
          if (!cancelled) setResults(searchResults)
        } catch {
          if (!cancelled) setError(t('search_error_message'))
        } finally {
          if (!cancelled) setIsLoading(false)
        }
        return
      }

      if (rawThemeId && !theme) {
        // Unrecognized theme id (even after legacy normalization) -- e.g. a
        // stale bookmark -- isn't one of the backend's confirmed canonical
        // ids, so don't send it as a filter.
        setResults([])
        setIsLoading(false)
        return
      }

      if (theme) {
        // Theme is a real backend hard filter (source_segment_id -> themes
        // mapping in theme_mapping.py), not CLIP keyword search, so it works
        // with q="" -- no free text needed to get results.
        setIsLoading(true)
        try {
          const regionFilter = query ? deriveRegionFilterFromQuery(query) : null
          const filters = {
            theme: [theme.id],
            ...(season ? { season: [season] } : {}),
            ...(regionFilter ? { region: regionFilter } : {}),
          }
          const searchResults = await searchSegmentsApi({ query, filters })
          if (!cancelled) setResults(searchResults)
        } catch {
          if (!cancelled) setError(t('search_error_message'))
        } finally {
          if (!cancelled) setIsLoading(false)
        }
        return
      }

      const effectiveQuery = query || season
      if (!effectiveQuery) {
        setResults([])
        setIsLoading(false)
        return
      }

      setIsLoading(true)
      try {
        const regionFilter = query ? deriveRegionFilterFromQuery(query) : null
        const filters = {
          ...(season ? { season: [season] } : {}),
          ...(regionFilter ? { region: regionFilter } : {}),
        }
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
  }, [query, season, rawThemeId, dramaTitle, rawSeasonsParam, rawThemesParam, rawGenresParam, rawRegionsParam, rawDramasParam])

  const displayResults = isDramaBrowsing
    ? dedupeByPlace(results)
    : isBrowsing
      ? dedupeByDrama(dedupeByPlace(results))
      : results
  const localizedResults = displayResults.map((segment) => localizeSegment(segment, lang))
  const trailer = isDramaBrowsing ? getDramaTrailer(dramaTitle) : null

  function handleSearch(newQuery) {
    navigate(`/search?q=${encodeURIComponent(newQuery)}`)
  }

  function handleApplyFilters({ seasons: nextSeasons, themeIds: nextThemeIds, genres: nextGenres, regions: nextRegions, dramas: nextDramas }) {
    const params = new URLSearchParams()
    if (nextSeasons.length) params.set('seasons', nextSeasons.join(','))
    if (nextThemeIds.length) params.set('themes', nextThemeIds.join(','))
    if (nextGenres.length) params.set('genres', nextGenres.join(','))
    if (nextRegions.length) params.set('regions', nextRegions.join(','))
    if (nextDramas.length) params.set('dramas', nextDramas.join(','))
    navigate(`/search?${params.toString()}`)
    setIsFilterPanelOpen(false)
  }

  // Shows what got the user to this page, above the results -- combined
  // filter panel selections, or a single season/theme/drama click from the
  // home page, whichever applies. Skipped when the drama trailer panel is
  // showing, since its own heading already names the drama.
  const browsingSummaryParts = hasCombinedFilters
    ? [
        ...selectedSeasons.map((id) => seasons.find((s) => s.id === id)?.label[lang] || id),
        ...selectedThemeIds.map((id) => themes.find((t2) => t2.id === id)?.label[lang] || id),
        ...selectedGenres.map((id) => {
          const genre = genres.find((g) => g.id === id)
          return genre ? t(genre.labelKey) : id
        }),
        ...selectedRegions.map((id) => regions.find((r) => r.id === id)?.label[lang] || id),
        ...selectedDramas.map((title) => localizeDramaTitle(title, lang)),
      ]
    : isDramaBrowsing
      ? [localizeDramaTitle(dramaTitle, lang)]
      : [
          ...(theme ? [theme.label[lang]] : rawThemeId ? [rawThemeId] : []),
          ...(season ? [seasons.find((s) => s.id === season)?.label[lang] || season] : []),
        ]
  const browsingSummary = browsingSummaryParts.join(' · ')
  const showBrowsingSummary = (isBrowsing || isDramaBrowsing) && !(isDramaBrowsing && trailer)

  const resultsListContent = isLoading ? (
    <p style={{ textAlign: 'center', color: '#94a3b8' }}>{t('search_loading_message')}</p>
  ) : error ? (
    <EmptyState message={error} />
  ) : localizedResults.length === 0 ? (
    <EmptyState message={t('empty_results_message')} />
  ) : (
    localizedResults.map((segment) => <ResultCard key={segment.uid} segment={segment} />)
  )

  return (
    <div>
      <Header />
      <div style={{ padding: '16px 24px' }}>
        <SearchBar initialValue={query} onSearch={handleSearch} />
      </div>
      <div className="mobile-only-filter-toggle" style={{ padding: '0 24px 8px' }}>
        <button
          onClick={() => setIsFilterPanelOpen((v) => !v)}
          style={{ background: '#EFF6FF', color: 'var(--color-primary)', border: 'none', borderRadius: 20, padding: '8px 16px', fontSize: 12.5, fontWeight: 700 }}
        >
          ☰ {t('filter_toggle')}
        </button>
      </div>
      {isFilterPanelOpen && (
        <div style={{ padding: '0 24px 16px' }}>
          <SearchFilterPanel
            seasons={selectedSeasons}
            themeIds={selectedThemeIds}
            genres={selectedGenres}
            regions={selectedRegions}
            dramas={selectedDramas}
            onApply={handleApplyFilters}
            onClose={() => setIsFilterPanelOpen(false)}
          />
        </div>
      )}
      {showBrowsingSummary && (
        <div style={{ padding: '0 24px 12px' }}>
          <span
            style={{
              display: 'inline-block',
              background: 'var(--color-primary)',
              color: 'white',
              fontSize: 14,
              fontWeight: 700,
              borderRadius: 20,
              padding: '8px 16px',
            }}
          >
            {browsingSummary}
          </span>
        </div>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 24px' }}>
        <span style={{ fontSize: 12.5, color: '#64748b' }}>
          {isLoading ? '' : t('results_count', { n: displayResults.length })}
        </span>
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
      {trailer ? (
        <div className="trailer-panel-row" style={{ padding: '14px 24px 24px' }}>
          <div className="trailer-panel-row__info">
            <h2 style={{ fontSize: 26, fontWeight: 800, margin: '0 0 12px' }}>{localizeDramaTitle(dramaTitle, lang)}</h2>
            <a href={trailer.watchUrl} target="_blank" rel="noreferrer">
              <img
                src={trailer.thumbnailUrl}
                alt={t('trailer_watch_alt', { drama: localizeDramaTitle(dramaTitle, lang) })}
                style={{ width: '100%', borderRadius: 12, display: 'block' }}
              />
            </a>
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
            {resultsListContent}
          </div>
        </div>
      ) : (
        <div style={{ padding: '14px 24px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {resultsListContent}
        </div>
      )}
      <Footer />
    </div>
  )
}
