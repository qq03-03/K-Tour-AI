import { describe, it, expect } from 'vitest'
import { placeCoordinates } from './placeCoordinates.js'
import { placeCoordinates517 } from './placeCoordinates517.js'

describe('placeCoordinates', () => {
  it('re-exports placeCoordinates517 (the only coordinate source now that the original 45-segment dataset was removed)', () => {
    expect(placeCoordinates).toBe(placeCoordinates517)
  })
})
