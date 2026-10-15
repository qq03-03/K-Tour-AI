import { readdirSync, copyFileSync } from 'node:fs'
import { join } from 'node:path'

const SOURCE_DIR = 'C:/Users/human/Documents/카카오톡 받은 파일/메인이미지'
const DEST_DIR = 'public/drama-images'

const files = readdirSync(SOURCE_DIR).filter((name) => name.toLowerCase().endsWith('.webp'))

let copied = 0
for (const fileName of files) {
  const match = fileName.match(/^(V\d+)_/)
  if (!match) {
    console.warn(`Skipping "${fileName}": no V-number prefix`)
    continue
  }
  const videoIdPrefix = match[1]
  copyFileSync(join(SOURCE_DIR, fileName), join(DEST_DIR, `${videoIdPrefix}.webp`))
  copied += 1
}

console.log(`Copied ${copied} drama main images to ${DEST_DIR}, keyed by video_id prefix (e.g. V001.webp).`)
