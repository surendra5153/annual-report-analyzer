import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowRight, BarChart3, Check, ChevronDown, Cpu, FileSearch, Gauge, GitCompareArrows, Lock, MessagesSquare,
  Moon, ScanSearch, ShieldAlert, Sparkles, Sun, Telescope, Workflow,
} from 'lucide-react'
import { Logo } from '@/components/app/Logo'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useTheme } from '@/lib/theme'
import { BRAND } from '@/lib/brand'
import { cn } from '@/lib/utils'

const fadeUp = { initial: { opacity: 0, y: 16 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, margin: '-60px' }, transition: { duration: 0.5 } }

const FEATURES = [
  { icon: MessagesSquare, title: 'Grounded Q&A with citations', body: 'Ask in plain English. Every answer cites the exact page, and one click opens the PDF with the passage highlighted.' },
  { icon: Gauge, title: 'KPI extraction we trained', body: 'A page classifier finds the statements; a fine-tuned NER model reads revenue, PAT, EPS and ratios — verified against accounting identities.' },
  { icon: ShieldAlert, title: 'Risk radar', body: 'Financial, regulatory, cyber, climate and supply-chain risks, classified and ranked by severity across your whole portfolio.' },
  { icon: FileSearch, title: 'Footnote & promise tracker', body: 'Flags where the notes contradict the MD&A narrative, and checks whether last year’s commitments were delivered.' },
  { icon: GitCompareArrows, title: 'Cross-company comparison', body: 'Units and currencies normalised automatically, so a ₹-lakh report and a ₹-million report compare like-for-like.' },
  { icon: Telescope, title: 'Forensic signals', body: 'Benford’s-law digit tests, Isolation-Forest anomalies and year-on-year swings surface numbers worth a second look.' },
]

const STEPS = [
  { icon: ScanSearch, title: 'Parse & clean', body: 'PyMuPDF text and tables; headers, ligatures and legacy ₹ glyphs normalised.' },
  { icon: Workflow, title: 'Classify & index', body: 'Pages typed by our classifier; chunks embedded with bge and indexed for BM25.' },
  { icon: Gauge, title: 'Extract & analyse', body: 'KPI-NER, risk classification, footnote cross-checks and anomaly detection.' },
  { icon: MessagesSquare, title: 'Ask & verify', body: 'Hybrid retrieval → rerank → FinSumm answers with page-level citations.' },
]



const FAQ = [
  ['Does any data leave my machine?', 'No. Parsing, embeddings, retrieval and the language model all run locally — the LLM is served by Ollama on your own GPU. There are zero cloud API calls at runtime.'],
  ['What hardware do I need?', 'It is built for a laptop: a 4 GB GPU runs the quantised 3-billion-parameter model, and every other model runs on the CPU.'],
  ['Which models did you train yourselves?', 'The page classifier and KPI-NER model (KPI extraction) and FinSumm, a QLoRA fine-tune of Qwen2.5-3B for summaries and grounded Q&A. Retrieval uses pre-trained bge embeddings, BM25 and a cross-encoder reranker.'],
  ['How accurate are the answers?', 'Answers may only use retrieved passages and must cite them; numbers are cross-checked against the verified KPI table, and each answer carries a confidence level. The Model Lab shows our evaluation metrics.'],
]

