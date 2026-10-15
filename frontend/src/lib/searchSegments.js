import { regionAliases } from '../data/regionAliases.js'

function buildSearchText(segment) {
  const matchingAliasTerms = regionAliases
    .filter((group) => group.regions.includes(segment.region))
    .flatMap((group) => group.terms)

  return [
    segment.place_name,
    segment.region,
    segment.city,
    segment.drama_title,
    segment.description,
    ...(segment.mood || []),
    ...(segment.scene_elements || []),
    ...(segment.activity || []),
    ...matchingAliasTerms,
  ]
    .join(' ')
    .toLowerCase()
}

function matchesSeason(segment, season) {
  if (!season) return true
  const segmentSeasons = (segment.season || '').split(',').map((s) => s.trim())
  return segmentSeasons.includes(season)
}

function scoreSegment(segment, query) {
  if (!query || !query.trim()) return 1
  const text = buildSearchText(segment)
  const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean)
  if (terms.length === 0) return 1
  const matched = terms.filter((term) => text.includes(term))
  return matched.length / terms.length
}

function matchesTheme(segment, themeKeywords) {
  // null/undefined = no theme selected, don't filter.
  // [] (a theme selected but with no known keyword matches yet) = match nothing,
  // rather than silently matching everything.
  if (themeKeywords == null) return true
  if (themeKeywords.length === 0) return false
  const text = buildSearchText(segment)
  return themeKeywords.some((keyword) => text.includes(keyword.toLowerCase()))
}

export function searchSegments(segments, { query = '', season = null, themeKeywords = null } = {}) {
  return segments
    .filter((segment) => matchesSeason(segment, season))
    .filter((segment) => matchesTheme(segment, themeKeywords))
    .map((segment) => ({ ...segment, similarity: scoreSegment(segment, query) }))
    .filter((segment) => segment.similarity > 0)
    .sort((a, b) => b.similarity - a.similarity)
}
