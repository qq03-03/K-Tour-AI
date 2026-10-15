import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import About from './About.jsx'
import { LanguageProvider } from '../i18n/LanguageContext.jsx'

function renderAbout() {
  return render(<LanguageProvider><MemoryRouter><About /></MemoryRouter></LanguageProvider>)
}

describe('About', () => {
  it('renders both pipeline sections', () => {
    renderAbout()
    expect(screen.getByText('영상 처리 파이프라인')).toBeInTheDocument()
    expect(screen.getByText('검색 파이프라인')).toBeInTheDocument()
  })

  it('marks exactly Query Analysis as pending confirmation (RRF confirmed done per team Slack update)', () => {
    renderAbout()
    expect(screen.getAllByText('🔲 확인 필요')).toHaveLength(1)
  })

  it('marks RRF as done (6 video-pipeline steps + Vector Search + RRF)', () => {
    renderAbout()
    expect(screen.getAllByText('✅ 완료')).toHaveLength(8)
  })

  it('switches pipeline titles to English when the EN button is clicked', async () => {
    const user = userEvent.setup()
    renderAbout()
    await user.click(screen.getByRole('button', { name: '메뉴' }))
    await user.click(screen.getByRole('button', { name: 'EN' }))
    expect(screen.getByText('Video Processing Pipeline')).toBeInTheDocument()
  })
})
