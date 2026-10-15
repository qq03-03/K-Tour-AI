import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import SearchFilterPanel from './SearchFilterPanel.jsx'
import { renderWithLanguage } from '../test-utils.jsx'

function setup(props = {}) {
  const onApply = vi.fn()
  const onClose = vi.fn()
  renderWithLanguage(
    <SearchFilterPanel
      seasons={[]}
      themeIds={[]}
      genres={[]}
      regions={[]}
      dramas={[]}
      onApply={onApply}
      onClose={onClose}
      {...props}
    />,
  )
  return { onApply, onClose }
}

describe('SearchFilterPanel', () => {
  it('shows a live summary of the currently selected filters next to the panel title', () => {
    setup({ seasons: ['summer'], regions: ['서울특별시'] })
    expect(screen.getByText('여름 · 서울특별시')).toBeInTheDocument()
  })

  it('updates the summary immediately when a pill is toggled, before Apply is clicked', async () => {
    const user = userEvent.setup()
    setup({ seasons: ['summer'] })

    expect(screen.getByTestId('filter-selection-summary')).toHaveTextContent('여름')

    await user.click(screen.getByRole('button', { name: '공포' }))

    expect(screen.getByText('여름 · 공포')).toBeInTheDocument()
  })

  it('shows nothing for the summary when no filters are selected', () => {
    setup()
    expect(screen.queryByTestId('filter-selection-summary')).not.toBeInTheDocument()
  })

  it('renders season, theme, genre, region, and drama sections as home-screen-style pill/card buttons', () => {
    setup()
    expect(screen.getByText('계절')).toBeInTheDocument()
    expect(screen.getByText('테마')).toBeInTheDocument()
    expect(screen.getByText('장르')).toBeInTheDocument()
    expect(screen.getByText('지역')).toBeInTheDocument()
    expect(screen.getByText('드라마·영화')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '여름' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '야경' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '공포' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '서울특별시' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '선재 업고 튀어' })).toBeInTheDocument()
  })

  it('shows drama cards with a cover image', () => {
    setup()
    const card = screen.getByRole('button', { name: '사랑의 불시착' })
    expect(card.querySelector('img')).toBeInTheDocument()
  })

  it('marks the boxes matching the current selection as pressed', () => {
    setup({ seasons: ['summer'], themeIds: ['flower'], genres: ['horror'], regions: ['서울특별시'] })
    expect(screen.getByRole('button', { name: '여름' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '꽃' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '공포' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '서울특별시' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '봄' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('calls onApply with the selected season, theme, genre, and region ids when submitted', async () => {
    const user = userEvent.setup()
    const { onApply } = setup()

    await user.click(screen.getByRole('button', { name: '여름' }))
    await user.click(screen.getByRole('button', { name: '야경' }))
    await user.click(screen.getByRole('button', { name: '공포' }))
    await user.click(screen.getByRole('button', { name: '서울특별시' }))
    await user.click(screen.getByRole('button', { name: '선택 조건으로 찾기' }))

    expect(onApply).toHaveBeenCalledWith({
      seasons: ['summer'],
      themeIds: ['night_view'],
      genres: ['horror'],
      regions: ['서울특별시'],
      dramas: [],
    })
  })

  it('toggles a season pill back off when clicked a second time', async () => {
    const user = userEvent.setup()
    const { onApply } = setup({ seasons: ['summer'] })

    await user.click(screen.getByRole('button', { name: '여름' }))
    await user.click(screen.getByRole('button', { name: '선택 조건으로 찾기' }))

    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ seasons: [] }))
  })

  it('clears every selection back to unpressed when the reset button is clicked', async () => {
    const user = userEvent.setup()
    setup({ seasons: ['summer'], themeIds: ['night_view'], genres: ['horror'], regions: ['서울특별시'], dramas: ['선재 업고 튀어'] })

    await user.click(screen.getByRole('button', { name: '초기화' }))

    expect(screen.getByRole('button', { name: '여름' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: '야경' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: '공포' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: '서울특별시' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: '선재 업고 튀어' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('reset does not call onApply or onClose by itself', async () => {
    const user = userEvent.setup()
    const { onApply, onClose } = setup({ seasons: ['summer'] })

    await user.click(screen.getByRole('button', { name: '초기화' }))

    expect(onApply).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('filters the drama card list by the title search box', async () => {
    const user = userEvent.setup()
    setup()

    expect(screen.getByRole('button', { name: '선재 업고 튀어' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '사랑의 불시착' })).toBeInTheDocument()

    await user.type(screen.getByPlaceholderText('제목·별칭 검색'), '불시착')

    expect(screen.getByRole('button', { name: '사랑의 불시착' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '선재 업고 튀어' })).not.toBeInTheDocument()
  })

  it('filters the drama card list by the displayed (localized) title, not just the raw Korean title', async () => {
    // Bug report: the search box matched only the raw Korean drama_title, but
    // the cards display the translated title in non-Korean languages -- so
    // typing the exact name shown on screen ("Crash Landing on You") found
    // nothing, because the underlying data is still "사랑의 불시착".
    const user = userEvent.setup()
    window.localStorage.setItem('ktourai_lang', 'en')
    setup()

    expect(screen.getByRole('button', { name: 'Crash Landing on You' })).toBeInTheDocument()

    await user.type(screen.getByPlaceholderText('Search by title or alias'), 'Crash Landing')

    expect(screen.getByRole('button', { name: 'Crash Landing on You' })).toBeInTheDocument()
  })

  it('calls onClose when the close button is clicked', async () => {
    const user = userEvent.setup()
    const { onClose } = setup()

    await user.click(screen.getByRole('button', { name: '닫기' }))

    expect(onClose).toHaveBeenCalled()
  })
})
