import { describe, it, expect } from 'vitest'
import { buildVideoUrl } from './buildVideoUrl.js'

describe('buildVideoUrl', () => {
  it('appends a start-time param to a watch?v= URL that already has a query string', () => {
    expect(buildVideoUrl('https://www.youtube.com/watch?v=mCeMgl6rR-U', 202.95)).toBe(
      'https://www.youtube.com/watch?v=mCeMgl6rR-U&t=202s',
    )
  })

  it('appends a start-time param to a youtu.be URL that has no query string yet', () => {
    expect(buildVideoUrl('https://youtu.be/i2ZuU6szFWE', 13.7)).toBe(
      'https://youtu.be/i2ZuU6szFWE?t=13s',
    )
  })

  it('floors fractional seconds down to a whole number', () => {
    expect(buildVideoUrl('https://youtu.be/abc', 9.99)).toBe('https://youtu.be/abc?t=9s')
  })

  it('uses t=0s for a segment that starts at the very beginning', () => {
    expect(buildVideoUrl('https://youtu.be/abc', 0)).toBe('https://youtu.be/abc?t=0s')
  })
})
