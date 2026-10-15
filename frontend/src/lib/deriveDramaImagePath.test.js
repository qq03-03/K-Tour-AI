import { describe, it, expect } from 'vitest'
import { deriveDramaImagePath } from './deriveDramaImagePath.js'

describe('deriveDramaImagePath', () => {
  it('builds the drama-images path from the video_id prefix', () => {
    expect(deriveDramaImagePath('V007_Z7u5SNDq0jw')).toBe('drama-images/V007.webp')
  })

  it('works for multi-digit prefixes', () => {
    expect(deriveDramaImagePath('V048_lqS0xAtpKVQ')).toBe('drama-images/V048.webp')
  })

  it('returns null for a video_id with no recognizable prefix', () => {
    expect(deriveDramaImagePath('not-a-real-id')).toBeNull()
  })
})
