// Returns one representative segment per unique drama_title (first occurrence
// order). Used by SearchResults when filtering by season, alongside
// dedupeByPlace.js: the same drama can be filmed at several different real
// places, so deduping by place alone still leaves the same drama repeated
// across those cards.
export function dedupeByDrama(segments) {
  const seen = new Set()
  const deduped = []
  for (const segment of segments) {
    if (seen.has(segment.drama_title)) continue
    seen.add(segment.drama_title)
    deduped.push(segment)
  }
  return deduped
}
