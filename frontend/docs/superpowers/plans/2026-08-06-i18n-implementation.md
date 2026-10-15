# 다국어(i18n) 지원 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 검색 결과/상세 페이지의 콘텐츠와 화면 UI 문구를 한국어/영어/일본어/중국어 4개 언어로 전환할 수 있게 한다.

**Architecture:** 콘텐츠 번역(백엔드 전달 `display_translations.json` + 사람 검수 `display_translation_overrides.json`을 병합한 정적 JSON)과 UI 문구 번역(직접 작성한 `strings.js` 사전)을 분리한다. `LanguageContext`가 앱 전역에 현재 언어와 `t()` 함수를 제공하고, `localizeSegment()`가 세그먼트를 렌더링 직전에 현재 언어로 감싼다. 검색/필터 로직(`searchSegments.js`)은 원본 텍스트 기준으로 그대로 둔다.

**Tech Stack:** React 19 Context API, Vite JSON import, Vitest + React Testing Library.

## Global Constraints

- 지원 언어는 정확히 `ko`, `en`, `ja`, `zh` 4개다.
- 검색 순위·필터링은 언어와 무관하게 항상 원본(raw) `mockSegments` 텍스트 기준으로 동작한다. 번역은 화면에 뿌리기 직전에만 적용한다.
- 콘텐츠 번역 데이터(드라마 제목, 장소명, 지역, 계절, 시간대, 설명, mood/activity/scene_elements)는 `K-Tour-AI_백엔드전달_v2/data/display_translations.json`과 `display_translation_overrides.json`에서 그대로 가져온다. 직접 번역을 작성하거나 고치지 않는다.
- UI 문구(메뉴, 버튼, 안내 문구)는 백엔드 데이터에 없으므로 이 계획에 정의된 값을 그대로 사용한다.
- 선택한 언어는 `localStorage` 키 `ktourai_lang`에 저장하고, 저장된 값이 없으면 기본값은 `ko`다.
- 언어 전환 UI는 Header에 `KO / EN / JA / ZH` 4개 버튼으로 노출한다.

---

## File Structure

**생성:**
- `scripts/generate-segment-translations.mjs` — 백엔드 전달 JSON 2개를 병합해 `src/data/segmentTranslations.json`을 생성하는 1회성 스크립트
- `src/data/segmentTranslations.json` — 위 스크립트의 생성 결과 (커밋 대상)
- `src/data/segmentTranslations.test.js`
- `src/i18n/strings.js` — UI 문구 4개 언어 사전
- `src/i18n/strings.test.js`
- `src/i18n/LanguageContext.jsx` — `LanguageProvider`, `useLanguage()`
- `src/i18n/LanguageContext.test.jsx`
- `src/test-utils.jsx` — 테스트에서 `LanguageProvider`로 감싸는 공용 헬퍼
- `src/lib/localizeSegment.js`
- `src/lib/localizeSegment.test.js`

**수정:**
- `src/main.jsx` — `LanguageProvider`로 `App` 감싸기
- `src/data/seasons.js`, `src/data/themes.js` — `label`을 언어별 객체로 변경
- `src/components/SeasonSection.jsx`, `src/components/SeasonSection.test.jsx`
- `src/components/ThemeSection.jsx`, `src/components/ThemeSection.test.jsx`
- `src/components/Header.jsx`, `src/components/Header.test.jsx`
- `src/components/Hero.jsx`
- `src/components/SearchBar.jsx`, `src/components/SearchBar.test.jsx`
- `src/components/DramaSection.jsx`, `src/components/DramaSection.test.jsx`
- `src/pages/Home.jsx`, `src/pages/Home.test.jsx`
- `src/pages/SearchResults.jsx`, `src/pages/SearchResults.test.jsx`
- `src/pages/Detail.jsx`, `src/pages/Detail.test.jsx`
- `src/components/KakaoMap.jsx`, `src/components/KakaoMap.test.jsx`
- `src/pages/About.jsx`, `src/pages/About.test.jsx`

**범위 밖(의도적으로 건드리지 않음):**
- `src/components/Footer.jsx` — "© 2026 K-Tour AI"는 브랜드명+연도뿐이라 언어별로 다를 내용이 없음
- `src/components/ResultCard.jsx`, `src/components/EmptyState.jsx` — 이미 로컬라이즈된 `segment`/`message`를 부모로부터 받아 그대로 렌더링하므로 자체 변경 불필요
- 카카오 지도 핀 라벨(`placeCoordinates.js`의 `place_name`) — 백엔드 번역 데이터 범위 밖이므로 한국어 유지

---

### Task 1: 콘텐츠 번역 데이터 생성 (segmentTranslations.json)

**Files:**
- Create: `scripts/generate-segment-translations.mjs`
- Create: `src/data/segmentTranslations.json`
- Test: `src/data/segmentTranslations.test.js`

**Interfaces:**
- Produces: `src/data/segmentTranslations.json` — `{ [keyframeId: string]: { ko|en|ja|zh: { drama_title, place_name, region, season, time_of_day, description, mood: string[], activity: string[], scene_elements: string[] } } }`. `keyframeId`는 `${segment_id}__${segment_id}` 형식 (전체 45개 레코드에서 검증됨).

- [ ] **Step 1: 생성 스크립트 작성**

`scripts/generate-segment-translations.mjs`:

```js
import { readFileSync, writeFileSync } from 'node:fs'

const SOURCE_DIR = 'C:/Users/human/Documents/카카오톡 받은 파일/K-Tour-AI_백엔드전달_v2/data'

const translations = JSON.parse(readFileSync(`${SOURCE_DIR}/display_translations.json`, 'utf8'))
const overrides = JSON.parse(readFileSync(`${SOURCE_DIR}/display_translation_overrides.json`, 'utf8'))

const merged = {}
for (const record of translations.records) {
  merged[record.keyframe_id] = structuredClone(record.translations)
}

for (const override of overrides.records) {
  const target = merged[override.keyframe_id]
  if (!target) {
    throw new Error(`Override references unknown keyframe_id: ${override.keyframe_id}`)
  }
  for (const [lang, fields] of Object.entries(override.translations)) {
    Object.assign(target[lang], fields)
  }
}

writeFileSync('src/data/segmentTranslations.json', JSON.stringify(merged, null, 2) + '\n')
console.log(`Wrote ${Object.keys(merged).length} translation records to src/data/segmentTranslations.json`)
```

- [ ] **Step 2: 스크립트 실행**

Run (K-Tour-AI 저장소 루트에서): `node scripts/generate-segment-translations.mjs`
Expected: `Wrote 45 translation records to src/data/segmentTranslations.json`

- [ ] **Step 3: 검증 테스트 작성**

`src/data/segmentTranslations.test.js`:

```js
import { describe, it, expect } from 'vitest'
import segmentTranslations from './segmentTranslations.json'
import { mockSegments } from './mockSegments.js'

describe('segmentTranslations', () => {
  it('has exactly 45 records', () => {
    expect(Object.keys(segmentTranslations)).toHaveLength(45)
  })

  it('has a record for every mockSegments entry, keyed by segment_id__segment_id', () => {
    for (const segment of mockSegments) {
      const keyframeId = `${segment.segment_id}__${segment.segment_id}`
      expect(segmentTranslations[keyframeId], keyframeId).toBeDefined()
    }
  })

  it('every record has all 4 languages with the required fields', () => {
    const requiredFields = [
      'drama_title', 'place_name', 'region', 'season', 'time_of_day',
      'description', 'mood', 'activity', 'scene_elements',
    ]
    for (const [keyframeId, record] of Object.entries(segmentTranslations)) {
      for (const lang of ['ko', 'en', 'ja', 'zh']) {
        expect(record[lang], `${keyframeId}.${lang}`).toBeDefined()
        for (const field of requiredFields) {
          expect(record[lang][field], `${keyframeId}.${lang}.${field}`).toBeDefined()
        }
      }
    }
  })

  it('applies the human-review override for GOBLIN_01_SCENE_01 description', () => {
    const record = segmentTranslations['GOBLIN_01_SCENE_01__GOBLIN_01_SCENE_01']
    expect(record.ko.description).toBe(
      '사람들이 해변의 바위 위에 서서 바다를 바라보며 조용히 대화를 나누는 장면입니다.',
    )
  })
})
```

- [ ] **Step 4: 테스트 실행**

Run: `npx vitest run src/data/segmentTranslations.test.js`
Expected: 4 tests pass.

- [ ] **Step 5: 커밋**

```bash
git add scripts/generate-segment-translations.mjs src/data/segmentTranslations.json src/data/segmentTranslations.test.js
git commit -m "Add merged segment content translations (ko/en/ja/zh)"
```

---

### Task 2: UI 문구 사전 (strings.js)

**Files:**
- Create: `src/i18n/strings.js`
- Test: `src/i18n/strings.test.js`

**Interfaces:**
- Produces: `strings` — `{ ko: Record<string,string>, en: Record<string,string>, ja: Record<string,string>, zh: Record<string,string> }`. 모든 언어가 동일한 키 집합을 가진다.

- [ ] **Step 1: 실패하는 테스트 작성**

`src/i18n/strings.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { strings } from './strings.js'

describe('strings', () => {
  const languages = ['ko', 'en', 'ja', 'zh']

  it('defines the same keys in every language', () => {
    const koKeys = Object.keys(strings.ko).sort()
    for (const lang of languages) {
      expect(Object.keys(strings[lang]).sort(), lang).toEqual(koKeys)
    }
  })

  it('has no empty string values', () => {
    for (const lang of languages) {
      for (const [key, value] of Object.entries(strings[lang])) {
        expect(value.length > 0, `${lang}.${key}`).toBe(true)
      }
    }
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run src/i18n/strings.test.js`
Expected: FAIL — `Cannot find module './strings.js'`

