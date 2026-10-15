import { describe, it, expect } from 'vitest'
import { localizeDramaTitle } from './localizeDramaTitle.js'

describe('localizeDramaTitle', () => {
  it('returns the official English title when translated', () => {
    expect(localizeDramaTitle('사랑의 불시착', 'en')).toBe('Crash Landing on You')
  })

  it('returns the official Japanese and Chinese titles when translated', () => {
    expect(localizeDramaTitle('도깨비', 'ja')).toBe('トッケビ')
    expect(localizeDramaTitle('도깨비', 'zh')).toBe('孤单又灿烂的神—鬼怪')
  })

  it('returns the original Korean title for lang "ko", even for a title whose catalog ko label differs (e.g. a nickname)', () => {
    expect(localizeDramaTitle('선재 업고 튀어', 'ko')).toBe('선재 업고 튀어')
  })

  it('returns the original title unchanged for a drama with no translation entry', () => {
    expect(localizeDramaTitle('존재하지 않는 드라마', 'en')).toBe('존재하지 않는 드라마')
  })

  it('returns the original title unchanged for a falsy title', () => {
    expect(localizeDramaTitle('', 'en')).toBe('')
    expect(localizeDramaTitle(null, 'en')).toBe(null)
  })
})
