import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import 'react-pdf/dist/Page/TextLayer.css'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import { ChevronLeft, ChevronRight, Download, Highlighter, Minus, Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/misc'
import { Tooltip } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

pdfjs.GlobalWorkerOptions.workerSrc = workerSrc

const norm = (s) => s.toLowerCase().replace(/[‘’]/g, "'").replace(/[\s ]+/g, ' ').trim()

/**
 * Builds a predicate for the PDF text layer: a text run is highlighted when it
 * is a meaningful fragment (≥ 5 chars, or a number with separators) of the
 * passage we are citing. Matching is done on normalised text, because the
 * chunk text came from PyMuPDF while the text layer comes from pdf.js.
 */
function makeMatcher(passage) {
  if (!passage) return null
  const hay = norm(passage)
  return (str) => {
    const s = norm(str)
    if (s.length < 5 && !/\d[\d,.]{3,}/.test(s)) return false
    return hay.includes(s)
  }
}

const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

/**
 * Single-page PDF viewer with page navigation, zoom and passage highlighting.
 *
 * Controlled by `target` = { page, text, nonce }: whenever the nonce changes the
 * viewer jumps to `page` and highlights `text` (a citation excerpt or a KPI's
 * source line).
 */
export default function PdfViewer({ url, target, onClearHighlight, className }) {
  const [numPages, setNumPages] = useState(null)
  const [page, setPage] = useState(1)
  const [scale, setScale] = useState(1)
  const [width, setWidth] = useState(600)
  const [error, setError] = useState(null)
  const wrapRef = useRef(null)
  const highlight = target?.text || null

  useEffect(() => {
    if (target?.page) setPage(target.page)
  }, [target?.page, target?.nonce])

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(280, e.contentRect.width - 32)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    const onKey = (e) => {
      if (e.target.closest('input, textarea')) return
      if (e.key === 'ArrowRight') setPage((p) => Math.min(numPages || p, p + 1))
      if (e.key === 'ArrowLeft') setPage((p) => Math.max(1, p - 1))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [numPages])

  const matcher = useMemo(() => makeMatcher(highlight), [highlight])
  const textRenderer = useCallback(
    ({ str }) => (matcher && matcher(str) ? `<mark>${escapeHtml(str)}</mark>` : escapeHtml(str)),
    [matcher]
  )

  // Scroll the first highlight into view once the text layer has rendered
  const onTextLayer = useCallback(() => {
    if (!matcher) return
    const mark = wrapRef.current?.querySelector('.react-pdf__Page__textContent mark')
    mark?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [matcher])

  const go = (p) => setPage(Math.min(numPages || 1, Math.max(1, p)))

  return (
    <div className={cn('flex h-full min-h-0 flex-col bg-muted/40', className)}>
      <div className="flex h-11 shrink-0 items-center gap-1 border-b bg-background px-2">
        <Button variant="ghost" size="icon-sm" onClick={() => go(page - 1)} disabled={page <= 1} aria-label="Previous page">
          <ChevronLeft />
        </Button>
        <div className="flex items-center gap-1 text-[12px] text-muted-foreground">
          <input
            value={page}
            onChange={(e) => go(Number(e.target.value) || 1)}
            className="tabular h-7 w-12 rounded-md border bg-background text-center text-[12px] text-foreground"
            aria-label="Page number"
          />
          <span>/ {numPages ?? '…'}</span>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={() => go(page + 1)} disabled={numPages && page >= numPages} aria-label="Next page">
          <ChevronRight />
        </Button>

        {highlight && (
          <span className="ml-2 inline-flex max-w-[45%] items-center gap-1.5 rounded-md bg-warning/15 px-2 py-1 text-[11.5px] text-warning">
            <Highlighter className="size-3.5 shrink-0" />
            <span className="truncate">Highlighting cited passage</span>
            {onClearHighlight && (
              <button onClick={onClearHighlight} className="rounded hover:bg-warning/20" aria-label="Clear highlight">
                <X className="size-3.5" />
              </button>
            )}
          </span>
        )}

        <div className="ml-auto flex items-center gap-0.5">
          <Button variant="ghost" size="icon-sm" onClick={() => setScale((s) => Math.max(0.6, +(s - 0.15).toFixed(2)))} aria-label="Zoom out"><Minus /></Button>
          <span className="tabular w-10 text-center text-[12px] text-muted-foreground">{Math.round(scale * 100)}%</span>
          <Button variant="ghost" size="icon-sm" onClick={() => setScale((s) => Math.min(2.5, +(s + 0.15).toFixed(2)))} aria-label="Zoom in"><Plus /></Button>
          <Tooltip content="Open original PDF">
            <Button variant="ghost" size="icon-sm" asChild>
              <a href={url} target="_blank" rel="noreferrer" aria-label="Open PDF"><Download /></a>
            </Button>
          </Tooltip>
        </div>
      </div>

      <div ref={wrapRef} className="min-h-0 flex-1 overflow-auto p-4">
        {error ? (
          <div className="grid h-full place-items-center text-center text-[13px] text-muted-foreground">
            <div>
              <p className="font-medium text-foreground">Could not load the PDF</p>
              <p className="mt-1">{error}</p>
            </div>
          </div>
        ) : (
          <Document
            file={url}
            onLoadSuccess={({ numPages: n }) => { setNumPages(n); setError(null) }}
            onLoadError={(e) => setError(e.message)}
            loading={<Skeleton className="mx-auto aspect-[1/1.414] w-full max-w-[640px]" />}
          >
            <Page
              key={`${page}-${highlight || ''}`}
              pageNumber={page}
              width={width * scale}
              customTextRenderer={textRenderer}
              onRenderTextLayerSuccess={onTextLayer}
              className="overflow-hidden rounded-sm shadow-lift ring-1 ring-border"
              loading={<Skeleton className="mx-auto aspect-[1/1.414]" style={{ width: width * scale }} />}
            />
          </Document>
        )}
      </div>
    </div>
  )
}
