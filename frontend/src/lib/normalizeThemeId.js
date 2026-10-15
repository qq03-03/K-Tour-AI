// Maps theme ids used in shared/bookmarked URLs before the 2026-08-26
// canonical id rename (dash-separated, e.g. "night-view") to the current
// canonical ids the search backend's theme hard filter expects (underscore,
// e.g. "night_view" -- see search-service/src/theme_mapping.py's
// ALLOWED_THEMES), so old links keep working.
const LEGACY_THEME_ID_MAP = {
  'night-view': 'night_view',
  'cherry-blossom': 'flower',
  'autumn-leaves': 'autumn_leaves',
  beach: 'sea',
}

export function normalizeThemeId(themeId) {
  return LEGACY_THEME_ID_MAP[themeId] || themeId
}
