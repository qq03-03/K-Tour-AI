import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import KakaoMap from './KakaoMap.jsx'
import { LanguageProvider } from '../i18n/LanguageContext.jsx'
import { renderWithLanguage } from '../test-utils.jsx'

function flushPromises() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}

function createKakaoMock() {
  return {
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
      InfoWindow: vi.fn(function InfoWindow(options) {
        this.content = options.content
        this.open = vi.fn()
        this.close = vi.fn()
      }),
      event: { addListener: vi.fn() },
      load: (callback) => callback(),
    },
  }
}

const oneMarker = [{ place_id: 'P001', label: '경복궁', latitude: 37.5, longitude: 127.0, dramaTitles: ['도깨비'] }]

describe('KakaoMap', () => {
  beforeEach(() => {
    delete window.kakao
  })

  afterEach(() => {
    vi.useRealTimers()
    document.querySelectorAll('script[data-kakao-map-sdk]').forEach((s) => s.remove())
  })

  it('shows an empty message when there are no markers', () => {
    renderWithLanguage(<KakaoMap markers={[]} />)
    expect(screen.getByText(/지도에 표시할 위치 정보가 없어요/)).toBeInTheDocument()
  })

  it('shows a loading message before the SDK resolves', () => {
    renderWithLanguage(<KakaoMap markers={oneMarker} />)
    expect(screen.getByText(/지도를 불러오는 중/)).toBeInTheDocument()
  })

  it('fills its container height instead of using a fixed pixel height when fillHeight is set', async () => {
    // Detail.jsx wraps the map in a square (aspect-ratio) container so the
    // map matches the photo next to it -- a hardcoded 260px height would
    // ignore that container's actual size instead of filling it.
    window.kakao = createKakaoMock()
    const { container } = renderWithLanguage(<KakaoMap markers={oneMarker} fillHeight />)
    const loadingBox = screen.getByText(/지도를 불러오는 중/).closest('div')
    expect(loadingBox.style.height).toBe('100%')
    expect([...container.querySelectorAll('div')].some((d) => d.style.height === '260px')).toBe(false)

    await flushPromises()
    expect([...container.querySelectorAll('div')].some((d) => d.style.height === '260px')).toBe(false)
  })

  it('renders a map once the SDK loads', async () => {
    window.kakao = createKakaoMock()
    renderWithLanguage(<KakaoMap markers={oneMarker} />)
    await flushPromises()
    expect(window.kakao.maps.Map).toHaveBeenCalledTimes(1)
    expect(screen.queryByText(/지도를 불러오는 중/)).not.toBeInTheDocument()
  })

  it('relays out the map so a container mis-measured at creation time re-fits', async () => {
    window.kakao = createKakaoMock()
    renderWithLanguage(<KakaoMap markers={oneMarker} />)
    await flushPromises()
    const mapInstance = window.kakao.maps.Map.mock.results[0].value
    expect(mapInstance.relayout).toHaveBeenCalled()
    expect(mapInstance.setCenter).toHaveBeenCalled()
  })

  it('opens an info window with the place name and drama titles when a marker is clicked', async () => {
    window.kakao = createKakaoMock()
    renderWithLanguage(<KakaoMap markers={oneMarker} />)
    await flushPromises()

    expect(window.kakao.maps.event.addListener).toHaveBeenCalledTimes(1)
    const [markerInstance, eventName, handler] = window.kakao.maps.event.addListener.mock.calls[0]
    expect(eventName).toBe('click')

    const infoWindowInstance = window.kakao.maps.InfoWindow.mock.results[0].value
    expect(infoWindowInstance.content).toContain('경복궁')
    expect(infoWindowInstance.content).toContain('도깨비')

    handler()
    const mapInstance = window.kakao.maps.Map.mock.results[0].value
    expect(infoWindowInstance.open).toHaveBeenCalledWith(mapInstance, markerInstance)
  })

  it('shows an error message and a retry button when the SDK script fails to load', async () => {
    renderWithLanguage(<KakaoMap markers={oneMarker} />)
    const script = document.querySelector('script[data-kakao-map-sdk]')
    script.dispatchEvent(new Event('error'))
    await waitFor(() => {
      expect(screen.getByText(/지도를 불러오지 못했어요/)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /다시 시도/ })).toBeInTheDocument()
  })

  it('shows an error message if the SDK never responds within the timeout', async () => {
    vi.useFakeTimers()
    renderWithLanguage(<KakaoMap markers={oneMarker} timeoutMs={5000} />)
    await vi.advanceTimersByTimeAsync(5001)
    await vi.advanceTimersByTimeAsync(0)
    expect(screen.getByText(/지도를 불러오지 못했어요/)).toBeInTheDocument()
  })

  it('removes the previous map\'s markers before creating new ones when markers change', async () => {
    // Reproduces the reported bug: switching language re-localizes segments,
    // producing a new markers array, which re-ran this effect without ever
    // clearing the old map's markers -- so pins and their 2km radius circles
    // accumulated 1 -> 2 -> 3 across KO -> EN -> JA instead of staying at 1.
    window.kakao = createKakaoMock()
    const { rerender } = renderWithLanguage(<KakaoMap markers={oneMarker} />)
    await flushPromises()
    const firstMarkerInstance = window.kakao.maps.Marker.mock.results[0].value

    const secondMarker = [{ place_id: 'P002', label: '남산타워', latitude: 37.55, longitude: 126.99, dramaTitles: [] }]
    rerender(<LanguageProvider><KakaoMap markers={secondMarker} /></LanguageProvider>)
    await flushPromises()

    expect(firstMarkerInstance.setMap).toHaveBeenCalledWith(null)
    expect(window.kakao.maps.Marker).toHaveBeenCalledTimes(2)
  })

  it('retries loading when the retry button is clicked', async () => {
    vi.useRealTimers()
    const user = userEvent.setup()
    renderWithLanguage(<KakaoMap markers={oneMarker} />)
    const script = document.querySelector('script[data-kakao-map-sdk]')
    script.dispatchEvent(new Event('error'))
    await waitFor(() => screen.getByRole('button', { name: /다시 시도/ }))

    window.kakao = createKakaoMock()
    await user.click(screen.getByRole('button', { name: /다시 시도/ }))
    await flushPromises()
    expect(window.kakao.maps.Map).toHaveBeenCalledTimes(1)
  })
})
