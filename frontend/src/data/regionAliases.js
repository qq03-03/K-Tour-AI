// Maps colloquial/historical region groupings to the specific administrative
// region names used in mockSegments.js, so a search for e.g. "경상도" finds
// segments tagged with the modern region name (e.g. "부산광역시") even though
// that exact string never appears in the segment's own text.
//
// The single-region entries below exist for a related but distinct reason:
// the backend ranks free text by CLIP semantic similarity, not by an exact
// match on the region column, so even searching a region's own literal name
// (e.g. "서울특별시") isn't guaranteed to return only that region -- it can
// still surface other regions that happen to score highly on semantic
// similarity. Every canonical region name (and its common short form) is
// listed here so it gets hard-filtered to itself, the same as a colloquial
// grouping term.
export const regionAliases = [
  { terms: ['경상도', '경상권', '경상'], regions: ['부산광역시', '대구광역시', '울산광역시', '경상북도', '경상남도'] },
  { terms: ['전라도', '호남', '전라'], regions: ['광주광역시', '전북특별자치도', '전라남도'] },
  { terms: ['충청도', '충청권', '충청'], regions: ['대전광역시', '세종특별자치시', '충청북도', '충청남도'] },
  { terms: ['수도권'], regions: ['서울특별시', '경기도', '인천광역시'] },
  { terms: ['서울특별시', '서울'], regions: ['서울특별시'] },
  { terms: ['경기도', '경기'], regions: ['경기도'] },
  { terms: ['인천광역시', '인천'], regions: ['인천광역시'] },
  { terms: ['부산광역시', '부산'], regions: ['부산광역시'] },
  { terms: ['대구광역시', '대구'], regions: ['대구광역시'] },
  { terms: ['경상북도', '경북'], regions: ['경상북도'] },
  { terms: ['경상남도', '경남'], regions: ['경상남도'] },
  { terms: ['전북특별자치도', '전북'], regions: ['전북특별자치도'] },
  { terms: ['전라남도', '전남'], regions: ['전라남도'] },
  { terms: ['충청북도', '충북'], regions: ['충청북도'] },
  { terms: ['충청남도', '충남'], regions: ['충청남도'] },
  { terms: ['강원도', '강원특별자치도', '강원'], regions: ['강원특별자치도'] },
  { terms: ['제주도', '제주특별자치도', '제주'], regions: ['제주특별자치도'] },
]
