import { dramaTitleTranslations } from '../data/dramaTitleTranslations.js'

export function localizeDramaTitle(title, lang) {
  if (!title) return title
  const translations = dramaTitleTranslations[title]
  if (!translations) return title
  return translations[lang] || title
}
