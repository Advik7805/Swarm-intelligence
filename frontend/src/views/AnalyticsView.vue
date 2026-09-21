<template>
  <div class="analytics-page">
    <!-- nav -->
    <nav class="anav">
      <router-link to="/" class="anav-brand">
        <img src="../assets/logo/hivemind_logo_left.png" alt="HiveMind" class="anav-logo" />
      </router-link>
      <div class="anav-actions">
        <select v-model="selectedRun" class="run-select" :disabled="loading">
          <option value="" disabled>{{ $t('analytics.selectRun') }}</option>
          <option v-for="r in runs" :key="r.simulation_id" :value="r.simulation_id">
            {{ shortId(r.simulation_id) }} · {{ $t('analytics.runMeta', { posts: r.n_posts, agents: r.n_agents }) }}
          </option>
        </select>
        <button class="hm-btn" @click="loadDemo" :disabled="loading">
          {{ $t('analytics.tryDemo') }}
        </button>
        <ThemeToggle />
      </div>
    </nav>

    <!-- loading / error -->
    <div v-if="loading" class="state-box"><span class="spinner"></span>{{ $t('analytics.loading') }}</div>
    <div v-else-if="error" class="state-box error">
      <p>{{ error }}</p>
      <button class="hm-btn hm-btn-ghost" @click="loadDemo">{{ $t('analytics.tryDemo') }}</button>
    </div>

    <!-- dashboard -->
    <div v-else-if="data" class="dashboard">
      <!-- header strip -->
      <header class="head">
        <div class="head-left">
          <span class="hm-chip">{{ data.demo ? $t('analytics.demoBadge') : $t('analytics.liveBadge') }}</span>
          <h1 class="topic">{{ data.run.topic || data.topic || $t('analytics.untitledRun') }}</h1>
          <p class="run-id">{{ data.simulation_id }}</p>
        </div>
        <div class="head-stats">
          <div class="stat"><span class="v">{{ agentsShown }}</span><span class="l">{{ $t('analytics.agents') }}</span></div>
          <div class="stat"><span class="v">{{ roundsShown }}</span><span class="l">{{ $t('analytics.rounds') }}</span></div>
          <div class="stat"><span class="v">{{ postsShown }}</span><span class="l">{{ $t('analytics.posts') }}</span></div>
          <div class="stat"><span class="v">{{ negShown }}%</span><span class="l">{{ $t('analytics.negative') }}</span></div>
        </div>
      </header>

      <!-- grid -->
      <div class="grid">
        <!-- confidence -->
        <section v-reveal="0" class="card span-4">
          <h2 class="card-title">{{ $t('analytics.confidenceTitle') }}</h2>
          <p class="card-sub">{{ $t('analytics.confidenceSub') }}</p>
          <ConfidenceGauge :score="confidence.score || 0" :band="confidence.band || 'low'"
            :factors="confidence.factors || {}" />
        </section>

        <!-- sentiment timeline -->
        <section v-reveal="60" class="card span-5">
          <h2 class="card-title">{{ $t('analytics.sentimentTitle') }}</h2>
          <p class="card-sub">{{ $t('analytics.sentimentSub') }}</p>
          <svg :viewBox="`0 0 460 220`" class="timeline-svg">
            <!-- grid -->
            <g v-for="i in 5" :key="'g'+i">
              <line x1="40" :y1="20 + (i-1)*40" x2="450" :y2="20 + (i-1)*40"
                stroke="var(--hm-grid)" stroke-width="1" />
            </g>
            <!-- zero line -->
            <line x1="40" :y1="yOf(0)" x2="450" :y2="yOf(0)"
              stroke="var(--hm-text-faint)" stroke-width="1" stroke-dasharray="4 4" />
            <!-- area + line -->
            <path :d="areaPath" fill="var(--hm-accent-soft)" />
            <path :d="linePath" fill="none" stroke="var(--hm-accent)" stroke-width="2.5"
              stroke-linejoin="round" stroke-linecap="round" />
            <!-- dots -->
            <circle v-for="p in timelinePts" :key="'d'+p.round" :cx="p.x" :cy="p.y" r="3.5"
              fill="var(--hm-accent-bright)" stroke="var(--hm-bg)" stroke-width="1.5" />
            <!-- labels -->
            <text :x="24" :y="yOf(1)+4" text-anchor="middle" class="ax-label">+1</text>
            <text :x="24" :y="yOf(0)+4" text-anchor="middle" class="ax-label">0</text>
            <text :x="24" :y="yOf(-1)+4" text-anchor="middle" class="ax-label">-1</text>
            <text x="40" :y="212" class="ax-label">R1</text>
            <text :x="450" :y="212" text-anchor="end" class="ax-label">R{{ lastRound }}</text>
          </svg>
          <div class="sentiment-strip">
            <div class="strip-seg pos" :style="{flex: sentimentSummary.positive_share || 0.001}"></div>
            <div class="strip-seg neu" :style="{flex: sentimentSummary.neutral_share || 0.001}"></div>
            <div class="strip-seg neg" :style="{flex: sentimentSummary.negative_share || 0.001}"></div>
          </div>
          <div class="strip-legend">
            <span>{{ $t('analytics.positive') }} {{ fmtPct(sentimentSummary.positive_share) }}</span>
            <span>{{ $t('analytics.neutral') }} {{ fmtPct(sentimentSummary.neutral_share) }}</span>
            <span>{{ $t('analytics.negative') }} {{ fmtPct(sentimentSummary.negative_share) }}</span>
          </div>
        </section>

        <!-- emotions -->
        <section v-reveal="120" class="card span-3">
          <h2 class="card-title">{{ $t('analytics.emotionTitle') }}</h2>
          <p class="card-sub">{{ $t('analytics.emotionSub') }}</p>
          <div class="emotion-list">
            <div v-for="e in emotionList" :key="e.name" class="emotion-row">
              <span class="emotion-name" :style="{ color: emotionColor(e.name) }">{{ $t(`analytics.emotions.${e.name}`) }}</span>
              <div class="emotion-bar">
                <div class="emotion-fill" :style="{ width: e.share * 100 + '%', background: emotionColor(e.name) }"></div>
              </div>
              <span class="emotion-val">{{ fmtPct(e.share) }}</span>
            </div>
          </div>
        </section>

        <!-- network -->
        <section v-reveal="180" class="card span-7">
          <h2 class="card-title">{{ $t('analytics.networkTitle') }}</h2>
          <p class="card-sub">
            {{ $t('analytics.networkSub') }}
            <span v-if="networkStats.echo_chamber_index !== undefined" class="echo-chip"
              :class="echoLevel">{{ $t('analytics.echoIndex') }}: {{ networkStats.echo_chamber_index }}</span>
          </p>
          <NetworkGraph :influencers="network.influencers" :communities="network.communities"
            :agents="data.agents" />
          <div class="net-stats" v-if="networkStats.nodes">
            <div class="net-stat"><span class="v">{{ networkStats.nodes }}</span><span class="l">{{ $t('analytics.nodes') }}</span></div>
            <div class="net-stat"><span class="v">{{ networkStats.edges }}</span><span class="l">{{ $t('analytics.edges') }}</span></div>
            <div class="net-stat"><span class="v">{{ networkStats.modularity }}</span><span class="l">{{ $t('analytics.modularity') }}</span></div>
            <div class="net-stat"><span class="v">{{ networkStats.reciprocity }}</span><span class="l">{{ $t('analytics.reciprocity') }}</span></div>
            <div class="net-stat"><span class="v">{{ networkStats.communities }}</span><span class="l">{{ $t('analytics.communities') }}</span></div>
          </div>
        </section>

        <!-- influencers -->
        <section class="card span-5">
          <h2 class="card-title">{{ $t('analytics.influencersTitle') }}</h2>
          <p class="card-sub">{{ $t('analytics.influencersSub') }}</p>
          <div class="influencer-table">
            <div v-for="(inf, idx) in topInfluencers" :key="inf.agent_id" class="inf-row">
              <span class="inf-rank" :class="{ top: idx < 3 }">#{{ idx + 1 }}</span>
              <span class="inf-name">{{ agentName(inf.agent_id) }}</span>
              <div class="inf-bar">
                <div class="inf-fill" :style="{ width: (inf.influence * 100) + '%' }"></div>
              </div>
              <span class="inf-val">{{ inf.influence.toFixed(3) }}</span>
            </div>
            <p v-if="!topInfluencers.length" class="empty-hint">{{ $t('common.noData') }}</p>
          </div>
        </section>

        <!-- personas -->
        <section v-reveal="240" class="card span-12">
          <h2 class="card-title">{{ $t('analytics.personasTitle') }}</h2>
          <p class="card-sub">{{ $t('analytics.personasSub') }}</p>
          <div class="persona-grid">
            <div v-for="c in personas" :key="c.id" class="persona-card">
              <div class="persona-head">
                <span class="persona-icon">{{ personaIcon(c) }}</span>
                <div>
                  <h3 class="persona-label">{{ c.label }}</h3>
                  <span class="persona-size">{{ $t('analytics.agentCount', { n: c.size }) }}</span>
                </div>
              </div>
              <div class="persona-chips">
                <span v-for="term in (c.top_terms || []).slice(0, 4)" :key="term" class="term-chip">{{ term }}</span>
              </div>
              <div class="persona-sig" v-if="c.signature">
                <div class="sig-row">
                  <span>{{ $t('analytics.sigPosting') }}</span>
                  <div class="sig-bar"><div :style="{ width: (c.signature.post_ratio * 200) + '%' }"></div></div>
                </div>
                <div class="sig-row">
                  <span>{{ $t('analytics.sigAmplify') }}</span>
                  <div class="sig-bar"><div :style="{ width: (c.signature.amplify_ratio * 200) + '%' }"></div></div>
                </div>
                <div class="sig-row">
                  <span>{{ $t('analytics.sigSentiment') }}</span>
                  <span class="sig-sent" :class="c.signature.mean_sentiment > 0.05 ? 'pos' : (c.signature.mean_sentiment < -0.05 ? 'neg' : '')">
                    {{ c.signature.mean_sentiment > 0 ? '+' : '' }}{{ c.signature.mean_sentiment }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <footer class="foot">
        <p>{{ $t('analytics.footer') }}</p>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import analyticsApi from '../api/analytics'
import ThemeToggle from '../components/ThemeToggle.vue'
import NetworkGraph from '../components/NetworkGraph.vue'
import ConfidenceGauge from '../components/ConfidenceGauge.vue'

const { t } = useI18n()
import { useCountUp } from '../composables/useCountUp'
const loading = ref(false)
const error = ref('')
const data = ref(null)
const runs = ref([])
const selectedRun = ref('')

const cAgents = useCountUp(() => data.value?.run?.n_agents || 0)
const cRounds = useCountUp(() => data.value?.run?.n_rounds || 0)
const cPosts = useCountUp(() => data.value?.run?.n_posts || 0)
const cNeg = useCountUp(() => Math.round((data.value?.sentiment_summary?.negative_share || 0) * 100))
const agentsShown = cAgents.shown
const roundsShown = cRounds.shown
const postsShown = cPosts.shown
const negShown = cNeg.shown

const sentimentSummary = computed(() => data.value?.sentiment_summary || {})
const network = computed(() => data.value?.network || {})
const networkStats = computed(() => {
  const s = { ...(network.value.stats || {}) }
  s.communities = (network.value.communities || []).length
  return s
})
const confidence = computed(() => data.value?.confidence || {})
const personas = computed(() => data.value?.personas || [])
const topInfluencers = computed(() => (network.value.influencers || []).slice(0, 8))

const emotionList = computed(() =>
  Object.entries(sentimentSummary.value.emotion_distribution || {})
    .map(([name, share]) => ({ name, share }))
    .sort((a, b) => b.share - a.share))

const echoLevel = computed(() => {
  const e = Number(networkStats.value.echo_chamber_index || 0)
  return e > 0.66 ? 'high' : e > 0.4 ? 'mid' : 'low'
})

const agentName = (id) => {
  const a = (data.value?.agents || []).find(x => x.agent_id === id)
  return a ? (a.name || `Agent ${id}`) : `Agent ${id}`
}

const personaIcon = (c) => {
  const l = (c.label || '').toLowerCase()
  if (l.includes('outraged') || l.includes('anger')) return '🔥'
  if (l.includes('silent') || l.includes('observer')) return '👀'
  if (l.includes('amplif')) return '📢'
  if (l.includes('connector')) return '🕸'
  if (l.includes('advocate') || l.includes('champion')) return '📣'
  return '🐝'
}

// ---- timeline geometry ----
const timeline = computed(() => data.value?.timeline || [])
const lastRound = computed(() => timeline.value.length ? timeline.value[timeline.value.length - 1].round : 1)
const timelinePts = computed(() => {
  if (timeline.value.length < 1) return []
  const w = 410, x0 = 40
  const maxR = lastRound.value || 1
  return timeline.value.map(p => ({
    ...p,
    x: x0 + ((p.round - 1) / Math.max(maxR - 1, 1)) * w,
    y: yOf(p.mean_sentiment),
  }))
})
function yOf(v) {
  // map [-1,1] -> [200,20]
  return 110 - (v * 90)
}
const linePath = computed(() => {
  const pts = timelinePts.value
  if (!pts.length) return ''
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
})
const areaPath = computed(() => {
  const pts = timelinePts.value
  if (!pts.length) return ''
  const base = yOf(0)
  const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
  return `${d} L ${pts[pts.length - 1].x.toFixed(1)} ${base} L ${pts[0].x.toFixed(1)} ${base} Z`
})

const emotionColor = (name) => `var(--em-${name}, var(--hm-neutral))`
const fmtPct = (v) => `${Math.round((v || 0) * 100)}%`
const shortId = (id) => (id || '').replace(/^sim-/, '').slice(0, 14)

// ---- data loading ----
async function loadOverview(simId) {
  loading.value = true
  error.value = ''
  try {
    data.value = await analyticsApi.overview(simId)
  } catch (e) {
    error.value = t('analytics.loadError')
    data.value = null
  } finally {
    loading.value = false
  }
}

async function loadDemo() {
  loading.value = true
  error.value = ''
  try {
    data.value = await analyticsApi.demo()
    selectedRun.value = data.value.simulation_id
    await loadRuns()
  } catch (e) {
    error.value = t('analytics.demoError')
  } finally {
    loading.value = false
  }
}

async function loadRuns() {
  try {
    runs.value = (await analyticsApi.runs()).runs || []
  } catch { /* backend down */ }
}

onMounted(async () => {
  await loadRuns()
  if (runs.value.length) {
    selectedRun.value = runs.value[0].simulation_id
    await loadOverview(selectedRun.value)
  } else {
    await loadDemo()
  }
})

watch(selectedRun, (v) => { if (v) loadOverview(v) })
</script>

<style scoped>
.analytics-page {
  min-height: 100vh;
  background:
    radial-gradient(1200px 500px at 85% -10%, var(--hm-accent-soft), transparent 60%),
    var(--hm-bg);
  color: var(--hm-text);
  font-family: var(--font-sans);
}

/* nav */
.anav {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 32px;
  border-bottom: 1px solid var(--hm-border-soft);
  background: var(--hm-bg);
  position: sticky; top: 0; z-index: 20;
}
.anav-logo { height: 34px; }
.anav-actions { display: flex; align-items: center; gap: 12px; }
.run-select {
  background: var(--hm-surface); color: var(--hm-text);
  border: 1px solid var(--hm-border); border-radius: 8px;
  padding: 8px 10px; font-size: 0.8rem; max-width: 280px;
  font-family: var(--font-mono);
}

/* states */
.state-box {
  display: flex; flex-direction: column; gap: 18px; align-items: center;
  justify-content: center; min-height: 60vh; color: var(--hm-text-muted);
}
.state-box.error { color: var(--hm-neg); }
.spinner {
  width: 34px; height: 34px; border-radius: 50%;
  border: 3px solid var(--hm-border); border-top-color: var(--hm-accent);
  animation: spin 0.9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* layout */
.dashboard { max-width: 1280px; margin: 0 auto; padding: 28px 32px 60px; }
.grid {
  display: grid; grid-template-columns: repeat(12, 1fr); gap: 18px;
}
.span-3 { grid-column: span 3; } .span-4 { grid-column: span 4; }
.span-5 { grid-column: span 5; } .span-7 { grid-column: span 7; }
.span-12 { grid-column: span 12; }
@media (max-width: 1024px) {
  .span-3, .span-4, .span-5, .span-7 { grid-column: span 12; }
}

/* header */
.head {
  display: flex; justify-content: space-between; align-items: flex-end;
  gap: 20px; margin-bottom: 26px; flex-wrap: wrap;
}
.topic { font-size: 1.5rem; font-weight: 700; margin: 10px 0 4px; letter-spacing: -0.3px; }
.run-id { font-family: var(--font-mono); font-size: 0.72rem; color: var(--hm-text-faint); }
.head-stats { display: flex; gap: 26px; }
.stat { display: flex; flex-direction: column; align-items: center; }
.stat .v { font-size: 1.6rem; font-weight: 800; color: var(--hm-accent); font-family: var(--font-mono); }
.stat .l { font-size: 0.68rem; letter-spacing: 1px; text-transform: uppercase; color: var(--hm-text-faint); }

/* cards */
.card {
  background: var(--hm-surface);
  border: 1px solid var(--hm-border);
  border-radius: 14px;
  padding: 20px 22px;
}
.card-title { font-size: 1rem; font-weight: 700; margin-bottom: 4px; }
.card-sub { font-size: 0.75rem; color: var(--hm-text-faint); margin-bottom: 14px; letter-spacing: 0.2px; }

/* timeline */
.timeline-svg { width: 100%; height: auto; }
.ax-label { fill: var(--hm-text-faint); font-size: 10px; font-family: var(--font-mono); }
.sentiment-strip { display: flex; height: 10px; border-radius: 5px; overflow: hidden; margin-top: 8px; border: 1px solid var(--hm-border-soft); }
.strip-seg.pos { background: var(--hm-pos); }
.strip-seg.neu { background: var(--hm-neutral); opacity: 0.5; }
.strip-seg.neg { background: var(--hm-neg); }
.strip-legend {
  display: flex; justify-content: space-between;
  font-size: 0.68rem; color: var(--hm-text-muted); margin-top: 6px;
}

/* emotions */
.emotion-list { display: grid; gap: 10px; }
.emotion-row { display: grid; grid-template-columns: 86px 1fr 40px; align-items: center; gap: 8px; }
.emotion-name { font-size: 0.72rem; font-weight: 600; }
.emotion-bar { height: 8px; background: var(--hm-bg-soft); border-radius: 4px; overflow: hidden; border: 1px solid var(--hm-border-soft); }
.emotion-fill { height: 100%; border-radius: 4px; transition: width 0.6s ease; }
.emotion-val { font-size: 0.7rem; color: var(--hm-text-muted); text-align: right; font-family: var(--font-mono); }

/* network */
.echo-chip {
  margin-left: 8px; padding: 2px 8px; border-radius: 999px;
  font-family: var(--font-mono); font-size: 0.68rem;
}
.echo-chip.high { background: rgba(229, 83, 75, 0.15); color: var(--hm-neg); }
.echo-chip.mid { background: var(--hm-accent-soft); color: var(--hm-accent-bright); }
.echo-chip.low { background: rgba(63, 182, 139, 0.15); color: var(--hm-pos); }
.net-stats { display: flex; gap: 24px; margin-top: 14px; flex-wrap: wrap; }
.net-stat .v { font-weight: 800; color: var(--hm-text); font-family: var(--font-mono); font-size: 1.05rem; }
.net-stat .l { display: block; font-size: 0.62rem; letter-spacing: 1px; text-transform: uppercase; color: var(--hm-text-faint); }

/* influencers */
.influencer-table { display: grid; gap: 9px; }
.inf-row { display: grid; grid-template-columns: 34px 1fr 64px 52px; align-items: center; gap: 8px; }
.inf-rank { font-family: var(--font-mono); font-size: 0.72rem; color: var(--hm-text-faint); }
.inf-rank.top { color: var(--hm-accent); font-weight: 800; }
.inf-name { font-size: 0.78rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.inf-bar { height: 7px; background: var(--hm-bg-soft); border-radius: 4px; overflow: hidden; border: 1px solid var(--hm-border-soft); }
.inf-fill { height: 100%; background: linear-gradient(90deg, var(--hm-accent-dim), var(--hm-accent-bright)); border-radius: 4px; transition: width 0.6s ease; }
.inf-val { font-size: 0.68rem; color: var(--hm-text-muted); text-align: right; font-family: var(--font-mono); }

/* personas */
.persona-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 14px; }
.persona-card {
  background: var(--hm-bg-soft);
  border: 1px solid var(--hm-border);
  border-radius: 12px; padding: 16px;
  transition: transform 0.2s ease, border-color 0.2s ease;
}
.persona-card:hover { transform: translateY(-2px); border-color: var(--hm-accent-dim); }
.persona-head { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; }
.persona-icon {
  width: 38px; height: 38px; border-radius: 10px;
  background: var(--hm-accent-soft); border: 1px solid var(--hm-accent-dim);
  display: flex; align-items: center; justify-content: center; font-size: 1.1rem;
}
.persona-label { font-size: 0.86rem; font-weight: 700; }
.persona-size { font-size: 0.66rem; color: var(--hm-text-faint); letter-spacing: 0.6px; text-transform: uppercase; }
.persona-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.term-chip {
  font-family: var(--font-mono); font-size: 0.64rem;
  background: var(--hm-surface-2); color: var(--hm-text-muted);
  padding: 2px 8px; border-radius: 999px; border: 1px solid var(--hm-border);
}
.persona-sig { display: grid; gap: 6px; }
.sig-row { display: grid; grid-template-columns: 82px 1fr auto; align-items: center; gap: 8px; font-size: 0.68rem; color: var(--hm-text-muted); }
.sig-bar { height: 5px; background: var(--hm-surface); border-radius: 3px; border: 1px solid var(--hm-border-soft); overflow: hidden; max-width: 120px; }
.sig-bar div { height: 100%; background: var(--hm-accent); }
.sig-sent { font-family: var(--font-mono); }
.sig-sent.pos { color: var(--hm-pos); }
.sig-sent.neg { color: var(--hm-neg); }

.empty-hint { color: var(--hm-text-faint); font-size: 0.78rem; }
.foot { margin-top: 40px; text-align: center; color: var(--hm-text-faint); font-size: 0.7rem; }
</style>
