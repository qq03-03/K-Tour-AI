// Theme ids are sent as-is to POST /api/search's `theme` field and applied
// server-side as a real hard filter over a curated source_segment_id ->
// themes mapping (see search-service/src/theme_mapping.py's ALLOWED_THEMES),
// not CLIP semantic search over keywords -- so these ids must exactly match
// the backend's confirmed canonical set. Old dash-separated ids from before
// this rename still work via normalizeThemeId.js's URL back-compat mapping.
// Labels match 동현's v2 catalog's filter_options.themes exactly (single
// source of truth for UI copy, per BACKEND_APPLY_GUIDE.md) -- note "sea"'s
// ko label is "바다", not "해변" (beach): the theme covers open-water/coast
// scenes generally, not just literal beaches.
export const themes = [
  { id: 'night_view', icon: '🌃', label: { ko: '야경', en: 'Night View', ja: '夜景', zh: '夜景' } },
  { id: 'drive', icon: '🚗', label: { ko: '드라이브', en: 'Drive', ja: 'ドライブ', zh: '驾车' } },
  { id: 'flower', icon: '🌸', label: { ko: '꽃', en: 'Flowers', ja: '花', zh: '花卉' } },
  { id: 'autumn_leaves', icon: '🍁', label: { ko: '단풍', en: 'Autumn Leaves', ja: '紅葉', zh: '红叶' } },
  { id: 'sea', icon: '🏖', label: { ko: '바다', en: 'Sea', ja: '海', zh: '海滨' } },
  { id: 'traditional', icon: '🏯', label: { ko: '전통', en: 'Traditional', ja: '伝統', zh: '传统' } },
  { id: 'field', icon: '🌾', label: { ko: '들판', en: 'Field', ja: '野原', zh: '田野' } },
  { id: 'hiking', icon: '🥾', label: { ko: '등산', en: 'Hiking', ja: '登山', zh: '登山' } },
  { id: 'forest', icon: '🌲', label: { ko: '숲', en: 'Forest', ja: '森林', zh: '森林' } },
]
