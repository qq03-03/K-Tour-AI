import { dramaTrailers } from '../data/dramaTrailers.js'

export function getDramaTrailer(dramaTitle) {
  const entry = dramaTitle ? dramaTrailers[dramaTitle] : null
  if (!entry) return null
  return {
    youtubeId: entry.youtubeId,
    watchUrl: `https://www.youtube.com/watch?v=${entry.youtubeId}`,
    thumbnailUrl: `https://img.youtube.com/vi/${entry.youtubeId}/hqdefault.jpg`,
  }
}
