import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, beforeEach } from 'vitest'
import { LanguageProvider, useLanguage } from './LanguageContext.jsx'

const STORAGE_KEY = 'ktourai_lang'

function Consumer() {
  const { lang, setLang, t } = useLanguage()
  return (
    <div>
      <span data-testid="lang">{lang}</span>
      <span data-testid="translated">{t('nav_home')}</span>
      <span data-testid="interpolated">{t('results_count', { n: 3 })}</span>
      <button onClick={() => setLang('en')}>switch to en</button>
    </div>
  )
}

describe('LanguageContext', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('defaults to Korean when nothing is stored', () => {
    render(<LanguageProvider><Consumer /></LanguageProvider>)
    expect(screen.getByTestId('lang')).toHaveTextContent('ko')
    expect(screen.getByTestId('translated')).toHaveTextContent('홈')
  })

  it('reads a previously stored language', () => {
    window.localStorage.setItem(STORAGE_KEY, 'ja')
    render(<LanguageProvider><Consumer /></LanguageProvider>)
    expect(screen.getByTestId('lang')).toHaveTextContent('ja')
  })

  it('updates language and persists it on setLang', async () => {
    const user = userEvent.setup()
    render(<LanguageProvider><Consumer /></LanguageProvider>)
    await user.click(screen.getByRole('button', { name: 'switch to en' }))
    expect(screen.getByTestId('lang')).toHaveTextContent('en')
    expect(screen.getByTestId('translated')).toHaveTextContent('Home')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('en')
  })

  it('interpolates {n} placeholders', () => {
    render(<LanguageProvider><Consumer /></LanguageProvider>)
    expect(screen.getByTestId('interpolated')).toHaveTextContent('검색 결과 3건')
  })
})
