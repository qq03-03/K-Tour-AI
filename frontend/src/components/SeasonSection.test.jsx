import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import SeasonSection from './SeasonSection.jsx'
import { renderWithLanguage } from '../test-utils.jsx'

describe('SeasonSection', () => {
  it('renders all 4 season chips in Korean by default', () => {
    renderWithLanguage(<SeasonSection selectedId={null} onSelect={() => {}} />)
    expect(screen.getByText('봄')).toBeInTheDocument()
    expect(screen.getByText('여름')).toBeInTheDocument()
    expect(screen.getByText('가을')).toBeInTheDocument()
    expect(screen.getByText('겨울')).toBeInTheDocument()
  })

  it('calls onSelect with the season id when a chip is clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    renderWithLanguage(<SeasonSection selectedId={null} onSelect={onSelect} />)
    await user.click(screen.getByText('여름'))
    expect(onSelect).toHaveBeenCalledWith('summer')
  })

  it('calls onSelect with null when the selected chip is clicked again', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    renderWithLanguage(<SeasonSection selectedId="summer" onSelect={onSelect} />)
    await user.click(screen.getByText('여름'))
    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it('renders season chips in English when the language is set to en', () => {
    window.localStorage.setItem('ktourai_lang', 'en')
    renderWithLanguage(<SeasonSection selectedId={null} onSelect={() => {}} />)
    expect(screen.getByText('Spring')).toBeInTheDocument()
  })
})
