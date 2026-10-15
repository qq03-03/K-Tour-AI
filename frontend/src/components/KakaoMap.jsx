import { useEffect, useRef, useState } from 'react'
import { useLanguage } from '../i18n/LanguageContext.jsx'

const KAKAO_SDK_SRC = 'https://dapi.kakao.com/v2/maps/sdk.js'
const DEFAULT_TIMEOUT_MS = 8000

function loadKakaoSdk(appKey, timeoutMs) {
  const loadPromise = new Promise((resolve, reject) => {
    if (window.kakao && window.kakao.maps) {
      resolve(window.kakao)
      return
    }
    // Always start from a fresh <script> tag. Reusing one whose load/error
    // event already fired (e.g. on retry after a failure) would never
    // resolve, since those events don't replay for newly added listeners.
    document.querySelectorAll('script[data-kakao-map-sdk]').forEach((old) => old.remove())
    const script = document.createElement('script')
    // Cache-bust: this app's Kakao service was disabled for part of testing,
    // during which some clients cached an error response for this exact URL.
    // A stable query string could keep serving that stale cached response
    // (which trips ERR_BLOCKED_BY_ORB); a per-load timestamp forces a fresh
    // fetch every time.
    script.src = `${KAKAO_SDK_SRC}?appkey=${appKey}&autoload=false&_=${Date.now()}`
    script.dataset.kakaoMapSdk = 'true'
    script.addEventListener('load', () => window.kakao.maps.load(() => resolve(window.kakao)))
    script.addEventListener('error', () => reject(new Error('Failed to load Kakao Maps SDK')))
    document.head.appendChild(script)
  })

  const timeoutPromise = new Promise((_, reject) => {
    setTimeout(() => reject(new Error('Timed out loading Kakao Maps SDK')), timeoutMs)
  })

  return Promise.race([loadPromise, timeoutPromise])
}

function buildInfoWindowContent(marker) {
  const dramaLine = marker.dramaTitles && marker.dramaTitles.length > 0
    ? `<div style="font-size:11px;color:#64748b;margin-top:2px;">${marker.dramaTitles.join(', ')}</div>`
    : ''
  return `<div style="padding:8px 12px;font-size:12px;font-weight:700;color:#1e293b;white-space:nowrap;">${marker.label}${dramaLine}</div>`
}

export default function KakaoMap({ markers, timeoutMs = DEFAULT_TIMEOUT_MS, fillHeight = false }) {
  const mapHeight = fillHeight ? '100%' : 260
  const placeholderHeight = fillHeight ? '100%' : 200
  const containerRef = useRef(null)
  const [status, setStatus] = useState('loading')
  const [retryCount, setRetryCount] = useState(0)
  const { t } = useLanguage()

  useEffect(() => {
    if (markers.length === 0) return

    let cancelled = false
    let resizeObserver
    // Markers created by this run of the effect. When markers changes again
    // (e.g. results re-localized on a language switch) or the component
    // unmounts, these must be explicitly detached with setMap(null) --
    // creating a new kakao.maps.Map on the same container does not remove
    // the previous map's marker/overlay layer on its own, so without this
    // pins (and their radius circles) accumulated across every re-run
    // instead of being replaced.
    let createdMarkers = []
    setStatus('loading')
    const appKey = import.meta.env.VITE_KAKAO_MAP_KEY

    loadKakaoSdk(appKey, timeoutMs)
      .then((kakao) => {
        if (cancelled || !containerRef.current) return

        const center = new kakao.maps.LatLng(markers[0].latitude, markers[0].longitude)
        const map = new kakao.maps.Map(containerRef.current, { center, level: 8 })
        const bounds = new kakao.maps.LatLngBounds()

        // Only one pin's info window should be visible at a time, so clicking
        // a new pin closes whichever one is currently open.
        let openInfoWindow = null

        markers.forEach((marker) => {
          const position = new kakao.maps.LatLng(marker.latitude, marker.longitude)
          const markerInstance = new kakao.maps.Marker({ map, position, title: marker.label })
          createdMarkers.push(markerInstance)
          bounds.extend(position)

          const infoWindow = new kakao.maps.InfoWindow({ content: buildInfoWindowContent(marker) })
          kakao.maps.event.addListener(markerInstance, 'click', () => {
            if (openInfoWindow) openInfoWindow.close()
            infoWindow.open(map, markerInstance)
            openInfoWindow = infoWindow
          })
        })

        // The map is created while its container is inside a conditionally
        // rendered (list/map toggle) flex layout, so the container isn't
        // always at its final width on the first paint yet. relayout() makes
        // the map re-measure the container; without it, the map keeps the
        // undersized dimensions it was born with and renders as a small tile
        // repeated as blank watermark. The ResizeObserver reapplies this if
        // the container resizes again later (toggle, window resize).
        const fitToContainer = () => {
          map.relayout()
          if (markers.length > 1) {
            map.setBounds(bounds)
          } else {
            map.setCenter(center)
          }
        }
        fitToContainer()

        if (typeof ResizeObserver !== 'undefined') {
          resizeObserver = new ResizeObserver(fitToContainer)
          resizeObserver.observe(containerRef.current)
        }

        setStatus('ready')
      })
      .catch(() => {
        if (cancelled) return
        setStatus('error')
      })

    return () => {
      cancelled = true
      if (resizeObserver) resizeObserver.disconnect()
      createdMarkers.forEach((marker) => marker.setMap(null))
      createdMarkers = []
    }
  }, [markers, timeoutMs, retryCount])

  if (markers.length === 0) {
    return (
      <div style={{ height: placeholderHeight, borderRadius: 16, background: '#eef2f7', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', fontSize: 13 }}>
        🗺️ {t('map_empty')}
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div style={{ height: placeholderHeight, borderRadius: 16, background: '#eef2f7', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10, color: '#94a3b8', fontSize: 13 }}>
        <span>🗺️ {t('map_error')}</span>
        <button
          onClick={() => setRetryCount((n) => n + 1)}
          style={{ border: 'none', background: 'var(--color-primary)', color: 'white', borderRadius: 20, padding: '8px 16px', fontSize: 12.5, fontWeight: 700 }}
        >
          {t('map_retry')}
        </button>
      </div>
    )
  }

  return (
    <div style={{ position: 'relative', height: fillHeight ? '100%' : undefined }}>
      {status === 'loading' && (
        <div style={{ height: mapHeight, borderRadius: 16, background: '#eef2f7', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', fontSize: 13 }}>
          {t('map_loading')}
        </div>
      )}
      <div
        ref={containerRef}
        style={{ width: '100%', height: mapHeight, borderRadius: 16, overflow: 'hidden', display: status === 'ready' ? 'block' : 'none' }}
      />
    </div>
  )
}
