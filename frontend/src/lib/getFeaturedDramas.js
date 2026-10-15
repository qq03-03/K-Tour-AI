// Returns one representative segment per unique drama_title (first occurrence
// order), capped at `limit`. Used by DramaSection so the homepage shows real
// dramas from mockSegments.js instead of a hardcoded list.
export function getFeaturedDramas(segments, limit = 6) {
  const seen = new Set()
  const featured = []
  for (const segment of segments) {
    if (seen.has(segment.drama_title)) continue
    seen.add(segment.drama_title)
    featured.push(segment)
    if (featured.length >= limit) break
  }
  return featured
}
