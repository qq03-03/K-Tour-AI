// Returns one representative segment per unique place_id (first occurrence
// order). Used by SearchResults when filtering by season, where a single
// place can have dozens of matching segments and showing every one of them
// buries the actual variety of places behind repeats of the same spot.
export function dedupeByPlace(segments) {
  const seen = new Set()
  const deduped = []
  for (const segment of segments) {
    if (seen.has(segment.place_id)) continue
    seen.add(segment.place_id)
    deduped.push(segment)
  }
  return deduped
}
