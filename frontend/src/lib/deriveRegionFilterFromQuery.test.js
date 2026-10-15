import { describe, it, expect } from 'vitest'
import { deriveRegionFilterFromQuery } from './deriveRegionFilterFromQuery.js'

describe('deriveRegionFilterFromQuery', () => {
  it('returns the region list for a recognized colloquial grouping', () => {
    expect(deriveRegionFilterFromQuery('경상도')).toEqual([
      '부산광역시', '대구광역시', '울산광역시', '경상북도', '경상남도',
    ])
  })

  it('matches the term as a substring of a longer query', () => {
    expect(deriveRegionFilterFromQuery('경상도 가을 여행지')).toEqual([
      '부산광역시', '대구광역시', '울산광역시', '경상북도', '경상남도',
    ])
  })

  it('matches an alternate term for the same grouping', () => {
    expect(deriveRegionFilterFromQuery('경상권 벚꽃')).toEqual([
      '부산광역시', '대구광역시', '울산광역시', '경상북도', '경상남도',
    ])
  })

  it('returns null for a query with no recognized region grouping', () => {
    expect(deriveRegionFilterFromQuery('가을 단풍길')).toBeNull()
  })

  it('returns null for an empty or whitespace-only query', () => {
    expect(deriveRegionFilterFromQuery('')).toBeNull()
    expect(deriveRegionFilterFromQuery('   ')).toBeNull()
  })

  it('hard-filters a literal administrative region name to itself', () => {
    // The backend ranks free text by CLIP semantic similarity, not by an
    // exact match on the region column -- so searching the literal region
    // name "경상북도" without a hard filter can still surface other regions
    // (e.g. Seoul) that score highly on semantic similarity. It must be
    // hard-filtered to itself, the same as a colloquial grouping term.
    expect(deriveRegionFilterFromQuery('경상북도')).toEqual(['경상북도'])
  })

  it('hard-filters the exact region name reported in the Seoul bug report', () => {
    expect(deriveRegionFilterFromQuery('서울특별시')).toEqual(['서울특별시'])
  })

  it('hard-filters every canonical region name present in the dataset', () => {
    const canonicalRegions = [
      '서울특별시', '경기도', '인천광역시', '부산광역시', '대구광역시',
      '경상북도', '경상남도', '전북특별자치도', '전라남도',
      '충청북도', '충청남도', '강원특별자치도', '제주특별자치도',
    ]
    for (const region of canonicalRegions) {
      expect(deriveRegionFilterFromQuery(region), region).toEqual([region])
    }
  })

  it('hard-filters a common short form of a region name', () => {
    expect(deriveRegionFilterFromQuery('서울 데이트 코스')).toEqual(['서울특별시'])
    expect(deriveRegionFilterFromQuery('부산 여행지')).toEqual(['부산광역시'])
  })

  it('hard-filters the shortened colloquial form of a region grouping, not just its full form', () => {
    // Bug report: searching "경상" or "전라" (the common 2-syllable short
    // form, dropping 도/권) fell through to plain CLIP search and surfaced
    // unrelated regions like Seoul and Gangwon-do, even though the full
    // "경상도"/"전라도" form was already hard-filtered correctly.
    expect(deriveRegionFilterFromQuery('경상')).toEqual([
      '부산광역시', '대구광역시', '울산광역시', '경상북도', '경상남도',
    ])
    expect(deriveRegionFilterFromQuery('전라')).toEqual([
      '광주광역시', '전북특별자치도', '전라남도',
    ])
    expect(deriveRegionFilterFromQuery('충청')).toEqual([
      '대전광역시', '세종특별자치시', '충청북도', '충청남도',
    ])
  })
})
