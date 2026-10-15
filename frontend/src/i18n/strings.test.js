import { describe, it, expect } from 'vitest'
import { strings } from './strings.js'

describe('strings', () => {
  const languages = ['ko', 'en', 'ja', 'zh']

  it('defines the same keys in every language', () => {
    const koKeys = Object.keys(strings.ko).sort()
    for (const lang of languages) {
      expect(Object.keys(strings[lang]).sort(), lang).toEqual(koKeys)
    }
  })

  it('has no empty string values', () => {
    for (const lang of languages) {
      for (const [key, value] of Object.entries(strings[lang])) {
        expect(value.length > 0, `${lang}.${key}`).toBe(true)
      }
    }
  })
})
