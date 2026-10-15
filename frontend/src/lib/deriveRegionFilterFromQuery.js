import { regionAliases } from '../data/regionAliases.js'

// The real search backend ranks free text by CLIP semantic similarity, which
// doesn't know "경상도" is a colloquial grouping of five separate
// administrative regions -- it just finds text that seems thematically
// related, which can surface unrelated high-scoring results (e.g. searching
// "경상도" returning 경복궁 in Seoul). When the query contains one of these
// grouping terms, return its real region list so the caller can send it as
// a hard filter alongside the free-text query, scoping results to those
// regions regardless of how CLIP would have ranked them.
export function deriveRegionFilterFromQuery(query, aliases = regionAliases) {
  const normalized = query.trim()
  if (!normalized) return null

  // Pick the longest matching term across all groups, not just the first
  // group that matches -- a short colloquial form like "경상" is itself a
  // substring of a specific region's own name ("경상북도"), so checking
  // groups in list order would hard-filter a query for "경상북도" down to
  // every Gyeongsang-do region instead of just itself.
  let best = null
  for (const group of aliases) {
    for (const term of group.terms) {
      if (normalized.includes(term) && (!best || term.length > best.term.length)) {
        best = { term, regions: group.regions }
      }
    }
  }

  return best ? best.regions : null
}
