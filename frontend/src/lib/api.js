import { mapSearchResponse } from './mapSearchResponse.js'

function baseUrl() {
  const url = import.meta.env.VITE_API_BASE_URL
  if (!url) throw new Error('VITE_API_BASE_URL이 설정되어 있지 않아요.')
  return url
}

export async function searchSegmentsApi({ query, filters = {} }) {
  const response = await fetch(`${baseUrl()}/api/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ q: query, ...filters }),
  }).catch(() => {
    throw new Error('검색 요청 실패: 네트워크 오류')
  })

  if (!response.ok) {
    throw new Error(`검색 요청 실패: ${response.status}`)
  }

  const data = await response.json()
  return mapSearchResponse(data.results)
}

function mapSegmentItem(data) {
  return {
    uid: data.segment_id,
    segment_id: data.segment_id,
    video_id: data.video_id,
    place_id: data.place_id,
    place_name: data.place_name,
    region: data.region,
    city: data.city,
    drama_title: data.drama_title,
    start_time: data.start_time,
    end_time: data.end_time,
    season: data.season,
    time_of_day: data.time_of_day,
    description: data.description,
    mood: data.mood,
    activity: data.activity,
    scene_elements: data.scene_elements,
    keyframe_path: data.keyframe_path,
  }
}

export async function getSegmentByIdApi(segmentId) {
  const response = await fetch(`${baseUrl()}/api/segments/${encodeURIComponent(segmentId)}`, {
    method: 'GET',
  })

  if (response.status === 404) return undefined
  if (!response.ok) {
    throw new Error(`상세 정보 요청 실패: ${response.status}`)
  }

  const data = await response.json()
  return mapSegmentItem(data)
}

// GET /api/segments (not /api/search) -- a plain, unranked listing straight
// from the video_segments table. POST /api/search always deduplicates down
// to one representative SCENE per source_segment_id (its own fixed
// principle: "same shot -> one result"), so a drama with 53 curated SCENE
// entries across only 4 distinct shots would only ever return 4 rows there.
// This endpoint returns every SCENE as its own row, which is what "show me
// every individual moment from this drama" actually needs. There's no
// ranking involved, so there's no similarity score to show.
export async function listSegmentsByDramaApi(dramaTitle) {
  const response = await fetch(`${baseUrl()}/api/segments?drama_title=${encodeURIComponent(dramaTitle)}`, {
    method: 'GET',
  }).catch(() => {
    throw new Error('구간 목록 요청 실패: 네트워크 오류')
  })

  if (!response.ok) {
    throw new Error(`구간 목록 요청 실패: ${response.status}`)
  }

  const data = await response.json()
  return data.map((item) => ({ ...mapSegmentItem(item), similarity: 1 }))
}
