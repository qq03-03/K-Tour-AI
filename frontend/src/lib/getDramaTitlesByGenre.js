import { dramaGenres } from '../data/dramaGenres.js'

export function getDramaTitlesByGenre(selectedGenres) {
  if (!selectedGenres || selectedGenres.length === 0) return []

  const requested = new Set(selectedGenres)
  const matches = []
  for (const [title, titleGenres] of Object.entries(dramaGenres)) {
    if (titleGenres.some((genre) => requested.has(genre))) {
      matches.push(title)
    }
  }
  return matches
}
