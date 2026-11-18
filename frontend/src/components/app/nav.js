import { Building2, FlaskConical, GitCompareArrows, LayoutDashboard, MessagesSquare, Upload } from 'lucide-react'

export const NAV = [
  {
    section: 'Workspace',
    items: [
      { label: 'Overview', to: '/app', icon: LayoutDashboard, end: true },
      { label: 'Companies', to: '/app/companies', icon: Building2 },
      { label: 'Ask AI', to: '/app/chat', icon: MessagesSquare },
      { label: 'Compare', to: '/app/compare', icon: GitCompareArrows },
      { label: 'Upload', to: '/app/upload', icon: Upload },
    ],
  },
  {
    section: 'Machine learning',
    items: [{ label: 'Model Lab', to: '/app/model-lab', icon: FlaskConical }],
  },
]
