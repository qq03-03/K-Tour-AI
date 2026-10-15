import { render } from '@testing-library/react'
import { LanguageProvider } from './i18n/LanguageContext.jsx'

export function renderWithLanguage(ui) {
  return render(<LanguageProvider>{ui}</LanguageProvider>)
}
