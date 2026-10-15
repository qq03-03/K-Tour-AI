import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import EmptyState from './EmptyState.jsx'

describe('EmptyState', () => {
  it('renders the given message', () => {
    render(<EmptyState message="검색 결과가 없어요" />)
    expect(screen.getByText('검색 결과가 없어요')).toBeInTheDocument()
  })
})
