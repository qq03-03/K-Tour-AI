import { Link } from 'react-router-dom'
import { mockSegments } from '../data/mockSegments.js'
import { getFeaturedDramas } from '../lib/getFeaturedDramas.js'
import { localizeSegment } from '../lib/localizeSegment.js'
import { deriveDramaImagePath } from '../lib/deriveDramaImagePath.js'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function DramaSection() {
  const { lang } = useLanguage()
  // Keep the raw (Korean) segments separate from their localized display
  // copy -- the link must always target the Korean drama_title, since
  // that's the only value the backend's drama_title filter matches.
  // localizeSegment swaps drama_title itself, so building the href from
  // the localized segment sent every non-Korean click to a title the
  // backend couldn't find at all (0 results in en/ja/zh).
  const rawDramas = getFeaturedDramas(mockSegments, Infinity)

  return (
    <div style={{ display: 'flex', gap: 14, overflowX: 'auto', paddingBottom: 8 }}>
      {rawDramas.map((drama) => {
        const localized = localizeSegment(drama, lang)
        return (
          <Link key={drama.segment_id} to={`/search?drama=${encodeURIComponent(drama.drama_title)}`} style={{ flex: '0 0 140px' }}>
            <img
              src={`${import.meta.env.BASE_URL}${deriveDramaImagePath(drama.video_id) || drama.keyframe_path}`}
              alt={localized.drama_title}
              onError={(event) => { event.currentTarget.style.visibility = 'hidden' }}
              style={{ width: '100%', height: 90, objectFit: 'cover', borderRadius: 16, background: '#e2e8f0' }}
            />
            <p style={{ fontSize: 12.5, margin: '8px 0 0', fontWeight: 600, color: 'var(--color-text)' }}>{localized.drama_title}</p>
          </Link>
        )
      })}
    </div>
  )
}
