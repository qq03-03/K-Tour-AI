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