function ThemeButton() {
  const { resolved, setTheme } = useTheme()
  return (
    <Button variant="ghost" size="icon-sm" onClick={() => setTheme(resolved === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme">
      {resolved === 'dark' ? <Sun /> : <Moon />}
    </Button>
  )
}

/** Stylised, animated product preview (pure markup — no screenshot). */
function ProductMock() {
  const bars = [62, 78, 54, 88, 71, 95, 83]
  return (
    <div className="relative mx-auto max-w-5xl">
      <div className="absolute -inset-x-10 -top-10 bottom-0 -z-10 rounded-[40px] bg-gradient-to-b from-primary/25 via-primary/5 to-transparent blur-3xl" />
      <motion.div
        initial={{ opacity: 0, y: 40, rotateX: 12 }} animate={{ opacity: 1, y: 0, rotateX: 0 }} transition={{ duration: 0.9, delay: 0.25, ease: [0.16, 1, 0.3, 1] }}
        style={{ transformPerspective: 1400 }}
        className="overflow-hidden rounded-xl border bg-background shadow-2xl ring-1 ring-black/5"
      >
        <div className="flex h-9 items-center gap-1.5 border-b bg-muted/50 px-3">
          {['bg-[#ff5f57]', 'bg-[#febc2e]', 'bg-[#28c840]'].map((c) => <span key={c} className={cn('size-2.5 rounded-full', c)} />)}
          <span className="mx-auto rounded-md bg-background px-12 py-0.5 text-[10.5px] text-muted-foreground">localhost:3000/app</span>
        </div>
        <div className="grid grid-cols-12">
          <div className="col-span-2 hidden space-y-1.5 border-r p-3 md:block">
            {['Overview', 'Companies', 'Ask AI', 'Compare', 'Model Lab'].map((t, i) => (
              <div key={t} className={cn('rounded-md px-2 py-1.5 text-[10.5px] text-muted-foreground', i === 0 && 'bg-accent font-medium text-foreground')}>{t}</div>
            ))}
          </div>
          <div className="col-span-12 space-y-3 p-4 md:col-span-7">
            <div className="grid grid-cols-3 gap-2">
              {[['Revenue', '₹36,794 Cr', '+9.7%'], ['Net profit', '₹9,116 Cr', '+8.7%'], ['Risks flagged', '23', '4 high']].map(([l, v, d]) => (
                <div key={l} className="rounded-lg border p-2.5">
                  <p className="text-[9.5px] text-muted-foreground">{l}</p>
                  <p className="tabular mt-1 text-[13px] font-semibold">{v}</p>
                  <p className="text-[9.5px] text-success">{d}</p>
                </div>
              ))}
            </div>
            <div className="rounded-lg border p-3">
              <p className="mb-2 text-[10.5px] font-medium">Revenue trend</p>
              <div className="flex h-28 items-end gap-2">
                {bars.map((h, i) => (
                  <motion.div key={i} className="flex-1 rounded-t bg-primary/80" initial={{ height: 0 }} animate={{ height: `${h}%` }}
                    transition={{ delay: 0.8 + i * 0.07, duration: 0.6, ease: 'easeOut' }} />
                ))}
              </div>
            </div>
          </div>
          <div className="col-span-12 space-y-2.5 border-l bg-muted/20 p-4 md:col-span-3">
            <p className="text-[10.5px] font-medium">Ask AI</p>
            <div className="ml-auto w-fit rounded-xl rounded-br-sm bg-primary px-2.5 py-1.5 text-[10px] text-primary-foreground">Who are the statutory auditors?</div>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.6 }} className="rounded-xl border bg-background p-2.5 text-[10px] leading-relaxed">
              The joint statutory auditors are <b>M/s Mukund & Rohit</b> and <b>M/s Mukund Patel & Co.</b>
              <span className="ml-1 rounded bg-primary/10 px-1 font-semibold text-primary">3</span>
              <div className="mt-2 flex gap-1">
                <span className="rounded border px-1 text-[9px] text-muted-foreground">p.4</span>
                <span className="rounded bg-success/15 px-1 text-[9px] text-success">high confidence</span>
              </div>
            </motion.div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

export default function Landing() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-transparent bg-background/70 backdrop-blur-md supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center gap-8">
          <Link to="/"><Logo /></Link>
          <nav className="hidden items-center gap-6 text-[13.5px] text-muted-foreground md:flex">
            {[['Features', '#features'], ['How it works', '#how'], ['Models', '#models'], ['FAQ', '#faq']].map(([l, h]) => (
              <a key={h} href={h} className="transition-colors hover:text-foreground">{l}</a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <ThemeButton />
            <Button asChild size="sm"><Link to="/app">Open app <ArrowRight /></Link></Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden pb-24 pt-20">
        <div className="bg-grid mask-radial absolute inset-0 -z-10 opacity-70" />
        <div className="container text-center">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <Badge variant="outline" className="mb-6 gap-1.5 rounded-full bg-background px-3 py-1 text-[12px]">
              <span className="size-1.5 rounded-full bg-success" /> 100% self-hosted · zero cloud API calls
            </Badge>
            <h1 className="text-balance mx-auto max-w-4xl text-4xl font-semibold tracking-tight sm:text-6xl">
              Read a 400-page annual report{' '}
              <span className="bg-gradient-to-r from-primary to-[hsl(var(--chart-4))] bg-clip-text text-transparent">in minutes</span>, not days.
            </h1>
            <p className="text-balance mx-auto mt-6 max-w-2xl text-[17px] leading-relaxed text-muted-foreground">
              {BRAND.name} extracts KPIs, surfaces risks and answers questions with page-level citations — powered by models we
              trained and fine-tuned, running entirely on your own hardware.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Button asChild size="lg"><Link to="/app">Open the app <ArrowRight /></Link></Button>
              <Button asChild size="lg" variant="outline"><a href="#how">See how it works</a></Button>
            </div>
          </motion.div>
          <div className="mt-16"><ProductMock /></div>
        </div>
      </section>

      {/* Tech strip */}
      <section className="border-y bg-muted/30 py-8">
        <div className="container">
          <p className="mb-5 text-center text-[12px] font-medium uppercase tracking-wider text-muted-foreground">Built on open models & proven algorithms</p>
          <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-3 text-[14px] font-semibold text-muted-foreground/80">
            {['Qwen2.5 · QLoRA', 'DeBERTa-v3 NER', 'LightGBM', 'bge-small', 'BM25 + RRF', 'Cross-encoder', 'ChromaDB', 'Ollama'].map((t) => <span key={t}>{t}</span>)}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="scroll-mt-16 py-24">
        <div className="container">
          <motion.div {...fadeUp} className="mx-auto max-w-2xl text-center">
            <p className="text-[13px] font-semibold text-primary">Features</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Everything an analyst does first — done for you</h2>
            <p className="mt-4 text-muted-foreground">From raw PDF to verified numbers, ranked risks and cited answers.</p>
          </motion.div>
          <div className="mt-14 grid gap-px overflow-hidden rounded-2xl border bg-border sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <motion.div key={f.title} {...fadeUp} transition={{ duration: 0.5, delay: i * 0.05 }} className="group bg-background p-7 transition-colors hover:bg-muted/30">
                <div className="grid size-10 place-items-center rounded-lg border bg-card shadow-card transition-colors group-hover:border-primary/40 group-hover:text-primary">
                  <f.icon className="size-5" />
                </div>
                <h3 className="mt-5 font-semibold">{f.title}</h3>
                <p className="mt-2 text-[13.5px] leading-relaxed text-muted-foreground">{f.body}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-16 border-y bg-muted/30 py-24">
        <div className="container">
          <motion.div {...fadeUp} className="mx-auto max-w-2xl text-center">
            <p className="text-[13px] font-semibold text-primary">How it works</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">A four-stage pipeline, end to end on-device</h2>
          </motion.div>
          <div className="relative mt-14 grid gap-6 md:grid-cols-4">
            <div className="absolute left-0 right-0 top-6 hidden h-px bg-gradient-to-r from-transparent via-border to-transparent md:block" />
            {STEPS.map((s, i) => (
              <motion.div key={s.title} {...fadeUp} transition={{ duration: 0.5, delay: i * 0.1 }} className="relative text-center">
                <div className="mx-auto grid size-12 place-items-center rounded-full border bg-background shadow-card">
                  <s.icon className="size-5 text-primary" />
                </div>
                <p className="mt-1 text-[11px] font-semibold text-muted-foreground">STEP {i + 1}</p>
                <h3 className="mt-2 font-semibold">{s.title}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">{s.body}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Models */}
      <section id="models" className="scroll-mt-16 py-24">
        <div className="container grid items-center gap-12 lg:grid-cols-2">
          <motion.div {...fadeUp}>
            <p className="text-[13px] font-semibold text-primary">Our models</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Trained for Indian annual reports</h2>
            <p className="mt-4 leading-relaxed text-muted-foreground">
              Generic LLMs misread lakh-vs-crore, standalone-vs-consolidated and Ind AS terminology. We trained our own models on
              cleaned, labelled Indian filings — and measure every one against a baseline.
            </p>
            <ul className="mt-6 space-y-3 text-[14px]">
              {['Data cleansing with a full audit trail', 'Leakage-free, company-grouped evaluation', 'Algorithms compared with cross-validation', 'Metrics published in the Model Lab'].map((t) => (
                <li key={t} className="flex items-center gap-2.5"><Check className="size-4 text-success" /> {t}</li>
              ))}
            </ul>
            <Button asChild variant="outline" className="mt-8"><Link to="/app/model-lab">Explore the Model Lab <ArrowRight /></Link></Button>
          </motion.div>
          <motion.div {...fadeUp} className="space-y-3">
            {[
              [Gauge, 'PageClassifier + KPI-NER', 'KPI extraction', 'LightGBM · DeBERTa-v3-small', 'Trained'],
              [Sparkles, 'FinSumm', 'Summaries & grounded Q&A', 'Qwen2.5-3B · QLoRA fine-tune', 'Fine-tuned'],
              [BarChart3, 'Hybrid retriever', 'Semantic search', 'BM25 + bge + RRF + cross-encoder', 'Pre-trained'],
            ].map(([Icon, n, t, m, k]) => (
              <div key={n} className="flex items-center gap-4 rounded-xl border bg-card p-5 shadow-card">
                <div className="grid size-11 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"><Icon className="size-5" /></div>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{n}</p>
                  <p className="text-[13px] text-muted-foreground">{t} · <span className="font-mono text-[12px]">{m}</span></p>
                </div>
                <Badge variant={k === 'Pre-trained' ? 'secondary' : 'default'}>{k}</Badge>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Privacy band */}
      <section className="py-6">
        <div className="container">
          <motion.div {...fadeUp} className="relative overflow-hidden rounded-3xl bg-foreground px-8 py-14 text-background sm:px-14">
            <div className="absolute -right-24 -top-24 size-72 rounded-full bg-primary/40 blur-3xl" />
            <div className="relative grid gap-10 lg:grid-cols-3">
              <div className="lg:col-span-1">
                <Lock className="size-7" />
                <h2 className="mt-4 text-2xl font-semibold tracking-tight">Your filings never leave your machine</h2>
              </div>
              {[[Cpu, 'Runs on a laptop', '4 GB GPU for the language model; everything else on CPU.'], [Lock, 'No external APIs', 'Embeddings, retrieval and generation all run locally via Ollama.']].map(([I, t, b]) => (
                <div key={t}>
                  <I className="size-5 opacity-70" />
                  <p className="mt-3 font-semibold">{t}</p>
                  <p className="mt-1 text-[14px] leading-relaxed opacity-70">{b}</p>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="scroll-mt-16 border-t bg-muted/30 py-24">
        <div className="container max-w-3xl">
          <h2 className="text-center text-3xl font-semibold tracking-tight">Frequently asked questions</h2>
          <div className="mt-10 divide-y rounded-2xl border bg-background">
            {FAQ.map(([q, a]) => (
              <details key={q} className="group px-6 py-5 [&_summary::-webkit-details-marker]:hidden">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
                  {q}
                  <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
                </summary>
                <p className="mt-3 text-[14px] leading-relaxed text-muted-foreground">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* CTA + footer */}
      <section className="py-24">
        <div className="container text-center">
          <h2 className="text-balance mx-auto max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">Turn your next annual report into answers.</h2>
          <Button asChild size="lg" className="mt-8"><Link to="/app/upload">Upload a report <ArrowRight /></Link></Button>
        </div>
      </section>
      <footer className="border-t py-10">
        <div className="container flex flex-col items-center justify-between gap-4 text-[13px] text-muted-foreground sm:flex-row">
          <Logo />
          <p>{BRAND.tagline}. A college ML project.</p>
        </div>
      </footer>
    </div>
  )
}
