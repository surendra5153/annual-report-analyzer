import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, Cell, ComposedChart, ErrorBar, Legend, Line, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts'
import { ArrowRight, BrainCircuit, Database, FlaskConical, Lightbulb, Microscope, Server, Sparkles } from 'lucide-react'
import { getMlEda, getMlHealth, getMlMetrics, getMlPreprocessing, mlFigureUrl } from '@/services/api'
import { PageBody, PageHeader } from '@/components/app/AppShell'
import { axisProps, CHART, ChartTooltip, gridProps, StatTile } from '@/components/app/domain'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsListLine, TabsTriggerLine } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { EmptyState, Skeleton } from '@/components/ui/misc'
import { cn, formatNumber, titleCase } from '@/lib/utils'

const LABEL_COLORS = [
  'hsl(243 75% 59%)', 'hsl(173 58% 39%)', 'hsl(35 92% 50%)', 'hsl(330 70% 55%)', 'hsl(199 89% 48%)',
  'hsl(262 60% 60%)', 'hsl(90 50% 45%)', 'hsl(15 80% 55%)', 'hsl(200 15% 50%)', 'hsl(240 5% 70%)',
]

const MODELS = [
  { name: 'PageClassifier', task: 'KPI extraction · page type', kind: 'trained', algo: 'TF-IDF + structural features → LightGBM (vs NB / LogReg / SVM / RF)', runs: 'CPU', key: 'page_classifier' },
  { name: 'KPI-NER', task: 'KPI extraction · entity tagging', kind: 'trained', algo: 'DeBERTa-v3-small token classification (vs regex / CRF)', runs: 'CPU · ONNX', key: 'kpi_ner' },
  { name: 'FinSumm', task: 'Summaries + grounded Q&A', kind: 'trained', algo: 'Qwen2.5-3B + QLoRA fine-tune (vs TextRank / base Qwen)', runs: 'GPU · Ollama GGUF', key: 'finsumm' },
  { name: 'bge-small-en-v1.5', task: 'Dense retrieval', kind: 'pretrained', algo: 'Bi-encoder embeddings, HNSW index (ChromaDB)', runs: 'CPU' },
  { name: 'BM25 + RRF', task: 'Sparse retrieval + fusion', kind: 'algorithm', algo: 'Okapi BM25 (from scratch) · Reciprocal Rank Fusion', runs: 'CPU' },
  { name: 'ms-marco MiniLM', task: 'Reranking', kind: 'pretrained', algo: 'Cross-encoder relevance scoring of top-30', runs: 'CPU' },
]
const KIND = { trained: ['default', 'Trained by us'], pretrained: ['secondary', 'Pre-trained'], algorithm: ['outline', 'Algorithm'] }

