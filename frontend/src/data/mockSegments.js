// Segment data comes from the team's 517-segment VLM dataset
// (metadata_517_yonghwasan_v2.json, see mockSegments517.js). The original
// 45-segment dataset was removed at the user's request once the 517 dataset
// was confirmed to be a strict superset -- every drama/place the 45 covered
// also has real images and metadata in the 517 set.
import { rawSegments517 } from './mockSegments517.js'

// The source data uses Korean season words; normalize to the English ids used by
// data/seasons.js and lib/searchSegments.js's season filter (1:1, lossless mapping).
const SEASON_KO_TO_EN = { 봄: 'spring', 여름: 'summer', 가을: 'autumn', 겨울: 'winter' }

export const mockSegments = rawSegments517.map((segment) => ({
  ...segment,
  season: SEASON_KO_TO_EN[segment.season] || segment.season,
  uid: segment.keyframe_path.replace(/[^a-zA-Z0-9]/g, '_'),
}))
