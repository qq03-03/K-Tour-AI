// The 13 administrative regions actually present in the 517-segment
// dataset (mockSegments517.js), in the order they're commonly listed.
// id is the exact region string stored in segments and sent to the
// backend's region filter -- en/ja/zh labels come from 동현's v2 catalog's
// place display data (locations.places[].localized[lang].region).
export const regions = [
  { id: '서울특별시', label: { ko: '서울특별시', en: 'Seoul', ja: 'ソウル特別市', zh: '首尔特别市' } },
  { id: '인천광역시', label: { ko: '인천광역시', en: 'Incheon Metropolitan City', ja: '仁川広域市', zh: '仁川广域市' } },
  { id: '경기도', label: { ko: '경기도', en: 'Gyeonggi Province', ja: '京畿道', zh: '京畿道' } },
  { id: '강원특별자치도', label: { ko: '강원특별자치도', en: 'Gangwon Special Self-Governing Province', ja: '江原特別自治道', zh: '江原特别自治道' } },
  { id: '충청북도', label: { ko: '충청북도', en: 'Chungcheongbuk-do', ja: '忠清北道', zh: '忠清北道' } },
  { id: '충청남도', label: { ko: '충청남도', en: 'Chungcheongnam-do', ja: '忠清南道', zh: '忠清南道' } },
  { id: '전북특별자치도', label: { ko: '전북특별자치도', en: 'Jeonbuk Special Self-Governing Province', ja: '全北特別自治道', zh: '全北特别自治道' } },
  { id: '전라남도', label: { ko: '전라남도', en: 'Jeollanam-do', ja: '全羅南道', zh: '全罗南道' } },
  { id: '경상북도', label: { ko: '경상북도', en: 'North Gyeongsang Province', ja: '慶尚北道', zh: '庆尚北道' } },
  { id: '경상남도', label: { ko: '경상남도', en: 'Gyeongsangnam-do', ja: '慶尚南道', zh: '庆尚南道' } },
  { id: '대구광역시', label: { ko: '대구광역시', en: 'Daegu Metropolitan City', ja: '大邱広域市', zh: '大邱广域市' } },
  { id: '부산광역시', label: { ko: '부산광역시', en: 'Busan Metropolitan City', ja: '釜山広域市', zh: '釜山广域市' } },
  { id: '제주특별자치도', label: { ko: '제주특별자치도', en: 'Jeju Special Self-Governing Province', ja: '済州特別自治道', zh: '济州特别自治道' } },
]
