// Appends a YouTube start-time param so "원본 영상 재생" jumps straight to the
// segment instead of playing the source video from the beginning.
export function buildVideoUrl(sourceUrl, startTimeSeconds) {
  const seconds = Math.floor(startTimeSeconds)
  const separator = sourceUrl.includes('?') ? '&' : '?'
  return `${sourceUrl}${separator}t=${seconds}s`
}
