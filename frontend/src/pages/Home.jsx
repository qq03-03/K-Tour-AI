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
        <h3 style={{ fontSize: 14, color: '#334155' }}>🎬 {t('home_section_dramas')}</h3>
        <DramaSection />
      </section>
      <Footer />
    </div>
  )
}
