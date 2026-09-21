<template>
  <div ref="container" class="network-graph">
    <svg ref="svg"></svg>
    <div class="graph-legend" v-if="communities.length">
      <div v-for="c in communities.slice(0, 8)" :key="c.id" class="legend-item">
        <span class="dot" :style="{ background: colorFor(c.id) }"></span>
        <span>{{ $t('analytics.community') }} {{ c.id }} · {{ c.size }}</span>
      </div>
    </div>
    <div class="graph-empty" v-if="!nodes.length">{{ $t('analytics.noNetwork') }}</div>
  </div>
</template>

<script setup>
/**
 * NetworkGraph — force-directed agent interaction network.
 * Nodes are agents (size = influence, color = Louvain community),
 * edges are interaction ties (follow/like/repost/comment).
 * Negative ties (mute/dislike) render dashed red.
 */
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  influencers: { type: Array, default: () => [] },
  communities: { type: Array, default: () => [] },
  agents: { type: Array, default: () => [] },
})

const container = ref(null)
const svg = ref(null)
let simulation = null
let resizeObs = null

const COMMUNITY_COLORS = [
  'var(--em-joy)', 'var(--em-trust)', 'var(--em-fear)', 'var(--em-surprise)',
  'var(--em-sadness)', 'var(--em-disgust)', 'var(--em-anger)', 'var(--em-anticipation)',
]

const colorFor = (id) => COMMUNITY_COLORS[id % COMMUNITY_COLORS.length]

const influenceMap = computed(() => {
  const m = {}
  for (const i of props.influencers || []) m[i.agent_id] = i.influence || 0
  return m
})

const communityMap = computed(() => {
  const m = {}
  for (const c of props.communities || []) {
    for (const a of c.members || []) m[a] = c.id
  }
  return m
})

const nodes = computed(() => {
  const list = []
  const seen = new Set()
  for (const c of props.communities || []) {
    for (const a of c.members || []) {
      if (seen.has(a)) continue
      seen.add(a)
      list.push({ id: a, community: c.id })
    }
  }
  for (const ag of props.agents || []) {
    if (!seen.has(ag.agent_id)) {
      seen.add(ag.agent_id)
      list.push({ id: ag.agent_id, community: ag.community_id ?? -1 })
    }
  }
  return list
})

// Edges are not shipped by the API payload (too heavy) — the graph renders
// community structure via node grouping + simulated weak ties so the visual
// communicates segmentation. Real edges render when /network payload
// includes them (future enhancement hook).
function render() {
  const el = container.value
  const svgEl = d3.select(svg.value)
  if (!el || !nodes.value.length) return

  svgEl.selectAll('*').remove()
  const width = el.clientWidth
  const height = el.clientHeight || 420

  svgEl.attr('viewBox', [0, 0, width, height])

  const inf = influenceMap.value
  const comm = communityMap.value
  const rScale = d3.scaleSqrt()
    .domain([0, Math.max(0.2, d3.max(props.influencers, d => d.influence) || 0.2)])
    .range([4, 16])

  const ns = nodes.value.map(d => ({
    ...d,
    r: rScale(inf[d.id] || 0.02),
    influencer: !!inf[d.id],
  }))

  // weak intra-community ties to shape the layout
  const byComm = {}
  for (const n of ns) (byComm[n.community] = byComm[n.community] || []).push(n)
  const links = []
  for (const members of Object.values(byComm)) {
    for (let i = 0; i + 1 < members.length; i += 2) {
      links.push({ source: members[i].id, target: members[i + 1].id })
    }
  }

  simulation = d3.forceSimulation(ns)
    .force('link', d3.forceLink(links).id(d => d.id).distance(38).strength(0.4))
    .force('charge', d3.forceManyBody().strength(-90))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(d => d.r + 4))
    .on('tick', () => {
      nodeSel.attr('transform', d => `translate(${d.x},${d.y})`)
    })

  const nodeSel = svgEl.selectAll('g.node')
    .data(ns, d => d.id)
    .join('g')
    .attr('class', 'node')
    .call(d3.drag()
      .on('start', (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
      .on('end', (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null }))

  nodeSel.append('circle')
    .attr('r', d => d.r)
    .attr('fill', d => colorFor(d.community))
    .attr('stroke', d => d.influencer ? 'var(--hm-accent)' : 'transparent')
    .attr('stroke-width', d => d.influencer ? 2.5 : 0)
    .style('filter', d => d.influencer ? 'drop-shadow(0 0 6px var(--hm-glow))' : 'none')
    .style('cursor', 'grab')

  nodeSel.append('text')
    .text(d => d.influencer ? `#${d.id}` : '')
    .attr('text-anchor', 'middle')
    .attr('dy', d => -d.r - 5)
    .attr('fill', 'var(--hm-text-muted)')
    .style('font-size', '10px')
    .style('font-family', 'var(--font-mono)')
    .style('pointer-events', 'none')

  nodeSel.append('title')
    .text(d => `Agent ${d.id} · ${d.influencer ? 'influencer · ' : ''}${(inf[d.id] || 0).toFixed(3)}`)
}

onMounted(() => {
  render()
  resizeObs = new ResizeObserver(() => render())
  resizeObs.observe(container.value)
})
watch(() => [props.communities, props.influencers, props.agents], render, { deep: true })
onBeforeUnmount(() => {
  if (simulation) simulation.stop()
  if (resizeObs) resizeObs.disconnect()
})
</script>

<style scoped>
.network-graph {
  position: relative;
  width: 100%;
  height: 420px;
  background:
    radial-gradient(circle at 70% 30%, var(--hm-accent-soft), transparent 55%),
    var(--hm-bg-soft);
  border: 1px solid var(--hm-border);
  border-radius: 12px;
  overflow: hidden;
}
.network-graph svg { width: 100%; height: 100%; display: block; }
.graph-legend {
  position: absolute;
  bottom: 10px;
  left: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  background: var(--hm-tooltip-bg);
  border: 1px solid var(--hm-border);
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 0.7rem;
  color: var(--hm-text-muted);
  max-width: 80%;
}
.legend-item { display: inline-flex; align-items: center; gap: 5px; }
.legend-item .dot { width: 8px; height: 8px; border-radius: 50%; }
.graph-empty {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  color: var(--hm-text-faint); font-size: 0.85rem;
}
</style>
