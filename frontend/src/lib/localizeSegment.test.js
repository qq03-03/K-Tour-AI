import { describe, it, expect } from 'vitest'
import { localizeSegment } from './localizeSegment.js'
import { mockSegments } from '../data/mockSegments.js'

const sample = mockSegments.find((s) => s.segment_id === 'V007_P031_S002_SCENE_001')

describe('localizeSegment', () => {
  it('replaces localizable fields with the requested language', () => {
    const result = localizeSegment(sample, 'en')
    expect(result.drama_title).toBe('Crash Landing on You')
    expect(result.place_name).not.toBe(sample.place_name)
  })

  it('keeps non-localizable fields unchanged', () => {
    const result = localizeSegment(sample, 'en')
    expect(result.uid).toBe(sample.uid)
    expect(result.segment_id).toBe(sample.segment_id)
    expect(result.start_time).toBe(sample.start_time)
    expect(result.place_id).toBe(sample.place_id)
  })

  it('falls back to Korean when the requested language is missing from a record', () => {
    const translations = {
      [`${sample.segment_id}__${sample.segment_id}`]: {
        ko: { ...sample, description: 'ko-only description' },
      },
    }
    const result = localizeSegment(sample, 'en', translations)
    expect(result.description).toBe('ko-only description')
  })

  it('returns the original segment unchanged when no translation record exists', () => {
    const result = localizeSegment(sample, 'en', {})
    expect(result).toEqual(sample)
  })
})
