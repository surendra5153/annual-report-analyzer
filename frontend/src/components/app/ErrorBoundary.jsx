import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

/** Keeps the app shell usable when a page throws; resets on navigation. */
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidUpdate(prev) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null })
  }

  componentDidCatch(error, info) {
    console.error('Page crashed:', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="mx-auto max-w-lg px-6 py-24 text-center">
        <div className="mx-auto grid size-12 place-items-center rounded-xl bg-danger/10 text-danger">
          <AlertTriangle className="size-5" />
        </div>
        <h2 className="mt-4 text-lg font-semibold">Something went wrong on this page</h2>
        <p className="mt-1 font-mono text-[12px] text-muted-foreground">{String(this.state.error?.message || this.state.error)}</p>
        <Button className="mt-6" variant="outline" onClick={() => this.setState({ error: null })}>Try again</Button>
      </div>
    )
  }
}