- [ ] **Step 3: strings.js 작성**

`src/i18n/strings.js`:

```js
export const strings = {
  ko: {
    nav_home: '홈',
    nav_search: '검색',
    nav_about: '소개',
    hero_title: 'K-드라마 & K-콘텐츠로\n떠나는 대한민국 여행',
    hero_subtitle: 'AI가 찾아주는 나만의 촬영지 여행',
    search_placeholder: '여행지를 검색해보세요...',
    search_button: '검색',
    home_section_season: '계절',
    home_section_theme: '테마',
    home_section_dramas: '인기 드라마',
    results_count: '검색 결과 {n}건',
    view_as_map: '지도로 보기',
    view_as_list: '리스트로 보기',
    empty_results_message: '검색 결과가 없어요. 다른 검색어를 시도해보세요.',
    detail_not_found: '해당 장면을 찾을 수 없어요.',
    detail_back_to_search: '검색으로 돌아가기',
    detail_drama_heading: '이 장면이 담긴 드라마',
    detail_play_original: '원본 영상 재생',
    detail_location_heading: '위치',
    map_empty: '지도에 표시할 위치 정보가 없어요.',
    map_loading: '지도를 불러오는 중...',
    map_error: '지도를 불러오지 못했어요. 네트워크 상태를 확인해주세요.',
    map_retry: '다시 시도',
    about_status_legend: '✅ 완료 · 🔲 예정 / 확인 필요',
    about_pipeline_video_title: '영상 처리 파이프라인',
    about_pipeline_search_title: '검색 파이프라인',
    about_step_video: '영상',
    about_step_search: '검색',
    about_step_recommend: '추천 결과',
    about_status_done: '✅ 완료',
    about_status_ui_building: '🔲 UI 구현 중',
    about_status_check_needed: '🔲 확인 필요',
  },
  en: {
    nav_home: 'Home',
    nav_search: 'Search',
    nav_about: 'About',
    hero_title: 'Discover Korea through\nK-Drama & K-Content',
    hero_subtitle: 'Your personalized filming location trip, found by AI',
    search_placeholder: 'Search Destination...',
    search_button: 'Search',
    home_section_season: 'SEASON',
    home_section_theme: 'THEME',
    home_section_dramas: 'POPULAR DRAMAS',
    results_count: '{n} results',
    view_as_map: 'View as Map',
    view_as_list: 'View as List',
    empty_results_message: 'No results found. Try a different search.',
    detail_not_found: 'This scene could not be found.',
    detail_back_to_search: 'Back to search',
    detail_drama_heading: 'Drama featuring this scene',
    detail_play_original: 'Watch Original Video',
    detail_location_heading: 'Location',
    map_empty: 'No location to show on the map.',
    map_loading: 'Loading map...',
    map_error: "Couldn't load the map. Please check your network connection.",
    map_retry: 'Retry',
    about_status_legend: '✅ Done · 🔲 Planned / Needs review',
    about_pipeline_video_title: 'Video Processing Pipeline',
    about_pipeline_search_title: 'Search Pipeline',
    about_step_video: 'Video',
    about_step_search: 'Search',
    about_step_recommend: 'Recommendations',
    about_status_done: '✅ Done',
    about_status_ui_building: '🔲 Building UI',
    about_status_check_needed: '🔲 Needs review',
  },
  ja: {
    nav_home: 'ホーム',
    nav_search: '検索',
    nav_about: '概要',
    hero_title: 'K-ドラマ&K-コンテンツで巡る\n韓国旅行',
    hero_subtitle: 'AIが見つけるあなただけのロケ地旅行',
    search_placeholder: '旅行先を検索...',
    search_button: '検索',
    home_section_season: '季節',
    home_section_theme: 'テーマ',
    home_section_dramas: '人気ドラマ',
    results_count: '検索結果 {n}件',
    view_as_map: '地図で見る',
    view_as_list: 'リストで見る',
    empty_results_message: '検索結果がありません。別のキーワードをお試しください。',
    detail_not_found: 'このシーンが見つかりません。',
    detail_back_to_search: '検索に戻る',
    detail_drama_heading: 'このシーンが登場するドラマ',
    detail_play_original: '元動画を再生',
    detail_location_heading: '位置',
    map_empty: '地図に表示する位置情報がありません。',
    map_loading: '地図を読み込み中...',
    map_error: '地図を読み込めませんでした。ネットワーク状態を確認してください。',
    map_retry: '再試行',
    about_status_legend: '✅ 完了 · 🔲 予定 / 要確認',
    about_pipeline_video_title: '映像処理パイプライン',
    about_pipeline_search_title: '検索パイプライン',
    about_step_video: '映像',
    about_step_search: '検索',
    about_step_recommend: 'おすすめ結果',
    about_status_done: '✅ 完了',
    about_status_ui_building: '🔲 UI実装中',
    about_status_check_needed: '🔲 要確認',
  },
  zh: {
    nav_home: '首页',
    nav_search: '搜索',
    nav_about: '关于',
    hero_title: '通过韩剧韩综\n探索韩国之旅',
    hero_subtitle: 'AI 为你寻找专属取景地之旅',
    search_placeholder: '搜索目的地...',
    search_button: '搜索',
    home_section_season: '季节',
    home_section_theme: '主题',
    home_section_dramas: '热门剧集',
    results_count: '搜索结果 {n} 条',
    view_as_map: '地图查看',
    view_as_list: '列表查看',
    empty_results_message: '没有找到结果，请尝试其他搜索词。',
    detail_not_found: '未找到该场景。',
    detail_back_to_search: '返回搜索',
    detail_drama_heading: '该场景出自的剧集',
    detail_play_original: '播放原始视频',
    detail_location_heading: '位置',
    map_empty: '没有可在地图上显示的位置信息。',
    map_loading: '正在加载地图...',
    map_error: '地图加载失败，请检查网络连接。',
    map_retry: '重试',
    about_status_legend: '✅ 已完成 · 🔲 计划中 / 待确认',
    about_pipeline_video_title: '视频处理流程',
    about_pipeline_search_title: '搜索流程',
    about_step_video: '视频',
    about_step_search: '搜索',
    about_step_recommend: '推荐结果',
    about_status_done: '✅ 已完成',
    about_status_ui_building: '🔲 UI 开发中',
    about_status_check_needed: '🔲 待确认',
  },
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `npx vitest run src/i18n/strings.test.js`
Expected: 2 tests pass.

- [ ] **Step 5: 커밋**

```bash
git add src/i18n/strings.js src/i18n/strings.test.js
git commit -m "Add UI copy dictionary for ko/en/ja/zh"
```

---

### Task 3: LanguageContext + 전역 연결

**Files:**
- Create: `src/i18n/LanguageContext.jsx`
- Test: `src/i18n/LanguageContext.test.jsx`
- Create: `src/test-utils.jsx`
- Modify: `src/main.jsx`
- Modify: `src/pages/Home.test.jsx` (wrapping only, no assertion changes)
- Modify: `src/pages/SearchResults.test.jsx` (wrapping only, no assertion changes)
- Modify: `src/pages/Detail.test.jsx` (wrapping only, no assertion changes)
- Modify: `src/pages/About.test.jsx` (wrapping only, no assertion changes)

**Interfaces:**
- Consumes: `strings` from `src/i18n/strings.js` (Task 2).
- Produces: `LanguageProvider` (component), `useLanguage()` returning `{ lang: 'ko'|'en'|'ja'|'zh', setLang: (lang) => void, t: (key: string, params?: Record<string,string|number>) => string }`. `renderWithLanguage(ui)` from `src/test-utils.jsx`.

이 태스크는 Header(Task 6)가 나중에 `useLanguage()`를 호출하기 시작하면 Home/SearchResults/Detail/About 페이지 전체가 깨지는 것을 미리 막기 위해, 아직 아무 컴포넌트도 context를 쓰지 않는 지금 4개 페이지 테스트 파일에 `LanguageProvider` 래핑을 선제적으로 추가한다. 이 스텝에서는 어떤 assertion도 바뀌지 않는다 — 순수 배관 작업이다.

- [ ] **Step 1: 실패하는 테스트 작성**

`src/i18n/LanguageContext.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, beforeEach } from 'vitest'
import { LanguageProvider, useLanguage } from './LanguageContext.jsx'

const STORAGE_KEY = 'ktourai_lang'

function Consumer() {
  const { lang, setLang, t } = useLanguage()
  return (
    <div>
      <span data-testid="lang">{lang}</span>
      <span data-testid="translated">{t('nav_home')}</span>
      <span data-testid="interpolated">{t('results_count', { n: 3 })}</span>
      <button onClick={() => setLang('en')}>switch to en</button>
    </div>
  )
}

