import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext.jsx'

const LANGUAGE_OPTIONS = [
  { code: 'ko', label: 'KO' },
  { code: 'en', label: 'EN' },
  { code: 'ja', label: 'JA' },
  { code: 'zh', label: 'ZH' },
]

export default function Header() {
  const { lang, setLang, t } = useLanguage()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  function closeMenu() {
    setMenuOpen(false)
  }

  // Desktop's way into the search filter panel: a hamburger-menu link
  // instead of the dedicated toggle button SearchResults shows on mobile
  // (see .desktop-only-menu-item / .mobile-only-filter-toggle in
  // index.css). Preserves whatever filters are already in the URL and
  // adds a fresh openFilter signal each time so re-clicking always
  // (re)opens the panel, even if the user had since closed it manually.
  const filterPanelParams = new URLSearchParams(location.pathname === '/search' ? location.search : '')
  filterPanelParams.set('openFilter', String(Date.now()))
  const searchFiltersHref = `/search?${filterPanelParams.toString()}`

  return (
    <header style={{ position: 'relative', background: '#fff' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 24px' }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, color: 'var(--color-primary)', fontSize: 18 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--color-accent)', display: 'inline-block' }} />
          K-Tour AI
        </Link>
        <button
          onClick={() => setMenuOpen((open) => !open)}
          aria-label={t('nav_menu')}
          aria-expanded={menuOpen}
          style={{ border: 'none', background: 'none', fontSize: 22, lineHeight: 1, padding: 4, cursor: 'pointer', color: 'var(--color-text)' }}
        >
          ☰
        </button>
      </div>
      {menuOpen && (
        <nav
          style={{
            position: 'absolute',
            top: '100%',
            right: 24,
            zIndex: 20,
            minWidth: 170,
            background: '#fff',
            borderRadius: 14,
            boxShadow: '0 10px 30px rgba(15,23,42,.15)',
            padding: 16,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            fontSize: 14,
          }}
        >
          <Link to="/" onClick={closeMenu}>{t('nav_home')}</Link>
          <Link to="/search" onClick={closeMenu}>{t('nav_search')}</Link>
          <Link to={searchFiltersHref} onClick={closeMenu} className="desktop-only-menu-item">
            {t('filter_toggle')}
          </Link>
          <div style={{ display: 'flex', gap: 6, paddingTop: 10, borderTop: '1px solid #e2e8f0' }}>
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
      )}
    </header>
  )
}
