import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import DramaSection from './DramaSection.jsx'
import { mockSegments } from '../data/mockSegments.js'
import { renderWithLanguage } from '../test-utils.jsx'

describe('DramaSection', () => {
  it('renders real drama titles from mockSegments', () => {
    renderWithLanguage(<MemoryRouter><DramaSection /></MemoryRouter>)
    expect(screen.getByText('폭싹 속았수다')).toBeInTheDocument()
    expect(screen.getByText('도깨비')).toBeInTheDocument()
  })

  it('shows every distinct drama/movie in mockSegments, not just a capped top few', () => {
    renderWithLanguage(<MemoryRouter><DramaSection /></MemoryRouter>)
    const uniqueDramaCount = new Set(mockSegments.map((s) => s.drama_title)).size
    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(uniqueDramaCount)
  })

  it('links each drama to a search filtered to every scene from that drama', () => {
    // Clicking a drama card used to go straight to one representative
    // scene's detail page -- but a drama can have dozens of segments, and
    // the single-scene link gave no way to see the rest. Linking to
    // /search?drama=<title> instead routes through SearchResults' drama
    // browsing mode, which fetches every matching scene unranked.
    renderWithLanguage(<MemoryRouter><DramaSection /></MemoryRouter>)
    const links = screen.getAllByRole('link')
    expect(links.length).toBeGreaterThan(0)
    for (const link of links) {
      expect(link.getAttribute('href')).toMatch(/^\/search\?drama=/)
    }
  })

  it('URL-encodes the drama title in the link', () => {
    renderWithLanguage(<MemoryRouter><DramaSection /></MemoryRouter>)
    const links = screen.getAllByRole('link')
    const hotelDelLuna = links.find((link) => link.textContent.includes('호텔 델루나'))
    expect(hotelDelLuna.getAttribute('href')).toBe(`/search?drama=${encodeURIComponent('호텔 델루나')}`)
  })

  it('links to the Korean drama_title even when the display language is English (the backend only matches the Korean value)', () => {
    // Regression test: the link used to build its href from the already-
    // localized segment (localizeSegment swaps drama_title to the English
    // title), so in English every drama card linked to a title the backend
    // couldn't match at all -- clicking any card in en/ja/zh returned zero
    // results. The visible card text should still be translated; only the
    // link target must stay Korean.
    window.localStorage.setItem('ktourai_lang', 'en')
    renderWithLanguage(<MemoryRouter><DramaSection /></MemoryRouter>)

    expect(screen.getByText('Crash Landing on You')).toBeInTheDocument()
    const links = screen.getAllByRole('link')
    const crashLanding = links.find((link) => link.textContent === 'Crash Landing on You')
    expect(crashLanding.getAttribute('href')).toBe(`/search?drama=${encodeURIComponent('사랑의 불시착')}`)
  })

  it('hides an image without crashing when the image fails to load', () => {
    renderWithLanguage(<MemoryRouter><DramaSection /></MemoryRouter>)
    const [firstImage] = screen.getAllByRole('img')
    fireEvent.error(firstImage)
    expect(firstImage.style.visibility).toBe('hidden')
  })

  it('uses the team-provided main image (drama-images/{video_id prefix}.webp) instead of a scene keyframe', () => {
    renderWithLanguage(<MemoryRouter><DramaSection /></MemoryRouter>)
    const images = screen.getAllByRole('img')
    for (const image of images) {
      expect(image.getAttribute('src')).toMatch(/drama-images\/V\d+\.webp$/)
    }
  })
})
