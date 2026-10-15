import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import ResultCard from './ResultCard.jsx'

const segment = {
  segment_id: 'V008_P013_S001',
  uid: 'keyframes_GOBLIN_01_GOBLIN_01_SCENE_01_jpg',
  place_name: 'seaside',
  region: '강원특별자치도',
  drama_title: '도깨비',
  description: 'A man and a woman stand on a rocky pier by the ocean, facing each other with waves crashing in the background.',
  start_time: 198.0,
  end_time: 207.0,
  keyframe_path: 'keyframes/GOBLIN_01/GOBLIN_01_SCENE_01.jpg',
  similarity: 0.92,
}

describe('ResultCard', () => {
  it('renders the place name and drama title', () => {
    render(<MemoryRouter><ResultCard segment={segment} /></MemoryRouter>)
    expect(screen.getByText('seaside')).toBeInTheDocument()
    expect(screen.getByText(/도깨비/)).toBeInTheDocument()
  })

  it('does not show a similarity percentage badge', () => {
    // The score badge always read 100% for theme/season/drama browsing
    // (backend returns a synthetic 0.0 for those, and this card rounded
    // any input to a percent), so it looked like a real relevance ranking
    // when it wasn't one -- misleading rather than informative.
    render(<MemoryRouter><ResultCard segment={segment} /></MemoryRouter>)
    expect(screen.queryByText('92%')).not.toBeInTheDocument()
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })

  it('resolves the image src under the configured base path', () => {
    render(<MemoryRouter><ResultCard segment={segment} /></MemoryRouter>)
    const src = screen.getByRole('img').getAttribute('src')
    expect(src.endsWith('keyframes/GOBLIN_01/GOBLIN_01_SCENE_01.jpg')).toBe(true)
    expect(src.includes('//keyframes')).toBe(false)
  })

  it('links to the detail page using the unique uid, not the (possibly duplicated) segment_id', () => {
    render(<MemoryRouter><ResultCard segment={segment} /></MemoryRouter>)
    expect(screen.getByRole('link')).toHaveAttribute('href', '/segment/keyframes_GOBLIN_01_GOBLIN_01_SCENE_01_jpg')
  })

  it('hides the image without crashing when the keyframe fails to load', () => {
    render(<MemoryRouter><ResultCard segment={segment} /></MemoryRouter>)
    const img = screen.getByRole('img')
    fireEvent.error(img)
    expect(img.style.visibility).toBe('hidden')
  })
})
