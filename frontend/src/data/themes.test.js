import { describe, it, expect } from 'vitest'
import { themes } from './themes.js'

describe('themes', () => {
  it('every theme has all 4 languages with non-empty labels', () => {
    for (const theme of themes) {
      for (const lang of ['ko', 'en', 'ja', 'zh']) {
        expect(theme.label[lang], `${theme.id}.${lang}`).toBeTruthy()
      }
    }
  })
})
