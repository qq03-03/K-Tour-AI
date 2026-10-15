import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import Home from './Home.jsx'
import { LanguageProvider } from '../i18n/LanguageContext.jsx'

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname}{location.search}</div>
}

function renderHome() {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<LocationDisplay />} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
}

describe('Home', () => {
  it('renders the hero tagline and search bar', () => {
    renderHome()
    expect(screen.getByText(/K-드라마/)).toBeInTheDocument()
    expect(screen.getByPlaceholderText('여행지를 검색해보세요...')).toBeInTheDocument()
  })

  it('navigates to /search?q=... when a search is submitted', async () => {
    const user = userEvent.setup()
    renderHome()
    await user.type(screen.getByPlaceholderText('여행지를 검색해보세요...'), 'lotus{Enter}')
    expect(screen.getByTestId('location')).toHaveTextContent('/search?q=lotus')
  })

  it('navigates to /search?season=... when a season chip is clicked', async () => {
    const user = userEvent.setup()
    renderHome()
    await user.click(screen.getByText('여름'))
    expect(screen.getByTestId('location')).toHaveTextContent('/search?season=summer')
  })
})
