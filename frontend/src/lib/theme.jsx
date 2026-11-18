import { createContext, useContext, useEffect, useState } from 'react'

const ThemeContext = createContext({ theme: 'system', setTheme: () => {}, resolved: 'light' })
const KEY = 'finsight-theme'

function read() {
  try { return localStorage.getItem(KEY) || 'system' } catch { return 'system' }
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(read)
  const [resolved, setResolved] = useState('light')

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const apply = () => {
      const r = theme === 'system' ? (mq.matches ? 'dark' : 'light') : theme
      document.documentElement.classList.toggle('dark', r === 'dark')
      setResolved(r)
    }
    apply()
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [theme])

  const setTheme = (t) => {
    try { localStorage.setItem(KEY, t) } catch { /* private mode */ }
    setThemeState(t)
  }

  return <ThemeContext.Provider value={{ theme, setTheme, resolved }}>{children}</ThemeContext.Provider>
}

export const useTheme = () => useContext(ThemeContext)
