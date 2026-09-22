import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Companies from './pages/Companies'
import CompanyProfile from './pages/CompanyProfile'
import Upload from './pages/Upload'
import FilingDetail from './pages/FilingDetail'
import Compare from './pages/Compare'
import Chat from './pages/Chat'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="companies" element={<Companies />} />
        <Route path="companies/:companyId" element={<CompanyProfile />} />
        <Route path="upload" element={<Upload />} />
        <Route path="filings/:filingId" element={<FilingDetail />} />
        <Route path="compare" element={<Compare />} />
        <Route path="chat" element={<Chat />} />
      </Route>
    </Routes>
  )
}