describe('LanguageContext', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('defaults to Korean when nothing is stored', () => {
    render(<LanguageProvider><Consumer /></LanguageProvider>)
    expect(screen.getByTestId('lang')).toHaveTextContent('ko')
    expect(screen.getByTestId('translated')).toHaveTextContent('홈')
  })

  it('reads a previously stored language', () => {
    window.localStorage.setItem(STORAGE_KEY, 'ja')
    render(<LanguageProvider><Consumer /></LanguageProvider>)
    expect(screen.getByTestId('lang')).toHaveTextContent('ja')
  })

  it('updates language and persists it on setLang', async () => {
    const user = userEvent.setup()
    render(<LanguageProvider><Consumer /></LanguageProvider>)
    await user.click(screen.getByRole('button', { name: 'switch to en' }))
    expect(screen.getByTestId('lang')).toHaveTextContent('en')
    expect(screen.getByTestId('translated')).toHaveTextContent('Home')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('en')
  })

  it('interpolates {n} placeholders', () => {
    render(<LanguageProvider><Consumer /></LanguageProvider>)
    expect(screen.getByTestId('interpolated')).toHaveTextContent('검색 결과 3건')
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run src/i18n/LanguageContext.test.jsx`
Expected: FAIL — `Cannot find module './LanguageContext.jsx'`

- [ ] **Step 3: LanguageContext.jsx 작성**

`src/i18n/LanguageContext.jsx`:

```jsx
import { createContext, useContext, useState, useCallback } from 'react'
import { strings } from './strings.js'

const STORAGE_KEY = 'ktourai_lang'
const SUPPORTED_LANGUAGES = ['ko', 'en', 'ja', 'zh']
const DEFAULT_LANGUAGE = 'ko'

const LanguageContext = createContext(null)

function readStoredLanguage() {
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return SUPPORTED_LANGUAGES.includes(stored) ? stored : DEFAULT_LANGUAGE
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(readStoredLanguage)

  const setLang = useCallback((next) => {
    if (!SUPPORTED_LANGUAGES.includes(next)) return
    window.localStorage.setItem(STORAGE_KEY, next)
    setLangState(next)
  }, [])

  const t = useCallback(
    (key, params) => {
      const template = strings[lang]?.[key] ?? strings[DEFAULT_LANGUAGE][key] ?? key
      if (!params) return template
      return Object.entries(params).reduce(
        (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
        template,
      )
    },
    [lang],
  )

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (!context) throw new Error('useLanguage must be used within a LanguageProvider')
  return context
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `npx vitest run src/i18n/LanguageContext.test.jsx`
Expected: 4 tests pass.

- [ ] **Step 5: 테스트용 공용 래퍼 작성**

`src/test-utils.jsx`:

```jsx
import { render } from '@testing-library/react'
import { LanguageProvider } from './i18n/LanguageContext.jsx'

export function renderWithLanguage(ui) {
  return render(<LanguageProvider>{ui}</LanguageProvider>)
}
```

- [ ] **Step 6: main.jsx에 Provider 연결**

`src/main.jsx` 전체:

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import { LanguageProvider } from './i18n/LanguageContext.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <LanguageProvider>
        <App />
      </LanguageProvider>
    </BrowserRouter>
  </StrictMode>,
)
```

- [ ] **Step 7: 4개 페이지 테스트에 선제적 래핑 추가 (assertion 변경 없음)**

`src/pages/Home.test.jsx` 전체를 아래로 교체 (아직 화면 문구는 바뀌지 않았으므로 assertion은 원래와 동일하다):

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import Home from './Home.jsx'
import { LanguageProvider } from '../i18n/LanguageContext.jsx'

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname}{location.search}</div>
}

function renderHome() {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<LocationDisplay />} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
}

describe('Home', () => {
  it('renders the hero tagline and search bar', () => {
    renderHome()
    expect(screen.getByText(/Discover Korea/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/search destination/i)).toBeInTheDocument()
  })

  it('navigates to /search?q=... when a search is submitted', async () => {
    const user = userEvent.setup()
    renderHome()
    await user.type(screen.getByPlaceholderText(/search destination/i), 'lotus{Enter}')
    expect(screen.getByTestId('location')).toHaveTextContent('/search?q=lotus')
  })

  it('navigates to /search?season=... when a season chip is clicked', async () => {
    const user = userEvent.setup()
    renderHome()
    await user.click(screen.getByText('Summer'))
    expect(screen.getByTestId('location')).toHaveTextContent('/search?season=summer')
  })
})
```

`src/pages/SearchResults.test.jsx` 전체를 아래로 교체 (아직 화면 문구는 바뀌지 않았으므로 assertion은 원래와 동일하다):

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SearchResults from './SearchResults.jsx'
import { LanguageProvider } from '../i18n/LanguageContext.jsx'

function renderAt(path) {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/search" element={<SearchResults />} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
}

describe('SearchResults', () => {
  beforeEach(() => {
    window.kakao = {
      maps: {
        LatLng: vi.fn(function LatLng() {}),
        LatLngBounds: vi.fn(function LatLngBounds() {
          this.extend = vi.fn()
        }),
        Map: vi.fn(function Map() {
          this.setBounds = vi.fn()
          this.setCenter = vi.fn()
          this.relayout = vi.fn()
        }),
        Marker: vi.fn(function Marker() {}),
        load: (callback) => callback(),
      },
    }
  })

  it('shows matching results for a query present in the real mock data', () => {
    renderAt('/search?q=canola')
    expect(screen.getByText('고창 학원농장')).toBeInTheDocument()
  })

  it('shows the empty state for a query that matches nothing', () => {
    renderAt('/search?q=submarine spaceship dinosaur')
    expect(screen.getByText(/검색 결과가 없어요/)).toBeInTheDocument()
  })

  it('filters by season from the URL', () => {
    renderAt('/search?season=summer')
    expect(screen.getAllByRole('link').length).toBeGreaterThan(0)
  })

  it('shows a map with markers when "지도로 보기" is clicked', async () => {
    const user = userEvent.setup()
    renderAt('/search?q=palace')
    await user.click(screen.getByText('🗺️ 지도로 보기'))
    expect(window.kakao.maps.Map).toHaveBeenCalledTimes(1)
    expect(window.kakao.maps.Marker).toHaveBeenCalled()
  })
})
```

`src/pages/Detail.test.jsx` 전체를 아래로 교체 (아직 화면 문구는 바뀌지 않았으므로 assertion은 원래와 동일하다):

```jsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Detail from './Detail.jsx'
import { LanguageProvider } from '../i18n/LanguageContext.jsx'

function renderAt(uid) {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[`/segment/${uid}`]}>
        <Routes>
          <Route path="/segment/:segmentId" element={<Detail />} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
}

describe('Detail', () => {
  beforeEach(() => {
    window.kakao = {
      maps: {
        LatLng: vi.fn(function LatLng() {}),
        LatLngBounds: vi.fn(function LatLngBounds() {
          this.extend = vi.fn()
        }),
        Map: vi.fn(function Map() {
          this.setBounds = vi.fn()
          this.setCenter = vi.fn()
          this.relayout = vi.fn()
        }),
        Marker: vi.fn(function Marker() {}),
        load: (callback) => callback(),
      },
    }
  })

  it('renders the place name and drama title for a known segment', () => {
    renderAt('keyframes_GOBLIN_01_GOBLIN_01_SCENE_01_jpg')
    expect(screen.getByText('강릉 주문진')).toBeInTheDocument()
    expect(screen.getByText('도깨비')).toBeInTheDocument()
  })

  it('renders a map marker for the segment\'s place', async () => {
    renderAt('keyframes_GOBLIN_01_GOBLIN_01_SCENE_01_jpg')
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(window.kakao.maps.Marker).toHaveBeenCalledTimes(1)
  })

  it('renders a not-found message for an unknown uid', () => {
    renderAt('does_not_exist')
    expect(screen.getByText(/찾을 수 없어요/)).toBeInTheDocument()
  })

  it('links to the original video source for the segment', () => {
    renderAt('keyframes_GOBLIN_01_GOBLIN_01_SCENE_01_jpg')
    const link = screen.getByRole('link', { name: /원본 영상 재생/ })
    expect(link).toHaveAttribute('href', 'https://www.youtube.com/watch?v=mCeMgl6rR-U')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
  })
})
```

`src/pages/About.test.jsx` 전체를 아래로 교체 (헬퍼 함수로 정리하며 래핑 추가):

```jsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import About from './About.jsx'
import { LanguageProvider } from '../i18n/LanguageContext.jsx'

function renderAbout() {
  return render(<LanguageProvider><MemoryRouter><About /></MemoryRouter></LanguageProvider>)
}

describe('About', () => {
  it('renders both pipeline sections', () => {
    renderAbout()
    expect(screen.getByText('영상 처리 파이프라인')).toBeInTheDocument()
    expect(screen.getByText('검색 파이프라인')).toBeInTheDocument()
  })

  it('marks exactly Query Analysis as pending confirmation (RRF confirmed done per team Slack update)', () => {
    renderAbout()
    expect(screen.getAllByText('🔲 확인 필요')).toHaveLength(1)
  })

  it('marks RRF as done (6 video-pipeline steps + Vector Search + RRF)', () => {
    renderAbout()
    expect(screen.getAllByText('✅ 완료')).toHaveLength(8)
  })
})
```

- [ ] **Step 8: 전체 테스트 실행**

Run: `npx vitest run`
Expected: 모든 기존 테스트 + 새 LanguageContext 테스트 통과 (아직 어떤 화면 문구도 바뀌지 않았으므로 기존 assertion은 그대로 통과해야 한다).

- [ ] **Step 9: 커밋**

```bash
git add src/i18n/LanguageContext.jsx src/i18n/LanguageContext.test.jsx src/test-utils.jsx src/main.jsx src/pages/Home.test.jsx src/pages/SearchResults.test.jsx src/pages/Detail.test.jsx src/pages/About.test.jsx
git commit -m "Add LanguageContext with localStorage persistence and wire it app-wide"
```

---

### Task 4: localizeSegment 라이브러리

**Files:**
- Create: `src/lib/localizeSegment.js`
- Test: `src/lib/localizeSegment.test.js`

**Interfaces:**
- Consumes: `segmentTranslations.json`의 형태 (Task 1).
- Produces: `localizeSegment(segment, lang, translations = segmentTranslations)` — `segment`의 `drama_title, place_name, region, season, time_of_day, description, mood, activity, scene_elements` 필드를 번역으로 치환한 새 객체를 반환. 나머지 필드(`uid`, `segment_id`, `video_id`, `place_id`, `start_time`, `end_time`, `keyframe_path`)는 그대로 유지. 번역 레코드가 없으면 원본 그대로 반환.

- [ ] **Step 1: 실패하는 테스트 작성**

`src/lib/localizeSegment.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { localizeSegment } from './localizeSegment.js'
import { mockSegments } from '../data/mockSegments.js'

const sample = mockSegments.find((s) => s.segment_id === 'GOBLIN_01_SCENE_01')

describe('localizeSegment', () => {
  it('replaces localizable fields with the requested language', () => {
    const result = localizeSegment(sample, 'en')
    expect(result.drama_title).toBe('Guardian: The Lonely and Great God')
    expect(result.place_name).not.toBe(sample.place_name)
  })

  it('keeps non-localizable fields unchanged', () => {
    const result = localizeSegment(sample, 'en')
    expect(result.uid).toBe(sample.uid)
    expect(result.segment_id).toBe(sample.segment_id)
    expect(result.start_time).toBe(sample.start_time)
    expect(result.place_id).toBe(sample.place_id)
  })

  it('falls back to Korean when the requested language is missing from a record', () => {
    const translations = {
      [`${sample.segment_id}__${sample.segment_id}`]: {
        ko: { ...sample, description: 'ko-only description' },
      },
    }
    const result = localizeSegment(sample, 'en', translations)
    expect(result.description).toBe('ko-only description')
  })

  it('returns the original segment unchanged when no translation record exists', () => {
    const result = localizeSegment(sample, 'en', {})
    expect(result).toEqual(sample)
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run src/lib/localizeSegment.test.js`
Expected: FAIL — `Cannot find module './localizeSegment.js'`

- [ ] **Step 3: localizeSegment.js 작성**

`src/lib/localizeSegment.js`:

```js
import segmentTranslations from '../data/segmentTranslations.json'

const LOCALIZABLE_FIELDS = [
  'drama_title', 'place_name', 'region', 'season', 'time_of_day',
  'description', 'mood', 'activity', 'scene_elements',
]

export function localizeSegment(segment, lang, translations = segmentTranslations) {
  const keyframeId = `${segment.segment_id}__${segment.segment_id}`
  const record = translations[keyframeId]
  const localized = record?.[lang] ?? record?.ko
  if (!localized) return segment

  const result = { ...segment }
  for (const field of LOCALIZABLE_FIELDS) {
    result[field] = localized[field]
  }
  return result
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `npx vitest run src/lib/localizeSegment.test.js`
Expected: 4 tests pass.

- [ ] **Step 5: 커밋**

```bash
git add src/lib/localizeSegment.js src/lib/localizeSegment.test.js
git commit -m "Add localizeSegment to apply display translations at render time"
```

---

### Task 5: 계절/테마 라벨 다국어화

**Files:**
- Modify: `src/data/seasons.js`
- Modify: `src/data/themes.js`
- Modify: `src/components/SeasonSection.jsx`
- Modify: `src/components/SeasonSection.test.jsx`
- Modify: `src/components/ThemeSection.jsx`
- Modify: `src/components/ThemeSection.test.jsx`

**Interfaces:**
- Consumes: `useLanguage()` (Task 3).
- Produces: `seasons`/`themes` 배열의 각 항목이 `label: { ko, en, ja, zh }` 형태를 가짐. `id`, `icon`, `keywords`(themes만)는 변경 없음.

- [ ] **Step 1: seasons.js/themes.js 라벨을 언어별 객체로 변경**

`src/data/seasons.js` 전체:

```js
export const seasons = [
  { id: 'spring', icon: '🍃', label: { ko: '봄', en: 'Spring', ja: '春', zh: '春' } },
  { id: 'summer', icon: '☀', label: { ko: '여름', en: 'Summer', ja: '夏', zh: '夏' } },
  { id: 'autumn', icon: '🍂', label: { ko: '가을', en: 'Autumn', ja: '秋', zh: '秋' } },
  { id: 'winter', icon: '❄', label: { ko: '겨울', en: 'Winter', ja: '冬', zh: '冬' } },
]
```

`src/data/themes.js` 전체:

```js
// keywords map each tag onto real place_name/drama_title/description/mood/
// scene_elements/activity text in mockSegments.js. An empty array is honest:
// no matching data exists yet for that tag, so it correctly returns zero
// results (see lib/searchSegments.js matchesTheme) instead of fabricating
// matches or silently showing everything.
export const themes = [
  { id: 'night-view', icon: '🌃', label: { ko: '야경', en: 'Night View', ja: '夜景', zh: '夜景' }, keywords: ['night', 'skyscrapers', 'light trails', 'lighting'] },
  { id: 'drive', icon: '🚗', label: { ko: '드라이브', en: 'Drive', ja: 'ドライブ', zh: '自驾游' }, keywords: ['driving', 'bus', 'road'] },
  { id: 'cherry-blossom', icon: '🌸', label: { ko: '벚꽃', en: 'Cherry Blossom', ja: '桜', zh: '樱花' }, keywords: [] },
  { id: 'autumn-leaves', icon: '🍁', label: { ko: '단풍', en: 'Autumn Leaves', ja: '紅葉', zh: '红叶' }, keywords: ['autumn'] },
  { id: 'beach', icon: '🏖', label: { ko: '해변', en: 'Beach', ja: 'ビーチ', zh: '海滩' }, keywords: ['beach', 'ocean', 'sea'] },
  { id: 'cafe', icon: '☕', label: { ko: '카페', en: 'Cafe', ja: 'カフェ', zh: '咖啡厅' }, keywords: [] },
  { id: 'food', icon: '🍜', label: { ko: '음식', en: 'Food', ja: 'グルメ', zh: '美食' }, keywords: [] },
  { id: 'drama', icon: '🎬', label: { ko: '드라마', en: 'Drama', ja: 'ドラマ', zh: '电视剧' }, keywords: ['hanok', 'palace', 'traditional'] },
]
```

- [ ] **Step 2: SeasonSection.jsx / ThemeSection.jsx가 현재 언어의 라벨을 쓰도록 수정**

`src/components/SeasonSection.jsx` 전체:

```jsx
import { seasons } from '../data/seasons.js'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function SeasonSection({ selectedId, onSelect }) {
  const { lang } = useLanguage()
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
      {seasons.map((season) => {
        const active = season.id === selectedId
        return (
          <div
            key={season.id}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(active ? null : season.id)}
            style={{
              background: active ? 'var(--color-accent)' : '#fff',
              color: active ? 'white' : 'var(--color-text)',
              border: '1px solid #e2e8f0',
              borderRadius: 14,
              padding: '10px 14px',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            <span aria-hidden="true">{season.icon}</span> <span>{season.label[lang]}</span>
          </div>
        )
      })}
    </div>
  )
}
```

`src/components/ThemeSection.jsx` 전체:

```jsx
import { themes } from '../data/themes.js'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function ThemeSection({ selectedId, onSelect }) {
  const { lang } = useLanguage()
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
      {themes.map((theme) => {
        const active = theme.id === selectedId
        return (
          <div
            key={theme.id}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(active ? null : theme.id)}
            style={{
              background: active ? 'var(--color-primary)' : '#EFF6FF',
              color: active ? 'white' : 'var(--color-primary)',
              borderRadius: 20,
              padding: '8px 14px',
              fontSize: 12.5,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <span aria-hidden="true">{theme.icon}</span> <span>{theme.label[lang]}</span>
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 3: 기존 테스트를 Korean 기본값 기준으로 갱신 + 언어 전환 테스트 추가**

`src/components/SeasonSection.test.jsx` 전체:

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import SeasonSection from './SeasonSection.jsx'
import { renderWithLanguage } from '../test-utils.jsx'

describe('SeasonSection', () => {
  it('renders all 4 season chips in Korean by default', () => {
    renderWithLanguage(<SeasonSection selectedId={null} onSelect={() => {}} />)
    expect(screen.getByText('봄')).toBeInTheDocument()
    expect(screen.getByText('여름')).toBeInTheDocument()
    expect(screen.getByText('가을')).toBeInTheDocument()
    expect(screen.getByText('겨울')).toBeInTheDocument()
  })

  it('calls onSelect with the season id when a chip is clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    renderWithLanguage(<SeasonSection selectedId={null} onSelect={onSelect} />)
    await user.click(screen.getByText('여름'))
    expect(onSelect).toHaveBeenCalledWith('summer')
  })

  it('calls onSelect with null when the selected chip is clicked again', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    renderWithLanguage(<SeasonSection selectedId="summer" onSelect={onSelect} />)
    await user.click(screen.getByText('여름'))
    expect(onSelect).toHaveBeenCalledWith(null)
  })
})
```

`src/components/ThemeSection.test.jsx` 전체:

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import ThemeSection from './ThemeSection.jsx'
import { renderWithLanguage } from '../test-utils.jsx'

describe('ThemeSection', () => {
  it('renders all 8 theme tags in Korean by default', () => {
    renderWithLanguage(<ThemeSection selectedId={null} onSelect={() => {}} />)
    expect(screen.getByText('해변')).toBeInTheDocument()
    expect(screen.getByText('카페')).toBeInTheDocument()
    expect(screen.getByText('드라마')).toBeInTheDocument()
  })

  it('calls onSelect with the theme id when a tag is clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    renderWithLanguage(<ThemeSection selectedId={null} onSelect={onSelect} />)
    await user.click(screen.getByText('해변'))
    expect(onSelect).toHaveBeenCalledWith('beach')
  })
})
```

- [ ] **Step 4: 테스트 실행**

Run: `npx vitest run src/components/SeasonSection.test.jsx src/components/ThemeSection.test.jsx`
Expected: 5 tests pass. (Home.test.jsx는 아직 영어 "Summer" 텍스트를 찾으므로 이 시점엔 깨진다 — Task 7에서 고친다.)

- [ ] **Step 5: 커밋**

```bash
git add src/data/seasons.js src/data/themes.js src/components/SeasonSection.jsx src/components/SeasonSection.test.jsx src/components/ThemeSection.jsx src/components/ThemeSection.test.jsx
git commit -m "Add ko/en/ja/zh labels to season and theme chips"
```

---

### Task 6: Header — 언어 전환 버튼 + 메뉴 번역

**Files:**
- Modify: `src/components/Header.jsx`
- Modify: `src/components/Header.test.jsx`

**Interfaces:**
- Consumes: `useLanguage()` (Task 3).

- [ ] **Step 1: Header.jsx에 언어 버튼과 t() 적용**

`src/components/Header.jsx` 전체:

```jsx
import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext.jsx'

const LANGUAGE_OPTIONS = [
  { code: 'ko', label: 'KO' },
  { code: 'en', label: 'EN' },
  { code: 'ja', label: 'JA' },
  { code: 'zh', label: 'ZH' },
]

export default function Header() {
  const { lang, setLang, t } = useLanguage()

  return (
    <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 24px', background: '#fff' }}>
      <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, color: 'var(--color-primary)', fontSize: 18 }}>
        <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--color-accent)', display: 'inline-block' }} />
        K-Tour AI
      </Link>
      <nav style={{ display: 'flex', gap: 20, alignItems: 'center', fontSize: 14, color: 'var(--color-text-muted)' }}>
        <Link to="/">{t('nav_home')}</Link>
        <Link to="/search">{t('nav_search')}</Link>
        <Link to="/about">{t('nav_about')}</Link>
        <div style={{ display: 'flex', gap: 6 }}>
          {LANGUAGE_OPTIONS.map((option) => (
            <button
              key={option.code}
              onClick={() => setLang(option.code)}
              aria-pressed={lang === option.code}
              style={{
                border: 'none',
                borderRadius: 10,
                padding: '4px 8px',
                fontSize: 11.5,
                fontWeight: 700,
                cursor: 'pointer',
                background: lang === option.code ? 'var(--color-primary)' : '#EFF6FF',
                color: lang === option.code ? 'white' : 'var(--color-primary)',
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      </nav>
    </header>
  )
}
```

- [ ] **Step 2: 테스트 갱신**

`src/components/Header.test.jsx` 전체:

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import Header from './Header.jsx'
import { renderWithLanguage } from '../test-utils.jsx'

describe('Header', () => {
  it('renders the logo text', () => {
    renderWithLanguage(<MemoryRouter><Header /></MemoryRouter>)
    expect(screen.getByText('K-Tour AI')).toBeInTheDocument()
  })

  it('renders nav labels in Korean by default', () => {
    renderWithLanguage(<MemoryRouter><Header /></MemoryRouter>)
    expect(screen.getByRole('link', { name: '홈' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: '소개' })).toHaveAttribute('href', '/about')
  })

  it('switches nav labels to English when the EN button is clicked', async () => {
    const user = userEvent.setup()
    renderWithLanguage(<MemoryRouter><Header /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: 'EN' }))
    expect(screen.getByRole('link', { name: 'Home' })).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: 테스트 실행**

Run: `npx vitest run src/components/Header.test.jsx`
Expected: 3 tests pass.

- [ ] **Step 4: 커밋**

```bash
git add src/components/Header.jsx src/components/Header.test.jsx
git commit -m "Add KO/EN/JA/ZH language switcher and translate nav labels"
```

---

### Task 7: Home 페이지 (Hero, SearchBar, 섹션 제목, 인기 드라마)

**Files:**
- Modify: `src/components/Hero.jsx`
- Modify: `src/components/SearchBar.jsx`
- Modify: `src/components/SearchBar.test.jsx`
- Modify: `src/components/DramaSection.jsx`
- Modify: `src/components/DramaSection.test.jsx`
- Modify: `src/pages/Home.jsx`
- Modify: `src/pages/Home.test.jsx`

**Interfaces:**
- Consumes: `useLanguage()` (Task 3), `localizeSegment()` (Task 4).

- [ ] **Step 1: Hero.jsx**

`src/components/Hero.jsx` 전체:

```jsx
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function Hero() {
  const { t } = useLanguage()
  return (
    <div style={{ background: 'linear-gradient(135deg,#2563EB,#1d4ed8)', padding: '48px 24px 64px', textAlign: 'center', color: 'white' }}>
      <h1 style={{ fontSize: 26, margin: '0 0 8px', fontWeight: 800, whiteSpace: 'pre-line' }}>
        {t('hero_title')}
      </h1>
      <p style={{ fontSize: 14, opacity: 0.9, margin: 0 }}>{t('hero_subtitle')}</p>
    </div>
  )
}
```

- [ ] **Step 2: SearchBar.jsx + 테스트**

`src/components/SearchBar.jsx` 전체:

```jsx
import { useState } from 'react'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function SearchBar({ initialValue = '', onSearch }) {
  const [value, setValue] = useState(initialValue)
  const { t } = useLanguage()

  function submit() {
    onSearch(value.trim())
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter') submit()
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: '#fff', borderRadius: 16, padding: '14px 18px', boxShadow: '0 10px 30px rgba(37,99,235,.15)' }}>
      <span>🔍</span>
      <input
        style={{ flex: 1, border: 'none', outline: 'none', fontSize: 14 }}
        placeholder={t('search_placeholder')}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <button onClick={submit} aria-label="search" style={{ border: 'none', background: 'var(--color-primary)', color: 'white', borderRadius: 20, padding: '8px 16px', fontWeight: 700 }}>
        {t('search_button')}
      </button>
    </div>
  )
}
```

`src/components/SearchBar.test.jsx` 전체:

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import SearchBar from './SearchBar.jsx'
import { renderWithLanguage } from '../test-utils.jsx'

describe('SearchBar', () => {
  it('calls onSearch with the typed value when Enter is pressed', async () => {
    const user = userEvent.setup()
    const onSearch = vi.fn()
    renderWithLanguage(<SearchBar onSearch={onSearch} />)
    const input = screen.getByPlaceholderText('여행지를 검색해보세요...')
    await user.type(input, 'lotus pond{Enter}')
    expect(onSearch).toHaveBeenCalledWith('lotus pond')
  })

  it('calls onSearch when the search button is clicked', async () => {
    const user = userEvent.setup()
    const onSearch = vi.fn()
    renderWithLanguage(<SearchBar onSearch={onSearch} />)
    const input = screen.getByPlaceholderText('여행지를 검색해보세요...')
    await user.type(input, 'duck')
    await user.click(screen.getByRole('button', { name: '검색' }))
    expect(onSearch).toHaveBeenCalledWith('duck')
  })

  it('pre-fills the input from initialValue', () => {
    renderWithLanguage(<SearchBar initialValue="autumn trail" onSearch={() => {}} />)
    expect(screen.getByPlaceholderText('여행지를 검색해보세요...')).toHaveValue('autumn trail')
  })
})
```

- [ ] **Step 3: DramaSection.jsx가 drama_title을 로컬라이즈하도록 수정 + 테스트**

`src/components/DramaSection.jsx` 전체:

```jsx
import { Link } from 'react-router-dom'
import { mockSegments } from '../data/mockSegments.js'
import { getFeaturedDramas } from '../lib/getFeaturedDramas.js'
import { localizeSegment } from '../lib/localizeSegment.js'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function DramaSection() {
  const { lang } = useLanguage()
  const dramas = getFeaturedDramas(mockSegments).map((segment) => localizeSegment(segment, lang))

  return (
    <div style={{ display: 'flex', gap: 14, overflowX: 'auto', paddingBottom: 8 }}>
      {dramas.map((drama) => (
        <Link key={drama.uid} to={`/segment/${drama.uid}`} style={{ flex: '0 0 140px' }}>
          <img
            src={`${import.meta.env.BASE_URL}${drama.keyframe_path}`}
            alt={drama.drama_title}
            style={{ width: '100%', height: 90, objectFit: 'cover', borderRadius: 16 }}
          />
          <p style={{ fontSize: 12.5, margin: '8px 0 0', fontWeight: 600, color: 'var(--color-text)' }}>{drama.drama_title}</p>
        </Link>
      ))}
    </div>
  )
}
```

`src/components/DramaSection.test.jsx` 전체:

```jsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import DramaSection from './DramaSection.jsx'
import { renderWithLanguage } from '../test-utils.jsx'

describe('DramaSection', () => {
  it('renders real drama titles from mockSegments', () => {
    renderWithLanguage(<MemoryRouter><DramaSection /></MemoryRouter>)
    expect(screen.getByText('폭싹 속았수다')).toBeInTheDocument()
    expect(screen.getByText('도깨비')).toBeInTheDocument()
  })

  it('links each drama to its detail page', () => {
    renderWithLanguage(<MemoryRouter><DramaSection /></MemoryRouter>)
    const links = screen.getAllByRole('link')
    expect(links.length).toBeGreaterThan(0)
    for (const link of links) {
      expect(link.getAttribute('href')).toMatch(/^\/segment\//)
    }
  })
})
```

- [ ] **Step 4: Home.jsx 섹션 제목을 t()로 교체**

`src/pages/Home.jsx` 전체:

```jsx
import { useNavigate } from 'react-router-dom'
import Header from '../components/Header.jsx'
import Hero from '../components/Hero.jsx'
import SearchBar from '../components/SearchBar.jsx'
import SeasonSection from '../components/SeasonSection.jsx'
import ThemeSection from '../components/ThemeSection.jsx'
import DramaSection from '../components/DramaSection.jsx'
import Footer from '../components/Footer.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function Home() {
  const navigate = useNavigate()
  const { t } = useLanguage()

  function handleSearch(query) {
    navigate(`/search?q=${encodeURIComponent(query)}`)
  }

  function handleSeasonSelect(seasonId) {
    if (seasonId) navigate(`/search?season=${encodeURIComponent(seasonId)}`)
  }

  function handleThemeSelect(themeId) {
    if (themeId) navigate(`/search?theme=${encodeURIComponent(themeId)}`)
  }

  return (
    <div>
      <Header />
      <Hero />
      <div style={{ margin: '-32px 24px 0' }}>
        <SearchBar onSearch={handleSearch} />
      </div>
      <section style={{ padding: '28px 24px 4px' }}>
        <h3 style={{ fontSize: 14, color: '#334155' }}>{t('home_section_season')}</h3>
        <SeasonSection selectedId={null} onSelect={handleSeasonSelect} />
      </section>
      <section style={{ padding: '28px 24px 4px' }}>
        <h3 style={{ fontSize: 14, color: '#334155' }}>{t('home_section_theme')}</h3>
        <ThemeSection selectedId={null} onSelect={handleThemeSelect} />
      </section>
      <section style={{ padding: '28px 24px' }}>
        <h3 style={{ fontSize: 14, color: '#334155' }}>🔥 {t('home_section_dramas')}</h3>
        <DramaSection />
      </section>
      <Footer />
    </div>
  )
}
```

- [ ] **Step 5: Home.test.jsx를 한국어 기본값 기준으로 갱신**

`src/pages/Home.test.jsx`의 `describe` 블록만 아래로 교체 (Task 3에서 만든 `renderHome` 헬퍼는 그대로 유지):

```jsx
describe('Home', () => {
  it('renders the hero tagline and search bar', () => {
    renderHome()
    expect(screen.getByText(/K-드라마/)).toBeInTheDocument()
    expect(screen.getByPlaceholderText('여행지를 검색해보세요...')).toBeInTheDocument()
  })

  it('navigates to /search?q=... when a search is submitted', async () => {
    const user = userEvent.setup()
    renderHome()
    await user.type(screen.getByPlaceholderText('여행지를 검색해보세요...'), 'lotus{Enter}')
    expect(screen.getByTestId('location')).toHaveTextContent('/search?q=lotus')
  })

  it('navigates to /search?season=... when a season chip is clicked', async () => {
    const user = userEvent.setup()
    renderHome()
    await user.click(screen.getByText('여름'))
    expect(screen.getByTestId('location')).toHaveTextContent('/search?season=summer')
  })
})
```

- [ ] **Step 6: 테스트 실행**

Run: `npx vitest run src/components/SearchBar.test.jsx src/components/DramaSection.test.jsx src/pages/Home.test.jsx`
Expected: 9 tests pass.

- [ ] **Step 7: 커밋**

```bash
git add src/components/Hero.jsx src/components/SearchBar.jsx src/components/SearchBar.test.jsx src/components/DramaSection.jsx src/components/DramaSection.test.jsx src/pages/Home.jsx src/pages/Home.test.jsx
git commit -m "Translate Home page copy and localize featured drama titles"
```

---

### Task 8: SearchResults 페이지

**Files:**
- Modify: `src/pages/SearchResults.jsx`
- Modify: `src/pages/SearchResults.test.jsx`

**Interfaces:**
- Consumes: `useLanguage()`, `localizeSegment()`.

- [ ] **Step 1: SearchResults.jsx 수정**

`src/pages/SearchResults.jsx` 전체 (기존 `themes.find((t) => ...)`의 콜백 인자명을 `theme`으로 바꿔 `t()` 함수와의 이름 충돌을 피한다):

```jsx
import { useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import Header from '../components/Header.jsx'
import SearchBar from '../components/SearchBar.jsx'
import ResultCard from '../components/ResultCard.jsx'
import EmptyState from '../components/EmptyState.jsx'
import Footer from '../components/Footer.jsx'
import KakaoMap from '../components/KakaoMap.jsx'
import { mockSegments } from '../data/mockSegments.js'
import { themes } from '../data/themes.js'
import { placeCoordinates } from '../data/placeCoordinates.js'
import { searchSegments } from '../lib/searchSegments.js'
import { getMapMarkers } from '../lib/getMapMarkers.js'
import { localizeSegment } from '../lib/localizeSegment.js'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function SearchResults() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [showMap, setShowMap] = useState(false)
  const { lang, t } = useLanguage()

  const query = searchParams.get('q') || ''
  const season = searchParams.get('season')
  const themeId = searchParams.get('theme')
  const themeKeywords = themeId ? themes.find((theme) => theme.id === themeId)?.keywords || [] : null

  const results = searchSegments(mockSegments, { query, season, themeKeywords })
  const localizedResults = results.map((segment) => localizeSegment(segment, lang))

  function handleSearch(newQuery) {
    navigate(`/search?q=${encodeURIComponent(newQuery)}`)
  }

  return (
    <div>
      <Header />
      <div style={{ padding: '16px 24px' }}>
        <SearchBar initialValue={query} onSearch={handleSearch} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 24px' }}>
        <span style={{ fontSize: 12.5, color: '#64748b' }}>{t('results_count', { n: results.length })}</span>
        <button
          onClick={() => setShowMap((v) => !v)}
          style={{ background: 'var(--color-primary)', color: 'white', border: 'none', borderRadius: 20, padding: '8px 16px', fontSize: 12.5, fontWeight: 700 }}
        >
          🗺️ {showMap ? t('view_as_list') : t('view_as_map')}
        </button>
      </div>
      {showMap && (
        <div style={{ margin: '14px 24px' }}>
          <KakaoMap markers={getMapMarkers(results, placeCoordinates)} />
        </div>
      )}
      <div style={{ padding: '14px 24px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {localizedResults.length === 0 ? (
          <EmptyState message={t('empty_results_message')} />
        ) : (
          localizedResults.map((segment) => <ResultCard key={segment.uid} segment={segment} />)
        )}
      </div>
      <Footer />
    </div>
  )
}
```

- [ ] **Step 2: 테스트에 언어 전환 케이스 추가 (기존 assertion은 한국어 기본값이라 그대로 유지)**

`src/pages/SearchResults.test.jsx`의 `describe` 블록 마지막에 새 테스트를 추가 (기존 4개 테스트는 그대로 둔다):

```jsx
  it('shows results in English when the language is switched to en', async () => {
    const user = userEvent.setup()
    renderAt('/search?q=canola')
    await user.click(screen.getByRole('button', { name: 'EN' }))
    expect(await screen.findByText('Hagwon Tourist Farm')).toBeInTheDocument()
  })
```

- [ ] **Step 3: 테스트 실행**

Run: `npx vitest run src/pages/SearchResults.test.jsx`
Expected: 5 tests pass.

- [ ] **Step 4: 커밋**

```bash
git add src/pages/SearchResults.jsx src/pages/SearchResults.test.jsx
git commit -m "Translate SearchResults page copy and localize result cards"
```

---

### Task 9: Detail 페이지

**Files:**
- Modify: `src/pages/Detail.jsx`
- Modify: `src/pages/Detail.test.jsx`

**Interfaces:**
- Consumes: `useLanguage()`, `localizeSegment()`.

- [ ] **Step 1: Detail.jsx 수정**

`src/pages/Detail.jsx` 전체:

```jsx
import { useParams, Link } from 'react-router-dom'
import Header from '../components/Header.jsx'
import Footer from '../components/Footer.jsx'
import KakaoMap from '../components/KakaoMap.jsx'
import { mockSegments } from '../data/mockSegments.js'
import { placeCoordinates } from '../data/placeCoordinates.js'
import { videoSources } from '../data/videoSources.js'
import { getMapMarkers } from '../lib/getMapMarkers.js'
import { localizeSegment } from '../lib/localizeSegment.js'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function Detail() {
  const { segmentId: uid } = useParams()
  const { lang, t } = useLanguage()
  const found = mockSegments.find((s) => s.uid === uid)
  const segment = found ? localizeSegment(found, lang) : undefined
  const videoSource = segment ? videoSources[segment.video_id] : undefined

  if (!segment) {
    return (
      <div>
        <Header />
        <div style={{ padding: 48, textAlign: 'center', color: '#94a3b8' }}>
          <p>{t('detail_not_found')}</p>
          <Link to="/search" style={{ color: 'var(--color-primary)' }}>{t('detail_back_to_search')}</Link>
        </div>
        <Footer />
      </div>
    )
  }

  return (
    <div>
      <Header />
      <div style={{ position: 'relative', height: 200, background: 'linear-gradient(135deg,#c7d2fe,#a5f3fc)' }}>
        <img src={`${import.meta.env.BASE_URL}${segment.keyframe_path}`} alt={segment.place_name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      </div>
      <div style={{ padding: '20px 24px' }}>
        <h2 style={{ margin: 0, fontSize: 19 }}>{segment.place_name}</h2>
        <p style={{ fontSize: 12.5, color: '#64748b', margin: '4px 0 14px' }}>
          📍 {segment.region} · ⏱ {segment.start_time.toFixed(2)}s–{segment.end_time.toFixed(2)}s
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
          {segment.mood.slice(0, 3).map((tag) => (
            <span key={tag} style={{ background: '#EFF6FF', color: 'var(--color-primary)', borderRadius: 16, padding: '6px 12px', fontSize: 12, fontWeight: 600 }}>
              {tag}
            </span>
          ))}
        </div>
        <p style={{ fontSize: 13.5, color: '#334155', lineHeight: 1.6, marginBottom: 20 }}>{segment.description}</p>
        <div style={{ background: '#fff', borderRadius: 16, padding: 16, marginBottom: 14, boxShadow: '0 4px 14px rgba(15,23,42,.05)' }}>
          <h4 style={{ margin: '0 0 10px', fontSize: 13 }}>🎬 {t('detail_drama_heading')}</h4>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 700 }}>{segment.drama_title}</p>
          {videoSource && (
            <a
              href={videoSource.source_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ display: 'inline-block', marginTop: 12, background: 'var(--color-primary)', color: 'white', borderRadius: 20, padding: '8px 16px', fontSize: 12.5, fontWeight: 700, textDecoration: 'none' }}
            >
              ▶ {t('detail_play_original')}
            </a>
          )}
        </div>
        <div style={{ background: '#fff', borderRadius: 16, padding: 16, boxShadow: '0 4px 14px rgba(15,23,42,.05)' }}>
          <h4 style={{ margin: '0 0 10px', fontSize: 13 }}>📍 {t('detail_location_heading')}</h4>
          <KakaoMap markers={getMapMarkers([segment], placeCoordinates)} />
        </div>
      </div>
      <Footer />
    </div>
  )
}
```

- [ ] **Step 2: 테스트 갱신**

`display_translations.json`의 GOBLIN_01_SCENE_01 `place_name`은 `강릉 주문진방파제`로, `mockSegments.js`의 원본 `강릉 주문진`과 문구가 조금 다르다(두 실제 데이터 소스 간 차이). `localizeSegment` 적용 이후에는 번역 카탈로그 값이 화면에 표시되므로, 이 문구가 새로운 기준값이다.

`src/pages/Detail.test.jsx`의 `describe` 블록만 아래로 교체 (Task 3에서 만든 `renderAt` 헬퍼는 그대로 유지):

```jsx
describe('Detail', () => {
  it('renders the place name and drama title for a known segment', () => {
    renderAt('keyframes_GOBLIN_01_GOBLIN_01_SCENE_01_jpg')
    expect(screen.getByText('강릉 주문진방파제')).toBeInTheDocument()
    expect(screen.getByText('도깨비')).toBeInTheDocument()
  })

  it('renders a map marker for the segment\'s place', async () => {
    renderAt('keyframes_GOBLIN_01_GOBLIN_01_SCENE_01_jpg')
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(window.kakao.maps.Marker).toHaveBeenCalledTimes(1)
  })

  it('renders a not-found message for an unknown uid', () => {
    renderAt('does_not_exist')
    expect(screen.getByText(/찾을 수 없어요/)).toBeInTheDocument()
  })

  it('links to the original video source for the segment', () => {
    renderAt('keyframes_GOBLIN_01_GOBLIN_01_SCENE_01_jpg')
    const link = screen.getByRole('link', { name: /원본 영상 재생/ })
    expect(link).toHaveAttribute('href', 'https://www.youtube.com/watch?v=mCeMgl6rR-U')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
  })

  it('shows the place name in English when the language is switched to en', async () => {
    const user = userEvent.setup()
    renderAt('keyframes_GOBLIN_01_GOBLIN_01_SCENE_01_jpg')
    await user.click(screen.getByRole('button', { name: 'EN' }))
    expect(screen.getByText('Jumunjin Breakwater')).toBeInTheDocument()
  })
})
```

`import userEvent from '@testing-library/user-event'`를 파일 상단 import 목록에 추가한다.

- [ ] **Step 3: 테스트 실행**

Run: `npx vitest run src/pages/Detail.test.jsx`
Expected: 5 tests pass.

- [ ] **Step 4: 커밋**

```bash
git add src/pages/Detail.jsx src/pages/Detail.test.jsx
git commit -m "Translate Detail page copy and localize segment content"
```

---

### Task 10: KakaoMap 문구

**Files:**
- Modify: `src/components/KakaoMap.jsx`
- Modify: `src/components/KakaoMap.test.jsx`

**Interfaces:**
- Consumes: `useLanguage()`.

- [ ] **Step 1: KakaoMap.jsx의 하드코딩 문구를 t()로 교체**

`src/components/KakaoMap.jsx` 전체를 아래로 교체한다 (SDK 로딩 로직인 `loadKakaoSdk`와 지도 생성 `useEffect`는 지금 코드 그대로이고, `useLanguage()` import/호출과 4개 문구만 바뀐다):

```jsx
import { useEffect, useRef, useState } from 'react'
import { useLanguage } from '../i18n/LanguageContext.jsx'

const KAKAO_SDK_SRC = 'https://dapi.kakao.com/v2/maps/sdk.js'
const DEFAULT_TIMEOUT_MS = 8000

function loadKakaoSdk(appKey, timeoutMs) {
  const loadPromise = new Promise((resolve, reject) => {
    if (window.kakao && window.kakao.maps) {
      resolve(window.kakao)
      return
    }
    // Always start from a fresh <script> tag. Reusing one whose load/error
    // event already fired (e.g. on retry after a failure) would never
    // resolve, since those events don't replay for newly added listeners.
    document.querySelectorAll('script[data-kakao-map-sdk]').forEach((old) => old.remove())
    const script = document.createElement('script')
    // Cache-bust: this app's Kakao service was disabled for part of testing,
    // during which some clients cached an error response for this exact URL.
    // A stable query string could keep serving that stale cached response
    // (which trips ERR_BLOCKED_BY_ORB); a per-load timestamp forces a fresh
    // fetch every time.
    script.src = `${KAKAO_SDK_SRC}?appkey=${appKey}&autoload=false&_=${Date.now()}`
    script.dataset.kakaoMapSdk = 'true'
    script.addEventListener('load', () => window.kakao.maps.load(() => resolve(window.kakao)))
    script.addEventListener('error', () => reject(new Error('Failed to load Kakao Maps SDK')))
    document.head.appendChild(script)
  })

  const timeoutPromise = new Promise((_, reject) => {
    setTimeout(() => reject(new Error('Timed out loading Kakao Maps SDK')), timeoutMs)
  })

  return Promise.race([loadPromise, timeoutPromise])
}

export default function KakaoMap({ markers, timeoutMs = DEFAULT_TIMEOUT_MS }) {
  const containerRef = useRef(null)
  const [status, setStatus] = useState('loading')
  const [retryCount, setRetryCount] = useState(0)
  const { t } = useLanguage()

  useEffect(() => {
    if (markers.length === 0) return

    let cancelled = false
    let resizeObserver
    setStatus('loading')
    const appKey = import.meta.env.VITE_KAKAO_MAP_KEY

    loadKakaoSdk(appKey, timeoutMs)
      .then((kakao) => {
        if (cancelled || !containerRef.current) return

        const center = new kakao.maps.LatLng(markers[0].latitude, markers[0].longitude)
        const map = new kakao.maps.Map(containerRef.current, { center, level: 8 })
        const bounds = new kakao.maps.LatLngBounds()

        markers.forEach((marker) => {
          const position = new kakao.maps.LatLng(marker.latitude, marker.longitude)
          new kakao.maps.Marker({ map, position, title: marker.label })
          bounds.extend(position)
        })

        // The map is created while its container is inside a conditionally
        // rendered (list/map toggle) flex layout, so the container isn't
        // always at its final width on the first paint yet. relayout() makes
        // the map re-measure the container; without it, the map keeps the
        // undersized dimensions it was born with and renders as a small tile
        // repeated as blank watermark. The ResizeObserver reapplies this if
        // the container resizes again later (toggle, window resize).
        const fitToContainer = () => {
          map.relayout()
          if (markers.length > 1) {
            map.setBounds(bounds)
          } else {
            map.setCenter(center)
          }
        }
        fitToContainer()

        if (typeof ResizeObserver !== 'undefined') {
          resizeObserver = new ResizeObserver(fitToContainer)
          resizeObserver.observe(containerRef.current)
        }

        setStatus('ready')
      })
      .catch(() => {
        if (cancelled) return
        setStatus('error')
      })

    return () => {
      cancelled = true
      if (resizeObserver) resizeObserver.disconnect()
    }
  }, [markers, timeoutMs, retryCount])

  if (markers.length === 0) {
    return (
      <div style={{ height: 200, borderRadius: 16, background: '#eef2f7', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', fontSize: 13 }}>
        🗺️ {t('map_empty')}
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div style={{ height: 200, borderRadius: 16, background: '#eef2f7', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10, color: '#94a3b8', fontSize: 13 }}>
        <span>🗺️ {t('map_error')}</span>
        <button
          onClick={() => setRetryCount((n) => n + 1)}
          style={{ border: 'none', background: 'var(--color-primary)', color: 'white', borderRadius: 20, padding: '8px 16px', fontSize: 12.5, fontWeight: 700 }}
        >
          {t('map_retry')}
        </button>
      </div>
    )
  }

  return (
    <div style={{ position: 'relative' }}>
      {status === 'loading' && (
        <div style={{ height: 260, borderRadius: 16, background: '#eef2f7', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', fontSize: 13 }}>
          {t('map_loading')}
        </div>
      )}
      <div
        ref={containerRef}
        style={{ width: '100%', height: 260, borderRadius: 16, overflow: 'hidden', display: status === 'ready' ? 'block' : 'none' }}
      />
    </div>
  )
}
```

- [ ] **Step 2: 테스트에 LanguageProvider 래핑 추가**

`src/components/KakaoMap.test.jsx` 전체를 아래로 교체한다 (기존 7개 테스트의 assertion 문자열은 바꾸지 않는다 — 기본 언어가 한국어라 기존 한국어 문구와 그대로 일치한다. 모든 `render(<KakaoMap ... />)` 호출만 `renderWithLanguage(<KakaoMap ... />)`로 바뀐다):

```jsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import KakaoMap from './KakaoMap.jsx'
import { renderWithLanguage } from '../test-utils.jsx'

function flushPromises() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}

const oneMarker = [{ place_id: 'P001', label: '경복궁', latitude: 37.5, longitude: 127.0 }]

describe('KakaoMap', () => {
  beforeEach(() => {
    delete window.kakao
  })

  afterEach(() => {
    vi.useRealTimers()
    document.querySelectorAll('script[data-kakao-map-sdk]').forEach((s) => s.remove())
  })

  it('shows an empty message when there are no markers', () => {
    renderWithLanguage(<KakaoMap markers={[]} />)
    expect(screen.getByText(/지도에 표시할 위치 정보가 없어요/)).toBeInTheDocument()
  })

  it('shows a loading message before the SDK resolves', () => {
    renderWithLanguage(<KakaoMap markers={oneMarker} />)
    expect(screen.getByText(/지도를 불러오는 중/)).toBeInTheDocument()
  })

  it('renders a map once the SDK loads', async () => {
    window.kakao = {
      maps: {
        LatLng: vi.fn(function LatLng() {}),
        LatLngBounds: vi.fn(function LatLngBounds() {
          this.extend = vi.fn()
        }),
        Map: vi.fn(function Map() {
          this.setBounds = vi.fn()
          this.setCenter = vi.fn()
          this.relayout = vi.fn()
        }),
        Marker: vi.fn(function Marker() {}),
        load: (callback) => callback(),
      },
    }
    renderWithLanguage(<KakaoMap markers={oneMarker} />)
    await flushPromises()
    expect(window.kakao.maps.Map).toHaveBeenCalledTimes(1)
    expect(screen.queryByText(/지도를 불러오는 중/)).not.toBeInTheDocument()
  })

  it('relays out the map so a container mis-measured at creation time re-fits', async () => {
    window.kakao = {
      maps: {
        LatLng: vi.fn(function LatLng() {}),
        LatLngBounds: vi.fn(function LatLngBounds() {
          this.extend = vi.fn()
        }),
        Map: vi.fn(function Map() {
          this.setBounds = vi.fn()
          this.setCenter = vi.fn()
          this.relayout = vi.fn()
        }),
        Marker: vi.fn(function Marker() {}),
        load: (callback) => callback(),
      },
    }
    renderWithLanguage(<KakaoMap markers={oneMarker} />)
    await flushPromises()
    const mapInstance = window.kakao.maps.Map.mock.results[0].value
    expect(mapInstance.relayout).toHaveBeenCalled()
    expect(mapInstance.setCenter).toHaveBeenCalled()
  })

  it('shows an error message and a retry button when the SDK script fails to load', async () => {
    renderWithLanguage(<KakaoMap markers={oneMarker} />)
    const script = document.querySelector('script[data-kakao-map-sdk]')
    script.dispatchEvent(new Event('error'))
    await waitFor(() => {
      expect(screen.getByText(/지도를 불러오지 못했어요/)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /다시 시도/ })).toBeInTheDocument()
  })

  it('shows an error message if the SDK never responds within the timeout', async () => {
    vi.useFakeTimers()
    renderWithLanguage(<KakaoMap markers={oneMarker} timeoutMs={5000} />)
    await vi.advanceTimersByTimeAsync(5001)
    await vi.advanceTimersByTimeAsync(0)
    expect(screen.getByText(/지도를 불러오지 못했어요/)).toBeInTheDocument()
  })

  it('retries loading when the retry button is clicked', async () => {
    vi.useRealTimers()
    const user = userEvent.setup()
    renderWithLanguage(<KakaoMap markers={oneMarker} />)
    const script = document.querySelector('script[data-kakao-map-sdk]')
    script.dispatchEvent(new Event('error'))
    await waitFor(() => screen.getByRole('button', { name: /다시 시도/ }))

    window.kakao = {
      maps: {
        LatLng: vi.fn(function LatLng() {}),
        LatLngBounds: vi.fn(function LatLngBounds() {
          this.extend = vi.fn()
        }),
        Map: vi.fn(function Map() {
          this.setBounds = vi.fn()
          this.setCenter = vi.fn()
          this.relayout = vi.fn()
        }),
        Marker: vi.fn(function Marker() {}),
        load: (callback) => callback(),
      },
    }
    await user.click(screen.getByRole('button', { name: /다시 시도/ }))
    await flushPromises()
    expect(window.kakao.maps.Map).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 3: 테스트 실행**

Run: `npx vitest run src/components/KakaoMap.test.jsx`
Expected: 7 tests pass.

- [ ] **Step 4: 커밋**

```bash
git add src/components/KakaoMap.jsx src/components/KakaoMap.test.jsx
git commit -m "Translate KakaoMap status copy"
```

---

### Task 11: About 페이지

**Files:**
- Modify: `src/pages/About.jsx`
- Modify: `src/pages/About.test.jsx`

**Interfaces:**
- Consumes: `useLanguage()`.

- [ ] **Step 1: About.jsx 수정**

`src/pages/About.jsx` 전체:

```jsx
import Header from '../components/Header.jsx'
import Footer from '../components/Footer.jsx'
import PipelineDiagram from '../components/PipelineDiagram.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function About() {
  const { t } = useLanguage()

  const videoPipelineSteps = [
    { icon: '🎬', label: t('about_step_video'), status: 'done', statusLabel: t('about_status_done') },
    { icon: '✂️', label: 'Scene Detection', status: 'done', statusLabel: t('about_status_done') },
    { icon: '🤖', label: 'VLM', status: 'done', statusLabel: t('about_status_done') },
    { icon: '🏷️', label: 'Metadata', status: 'done', statusLabel: t('about_status_done') },
    { icon: '🧬', label: 'Embedding', status: 'done', statusLabel: t('about_status_done') },
    { icon: '🗄️', label: 'Vector DB', status: 'done', statusLabel: t('about_status_done') },
  ]

  const searchPipelineSteps = [
    { icon: '⌨️', label: t('about_step_search'), status: 'pending', statusLabel: t('about_status_ui_building') },
    { icon: '🧠', label: 'Query Analysis', status: 'pending', statusLabel: t('about_status_check_needed') },
    { icon: '🔎', label: 'Vector Search', status: 'done', statusLabel: t('about_status_done') },
    { icon: '🔀', label: 'RRF', status: 'done', statusLabel: t('about_status_done') },
    { icon: '✨', label: t('about_step_recommend'), status: 'pending', statusLabel: t('about_status_ui_building') },
  ]

  return (
    <div>
      <Header />
      <div style={{ padding: '28px 24px' }}>
        <p style={{ fontSize: 11.5, color: '#64748b', marginBottom: 8 }}>{t('about_status_legend')}</p>
        <PipelineDiagram title={t('about_pipeline_video_title')} steps={videoPipelineSteps} />
        <PipelineDiagram title={t('about_pipeline_search_title')} steps={searchPipelineSteps} />
      </div>
      <Footer />
    </div>
  )
}
```

- [ ] **Step 2: 언어 전환 테스트 추가**

`src/pages/About.test.jsx`의 `describe` 블록 마지막에 추가 (파일 상단에 `import userEvent from '@testing-library/user-event'` 추가):

```jsx
  it('switches pipeline titles to English when the EN button is clicked', async () => {
    const user = userEvent.setup()
    renderAbout()
    await user.click(screen.getByRole('button', { name: 'EN' }))
    expect(screen.getByText('Video Processing Pipeline')).toBeInTheDocument()
  })
```

- [ ] **Step 3: 테스트 실행**

Run: `npx vitest run src/pages/About.test.jsx`
Expected: 4 tests pass. (기존 3개는 t() 값이 원문과 정확히 일치하므로 코드 변경 없이 그대로 통과한다.)

- [ ] **Step 4: 커밋**

```bash
git add src/pages/About.jsx src/pages/About.test.jsx
git commit -m "Translate About page pipeline labels"
```

---

### Task 12: 전체 회귀 테스트 + 수동 확인 + 배포

**Files:** 없음 (검증 전용 태스크)

- [ ] **Step 1: 전체 테스트 스위트 실행**

Run: `npx vitest run`
Expected: 모든 테스트 파일 통과 (0 failed).

- [ ] **Step 2: 브라우저에서 수동 확인**

`npm run dev`로 로컬 서버를 띄우고 (base path가 `/k-tour-ai-frontend/`이므로 `http://localhost:5173/k-tour-ai-frontend/`로 접속):
- Header의 KO/EN/JA/ZH 버튼을 각각 눌러 Home, Search, Detail, About 페이지 문구가 바뀌는지 확인
- 새로고침 후에도 마지막으로 고른 언어가 유지되는지 확인 (localStorage)
- 검색어 입력 자체는 언어를 바꿔도 그대로 동작하는지 확인 (예: 영어로 전환한 상태에서 한국어로 검색해도 결과가 나오는지)

- [ ] **Step 3: 커밋 및 안내**

이 태스크는 코드 변경이 없으므로 커밋할 것이 없다. 전체 스위트가 통과하고 수동 확인이 끝나면, 지금까지의 커밋들을 `frontend-only` 브랜치에서 GitHub 원격 저장소로 푸시하도록 사용자에게 안내한다 (이 세션은 push 자격 증명이 없어 사용자가 직접 실행해야 한다):

```bash
git push https://<본인_토큰>@github.com/qq03-03/k-tour-ai-frontend.git frontend-only
```
