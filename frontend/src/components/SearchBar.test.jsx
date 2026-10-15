import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import SearchBar from './SearchBar.jsx'
import { renderWithLanguage } from '../test-utils.jsx'

describe('SearchBar', () => {
  it('calls onSearch with the typed value when Enter is pressed', async () => {
    const user = userEvent.setup()
    const onSearch = vi.fn()
    renderWithLanguage(<SearchBar onSearch={onSearch} />)
    const input = screen.getByPlaceholderText('여행지를 검색해보세요...')
    await user.type(input, 'lotus pond{Enter}')
    expect(onSearch).toHaveBeenCalledWith('lotus pond')
  })

  it('calls onSearch when the search button is clicked', async () => {
    const user = userEvent.setup()
    const onSearch = vi.fn()
    renderWithLanguage(<SearchBar onSearch={onSearch} />)
    const input = screen.getByPlaceholderText('여행지를 검색해보세요...')
    await user.type(input, 'duck')
    await user.click(screen.getByRole('button', { name: '검색' }))
    expect(onSearch).toHaveBeenCalledWith('duck')
  })

  it('pre-fills the input from initialValue', () => {
    renderWithLanguage(<SearchBar initialValue="autumn trail" onSearch={() => {}} />)
    expect(screen.getByPlaceholderText('여행지를 검색해보세요...')).toHaveValue('autumn trail')
  })
})
