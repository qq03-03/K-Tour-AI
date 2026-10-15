import { Link } from 'react-router-dom'

function formatSeconds(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = Math.floor(totalSeconds % 60)
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

export default function ResultCard({ segment }) {
  return (
    <Link
      to={`/segment/${segment.uid}`}
      style={{ background: '#fff', borderRadius: 18, boxShadow: '0 4px 14px rgba(15,23,42,.06)', display: 'flex', overflow: 'hidden' }}
    >
      <img
        src={`${import.meta.env.BASE_URL}${segment.keyframe_path}`}
        alt={segment.place_name}
        onError={(event) => { event.currentTarget.style.visibility = 'hidden' }}
        style={{ width: 96, height: 96, objectFit: 'cover', flexShrink: 0, background: '#e2e8f0' }}
      />
      <div style={{ padding: '12px 14px', flex: 1 }}>
        <h4 style={{ margin: 0, fontSize: 14.5, color: '#1e293b' }}>{segment.place_name}</h4>
        <p style={{ fontSize: 11, color: 'var(--color-primary)', margin: '2px 0 6px', fontWeight: 600 }}>🎬 {segment.drama_title}</p>
        <p style={{ fontSize: 12, color: '#64748b', margin: '4px 0 8px' }}>{segment.description}</p>
        <div style={{ fontSize: 11.5, color: '#94a3b8' }}>
          📍 {segment.region} · ⏱ {formatSeconds(segment.start_time)}–{formatSeconds(segment.end_time)}
        </div>
      </div>
    </Link>
  )
}
