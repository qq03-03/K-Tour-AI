import { describe, it, expect } from 'vitest'
import { deriveVideoUrlFromVideoId } from './deriveVideoUrlFromVideoId.js'

describe('deriveVideoUrlFromVideoId', () => {
  it('extracts the youtube_id from a 517-dataset video_id and builds a watch URL', () => {
    expect(deriveVideoUrlFromVideoId('V007_Z7u5SNDq0jw')).toBe('https://www.youtube.com/watch?v=Z7u5SNDq0jw')
  })

  it('handles youtube_ids that contain a leading underscore or hyphen', () => {
    expect(deriveVideoUrlFromVideoId('V045__fmhzDFTIH8')).toBe('https://www.youtube.com/watch?v=_fmhzDFTIH8')
    expect(deriveVideoUrlFromVideoId('V052_URa5-lfWhII')).toBe('https://www.youtube.com/watch?v=URa5-lfWhII')
  })

  it('returns null for old-style video_ids with no embedded youtube_id', () => {
    expect(deriveVideoUrlFromVideoId('GOBLIN_01')).toBe(null)
    expect(deriveVideoUrlFromVideoId('kingdom_gyeongbok_01')).toBe(null)
  })
})
