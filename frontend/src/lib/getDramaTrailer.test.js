import { describe, it, expect } from 'vitest'
import { getDramaTrailer } from './getDramaTrailer.js'

describe('getDramaTrailer', () => {
  it('returns the watch and thumbnail URLs for a drama with a known trailer', () => {
    const trailer = getDramaTrailer('사랑의 불시착')
    expect(trailer).toEqual({
      youtubeId: '6-imtz9v3-g',
      watchUrl: 'https://www.youtube.com/watch?v=6-imtz9v3-g',
      thumbnailUrl: 'https://img.youtube.com/vi/6-imtz9v3-g/hqdefault.jpg',
    })
  })

  it('returns null for a drama with no trailer data', () => {
    expect(getDramaTrailer('존재하지 않는 드라마')).toBeNull()
  })

  it('returns null when dramaTitle is falsy', () => {
    expect(getDramaTrailer(null)).toBeNull()
    expect(getDramaTrailer('')).toBeNull()
  })
})
