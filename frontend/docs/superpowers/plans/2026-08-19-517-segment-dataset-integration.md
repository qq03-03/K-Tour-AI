# 517 세그먼트 데이터셋 반영 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the team's 517-segment VLM dataset (metadata, coordinates, translations) to the K-Tour-AI frontend as static data, alongside the existing 45 real-image segments, without touching keyframe images or the real backend search API.

**Architecture:** Three new generator scripts turn the team's delivered JSON files into three new `src/data/*517*` modules with namespaced `place_id`s. Six small edits wire those modules into the existing `mockSegments.js` / `placeCoordinates.js` / `localizeSegment.js` / video-link / image-rendering code paths, which otherwise keep working exactly as they do today for the original 45 segments.

**Tech Stack:** React 18 + Vite, Vitest + React Testing Library, plain Node scripts (`node scripts/*.mjs`) for one-time data generation.

## Global Constraints

- Source data lives outside the repo at `C:/Users/human/Downloads/K-Tour_AI_Backend_Handoff_517_Yonghwasan_GT_v2_20260818/data` — generator scripts read from there, matching the existing convention in `scripts/generate-segment-translations.mjs`.
- Every `place_id` sourced from the 517 dataset MUST be prefixed with `N-` (e.g. `P031` → `N-P031`) before it enters any file the app reads. The 517 dataset reuses P001–P0xx for different physical places than the existing 45-segment dataset; without the prefix, map pins render at the wrong location.
- The existing 45-segment data (`mockSegments.js`'s `rawSegments` array, `placeCoordinates.js`'s 30 entries, `segmentTranslations.json`) must not be edited — only appended to or merged with.
- Translation lookup keys are `${segment_id}__${keyframe_id}` (in this dataset `segment_id === keyframe_id`, so it's the same string twice, joined by `__`) — this is the existing, tested convention `localizeSegment.js` relies on; the 517 data must be written in the same format rather than changing `localizeSegment.js`'s lookup.
- No keyframe image files exist for the 517 dataset yet (confirmed: not in the handoff folder, not in any branch of the `origin` Git remote, not shared in Slack). Every image-rendering spot must fail gracefully (hide broken image, grey background) rather than assume the file exists.
- No changes to search logic, the real backend API, or `videoSources.js` — out of scope per the design spec.

---

### Task 1: Generate `mockSegments517.js` from the team's metadata file

**Files:**
- Create: `scripts/generate-mock-segments-517.mjs`
- Create: `src/data/mockSegments517.js` (generated output, not hand-written)
- Test: `src/data/mockSegments517.test.js`

**Interfaces:**
- Produces: `export const rawSegments517` — an array of 517 raw segment objects with the same shape as `mockSegments.js`'s internal `rawSegments` entries (`segment_id`, `source_segment_id`, `video_id`, `place_id`, `place_name`, `season`, `region`, `city`, `drama_title`, `start_time`, `end_time`, `keyframe_path`, `time_of_day`, `mood`, `scene_elements`, `activity`, `description`), except `place_id` is prefixed with `N-`. Not yet season-normalized or `uid`-assigned — that happens later when merged into `mockSegments.js` (Task 5).

- [ ] **Step 1: Write the failing test**

Create `src/data/mockSegments517.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { rawSegments517 } from './mockSegments517.js'

describe('mockSegments517', () => {
  it('has exactly 517 entries', () => {
    expect(rawSegments517).toHaveLength(517)
  })

  it('has unique segment_id values', () => {
    const ids = rawSegments517.map((s) => s.segment_id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('prefixes every place_id with N- to avoid colliding with the original 45-segment dataset', () => {
    for (const segment of rawSegments517) {
      expect(segment.place_id.startsWith('N-'), segment.segment_id).toBe(true)
    }
  })

  it('every entry has the required fields', () => {
    const requiredFields = [
      'place_id', 'place_name', 'region', 'city', 'drama_title', 'season', 'time_of_day',
      'mood', 'scene_elements', 'activity', 'description', 'segment_id',
      'source_segment_id', 'video_id', 'start_time', 'end_time', 'keyframe_path',
    ]
    for (const segment of rawSegments517) {
      for (const field of requiredFields) {
        expect(segment[field], `${segment.segment_id}.${field}`).toBeDefined()
      }
    }
  })

  it('every season is a raw Korean value the SEASON_KO_TO_EN map in mockSegments.js understands', () => {
    const knownSeasons = new Set(['봄', '여름', '가을', '겨울'])
    for (const segment of rawSegments517) {
      expect(knownSeasons.has(segment.season), `${segment.segment_id}: ${segment.season}`).toBe(true)
    }
  })

  it('every keyframe_path is a public/-relative path under keyframes/', () => {
    for (const segment of rawSegments517) {
      expect(segment.keyframe_path.startsWith('keyframes/')).toBe(true)
    }
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/data/mockSegments517.test.js`
Expected: FAIL — `Failed to resolve import "./mockSegments517.js"` (file doesn't exist yet).

- [ ] **Step 3: Write the generator script**

Create `scripts/generate-mock-segments-517.mjs`:

```js
import { readFileSync, writeFileSync } from 'node:fs'

const SOURCE_DIR = 'C:/Users/human/Downloads/K-Tour_AI_Backend_Handoff_517_Yonghwasan_GT_v2_20260818/data'
const PLACE_ID_PREFIX = 'N-'

const metadata = JSON.parse(readFileSync(`${SOURCE_DIR}/metadata_517_yonghwasan_v2.json`, 'utf8'))

const rawSegments517 = metadata.map((record) => ({
  ...record,
  place_id: `${PLACE_ID_PREFIX}${record.place_id}`,
}))

const header = `// Generated by scripts/generate-mock-segments-517.mjs from the team's
// 517-segment VLM handoff (metadata_517_yonghwasan_v2.json, 2026-08-18).
// place_id is prefixed with "${PLACE_ID_PREFIX}" because this dataset reuses
// P001-P0xx numbers for different places than the original 45-segment dataset
// in mockSegments.js -- see
// docs/superpowers/specs/2026-08-19-517-segment-dataset-integration-design.md.
// Raw data only; season/uid normalization happens in mockSegments.js.
export const rawSegments517 = ${JSON.stringify(rawSegments517, null, 2)}
`

writeFileSync('src/data/mockSegments517.js', header)
console.log(\`Wrote \${rawSegments517.length} segments to src/data/mockSegments517.js\`)
```

- [ ] **Step 4: Run the script**

Run: `node scripts/generate-mock-segments-517.mjs`
Expected: `Wrote 517 segments to src/data/mockSegments517.js`

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/data/mockSegments517.test.js`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add scripts/generate-mock-segments-517.mjs src/data/mockSegments517.js src/data/mockSegments517.test.js
git commit -m "Add generator for the 517-segment dataset's raw metadata"
```

---

### Task 2: Generate `placeCoordinates517.js` from the team's coordinates file

**Files:**
- Create: `scripts/generate-place-coordinates-517.mjs`
- Create: `src/data/placeCoordinates517.js` (generated output)
- Test: `src/data/placeCoordinates517.test.js`

**Interfaces:**
- Produces: `export const placeCoordinates517` — an object keyed by namespaced `place_id` (`N-P001`, ...), each value `{ place_name, latitude, longitude }`, matching the shape of entries in `placeCoordinates.js`.

- [ ] **Step 1: Write the failing test**

Create `src/data/placeCoordinates517.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { placeCoordinates517 } from './placeCoordinates517.js'

describe('placeCoordinates517', () => {
  it('has exactly 74 entries', () => {
    expect(Object.keys(placeCoordinates517)).toHaveLength(74)
  })

  it('prefixes every key with N-', () => {
    for (const key of Object.keys(placeCoordinates517)) {
      expect(key.startsWith('N-'), key).toBe(true)
    }
  })

  it('every entry has a place_name and numeric coordinates', () => {
    for (const [key, coord] of Object.entries(placeCoordinates517)) {
      expect(typeof coord.place_name, key).toBe('string')
      expect(typeof coord.latitude, key).toBe('number')
      expect(typeof coord.longitude, key).toBe('number')
    }
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/data/placeCoordinates517.test.js`
Expected: FAIL — `Failed to resolve import "./placeCoordinates517.js"`.

- [ ] **Step 3: Write the generator script**

Create `scripts/generate-place-coordinates-517.mjs`:

```js
import { readFileSync, writeFileSync } from 'node:fs'

const SOURCE_DIR = 'C:/Users/human/Downloads/K-Tour_AI_Backend_Handoff_517_Yonghwasan_GT_v2_20260818/data'
const PLACE_ID_PREFIX = 'N-'

const coordinates = JSON.parse(readFileSync(`${SOURCE_DIR}/places_coordinates_517.json`, 'utf8'))

const entries = coordinates.records.map((record) => [
  `${PLACE_ID_PREFIX}${record.place_id}`,
  { place_name: record.place_name, latitude: record.latitude, longitude: record.longitude },
])

const header = `// Generated by scripts/generate-place-coordinates-517.mjs from the team's
// 517-segment VLM handoff (places_coordinates_517.json, 2026-08-18).
// place_id is prefixed with "${PLACE_ID_PREFIX}" to avoid colliding with
// placeCoordinates.js -- see
// docs/superpowers/specs/2026-08-19-517-segment-dataset-integration-design.md.
export const placeCoordinates517 = ${JSON.stringify(Object.fromEntries(entries), null, 2)}
`

writeFileSync('src/data/placeCoordinates517.js', header)
console.log(\`Wrote \${entries.length} place coordinates to src/data/placeCoordinates517.js\`)
```

- [ ] **Step 4: Run the script**

Run: `node scripts/generate-place-coordinates-517.mjs`
Expected: `Wrote 74 place coordinates to src/data/placeCoordinates517.js`

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/data/placeCoordinates517.test.js`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add scripts/generate-place-coordinates-517.mjs src/data/placeCoordinates517.js src/data/placeCoordinates517.test.js
git commit -m "Add generator for the 517-segment dataset's place coordinates"
```

---

### Task 3: Generate `segmentTranslations517.json` from the team's translations file

**Files:**
- Create: `scripts/generate-segment-translations-517.mjs`
- Create: `src/data/segmentTranslations517.json` (generated output)
- Test: `src/data/segmentTranslations517.test.js`

**Interfaces:**
- Consumes: `rawSegments517` from Task 1 (`src/data/mockSegments517.js`).
- Produces: `segmentTranslations517.json` — a JSON object keyed by `${segment_id}__${keyframe_id}`, each value `{ ko: {...}, en: {...}, ja: {...}, zh: {...} }` with fields `drama_title, place_name, region, season, time_of_day, description, mood, activity, scene_elements`. Same shape as `segmentTranslations.json`.

- [ ] **Step 1: Write the failing test**

Create `src/data/segmentTranslations517.test.js`:

```js
import { describe, it, expect } from 'vitest'
import segmentTranslations517 from './segmentTranslations517.json'
import { rawSegments517 } from './mockSegments517.js'

describe('segmentTranslations517', () => {
  it('has exactly 517 records', () => {
    expect(Object.keys(segmentTranslations517)).toHaveLength(517)
  })

  it('has a record for every mockSegments517 entry, keyed by segment_id__segment_id', () => {
    for (const segment of rawSegments517) {
      const keyframeId = `${segment.segment_id}__${segment.segment_id}`
      expect(segmentTranslations517[keyframeId], keyframeId).toBeDefined()
    }
  })

  it('every record has all 4 languages with the required fields', () => {
    const requiredFields = [
      'drama_title', 'place_name', 'region', 'season', 'time_of_day',
      'description', 'mood', 'activity', 'scene_elements',
    ]
    for (const [keyframeId, record] of Object.entries(segmentTranslations517)) {
      for (const lang of ['ko', 'en', 'ja', 'zh']) {
        expect(record[lang], `${keyframeId}.${lang}`).toBeDefined()
        for (const field of requiredFields) {
          expect(record[lang][field], `${keyframeId}.${lang}.${field}`).toBeDefined()
        }
      }
    }
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/data/segmentTranslations517.test.js`
Expected: FAIL — `Failed to resolve import "./segmentTranslations517.json"`.

- [ ] **Step 3: Write the generator script**

Create `scripts/generate-segment-translations-517.mjs`:

```js
import { readFileSync, writeFileSync } from 'node:fs'

const SOURCE_DIR = 'C:/Users/human/Downloads/K-Tour_AI_Backend_Handoff_517_Yonghwasan_GT_v2_20260818/data'

const translations = JSON.parse(readFileSync(`${SOURCE_DIR}/display_translations_517_no_P063.json`, 'utf8'))

const merged = {}
for (const record of translations.records) {
  merged[`${record.segment_id}__${record.keyframe_id}`] = structuredClone(record.translations)
}

writeFileSync('src/data/segmentTranslations517.json', JSON.stringify(merged, null, 2) + '\n')
console.log(`Wrote ${Object.keys(merged).length} translation records to src/data/segmentTranslations517.json`)
```

- [ ] **Step 4: Run the script**

Run: `node scripts/generate-segment-translations-517.mjs`
Expected: `Wrote 517 translation records to src/data/segmentTranslations517.json`

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/data/segmentTranslations517.test.js`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add scripts/generate-segment-translations-517.mjs src/data/segmentTranslations517.json src/data/segmentTranslations517.test.js
git commit -m "Add generator for the 517-segment dataset's translations"
```

---

### Task 4: Merge module `allSegmentTranslations.js`

**Files:**
- Create: `src/data/allSegmentTranslations.js`
- Test: `src/data/allSegmentTranslations.test.js`

**Interfaces:**
- Consumes: `segmentTranslations.json` (existing, 45 records) and `segmentTranslations517.json` (Task 3, 517 records).
- Produces: `export const allSegmentTranslations` — a single object with both merged in. Task 7 (`localizeSegment.js`) will use this as its default translations source.

- [ ] **Step 1: Write the failing test**

Create `src/data/allSegmentTranslations.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { allSegmentTranslations } from './allSegmentTranslations.js'
import segmentTranslations from './segmentTranslations.json'
import segmentTranslations517 from './segmentTranslations517.json'

describe('allSegmentTranslations', () => {
  it('contains every record from both segmentTranslations.json and segmentTranslations517.json', () => {
    expect(Object.keys(allSegmentTranslations)).toHaveLength(
      Object.keys(segmentTranslations).length + Object.keys(segmentTranslations517).length,
    )
  })

  it('does not lose any original 45-segment record to a key collision', () => {
    for (const key of Object.keys(segmentTranslations)) {
      expect(allSegmentTranslations[key]).toBe(segmentTranslations[key])
    }
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/data/allSegmentTranslations.test.js`
Expected: FAIL — `Failed to resolve import "./allSegmentTranslations.js"`.

- [ ] **Step 3: Write the implementation**

Create `src/data/allSegmentTranslations.js`:

```js
import segmentTranslations from './segmentTranslations.json'
import segmentTranslations517 from './segmentTranslations517.json'

export const allSegmentTranslations = { ...segmentTranslations, ...segmentTranslations517 }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/data/allSegmentTranslations.test.js`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/data/allSegmentTranslations.js src/data/allSegmentTranslations.test.js
git commit -m "Add merged translations module covering both the 45- and 517-segment datasets"
```

---

### Task 5: Merge the 517 segments into `mockSegments.js`

**Files:**
- Modify: `src/data/mockSegments.js:10` (import area) and `src/data/mockSegments.js:1500-1509` (export)
- Modify: `src/data/mockSegments.test.js`

**Interfaces:**
- Consumes: `rawSegments517` from Task 1.
- Produces: `export const mockSegments` now has 562 entries (45 original + 517 new) instead of 45. Shape of each entry (fields, `uid` derivation, season normalization) is unchanged.

- [ ] **Step 1: Update the failing assertion first**

In `src/data/mockSegments.test.js`, change:

```js
  it('has exactly 45 entries', () => {
    expect(mockSegments).toHaveLength(45)
  })
```

to:

```js
  it('has exactly 562 entries', () => {
    expect(mockSegments).toHaveLength(562)
  })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/data/mockSegments.test.js`
Expected: FAIL — `expected 45 to be 562`.

- [ ] **Step 3: Wire in the 517 segments**

In `src/data/mockSegments.js`, add an import near the top of the file (after the existing header comment, before `const rawSegments = [`):

```js
import { rawSegments517 } from './mockSegments517.js'
```

Then change the export at the bottom of the file from:

```js
export const mockSegments = rawSegments.map((segment) => ({
  ...segment,
  season: SEASON_KO_TO_EN[segment.season] || segment.season,
  uid: segment.keyframe_path.replace(/[^a-zA-Z0-9]/g, '_'),
}))
```

to:

```js
export const mockSegments = [...rawSegments, ...rawSegments517].map((segment) => ({
  ...segment,
  season: SEASON_KO_TO_EN[segment.season] || segment.season,
  uid: segment.keyframe_path.replace(/[^a-zA-Z0-9]/g, '_'),
}))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/data/mockSegments.test.js`
Expected: PASS (5 tests — the pre-existing "unique uid values", "normalizes season", "every entry has required fields", and "keyframe_path under keyframes/" tests all still pass unchanged, now covering all 562 entries).

- [ ] **Step 5: Commit**

```bash
git add src/data/mockSegments.js src/data/mockSegments.test.js
git commit -m "Merge the 517-segment dataset into mockSegments"
```

---

### Task 6: Merge the 517 place coordinates into `placeCoordinates.js`

**Files:**
- Modify: `src/data/placeCoordinates.js`
- Create: `src/data/placeCoordinates.test.js` (no test file exists for this module yet)

**Interfaces:**
- Consumes: `placeCoordinates517` from Task 2.
- Produces: `export const placeCoordinates` now has 104 entries (30 original + 74 new) instead of 30.

- [ ] **Step 1: Write the failing test**

Create `src/data/placeCoordinates.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { placeCoordinates } from './placeCoordinates.js'

describe('placeCoordinates', () => {
  it('merges the original 30 entries with the 74 namespaced 517-dataset entries with no key collisions', () => {
    expect(Object.keys(placeCoordinates)).toHaveLength(104)
  })

  it('keeps the original place_id keys unprefixed and the 517-dataset keys prefixed with N-', () => {
    const prefixed = Object.keys(placeCoordinates).filter((key) => key.startsWith('N-'))
    const unprefixed = Object.keys(placeCoordinates).filter((key) => !key.startsWith('N-'))
    expect(prefixed).toHaveLength(74)
    expect(unprefixed).toHaveLength(30)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/data/placeCoordinates.test.js`
Expected: FAIL — `expected 30 to be 104`.

- [ ] **Step 3: Wire in the 517 place coordinates**

In `src/data/placeCoordinates.js`, add an import at the top:

```js
import { placeCoordinates517 } from './placeCoordinates517.js'
```

Then change the closing of the `placeCoordinates` object from:

```js
  P030: { place_name: '창경궁', latitude: 37.5776782272, longitude: 126.9938554166 },
}
```

to:

```js
  P030: { place_name: '창경궁', latitude: 37.5776782272, longitude: 126.9938554166 },
  ...placeCoordinates517,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/data/placeCoordinates.test.js`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/data/placeCoordinates.js src/data/placeCoordinates.test.js
git commit -m "Merge the 517-segment dataset's place coordinates into placeCoordinates"
```

---

### Task 7: Use the merged translations in `localizeSegment.js`

**Files:**
- Modify: `src/lib/localizeSegment.js`

**Interfaces:**
- Consumes: `allSegmentTranslations` from Task 4.
- Produces: `localizeSegment(segment, lang, translations = allSegmentTranslations)` — same signature and behavior as before, only the default `translations` source changes. No caller passes its own `translations` argument today, so all existing call sites automatically pick up the 517-segment coverage.

- [ ] **Step 1: Confirm the existing tests still describe the required behavior**

`src/lib/localizeSegment.test.js` already covers: localizing to a requested language, keeping non-localizable fields, falling back to Korean, and returning the segment unchanged when no record exists. No new test is needed for this task — it's a pure dependency swap. Run it now to confirm it currently passes:

Run: `npx vitest run src/lib/localizeSegment.test.js`
Expected: PASS (4 tests) — this is the baseline before the change.

- [ ] **Step 2: Swap the translations source**

In `src/lib/localizeSegment.js`, change:

```js
import segmentTranslations from '../data/segmentTranslations.json'

const LOCALIZABLE_FIELDS = [
  'drama_title', 'place_name', 'region', 'season', 'time_of_day',
  'description', 'mood', 'activity', 'scene_elements',
]

export function localizeSegment(segment, lang, translations = segmentTranslations) {
```

to:

```js
import { allSegmentTranslations } from '../data/allSegmentTranslations.js'

const LOCALIZABLE_FIELDS = [
  'drama_title', 'place_name', 'region', 'season', 'time_of_day',
  'description', 'mood', 'activity', 'scene_elements',
]

export function localizeSegment(segment, lang, translations = allSegmentTranslations) {
```

- [ ] **Step 3: Run tests to verify nothing broke**

Run: `npx vitest run src/lib/localizeSegment.test.js`
Expected: PASS (4 tests) — same as Step 1, confirming the swap is behavior-preserving for existing data.

Also run the full data-layer test suite, since `DramaSection.jsx` and `Detail.jsx` both call `localizeSegment` on `mockSegments` (now 562 entries):

Run: `npx vitest run src/components/DramaSection.test.jsx src/pages/Detail.test.jsx`
Expected: PASS (existing tests for both, unchanged).

- [ ] **Step 4: Commit**

```bash
git add src/lib/localizeSegment.js
git commit -m "Point localizeSegment at the merged 45+517 translations"
```

---

### Task 8: Derive YouTube links for 517-dataset video_ids

**Files:**
- Create: `src/lib/deriveVideoUrlFromVideoId.js`
- Test: `src/lib/deriveVideoUrlFromVideoId.test.js`
- Modify: `src/pages/Detail.jsx`
- Modify: `src/pages/Detail.test.jsx`

**Interfaces:**
- Produces: `deriveVideoUrlFromVideoId(videoId: string): string | null` — for a 517-dataset `video_id` like `"V007_Z7u5SNDq0jw"`, returns `"https://www.youtube.com/watch?v=Z7u5SNDq0jw"`. For an old-style `video_id` like `"GOBLIN_01"` (no embedded YouTube ID), returns `null`.
- Consumes (in `Detail.jsx`): `videoSources` (existing) as the first choice; falls back to `deriveVideoUrlFromVideoId(segment.video_id)` when `videoSources` has no entry for that `video_id`.

- [ ] **Step 1: Write the failing test**

Create `src/lib/deriveVideoUrlFromVideoId.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { deriveVideoUrlFromVideoId } from './deriveVideoUrlFromVideoId.js'

describe('deriveVideoUrlFromVideoId', () => {
  it('extracts the youtube_id from a 517-dataset video_id and builds a watch URL', () => {
    expect(deriveVideoUrlFromVideoId('V007_Z7u5SNDq0jw')).toBe('https://www.youtube.com/watch?v=Z7u5SNDq0jw')
  })

  it('handles youtube_ids that contain a leading underscore or hyphen', () => {
    expect(deriveVideoUrlFromVideoId('V045__fmhzDFTIH8')).toBe('https://www.youtube.com/watch?v=_fmhzDFTIH8')
    expect(deriveVideoUrlFromVideoId('V052_URa5-lfWhII')).toBe('https://www.youtube.com/watch?v=URa5-lfWhII')
  })

  it('returns null for old-style video_ids with no embedded youtube_id', () => {
    expect(deriveVideoUrlFromVideoId('GOBLIN_01')).toBe(null)
    expect(deriveVideoUrlFromVideoId('kingdom_gyeongbok_01')).toBe(null)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/lib/deriveVideoUrlFromVideoId.test.js`
Expected: FAIL — `Failed to resolve import "./deriveVideoUrlFromVideoId.js"`.

- [ ] **Step 3: Write the implementation**

Create `src/lib/deriveVideoUrlFromVideoId.js`:

```js
// 517-dataset video_id values are "{prefix}_{youtubeId}" (e.g. "V007_Z7u5SNDq0jw"),
// confirmed via regex against all 517 records in metadata_517_yonghwasan_v2.json --
// see docs/superpowers/specs/2026-08-19-517-segment-dataset-integration-design.md.
// Old-style video_ids (e.g. "GOBLIN_01") have no embedded youtube_id and must
// go through videoSources.js instead -- this returns null for those.
const VIDEO_ID_PATTERN = /^V\d+_(.+)$/

export function deriveVideoUrlFromVideoId(videoId) {
  const match = VIDEO_ID_PATTERN.exec(videoId)
  if (!match) return null
  return `https://www.youtube.com/watch?v=${match[1]}`
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/lib/deriveVideoUrlFromVideoId.test.js`
Expected: PASS (3 tests)

- [ ] **Step 5: Write the failing Detail.jsx test**

In `src/pages/Detail.test.jsx`, add this test inside the `describe('Detail', ...)` block:

```js
  it('derives and links to a play URL for a 517-dataset segment with no videoSources entry', () => {
    renderAt('keyframes_V007_Z7u5SNDq0jw_V007_P031_S002_SCENE_001_jpg')
    const link = screen.getByRole('link', { name: /원본 영상 재생/ })
    expect(link).toHaveAttribute('href', 'https://www.youtube.com/watch?v=Z7u5SNDq0jw&t=0s')
  })
```

- [ ] **Step 6: Run test to verify it fails**

Run: `npx vitest run src/pages/Detail.test.jsx`
Expected: FAIL — no link with accessible name `원본 영상 재생` is found, because `videoSources['V007_Z7u5SNDq0jw']` is undefined and `Detail.jsx` doesn't yet fall back to a derived URL.

- [ ] **Step 7: Wire the fallback into Detail.jsx**

In `src/pages/Detail.jsx`, add the import:

```js
import { deriveVideoUrlFromVideoId } from '../lib/deriveVideoUrlFromVideoId.js'
```

Change:

```js
  const videoSource = segment ? videoSources[segment.video_id] : undefined
```

to:

```js
  const videoSource = segment ? videoSources[segment.video_id] : undefined
  const videoUrl = videoSource
    ? videoSource.source_url
    : segment
      ? deriveVideoUrlFromVideoId(segment.video_id)
      : undefined
```

Then change:

```js
          {videoSource && (
            <a
              href={buildVideoUrl(videoSource.source_url, segment.start_time)}
```

to:

```js
          {videoUrl && (
            <a
              href={buildVideoUrl(videoUrl, segment.start_time)}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `npx vitest run src/pages/Detail.test.jsx`
Expected: PASS (6 tests — the original "links to the original video source" test for the old-style `GOBLIN_01` segment still passes via the `videoSource` branch, and the new test passes via the derived-URL branch).

- [ ] **Step 9: Commit**

```bash
git add src/lib/deriveVideoUrlFromVideoId.js src/lib/deriveVideoUrlFromVideoId.test.js src/pages/Detail.jsx src/pages/Detail.test.jsx
git commit -m "Derive YouTube links for 517-dataset segments with no videoSources entry"
```

---

### Task 9: Gracefully hide broken images (517-dataset segments have no keyframe file yet)

**Files:**
- Modify: `src/components/ResultCard.jsx`
- Modify: `src/components/ResultCard.test.jsx`
- Modify: `src/components/DramaSection.jsx`
- Modify: `src/components/DramaSection.test.jsx`
- Modify: `src/pages/Detail.jsx`
- Modify: `src/pages/Detail.test.jsx`

**Interfaces:**
- No new exports. Each `<img>` gains an `onError` handler that hides the broken-image icon, and a grey (`#e2e8f0`) background so the empty space still reads as a placeholder rather than a rendering bug.

- [ ] **Step 1: Write the failing ResultCard test**

In `src/components/ResultCard.test.jsx`, change the import line:

```js
import { render, screen } from '@testing-library/react'
```

to:

```js
import { render, screen, fireEvent } from '@testing-library/react'
```

Then add this test inside `describe('ResultCard', ...)`:

```js
  it('hides the image without crashing when the keyframe fails to load', () => {
    render(<MemoryRouter><ResultCard segment={segment} /></MemoryRouter>)
    const img = screen.getByRole('img')
    fireEvent.error(img)
    expect(img.style.visibility).toBe('hidden')
  })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/ResultCard.test.jsx`
Expected: FAIL — `expected '' to be 'hidden'` (no `onError` handler exists yet).

- [ ] **Step 3: Add the fallback to ResultCard.jsx**

In `src/components/ResultCard.jsx`, change:

```jsx
      <img
        src={`${import.meta.env.BASE_URL}${segment.keyframe_path}`}
        alt={segment.place_name}
        style={{ width: 96, height: 96, objectFit: 'cover', flexShrink: 0 }}
      />
```

to:

```jsx
      <img
        src={`${import.meta.env.BASE_URL}${segment.keyframe_path}`}
        alt={segment.place_name}
        onError={(event) => { event.currentTarget.style.visibility = 'hidden' }}
        style={{ width: 96, height: 96, objectFit: 'cover', flexShrink: 0, background: '#e2e8f0' }}
      />
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/ResultCard.test.jsx`
Expected: PASS (4 tests)

- [ ] **Step 5: Write the failing DramaSection test**

In `src/components/DramaSection.test.jsx`, change the import line:

```js
import { render, screen } from '@testing-library/react'
```

to:

```js
import { render, screen, fireEvent } from '@testing-library/react'
```

Then add this test inside `describe('DramaSection', ...)`:

```js
  it('hides an image without crashing when the keyframe fails to load', () => {
    renderWithLanguage(<MemoryRouter><DramaSection /></MemoryRouter>)
    const [firstImage] = screen.getAllByRole('img')
    fireEvent.error(firstImage)
    expect(firstImage.style.visibility).toBe('hidden')
  })
```

- [ ] **Step 6: Run test to verify it fails**

Run: `npx vitest run src/components/DramaSection.test.jsx`
Expected: FAIL — `expected '' to be 'hidden'`.

- [ ] **Step 7: Add the fallback to DramaSection.jsx**

In `src/components/DramaSection.jsx`, change:

```jsx
          <img
            src={`${import.meta.env.BASE_URL}${drama.keyframe_path}`}
            alt={drama.drama_title}
            style={{ width: '100%', height: 90, objectFit: 'cover', borderRadius: 16 }}
          />
```

to:

```jsx
          <img
            src={`${import.meta.env.BASE_URL}${drama.keyframe_path}`}
            alt={drama.drama_title}
            onError={(event) => { event.currentTarget.style.visibility = 'hidden' }}
            style={{ width: '100%', height: 90, objectFit: 'cover', borderRadius: 16, background: '#e2e8f0' }}
          />
```

- [ ] **Step 8: Run test to verify it passes**

Run: `npx vitest run src/components/DramaSection.test.jsx`
Expected: PASS (3 tests)

- [ ] **Step 9: Write the failing Detail test**

In `src/pages/Detail.test.jsx`, add this test inside `describe('Detail', ...)`:

```js
  it('hides the image without crashing when the keyframe fails to load', () => {
    renderAt('keyframes_GOBLIN_01_GOBLIN_01_SCENE_01_jpg')
    const img = screen.getByRole('img', { name: '강릉 주문진방파제' })
    fireEvent.error(img)
    expect(img.style.visibility).toBe('hidden')
  })
```

Add `fireEvent` to the existing import line at the top of the file:

```js
import { render, screen } from '@testing-library/react'
```

becomes:

```js
import { render, screen, fireEvent } from '@testing-library/react'
```

- [ ] **Step 10: Run test to verify it fails**

Run: `npx vitest run src/pages/Detail.test.jsx`
Expected: FAIL — `expected '' to be 'hidden'`.

- [ ] **Step 11: Add the fallback to Detail.jsx**

In `src/pages/Detail.jsx`, change:

```jsx
          <img src={`${import.meta.env.BASE_URL}${segment.keyframe_path}`} alt={segment.place_name} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
```

to:

```jsx
          <img
            src={`${import.meta.env.BASE_URL}${segment.keyframe_path}`}
            alt={segment.place_name}
            onError={(event) => { event.currentTarget.style.visibility = 'hidden' }}
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', background: '#e2e8f0' }}
          />
```

- [ ] **Step 12: Run test to verify it passes**

Run: `npx vitest run src/pages/Detail.test.jsx`
Expected: PASS (8 tests)

- [ ] **Step 13: Commit**

```bash
git add src/components/ResultCard.jsx src/components/ResultCard.test.jsx src/components/DramaSection.jsx src/components/DramaSection.test.jsx src/pages/Detail.jsx src/pages/Detail.test.jsx
git commit -m "Hide broken keyframe images instead of showing the browser's broken-icon"
```

---

### Task 10: Full regression and manual verification

**Files:** None (verification only).

- [ ] **Step 1: Run the full automated test suite**

Run: `npm test`
Expected: All test files pass, including every file touched in Tasks 1–9. No test count regressions elsewhere (this task touches shared modules — `mockSegments.js`, `placeCoordinates.js`, `localizeSegment.js` — so it's important to run the whole suite, not just the files this plan directly edited).

- [ ] **Step 2: Start the dev server**

Run: `npm run dev` (or use the project's preview tooling)

- [ ] **Step 3: Manually verify search and theme filters**

Open the search page, search for a drama title that only exists in the 517 dataset (e.g. "옥씨부인전" or "더 글로리" — neither is in the original 11 dramas). Confirm results appear with a grey placeholder image instead of a broken-image icon, and that place name, description, and drama title read correctly in Korean.

- [ ] **Step 4: Manually verify language switching on a 517-dataset segment**

Open the detail page for a result from Step 3. Switch language to English, Japanese, and Chinese via the header menu. Confirm the place name, description, mood tags, and drama title all translate (not just fall back to Korean).

- [ ] **Step 5: Manually verify the map**

On the same detail page, confirm the map pin appears at the correct location (cross-check the coordinates against `places_coordinates_517.json` or a maps search for the place name) — this is the key check for the `N-` place_id namespacing working correctly.

- [ ] **Step 6: Manually verify the 8 overlapping places**

Search for "경복궁" (one of the 8 places that exist in both the original 45 and the new 517). Confirm two cards appear — one with a real photo (from the original dataset) and one with a grey placeholder (from the 517 dataset) — and that both link to working, distinct detail pages.

- [ ] **Step 7: Manually verify the "play original video" link**

On a 517-dataset segment's detail page, click "▶ 원본 영상 재생" and confirm it opens a valid YouTube video in a new tab.

- [ ] **Step 8: Report results to the user**

Summarize pass/fail for each manual check above before considering this plan complete. Do not mark this task done until all checks in Steps 3–7 pass.
