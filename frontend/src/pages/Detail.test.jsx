import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Detail from './Detail.jsx'
import { LanguageProvider } from '../i18n/LanguageContext.jsx'
import { getSegmentByIdApi } from '../lib/api.js'

vi.mock('../lib/api.js')

function renderAt(uid) {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[`/segment/${uid}`]}>
        <Routes>
          <Route path="/segment/:segmentId" element={<Detail />} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
}

// Real segment (from the team's 517-segment dataset) with a real entry in
// placeCoordinates517.js (has a detailed `address`) and in
// segmentTranslations517.json (has an English translation), so the address
// and language-switch tests exercise real lookups -- api.js is mocked, but
// the shape it resolves matches exactly what getSegmentByIdApi returns.
function makeSegment(overrides = {}) {
  return {
    uid: 'V007_P031_S002_SCENE_001',
    segment_id: 'V007_P031_S002_SCENE_001',
    video_id: 'V007_Z7u5SNDq0jw',
    place_id: 'P031',
    place_name: '충주 중앙탑공원',
    region: '충청북도',
    city: '충주시',
    drama_title: '사랑의 불시착',
    start_time: 0,
    end_time: 3.75,
    season: 'summer',
    time_of_day: 'night',
    description: 'A nighttime view of a brightly lit bridge over a calm waterway, with colorful lights reflecting on the surface and trees lining the shore.',
    mood: ['peaceful', 'calm', 'serene'],
    activity: ['walking', 'strolling'],
    scene_elements: ['bridge', 'water', 'lights', 'trees', 'railing', 'floating_lights', 'reflection', 'sky', 'lighthouse'],
    keyframe_path: 'keyframes/V007_Z7u5SNDq0jw/V007_P031_S002_SCENE_001.jpg',
    ...overrides,
  }
}

// A second real segment whose place (P001) has no `address` entry in
// placeCoordinates517.js, so the location label falls back to `region`.
function makeSegmentWithoutAddress(overrides = {}) {
  return {
    uid: 'V001_P001_S001_SCENE_001',
    segment_id: 'V001_P001_S001_SCENE_001',
    video_id: 'V001_nypQChEVN0c',
    place_id: 'P001',
    place_name: '수원 화성',
    region: '경기도',
    city: '수원시',
    drama_title: '선재 업고 튀어',
    start_time: 0,
    end_time: 4.75,
    season: 'spring',
    time_of_day: 'day',
    description: 'A group of people are walking and enjoying the cherry blossom trees in a park on a sunny day.',
    mood: ['peaceful', 'serene', 'vibrant'],
    activity: ['walking', 'photographing'],
    scene_elements: ['cherry_blossom_tree', 'path', 'grass', 'people', 'sky'],
    keyframe_path: 'keyframes/V001_nypQChEVN0c/V001_P001_S001_SCENE_001.jpg',
    ...overrides,
  }
}

