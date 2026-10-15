import { describe, it, expect } from 'vitest'
import { getFeaturedDramas } from './getFeaturedDramas.js'

const fixtures = [
  { drama_title: '도깨비', keyframe_path: 'keyframes/GOBLIN_01/GOBLIN_01_SCENE_01.jpg' },
  { drama_title: '도깨비', keyframe_path: 'keyframes/GOBLIN_02/GOBLIN_02_SCENE_01.jpg' },
  { drama_title: '킹덤', keyframe_path: 'keyframes/kingdom_gyeongbok_01/kingdom_gyeongbok_01_SCENE_01.jpg' },
  { drama_title: '호텔 델루나', keyframe_path: 'keyframes/hotel_deluna_mangsang_02/hotel_deluna_mangsang_02_SCENE_01.jpg' },
]

describe('getFeaturedDramas', () => {
  it('returns one representative segment per unique drama_title', () => {
    const result = getFeaturedDramas(fixtures)
    expect(result.map((s) => s.drama_title)).toEqual(['도깨비', '킹덤', '호텔 델루나'])
  })

  it('keeps the first occurrence of each drama as the representative', () => {
    const result = getFeaturedDramas(fixtures)
    expect(result[0].keyframe_path).toBe('keyframes/GOBLIN_01/GOBLIN_01_SCENE_01.jpg')
  })

  it('caps the result at the given limit', () => {
    const result = getFeaturedDramas(fixtures, 2)
    expect(result).toHaveLength(2)
  })
})
