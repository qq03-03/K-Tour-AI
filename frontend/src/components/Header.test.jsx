import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import Header from './Header.jsx'
import { renderWithLanguage } from '../test-utils.jsx'

describe('Header', () => {
  it('renders the logo text', () => {
    renderWithLanguage(<MemoryRouter><Header /></MemoryRouter>)
    expect(screen.getByText('K-Tour AI')).toBeInTheDocument()
  })

  it('hides the nav links and language buttons until the hamburger menu is opened', () => {
    renderWithLanguage(<MemoryRouter><Header /></MemoryRouter>)
    expect(screen.queryByRole('link', { name: '홈' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'EN' })).not.toBeInTheDocument()
  })

  it('shows nav labels in Korean by default after opening the menu', async () => {
    const user = userEvent.setup()
    renderWithLanguage(<MemoryRouter><Header /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: '메뉴' }))
    expect(screen.getByRole('link', { name: '홈' })).toHaveAttribute('href', '/')
  })

  it('localizes the hamburger button aria-label instead of always saying "메뉴"', async () => {
    window.localStorage.setItem('ktourai_lang', 'en')
    renderWithLanguage(<MemoryRouter><Header /></MemoryRouter>)
    expect(screen.getByRole('button', { name: 'Menu' })).toBeInTheDocument()
  })

  it('does not show a 소개 (about) link in the menu', async () => {
    const user = userEvent.setup()
    renderWithLanguage(<MemoryRouter><Header /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: '메뉴' }))
    expect(screen.queryByRole('link', { name: '소개' })).not.toBeInTheDocument()
  })

  it('switches nav labels to English when the EN button is clicked', async () => {
    const user = userEvent.setup()
    renderWithLanguage(<MemoryRouter><Header /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: '메뉴' }))
    await user.click(screen.getByRole('button', { name: 'EN' }))
    expect(screen.getByRole('link', { name: 'Home' })).toBeInTheDocument()
  })

  it('closes the menu again when the hamburger button is clicked a second time', async () => {
    const user = userEvent.setup()
    renderWithLanguage(<MemoryRouter><Header /></MemoryRouter>)
    const menuButton = screen.getByRole('button', { name: '메뉴' })
    await user.click(menuButton)
    expect(screen.getByRole('link', { name: '홈' })).toBeInTheDocument()
    await user.click(menuButton)
    expect(screen.queryByRole('link', { name: '홈' })).not.toBeInTheDocument()
  })

  it('closes the menu after a nav link is clicked', async () => {
    const user = userEvent.setup()
    renderWithLanguage(<MemoryRouter><Header /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: '메뉴' }))
    await user.click(screen.getByRole('link', { name: '홈' }))
    expect(screen.queryByRole('link', { name: '홈' })).not.toBeInTheDocument()
  })

  it('shows a 검색 조건 link that opens the filter panel, going to a fresh /search when not already there', async () => {
    const user = userEvent.setup()
    renderWithLanguage(<MemoryRouter><Header /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: '메뉴' }))
    const link = screen.getByRole('link', { name: '검색 조건' })
    const href = link.getAttribute('href')
    expect(href.startsWith('/search?')).toBe(true)
    expect(new URLSearchParams(href.split('?')[1]).get('openFilter')).toBeTruthy()
  })

  it('preserves the current search filters in the 검색 조건 link when already on /search', async () => {
    const user = userEvent.setup()
    renderWithLanguage(
      <MemoryRouter initialEntries={['/search?seasons=summer&genres=horror']}>
        <Header />
      </MemoryRouter>,
    )
    await user.click(screen.getByRole('button', { name: '메뉴' }))
    const link = screen.getByRole('link', { name: '검색 조건' })
    const params = new URLSearchParams(link.getAttribute('href').split('?')[1])
    expect(params.get('seasons')).toBe('summer')
    expect(params.get('genres')).toBe('horror')
    expect(params.get('openFilter')).toBeTruthy()
  })
})
