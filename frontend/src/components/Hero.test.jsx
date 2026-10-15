import { screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Hero from './Hero.jsx'
import { renderWithLanguage } from '../test-utils.jsx'

describe('Hero', () => {
  it('renders the tagline', () => {
    renderWithLanguage(<Hero />)
    expect(screen.getByText(/K-드라마/)).toBeInTheDocument()
  })

  it('has a fixed minimum height so switching languages does not resize the banner', () => {
    // hero_title/hero_subtitle vary in length across languages (the English
    // subtitle in particular runs noticeably longer than Korean), which can
    // wrap onto an extra line and change the banner's height. A fixed
    // min-height on the container keeps the layout stable regardless.
    const { container } = renderWithLanguage(<Hero />)
    const heroDiv = container.firstChild
    expect(heroDiv.style.minHeight).toBeTruthy()
  })
})