function Section({ title, description, children, className, action }) {
  return (
    <Card className={className}>
      <CardHeader>
        <div><CardTitle>{title}</CardTitle>{description && <CardDescription>{description}</CardDescription>}</div>
        {action}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

function Pending({ what }) {
  return <EmptyState icon={FlaskConical} title={`${what} not generated yet`} description="Run the corresponding notebook in ml/notebooks — results appear here automatically." />
}

// ── Overview ─────────────────────────────────────────────────────────────────
function OverviewTab({ health, metrics }) {
  const steps = [
    ['Query', 'user question'], ['BM25', 'keyword top-30'], ['bge dense', 'semantic top-30'],
    ['RRF', 'rank fusion'], ['Cross-encoder', 'rerank → top-6'], ['FinSumm', 'grounded answer + [n] citations'],
  ]
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="LLM runtime" icon={Server} value={health?.llm?.up ? 'Online' : 'Offline'}
          sub={health?.llm ? `${health.llm.model} · ${health.llm.provider}` : '—'} />
        <StatTile label="Embedding model" icon={Database} value="bge-small" sub={health?.embedding?.loaded ? 'loaded in memory' : 'lazy-loaded on first use'} />
        <StatTile label="Reranker" icon={Microscope} value="MiniLM-L6" sub={health?.reranker?.enabled ? 'enabled' : 'disabled'} />
        <StatTile label="Cloud API calls" icon={Sparkles} value="0" sub="runtime is fully self-hosted" />
      </div>

      <Section title="Retrieval-augmented generation pipeline" description="How a question becomes a cited answer — every stage runs locally">
        <div className="flex flex-wrap items-stretch gap-2">
          {steps.map(([t, d], i) => (
            <div key={t} className="flex items-center gap-2">
              <div className={cn('rounded-lg border px-3 py-2', i === steps.length - 1 && 'border-primary/40 bg-primary/5')}>
                <p className="text-[13px] font-medium">{t}</p>
                <p className="text-[11.5px] text-muted-foreground">{d}</p>
              </div>
              {i < steps.length - 1 && <ArrowRight className="size-4 text-muted-foreground" />}
            </div>
          ))}
        </div>
      </Section>

      <Section title="Model stack" description="What we trained ourselves vs. what we use off the shelf">
        <div className="-mx-5 overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-y bg-muted/40 text-left text-[12px] text-muted-foreground">
                <th className="px-5 py-2 font-medium">Model</th><th className="px-3 py-2 font-medium">Task</th>
                <th className="px-3 py-2 font-medium">Method</th><th className="px-3 py-2 font-medium">Runs on</th>
                <th className="px-5 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {MODELS.map((m) => {
                const trained = m.key && metrics?.models?.[m.key]?.status === 'trained'
                return (
                  <tr key={m.name} className="border-b last:border-0">
                    <td className="px-5 py-3"><p className="font-medium">{m.name}</p><Badge variant={KIND[m.kind][0]} className="mt-1">{KIND[m.kind][1]}</Badge></td>
                    <td className="px-3 py-3 text-muted-foreground">{m.task}</td>
                    <td className="max-w-[340px] px-3 py-3 text-muted-foreground">{m.algo}</td>
                    <td className="whitespace-nowrap px-3 py-3 font-mono text-[11.5px]">{m.runs}</td>
                    <td className="px-5 py-3">
                      {m.kind !== 'trained' ? <Badge variant="success">Active</Badge>
                        : trained ? <Badge variant="success">Trained</Badge> : <Badge variant="warning">Training pending</Badge>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  )
}

// ── Data & preprocessing ─────────────────────────────────────────────────────
function DataTab({ pre }) {
  if (!pre?.available) return <Pending what="Preprocessing summary" />
  const audit = Object.entries(pre.quality_audit || {}).filter(([, v]) => v > 0).map(([k, v]) => ({ name: k, value: v }))
  const rules = Object.entries(pre.kpi_rule_counts || {}).map(([k, v]) => ({ name: titleCase(k), value: v }))
  const classes = Object.entries(pre.class_counts || {}).map(([k, v]) => ({ name: titleCase(k), value: v }))
  const funnel = [
    ['Raw pages', pre.raw_pages], ['Empty removed', -pre.empty_pages_removed], ['Duplicates removed', -pre.duplicate_pages_removed], ['Clean pages', pre.clean_pages],
  ]
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Reports → pages" value={formatNumber(pre.clean_pages, 0)} sub={`from ${pre.reports} reports, ${pre.companies} companies`} />
        <StatTile label="Noise removed" value={`${pre.chars_removed_pct}%`} sub={`${formatNumber(pre.header_footer_lines_removed, 0)} header/footer lines`} />
        <StatTile label="Class imbalance" value={`${pre.imbalance_ratio}:1`} sub="largest / smallest page class" />
        <StatTile label="KPI rows cleaned" value={`${pre.kpi_rows_clean}/${pre.kpi_rows_raw}`} sub={`${Math.round(pre.kpi_missingness * 100)}% missing after cleansing`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Data-quality audit" description="Pages affected by each noise source, before cleaning">
          <div className="h-[260px]">
            <ResponsiveContainer>
              <BarChart data={audit} layout="vertical" margin={{ left: 40 }}>
                <CartesianGrid {...gridProps} horizontal={false} vertical />
                <XAxis type="number" {...axisProps} />
                <YAxis type="category" dataKey="name" {...axisProps} width={190} fontSize={10.5} />
                <Tooltip cursor={{ fill: 'hsl(var(--muted))' }} content={<ChartTooltip />} />
                <Bar dataKey="value" name="pages" fill={CHART[2]} radius={[0, 4, 4, 0]} maxBarSize={16} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>

        <Section title="KPI cleansing rules applied" description="Every change is logged in kpi_audit_log.csv">
          <div className="h-[260px]">
            <ResponsiveContainer>
              <BarChart data={rules} margin={{ left: -16 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="name" {...axisProps} fontSize={10.5} interval={0} />
                <YAxis {...axisProps} allowDecimals={false} />
                <Tooltip cursor={{ fill: 'hsl(var(--muted))' }} content={<ChartTooltip />} />
                <Bar dataKey="value" name="changes" fill={CHART[0]} radius={[4, 4, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Section title="Page funnel" className="lg:col-span-1">
          <ul className="space-y-2.5">
            {funnel.map(([k, v]) => (
              <li key={k} className="flex items-center justify-between text-[13px]">
                <span className="text-muted-foreground">{k}</span>
                <span className={cn('tabular font-medium', v < 0 && 'text-danger')}>{v < 0 ? `−${Math.abs(v)}` : formatNumber(v, 0)}</span>
              </li>
            ))}
          </ul>
          <div className="mt-5 border-t pt-4">
            <p className="mb-2 text-[12px] font-medium text-muted-foreground">Detected reporting units</p>
            {Object.entries(pre.report_units || {}).map(([r, u]) => (
              <div key={r} className="flex justify-between py-0.5 text-[12.5px]"><span className="truncate">{r}</span><Badge variant="secondary">₹ {u}</Badge></div>
            ))}
          </div>
        </Section>

        <Section title="Leakage-free split" description="Grouped by company — no company appears in two splits" className="lg:col-span-2">
          <div className="grid gap-3 sm:grid-cols-3">
            {['train', 'val', 'test'].map((s) => (
              <div key={s} className="rounded-lg border p-4">
                <div className="flex items-baseline justify-between">
                  <p className="text-[12px] font-medium uppercase tracking-wide text-muted-foreground">{s}</p>
                  <p className="tabular text-lg font-semibold">{pre.splits?.[s] ?? 0}</p>
                </div>
                <p className="mt-2 text-[12px] text-muted-foreground">{(pre.split_companies?.[s] || []).join(', ')}</p>
              </div>
            ))}
          </div>
          <p className="mb-2 mt-5 text-[12px] font-medium text-muted-foreground">Class distribution (weak labels)</p>
          <div className="h-[170px]">
            <ResponsiveContainer>
              <BarChart data={classes} margin={{ left: -16 }}>
                <XAxis dataKey="name" {...axisProps} fontSize={10} interval={0} angle={-20} textAnchor="end" height={44} />
                <YAxis {...axisProps} scale="log" domain={[1, 'auto']} allowDataOverflow />
                <Tooltip cursor={{ fill: 'hsl(var(--muted))' }} content={<ChartTooltip />} />
                <Bar dataKey="value" name="pages" fill={CHART[1]} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>
      </div>
    </div>
  )
}

// ── EDA ──────────────────────────────────────────────────────────────────────
const FIGURES = [
  ['02_corpus_overview.png', 'Corpus overview'], ['02_feature_histograms.png', 'Feature distributions'],
  ['02_features_by_label.png', 'Features by page type'], ['02_position_by_label.png', 'Section position'],
  ['02_feature_correlation.png', 'Feature correlation'], ['02_top_terms.png', 'Top TF-IDF terms'],
  ['02_wordclouds.png', 'Word clouds'], ['02_tsne.png', 't-SNE'], ['02_kpi_distribution.png', 'KPI distribution'],
  ['02_headline_kpis.png', 'Headline KPIs'], ['02_yoy.png', 'Year-on-year'], ['02_kpi_correlation.png', 'KPI correlation'],
  ['02_benford.png', "Benford's law"], ['01_kpi_missingness.png', 'KPI missingness'],
]

function EdaTab({ eda }) {
  const [zoom, setZoom] = useState(null)
  const tsne = useMemo(() => {
    const by = {}
    for (const p of eda?.tsne || []) (by[p.label] ||= []).push({ x: p.tsne_x, y: p.tsne_y, report: p.report })
    return Object.entries(by)
  }, [eda])
  if (!eda?.available) return <Pending what="EDA report" />

  const benford = eda.benford.expected.map((e, i) => ({
    digit: i + 1, Expected: e, ...Object.fromEntries(Object.entries(eda.benford.observed).map(([r, f]) => [r, f[i]])),
  }))
  const reports = Object.keys(eda.benford.observed)
  const kruskal = (eda.kruskal || []).map((k) => ({ name: k.feature, value: k['epsilon²'] }))

  return (
    <div className="space-y-4">
      <Section title="Key findings" description="Generated from the data by notebook 02_eda">
        <ol className="space-y-2.5">
          {eda.insights.map((s, i) => (
            <li key={i} className="flex gap-3 text-[13px] leading-relaxed">
              <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">{i + 1}</span>
              <span className="text-muted-foreground">{s}</span>
            </li>
          ))}
        </ol>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="t-SNE of page text" description="TF-IDF → LSA (50-d) → t-SNE, coloured by page type">
          <div className="h-[340px]">
            <ResponsiveContainer>
              <ScatterChart margin={{ left: -20, right: 8 }}>
                <XAxis type="number" dataKey="x" {...axisProps} tick={false} />
                <YAxis type="number" dataKey="y" {...axisProps} tick={false} />
                <ZAxis range={[14, 14]} />
                <Tooltip content={({ active, payload }) => active && payload?.length ? (
                  <div className="rounded-md border bg-popover px-2.5 py-1.5 text-[12px] shadow-lift">{payload[0].payload.report}</div>) : null} />
                <Legend iconType="circle" iconSize={7} wrapperStyle={{ fontSize: 11 }} />
                {tsne.map(([label, pts], i) => (
                  <Scatter key={label} name={titleCase(label)} data={pts} fill={LABEL_COLORS[i % LABEL_COLORS.length]} fillOpacity={0.75} />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </Section>

        <Section title="Benford's law" description="Leading-digit frequency of reported amounts vs expected">
          <div className="h-[340px]">
            <ResponsiveContainer>
              <ComposedChart data={benford} margin={{ left: -16 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="digit" {...axisProps} />
                <YAxis {...axisProps} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                <Tooltip content={<ChartTooltip formatter={(v) => `${(v * 100).toFixed(1)}%`} labelFormatter={(d) => `Digit ${d}`} />} />
                <Legend iconType="circle" iconSize={7} wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="Expected" fill="hsl(var(--muted-foreground) / .25)" radius={[3, 3, 0, 0]} />
                {reports.map((r, i) => <Line key={r} dataKey={r} stroke={CHART[i % CHART.length]} strokeWidth={1.6} dot={{ r: 2 }} />)}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {eda.benford.tests.map((t) => (
              <Badge key={t.report} variant={t.verdict.includes('conformity') && !t.verdict.startsWith('non') ? 'success' : t.verdict === 'acceptable' ? 'secondary' : t.verdict.startsWith('insufficient') ? 'outline' : 'warning'}>
                {t.report}: {t.verdict} (MAD {t.MAD})
              </Badge>
            ))}
          </div>
        </Section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Feature discriminative power" description="Kruskal–Wallis effect size ε² across page types">
          <div className="h-[260px]">
            <ResponsiveContainer>
              <BarChart data={kruskal} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid {...gridProps} horizontal={false} vertical />
                <XAxis type="number" {...axisProps} />
                <YAxis type="category" dataKey="name" {...axisProps} width={120} />
                <Tooltip cursor={{ fill: 'hsl(var(--muted))' }} content={<ChartTooltip formatter={(v) => v.toFixed(3)} />} />
                <Bar dataKey="value" name="ε²" fill={CHART[0]} radius={[0, 4, 4, 0]} maxBarSize={16} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>

        <Section title="Distinctive vocabulary" description="Top mean TF-IDF terms per page type">
          <div className="grid max-h-[260px] gap-3 overflow-y-auto sm:grid-cols-2">
            {Object.entries(eda.top_terms || {}).map(([label, terms]) => (
              <div key={label}>
                <p className="mb-1 text-[12px] font-medium">{titleCase(label)}</p>
                <div className="flex flex-wrap gap-1">
                  {terms.slice(0, 6).map(([t]) => <Badge key={t} variant="secondary">{t}</Badge>)}
                </div>
              </div>
            ))}
          </div>
        </Section>
      </div>

      <Section title="Notebook figures" description="Click to enlarge — exported by the EDA notebook">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {FIGURES.map(([file, title]) => (
            <button key={file} onClick={() => setZoom([file, title])} className="group overflow-hidden rounded-lg border bg-white text-left">
              <img src={mlFigureUrl(file)} alt={title} loading="lazy" className="aspect-[16/10] w-full object-contain p-1 transition-transform group-hover:scale-[1.03]" />
              <p className="border-t bg-card px-3 py-2 text-[12px] font-medium">{title}</p>
            </button>
          ))}
        </div>
      </Section>

      <Dialog open={!!zoom} onOpenChange={(o) => !o && setZoom(null)}>
        <DialogContent className="top-[6vh] max-w-5xl">
          <DialogTitle>{zoom?.[1]}</DialogTitle>
          {zoom && <img src={mlFigureUrl(zoom[0])} alt={zoom[1]} className="mt-4 w-full rounded-md bg-white" />}
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ── Evaluation ───────────────────────────────────────────────────────────────
function ComparisonChart({ c }) {
  const data = c.results.map((r) => ({ ...r, err: r.std ?? 0 }))
  return (
    <div className="h-[230px]">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 20, right: 30 }}>
          <CartesianGrid {...gridProps} horizontal={false} vertical />
          <XAxis type="number" domain={[0, 1]} {...axisProps} />
          <YAxis type="category" dataKey="model" {...axisProps} width={150} fontSize={11} />
          <Tooltip cursor={{ fill: 'hsl(var(--muted))' }}
            content={<ChartTooltip formatter={(v, n) => (n === c.metric ? v.toFixed(3) : v)} />} />
          <Bar dataKey="score" name={c.metric} radius={[0, 4, 4, 0]} maxBarSize={18}>
            {data.map((d, i) => (
              <Cell key={d.model} fill={i === 0 ? CHART[0] : /baseline/i.test(d.model) ? 'hsl(var(--muted-foreground) / .35)' : 'hsl(var(--chart-1) / .45)'} />
            ))}
            <ErrorBar dataKey="err" width={4} strokeWidth={1.2} stroke="hsl(var(--foreground) / .5)" direction="x" />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function ConfusionMatrix({ labels, matrix }) {
  const rowSums = matrix.map((r) => r.reduce((a, b) => a + b, 0) || 1)
  return (
    <div className="overflow-x-auto">
      <table className="text-[11.5px]">
        <thead>
          <tr>
            <th className="p-1 text-right font-normal text-muted-foreground">weak label ↓ · predicted →</th>
            {labels.map((l) => <th key={l} className="w-[86px] p-1 font-medium">{titleCase(l)}</th>)}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={labels[i]}>
              <td className="whitespace-nowrap p-1 pr-3 text-right font-medium">{titleCase(labels[i])}</td>
              {row.map((v, j) => {
                const share = v / rowSums[i]
                return (
                  <td key={j} className="p-0.5">
                    <div className={cn('tabular grid h-10 place-items-center rounded text-[12px]', share > 0.5 && 'text-primary-foreground font-semibold')}
                      style={{ background: `hsl(var(--primary) / ${0.06 + share * 0.9})`, outline: i === j ? '1.5px solid hsl(var(--primary))' : 'none' }}>
                      {v}
                    </div>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Metric({ label, value, hint }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-[11.5px] text-muted-foreground">{label}</p>
      <p className="tabular mt-1 text-xl font-semibold">{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  )
}

function EvalTab({ metrics }) {
  if (!metrics?.available) {
    return (
      <EmptyState icon={BrainCircuit} title="Model evaluation pending"
        description="Run notebooks 03 (algorithm selection) and 04 (evaluation) — they write ml/reports/metrics.json." />
    )
  }
  const pc = metrics.models?.page_classifier
  const pcx = metrics.page_classifier
  const kc = metrics.models?.kpi_cleaning
  const t = pc?.test || {}
  const viol = kc?.violations
  const violRows = viol ? Object.keys(viol['before cleansing'] || {}).filter((k) => k !== 'TOTAL')
    .map((k) => ({ name: titleCase(k), Before: viol['before cleansing'][k], After: viol['after cleansing'][k] })) : []

  return (
    <div className="space-y-4">
      {pc && (
        <Section title="PageClassifier · held-out company" description={`Selected: ${pc.config.algorithm} · ${pc.config.features} · ${pc.config.imbalance} · evaluated on ${pc.test_company.join(', ')} (never seen in training or tuning)`}>
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Metric label="Macro-F1 (test)" value={t.macro_f1?.toFixed(3)} hint={`CV ${pc.cv_macro_f1?.toFixed(3)}`} />
            <Metric label="Accuracy" value={t.accuracy?.toFixed(3)} />
            <Metric label="Balanced accuracy" value={t.balanced_accuracy?.toFixed(3)} />
            <Metric label="Cohen's κ" value={t.cohen_kappa?.toFixed(3)} hint="chance-corrected" />
            <Metric label="ROC-AUC (OvR)" value={t.roc_auc_ovr_macro?.toFixed(3)} hint="ranking quality" />
            <Metric label="Inference" value={`${pc.ms_per_page} ms`} hint="per page, CPU" />
          </div>
          {pcx?.selection?.justification && (
            <p className="mt-4 rounded-md bg-muted/50 p-3 text-[12.5px] leading-relaxed text-muted-foreground">
              <span className="font-medium text-foreground">Why this model: </span>{pcx.selection.justification}
            </p>
          )}
        </Section>
      )}

      {metrics.benchmarks && (
        <Section title="Benchmarks" description="Frozen test sets, each run once · TAT-QA scored with the official metric">
          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <p className="mb-2 text-[12px] font-medium text-muted-foreground">Indian annual reports: numeric accuracy</p>
              <table className="w-full text-[12.5px]">
                <thead>
                  <tr className="border-b text-left text-[11.5px] text-muted-foreground">
                    <th className="py-1.5 font-medium">Configuration</th><th className="text-right font-medium">Test v1 (lookups)</th><th className="text-right font-medium">Test v2 (harder)</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.benchmarks.test_v1.map((r, i) => {
                    const v2 = metrics.benchmarks.test_v2[i]
                    const live = r.config.includes('live')
                    return (
                      <tr key={r.config} className={cn('tabular border-b last:border-0', live && 'bg-primary/5 font-medium')}>
                        <td className="py-1.5">{r.config}</td>
                        <td className="text-right">{Math.round(r.accuracy * 100)}% <span className="text-[11px] font-normal text-muted-foreground">({r.ci})</span></td>
                        <td className="text-right">{v2 ? Math.round(v2.accuracy * 100) : '—'}% <span className="text-[11px] font-normal text-muted-foreground">({v2?.ci})</span></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <p className="mt-3 text-[12px] leading-relaxed text-muted-foreground">
                Table reader alone: precision {Math.round(metrics.benchmarks.reader_only.test2.precision * 100)}% on every set; coverage{' '}
                {Math.round(metrics.benchmarks.reader_only.test.coverage * 100)}% (v1) vs {Math.round(metrics.benchmarks.reader_only.test2.coverage * 100)}% (v2). Uncovered questions fall back to the LLM.
              </p>
            </div>
            <div>
              <p className="mb-2 text-[12px] font-medium text-muted-foreground">TAT-QA (Zhu et al., ACL 2021): F1 / EM</p>
              <table className="w-full text-[12.5px]">
                <tbody>
                  {metrics.benchmarks.tatqa.published.map((r) => (
                    <tr key={r.system} className={cn('tabular border-b last:border-0', r.system.includes('FinSight') && 'bg-primary/5 font-medium')}>
                      <td className="py-1.5 pr-2">{r.system}</td>
                      <td className="text-right">{r.F1.toFixed(1)}</td>
                      <td className="text-right text-muted-foreground">{r.EM.toFixed(1)}</td>
                      <td className="pl-2 text-right text-[11px] text-muted-foreground">{r.split}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 text-[12px] leading-relaxed text-muted-foreground">
                Published systems were trained on TAT-QA and scored on the hidden test split; FinSight is zero-shot (3B, local) on a 300-question dev sample.
              </p>
            </div>
          </div>
        </Section>
      )}

      {metrics.rag && (
        <Section title="Q&A · configuration comparison on the gold set"
          description={`${metrics.rag.answerable} answerable + ${metrics.rag.gold_questions - metrics.rag.answerable} unanswerable questions, answers checked against the financial statements · ${metrics.rag.llm}`}>
          <div className="-mx-5 overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-y bg-muted/40 text-left text-[11.5px] text-muted-foreground">
                  <th className="px-5 py-2 font-medium">Configuration</th>
                  <th className="px-3 text-right font-medium">Numeric acc. (95% CI)</th>
                  <th className="px-3 text-right font-medium">Unit acc.</th>
                  <th className="px-3 text-right font-medium">Fabricated ↓</th>
                  <th className="px-3 text-right font-medium">Cited</th>
                  <th className="px-3 text-right font-medium">Refusal acc.</th>
                  <th className="px-5 text-right font-medium">Median latency</th>
                </tr>
              </thead>
              <tbody>
                {metrics.rag.summary.map((r) => {
                  const chosen = r.config === metrics.rag.decision?.selected
                  return (
                    <tr key={r.config} className={cn('tabular border-b last:border-0', chosen && 'bg-primary/5')}>
                      <td className="px-5 py-2 font-medium">{r.config} {chosen && <Badge className="ml-1.5">selected</Badge>}</td>
                      <td className="px-3 text-right font-semibold">{Math.round(r.numeric_accuracy * 100)}% <span className="font-normal text-muted-foreground">({Math.round(r.ci_low * 100)}–{Math.round(r.ci_high * 100)})</span></td>
                      <td className="px-3 text-right">{Math.round(r.unit_accuracy * 100)}%</td>
                      <td className="px-3 text-right">{Math.round(r.fabrication_rate * 100)}%</td>
                      <td className="px-3 text-right">{Math.round(r.citation_rate * 100)}%</td>
                      <td className="px-3 text-right">{Math.round(r.refusal_accuracy * 100)}%</td>
                      <td className="px-5 text-right">{r.median_latency_s.toFixed(1)} s</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <div className="rounded-md border p-3 text-[12.5px]">
              <p className="mb-1.5 font-medium">McNemar's exact test (paired, numeric accuracy)</p>
              {metrics.rag.mcnemar.map((t) => (
                <p key={t.comparison} className="tabular text-muted-foreground">
                  {t.comparison}: fixed {t.fixed}, broke {t.broken}, p = {t.p_value.toFixed(3)}
                </p>
              ))}
            </div>
            <p className="rounded-md bg-muted/50 p-3 text-[12.5px] leading-relaxed text-muted-foreground">
              <span className="font-medium text-foreground">Decision: </span>{metrics.rag.decision?.reason}
            </p>
          </div>
        </Section>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {(metrics.comparisons || []).map((c) => (
          <Section key={c.title} title={c.title} description={`${c.metric}${c.results.some((r) => r.std) ? ' · error bars = std across held-out companies' : ''}`}>
            <ComparisonChart c={c} />
          </Section>
        ))}
      </div>

      {pcx && (
        <div className="grid gap-4 xl:grid-cols-5">
          <Section title="Confusion matrix (test company)" description="Counts; colour = row share (recall)" className="xl:col-span-3">
            <ConfusionMatrix labels={pcx.labels} matrix={pcx.confusion} />
          </Section>
          <Section title="Per-class results" description="Precision / recall / F1 and one-vs-rest curve areas" className="xl:col-span-2">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-b text-left text-[11.5px] text-muted-foreground">
                  <th className="py-1.5 font-medium">Class</th><th className="text-right font-medium">P</th><th className="text-right font-medium">R</th>
                  <th className="text-right font-medium">F1</th><th className="text-right font-medium">AUC</th><th className="text-right font-medium">AP</th><th className="text-right font-medium">n</th>
                </tr>
              </thead>
              <tbody>
                {pcx.per_class.map((r) => (
                  <tr key={r.label} className="tabular border-b last:border-0">
                    <td className="py-1.5 font-medium">{titleCase(r.label)}</td>
                    <td className="text-right">{r.precision.toFixed(2)}</td><td className="text-right">{r.recall.toFixed(2)}</td>
                    <td className="text-right font-semibold">{r.f1.toFixed(2)}</td>
                    <td className="text-right">{pcx.curves?.[r.label]?.roc_auc?.toFixed(2) ?? '—'}</td>
                    <td className="text-right">{pcx.curves?.[r.label]?.average_precision?.toFixed(2) ?? '—'}</td>
                    <td className="text-right text-muted-foreground">{r.support}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {pc?.statement_detection && (
              <div className="mt-4 rounded-md border p-3 text-[12.5px]">
                <p className="font-medium">Downstream: statement + notes vs rest</p>
                <p className="tabular mt-1 text-muted-foreground">
                  precision {pc.statement_detection.precision.toFixed(2)} · recall {pc.statement_detection.recall.toFixed(2)} · F1 {pc.statement_detection.f1.toFixed(2)} · AUC {pc.statement_detection.roc_auc.toFixed(2)}
                </p>
              </div>
            )}
          </Section>
        </div>
      )}

      {pcx && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Section title="Learning curve" description="Test macro-F1 vs number of training pages — does more data help?">
            <div className="h-[230px]">
              <ResponsiveContainer>
                <ComposedChart data={pcx.learning_curve} margin={{ left: -16, right: 8 }}>
                  <CartesianGrid {...gridProps} />
                  <XAxis dataKey="train_pages" {...axisProps} />
                  <YAxis domain={[0, 1]} {...axisProps} />
                  <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(3)} labelFormatter={(l) => `${l} training pages`} />} />
                  <Line dataKey="macro_f1" name="macro-F1" stroke={CHART[0]} strokeWidth={2} dot={{ r: 3 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </Section>
          <Section title="What the model learned" description="Highest-weighted terms per class (Linear SVM coefficients)">
            <div className="grid max-h-[230px] gap-3 overflow-y-auto sm:grid-cols-2">
              {Object.entries(pcx.top_terms || {}).map(([label, terms]) => (
                <div key={label}>
                  <p className="mb-1 text-[12px] font-medium">{titleCase(label)}</p>
                  <div className="flex flex-wrap gap-1">{terms.slice(0, 7).map((x) => <Badge key={x} variant="secondary">{x}</Badge>)}</div>
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}

      {pcx?.predictions_sample && (
        <Section title="Prediction results (sample of test pages)" description="Prediction, confidence and the weak label it is compared against">
          <div className="-mx-5 overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-y bg-muted/40 text-left text-[11.5px] text-muted-foreground">
                  <th className="px-5 py-2 font-medium">Page</th><th className="px-3 font-medium">Predicted</th><th className="px-3 font-medium">Confidence</th>
                  <th className="px-3 font-medium">Weak label</th><th className="px-5 font-medium">Text</th>
                </tr>
              </thead>
              <tbody>
                {pcx.predictions_sample.map((r) => (
                  <tr key={r.page_number} className="border-b last:border-0">
                    <td className="tabular px-5 py-2">{r.page_number}</td>
                    <td className="px-3"><Badge variant={r.pred === r.weak_label ? 'success' : 'warning'}>{titleCase(r.pred)}</Badge></td>
                    <td className="tabular px-3">{(r.confidence * 100).toFixed(0)}%</td>
                    <td className="px-3 text-muted-foreground">{titleCase(r.weak_label)}</td>
                    <td className="max-w-[420px] truncate px-5 text-muted-foreground">{r.snippet}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {kc && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Section title="KPI cleansing · accounting-identity violations" description={`Coverage ${Math.round(kc.coverage.before * 100)}% → ${Math.round(kc.coverage.after * 100)}% of KPI rows hold a value`}>
            <div className="h-[230px]">
              <ResponsiveContainer>
                <BarChart data={violRows} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid {...gridProps} horizontal={false} vertical />
                  <XAxis type="number" allowDecimals={false} {...axisProps} />
                  <YAxis type="category" dataKey="name" width={120} {...axisProps} />
                  <Tooltip cursor={{ fill: 'hsl(var(--muted))' }} content={<ChartTooltip />} />
                  <Legend iconType="circle" iconSize={7} wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="Before" fill={CHART[3]} radius={[0, 3, 3, 0]} maxBarSize={12} />
                  <Bar dataKey="After" fill={CHART[1]} radius={[0, 3, 3, 0]} maxBarSize={12} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Section>
          <Section title="Reporting-unit detection" description="Detected ₹ unit vs the unit verified on the statement pages">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-b text-left text-[11.5px] text-muted-foreground">
                  <th className="py-1.5 font-medium">Report</th><th className="font-medium">Reference</th><th className="font-medium">Whole report</th>
                  <th className="font-medium">Heading rules</th><th className="font-medium">PageClassifier</th>
                </tr>
              </thead>
              <tbody>
                {(metrics.unit_detection || []).map((r) => (
                  <tr key={r.report} className="border-b last:border-0">
                    <td className="py-1.5 font-medium">{r.report}</td><td>{r.reference}</td>
                    {['whole report', 'heading rules', 'PageClassifier'].map((k) => (
                      <td key={k} className={r[k] === r.reference ? 'text-success' : 'text-danger'}>{r[k]}</td>
                    ))}
                  </tr>
                ))}
                <tr className="tabular font-medium">
                  <td className="pt-2">Accuracy</td><td />
                  {['whole report', 'heading rules', 'PageClassifier'].map((k) => <td key={k} className="pt-2">{Math.round(kc.unit_detection_accuracy[k] * 100)}%</td>)}
                </tr>
              </tbody>
            </table>
          </Section>
        </div>
      )}
    </div>
  )
}

export default function ModelLab() {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') || 'overview'
  const setTab = (t) => setParams({ tab: t }, { replace: true })
  const { data: health } = useQuery({ queryKey: ['ml-health'], queryFn: getMlHealth })
  const { data: metrics } = useQuery({ queryKey: ['ml-metrics'], queryFn: getMlMetrics })
  const { data: pre, isLoading: lp } = useQuery({ queryKey: ['ml-pre'], queryFn: getMlPreprocessing })
  const { data: eda, isLoading: le } = useQuery({ queryKey: ['ml-eda'], queryFn: getMlEda })

  return (
    <PageBody>
      <PageHeader
        eyebrow={<span className="inline-flex items-center gap-1.5"><FlaskConical className="size-3.5" /> Machine learning</span>}
        title="Model Lab"
        description="Data pipeline, exploratory analysis, model stack and evaluation — the ML behind every answer."
      />
      <Tabs value={tab} onValueChange={setTab}>
        <TabsListLine>
          <TabsTriggerLine value="overview"><Server /> Overview</TabsTriggerLine>
          <TabsTriggerLine value="data"><Database /> Data & preprocessing</TabsTriggerLine>
          <TabsTriggerLine value="eda"><Lightbulb /> EDA</TabsTriggerLine>
          <TabsTriggerLine value="eval"><BrainCircuit /> Evaluation</TabsTriggerLine>
        </TabsListLine>
        <TabsContent value="overview"><OverviewTab health={health} metrics={metrics} /></TabsContent>
        <TabsContent value="data">{lp ? <Skeleton className="h-96" /> : <DataTab pre={pre} />}</TabsContent>
        <TabsContent value="eda">{le ? <Skeleton className="h-96" /> : <EdaTab eda={eda} />}</TabsContent>
        <TabsContent value="eval"><EvalTab metrics={metrics} /></TabsContent>
      </Tabs>
    </PageBody>
  )
}
