import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function Hero() {
  const { t } = useLanguage()
  return (
    <div style={{ background: 'linear-gradient(135deg,#2563EB,#1d4ed8)', padding: '48px 24px 64px', textAlign: 'center', color: 'white', boxSizing: 'border-box', minHeight: 230, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
      <h1 style={{ fontSize: 26, margin: '0 0 8px', fontWeight: 800, whiteSpace: 'pre-line', lineHeight: 1.3, minHeight: '2.6em' }}>
        {t('hero_title')}
      </h1>
      <p style={{ fontSize: 14, opacity: 0.9, margin: 0, lineHeight: 1.4, minHeight: '2.8em' }}>{t('hero_subtitle')}</p>
    </div>
  )
}
