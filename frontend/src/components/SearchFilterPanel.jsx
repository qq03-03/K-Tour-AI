import { useState } from 'react'
import { seasons } from '../data/seasons.js'
import { themes } from '../data/themes.js'
import { genres } from '../data/dramaGenres.js'
import { regions } from '../data/regions.js'
import { mockSegments } from '../data/mockSegments.js'
import { getFeaturedDramas } from '../lib/getFeaturedDramas.js'
import { deriveDramaImagePath } from '../lib/deriveDramaImagePath.js'
import { localizeDramaTitle } from '../lib/localizeDramaTitle.js'
import { useLanguage } from '../i18n/LanguageContext.jsx'

// Same one-card-per-drama_title source DramaSection.jsx uses on the home
// page, reused here so the drama picker can show the same cover images.
const allDramas = getFeaturedDramas(mockSegments, Infinity)

function toggle(list, value) {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value]
}

// Matches SeasonSection.jsx/ThemeSection.jsx's home-page pill style, made
// multi-select (aria-pressed instead of a single selectedId).
function PillButton({ active, onClick, children }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      style={{
        background: active ? 'var(--color-primary)' : '#EFF6FF',
        color: active ? 'white' : 'var(--color-primary)',
        border: 'none',
        borderRadius: 20,
        padding: '8px 14px',
        fontSize: 12.5,
        fontWeight: 600,
        cursor: 'pointer',
      }}
    >
      {children}
    </button>
  )
}

