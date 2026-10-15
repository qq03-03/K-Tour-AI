import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { strings } from './strings.js'

const STORAGE_KEY = 'ktourai_lang'
const SUPPORTED_LANGUAGES = ['ko', 'en', 'ja', 'zh']
const DEFAULT_LANGUAGE = 'ko'

const LanguageContext = createContext(null)

function readStoredLanguage() {
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return SUPPORTED_LANGUAGES.includes(stored) ? stored : DEFAULT_LANGUAGE
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(readStoredLanguage)

  const setLang = useCallback((next) => {
    if (!SUPPORTED_LANGUAGES.includes(next)) return
    window.localStorage.setItem(STORAGE_KEY, next)
    setLangState(next)
  }, [])

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const t = useCallback(
    (key, params) => {
      const template = strings[lang]?.[key] ?? strings[DEFAULT_LANGUAGE][key] ?? key
      if (!params) return template
      return Object.entries(params).reduce(
        (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
        template,
      )
    },
    [lang],
  )

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (!context) throw new Error('useLanguage must be used within a LanguageProvider')
  return context
}
