import { readFileSync, writeFileSync } from 'node:fs'

const SOURCE_DIR = 'C:/Users/human/Downloads/K-Tour_AI_Backend_Handoff_517_Yonghwasan_GT_v2_20260818/data'

const translations = JSON.parse(readFileSync(`${SOURCE_DIR}/display_translations_517_no_P063.json`, 'utf8'))

const merged = {}
for (const record of translations.records) {
  merged[`${record.segment_id}__${record.keyframe_id}`] = structuredClone(record.translations)
}

writeFileSync('src/data/segmentTranslations517.json', JSON.stringify(merged, null, 2) + '\n')
console.log(`Wrote ${Object.keys(merged).length} translation records to src/data/segmentTranslations517.json`)
