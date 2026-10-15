import { describe, it, expect } from 'vitest'
import { placeCoordinates517 } from './placeCoordinates517.js'

describe('placeCoordinates517', () => {
  it('has exactly 74 entries', () => {
    expect(Object.keys(placeCoordinates517)).toHaveLength(74)
  })

  it('keys every entry by the real backend place_id, unprefixed', () => {
    for (const key of Object.keys(placeCoordinates517)) {
      expect(key.startsWith('N-'), key).toBe(false)
      expect(key, key).toMatch(/^P\d+$/)
    }
  })

  it('every entry has a place_name and numeric coordinates', () => {
    for (const [key, coord] of Object.entries(placeCoordinates517)) {
      expect(typeof coord.place_name, key).toBe('string')
      expect(typeof coord.latitude, key).toBe('number')
      expect(typeof coord.longitude, key).toBe('number')
    }
  })

  it('includes a detailed street address for the places that have one (omits the key rather than storing an empty string)', () => {
    const withAddress = Object.values(placeCoordinates517).filter((c) => 'address' in c)
    expect(withAddress.length).toBeGreaterThan(0)
    for (const coord of withAddress) {
      expect(typeof coord.address).toBe('string')
      expect(coord.address.length).toBeGreaterThan(0)
    }
    const withoutAddress = Object.values(placeCoordinates517).filter((c) => !('address' in c))
    expect(withAddress.length + withoutAddress.length).toBe(Object.keys(placeCoordinates517).length)
  })
})
