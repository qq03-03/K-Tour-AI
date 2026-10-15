// 517-dataset video_id values are "{prefix}_{youtubeId}" (e.g. "V007_Z7u5SNDq0jw").
// public/drama-images/ holds one team-provided cover image per prefix (e.g.
// "V007.webp"), copied via scripts/copy-drama-main-images.mjs. Returns null
// for any video_id that doesn't match this pattern.
const VIDEO_ID_PATTERN = /^(V\d+)_/

export function deriveDramaImagePath(videoId) {
  const match = VIDEO_ID_PATTERN.exec(videoId)
  if (!match) return null
  return `drama-images/${match[1]}.webp`
}
