import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home.jsx'
import SearchResults from './pages/SearchResults.jsx'
import Detail from './pages/Detail.jsx'
import About from './pages/About.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/search" element={<SearchResults />} />
      <Route path="/segment/:segmentId" element={<Detail />} />
      <Route path="/about" element={<About />} />
    </Routes>
  )
}
