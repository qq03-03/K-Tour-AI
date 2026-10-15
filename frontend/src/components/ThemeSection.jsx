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
