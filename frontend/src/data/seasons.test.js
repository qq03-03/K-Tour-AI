import { describe, it, expect } from 'vitest'
import { seasons } from './seasons.js'

describe('seasons', () => {
  it('every season has all 4 languages with non-empty labels', () => {
    for (const season of seasons) {
      for (const lang of ['ko', 'en', 'ja', 'zh']) {
        expect(season.label[lang], `${season.id}.${lang}`).toBeTruthy()
      }
    }
  })
})
