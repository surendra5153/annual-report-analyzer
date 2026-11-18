import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useParams } from 'react-router-dom'
import AppShell from './components/app/AppShell'
import { Skeleton } from './components/ui/misc'

const Landing = lazy(() => import('./pages/landing/Landing'))
const Overview = lazy(() => import('./pages/app/Overview'))
const Companies = lazy(() => import('./pages/app/Companies'))
const CompanyProfile = lazy(() => import('./pages/app/CompanyProfile'))
const Upload = lazy(() => import('./pages/app/Upload'))
const FilingWorkspace = lazy(() => import('./pages/app/FilingWorkspace'))
const Chat = lazy(() => import('./pages/app/Chat'))
const Compare = lazy(() => import('./pages/app/Compare'))
const ModelLab = lazy(() => import('./pages/app/ModelLab'))

function PageFallback() {
  return (
    <div className="mx-auto max-w-[1320px] space-y-4 px-4 py-8 lg:px-8">
      <Skeleton className="h-7 w-56" />
      <Skeleton className="h-4 w-96" />
      <div className="grid gap-4 pt-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
      </div>
      <Skeleton className="h-72" />
    </div>
  )
}

// Old URLs (pre-redesign) keep working
const RedirectParam = ({ to }) => {
  const params = useParams()
  return <Navigate replace to={to.replace(/:(\w+)/g, (_, k) => params[k])} />
}

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<AppShell />}>
          <Route index element={<Overview />} />
          <Route path="companies" element={<Companies />} />
          <Route path="companies/:companyId" element={<CompanyProfile />} />
          <Route path="upload" element={<Upload />} />
          <Route path="filings/:filingId" element={<FilingWorkspace />} />
          <Route path="chat" element={<Chat />} />
          <Route path="compare" element={<Compare />} />
          <Route path="model-lab" element={<ModelLab />} />
        </Route>
        <Route path="/companies" element={<Navigate replace to="/app/companies" />} />
        <Route path="/companies/:companyId" element={<RedirectParam to="/app/companies/:companyId" />} />
        <Route path="/filings/:filingId" element={<RedirectParam to="/app/filings/:filingId" />} />
        <Route path="/upload" element={<Navigate replace to="/app/upload" />} />
        <Route path="/chat" element={<Navigate replace to="/app/chat" />} />
        <Route path="/compare" element={<Navigate replace to="/app/compare" />} />
        <Route path="*" element={<Navigate replace to="/" />} />
      </Routes>
    </Suspense>
  )
}