export default function SearchFilterPanel({ seasons: selectedSeasons, themeIds, genres: selectedGenres, regions: selectedRegions, dramas, onApply, onClose }) {
  const { lang, t } = useLanguage()
  const [draftSeasons, setDraftSeasons] = useState(selectedSeasons)
  const [draftThemeIds, setDraftThemeIds] = useState(themeIds)
  const [draftGenres, setDraftGenres] = useState(selectedGenres)
  const [draftRegions, setDraftRegions] = useState(selectedRegions)
  const [draftDramas, setDraftDramas] = useState(dramas)
  const [dramaSearch, setDramaSearch] = useState('')

  // Match against the displayed (localized) title, not the raw Korean
  // drama_title -- the card itself shows the translated name, so a
  // non-Korean user typing exactly what they see on screen must find it.
  const visibleDramas = allDramas.filter((drama) => localizeDramaTitle(drama.drama_title, lang).includes(dramaSearch))

  // Live preview of the draft selection, shown next to the panel title so
  // the user can see what they've picked so far without having to scroll
  // back up through every section -- updates as pills are toggled, before
  // Apply is clicked.
  const selectionSummary = [
    ...draftSeasons.map((id) => seasons.find((s) => s.id === id)?.label[lang] || id),
    ...draftThemeIds.map((id) => themes.find((t2) => t2.id === id)?.label[lang] || id),
    ...draftGenres.map((id) => {
      const genre = genres.find((g) => g.id === id)
      return genre ? t(genre.labelKey) : id
    }),
    ...draftRegions.map((id) => regions.find((r) => r.id === id)?.label[lang] || id),
    ...draftDramas.map((title) => localizeDramaTitle(title, lang)),
  ].join(' · ')

  function handleApply() {
    onApply({ seasons: draftSeasons, themeIds: draftThemeIds, genres: draftGenres, regions: draftRegions, dramas: draftDramas })
  }

  function handleReset() {
    setDraftSeasons([])
    setDraftThemeIds([])
    setDraftGenres([])
    setDraftRegions([])
    setDraftDramas([])
    setDramaSearch('')
  }

  return (
    <div style={{ background: 'white', borderRadius: 16, padding: '20px', boxShadow: '0 8px 24px rgba(15,23,42,.12)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: selectionSummary ? 4 : 12 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, minWidth: 0 }}>
          <h3 style={{ fontSize: 16, fontWeight: 800, margin: 0, flexShrink: 0 }}>{t('filter_panel_title')}</h3>
          {selectionSummary && (
            <span
              data-testid="filter-selection-summary"
              style={{ fontSize: 12, color: 'var(--color-primary)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            >
              {selectionSummary}
            </span>
          )}
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 14, cursor: 'pointer', flexShrink: 0 }}>
          {t('filter_close')}
        </button>
      </div>
      {selectionSummary && <div style={{ height: 1, background: '#e2e8f0', margin: '0 0 12px' }} />}

      <section style={{ marginBottom: 16 }}>
        <h4 style={{ fontSize: 13, margin: '0 0 8px' }}>{t('filter_season')}</h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {seasons.map((season) => (
            <PillButton
              key={season.id}
              active={draftSeasons.includes(season.id)}
              onClick={() => setDraftSeasons((current) => toggle(current, season.id))}
            >
              <span aria-hidden="true">{season.icon}</span> {season.label[lang]}
            </PillButton>
          ))}
        </div>
      </section>

      <section style={{ marginBottom: 16 }}>
        <h4 style={{ fontSize: 13, margin: '0 0 8px' }}>{t('filter_theme')}</h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {themes.map((theme) => (
            <PillButton
              key={theme.id}
              active={draftThemeIds.includes(theme.id)}
              onClick={() => setDraftThemeIds((current) => toggle(current, theme.id))}
            >
              <span aria-hidden="true">{theme.icon}</span> {theme.label[lang]}
            </PillButton>
          ))}
        </div>
      </section>

      <section style={{ marginBottom: 16 }}>
        <h4 style={{ fontSize: 13, margin: '0 0 8px' }}>{t('filter_genre')}</h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {genres.map((genre) => (
            <PillButton
              key={genre.id}
              active={draftGenres.includes(genre.id)}
              onClick={() => setDraftGenres((current) => toggle(current, genre.id))}
            >
              {t(genre.labelKey)}
            </PillButton>
          ))}
        </div>
      </section>

      <section style={{ marginBottom: 16 }}>
        <h4 style={{ fontSize: 13, margin: '0 0 8px' }}>{t('filter_region')}</h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {regions.map((region) => (
            <PillButton
              key={region.id}
              active={draftRegions.includes(region.id)}
              onClick={() => setDraftRegions((current) => toggle(current, region.id))}
            >
              {region.label[lang]}
            </PillButton>
          ))}
        </div>
      </section>

      <section style={{ marginBottom: 16 }}>
        <h4 style={{ fontSize: 13, margin: '0 0 8px' }}>{t('filter_drama_movie')}</h4>
        <input
          type="search"
          placeholder={t('filter_drama_search_placeholder')}
          value={dramaSearch}
          onChange={(event) => setDramaSearch(event.target.value)}
          style={{ width: '100%', padding: '6px 10px', borderRadius: 8, border: '1px solid #e2e8f0', marginBottom: 10, fontSize: 12.5 }}
        />
        <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 8 }}>
          {visibleDramas.map((drama) => {
            const active = draftDramas.includes(drama.drama_title)
            return (
              <button
                key={drama.drama_title}
                type="button"
                aria-pressed={active}
                onClick={() => setDraftDramas((current) => toggle(current, drama.drama_title))}
                style={{
                  flex: '0 0 96px',
                  border: active ? '3px solid var(--color-primary)' : '3px solid transparent',
                  borderRadius: 16,
                  padding: 0,
                  background: 'none',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <img
                  src={`${import.meta.env.BASE_URL}${deriveDramaImagePath(drama.video_id) || drama.keyframe_path}`}
                  alt=""
                  onError={(event) => { event.currentTarget.style.visibility = 'hidden' }}
                  style={{ width: '100%', height: 60, objectFit: 'cover', borderRadius: 12, background: '#e2e8f0', display: 'block' }}
                />
                <p style={{ fontSize: 11, margin: '6px 0 0', fontWeight: 600, color: 'var(--color-text)' }}>
                  {localizeDramaTitle(drama.drama_title, lang)}
                </p>
              </button>
            )
          })}
        </div>
      </section>

      <div style={{ display: 'flex', gap: 10 }}>
        <button
          onClick={handleReset}
          style={{ flex: '0 0 auto', background: '#EFF6FF', color: 'var(--color-primary)', border: 'none', borderRadius: 12, padding: '10px 16px', fontSize: 13, fontWeight: 700, cursor: 'pointer' }}
        >
          {t('filter_reset')}
        </button>
        <button
          onClick={handleApply}
          style={{ flex: 1, background: 'var(--color-primary)', color: 'white', border: 'none', borderRadius: 12, padding: '10px 16px', fontSize: 13, fontWeight: 700, cursor: 'pointer' }}
        >
          {t('filter_apply')}
        </button>
      </div>
    </div>
  )
}
