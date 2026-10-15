import { describe, it, expect } from 'vitest'
import { normalizeThemeId } from './normalizeThemeId.js'

describe('normalizeThemeId', () => {
  it('maps each legacy dash-separated id to its canonical underscore id', () => {
    expect(normalizeThemeId('night-view')).toBe('night_view')
    expect(normalizeThemeId('cherry-blossom')).toBe('flower')
    expect(normalizeThemeId('autumn-leaves')).toBe('autumn_leaves')
    expect(normalizeThemeId('beach')).toBe('sea')
  })

  it('returns already-canonical ids unchanged', () => {
    expect(normalizeThemeId('traditional')).toBe('traditional')
    expect(normalizeThemeId('drive')).toBe('drive')
  })

  it('returns unrecognized ids unchanged (caller decides how to handle)', () => {
    expect(normalizeThemeId('does-not-exist')).toBe('does-not-exist')
  })
})
