import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Footer from './Footer.jsx'

describe('Footer', () => {
  it('renders a copyright line', () => {
    render(<Footer />)
    expect(screen.getByText(/K-Tour AI/)).toBeInTheDocument()
  })
})
