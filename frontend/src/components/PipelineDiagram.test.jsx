import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import PipelineDiagram from './PipelineDiagram.jsx'

const steps = [
  { icon: '🎬', label: '영상', status: 'done', statusLabel: '✅ 완료' },
  { icon: '🔀', label: 'RRF', status: 'pending', statusLabel: '🔲 확인 필요' },
]

describe('PipelineDiagram', () => {
  it('renders the title and every step label', () => {
    render(<PipelineDiagram title="검색 파이프라인" steps={steps} />)
    expect(screen.getByText('검색 파이프라인')).toBeInTheDocument()
    expect(screen.getByText('영상')).toBeInTheDocument()
    expect(screen.getByText('RRF')).toBeInTheDocument()
  })

  it('renders the status label for each step', () => {
    render(<PipelineDiagram title="검색 파이프라인" steps={steps} />)
    expect(screen.getByText('✅ 완료')).toBeInTheDocument()
    expect(screen.getByText('🔲 확인 필요')).toBeInTheDocument()
  })
})