describe('Detail', () => {
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
    vi.mocked(getSegmentByIdApi).mockReset()
  })

  it('renders the place name, description and drama title for a segment the API resolves', async () => {
    vi.mocked(getSegmentByIdApi).mockResolvedValueOnce(makeSegment())

    renderAt('V007_P031_S002_SCENE_001')

    expect(await screen.findByText('충주 중앙탑공원')).toBeInTheDocument()
    expect(screen.getByText('사랑의 불시착')).toBeInTheDocument()
    expect(screen.getByText(/밝게 빛나는 다리/)).toBeInTheDocument()
    expect(getSegmentByIdApi).toHaveBeenCalledWith('V007_P031_S002_SCENE_001')
  })

  it('shows the loading message while the API call is in flight', async () => {
    let resolve
    const apiPromise = new Promise((r) => {
      resolve = r
    })
    vi.mocked(getSegmentByIdApi).mockReturnValueOnce(apiPromise)

    renderAt('V007_P031_S002_SCENE_001')

    expect(screen.getByText('검색 중이에요...')).toBeInTheDocument()

    resolve(makeSegment())

    expect(await screen.findByText('충주 중앙탑공원')).toBeInTheDocument()
    expect(screen.queryByText('검색 중이에요...')).not.toBeInTheDocument()
  })

  it('renders a map marker for the segment\'s place', async () => {
    vi.mocked(getSegmentByIdApi).mockResolvedValueOnce(makeSegment())

    renderAt('V007_P031_S002_SCENE_001')

    await screen.findByText('충주 중앙탑공원')
    await waitFor(() => expect(window.kakao.maps.Marker).toHaveBeenCalledTimes(1))
  })

  it('renders a not-found message when the API resolves undefined (404)', async () => {
    vi.mocked(getSegmentByIdApi).mockResolvedValueOnce(undefined)

    renderAt('does_not_exist')

    expect(await screen.findByText(/찾을 수 없어요/)).toBeInTheDocument()
  })

  it('renders a not-found message when the API call rejects', async () => {
    vi.mocked(getSegmentByIdApi).mockRejectedValueOnce(new Error('network down'))

    renderAt('V007_P031_S002_SCENE_001')

    expect(await screen.findByText(/찾을 수 없어요/)).toBeInTheDocument()
  })

  it('derives and links to the original YouTube video from the segment\'s video_id', async () => {
    vi.mocked(getSegmentByIdApi).mockResolvedValueOnce(makeSegment())

    renderAt('V007_P031_S002_SCENE_001')

    const link = await screen.findByRole('link', { name: /원본 영상 재생/ })
    expect(link).toHaveAttribute('href', 'https://www.youtube.com/watch?v=Z7u5SNDq0jw&t=0s')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
  })

  it('shows the detailed street address for a place that has one, instead of just the region', async () => {
    vi.mocked(getSegmentByIdApi).mockResolvedValueOnce(makeSegment())

    renderAt('V007_P031_S002_SCENE_001')

    expect(await screen.findByText(/충북 충주시 중앙탑면 탑정안길 6/)).toBeInTheDocument()
  })

  it('falls back to the region when the place has no detailed address', async () => {
    vi.mocked(getSegmentByIdApi).mockResolvedValueOnce(makeSegmentWithoutAddress())

    renderAt('V001_P001_S001_SCENE_001')

    expect(await screen.findByText(/경기도/)).toBeInTheDocument()
  })

  it('shows the place name in English when the language is switched to en', async () => {
    const user = userEvent.setup()
    vi.mocked(getSegmentByIdApi).mockResolvedValueOnce(makeSegment())

    renderAt('V007_P031_S002_SCENE_001')

    await screen.findByText('충주 중앙탑공원')
    await user.click(screen.getByRole('button', { name: '메뉴' }))
    await user.click(screen.getByRole('button', { name: 'EN' }))
    expect(await screen.findByText('Chungju Jungangtap Park')).toBeInTheDocument()
  })

  it('shows the translated region instead of the untranslated Korean street address when the language is switched to en', async () => {
    // placeCoordinates517.js only has Korean addresses -- there's no
    // translated string to show for a specific street address, so a
    // non-Korean viewer should see the region (which segmentTranslations517
    // does have a real translation for) instead of raw Korean text.
    const user = userEvent.setup()
    vi.mocked(getSegmentByIdApi).mockResolvedValueOnce(makeSegment())

    renderAt('V007_P031_S002_SCENE_001')

    await screen.findByText(/충북 충주시 중앙탑면 탑정안길 6/)
    await user.click(screen.getByRole('button', { name: '메뉴' }))
    await user.click(screen.getByRole('button', { name: 'EN' }))

    expect(await screen.findByText(/Chungcheongbuk-do/)).toBeInTheDocument()
    expect(screen.queryByText(/충북 충주시 중앙탑면 탑정안길 6/)).not.toBeInTheDocument()
  })

  it('hides the image without crashing when the keyframe fails to load', async () => {
    vi.mocked(getSegmentByIdApi).mockResolvedValueOnce(makeSegment())

    renderAt('V007_P031_S002_SCENE_001')

    const img = await screen.findByRole('img', { name: '충주 중앙탑공원' })
    fireEvent.error(img)
    expect(img.style.visibility).toBe('hidden')
  })
})
