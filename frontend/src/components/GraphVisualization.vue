<template>
  <div class="graph-visualization">
    <div class="viz-container" ref="containerRef">
      <svg ref="svgRef" :width="width" :height="height"></svg>
    </div>

    <div class="legend">
      <div class="legend-item">
        <div class="node-dot selected"></div>
        <span>Main Clause</span>
      </div>
      <div class="legend-item">
        <div class="node-dot reference"></div>
        <span>Referenced Clause</span>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch } from 'vue'
import * as d3 from 'd3'

export default {
  name: 'GraphVisualization',
  props: {
    sources: {
      type: Array,
      required: true
    },
    selectedArticle: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    const svgRef = ref(null)
    const containerRef = ref(null)
    const width = ref(800)
    const height = ref(300)

    const drawGraph = () => {
      if (!svgRef.value) return

      const svg = d3.select(svgRef.value)
      svg.selectAll('*').remove()

      // Adjust width based on container
      if (containerRef.value) {
        width.value = containerRef.value.clientWidth
      }

      // Build hierarchy data
      const root = {
        name: props.selectedArticle.id,
        type: 'selected',
        title: props.selectedArticle.title,
        children: []
      }

      props.sources.forEach((source, index) => {
        if (index > 0) {
          root.children.push({
            name: source.id,
            type: 'reference',
            title: source.title || ''
          })
        }
      })

      const treeLayout = d3.tree().size([width.value - 100, height.value - 100])
      const hierarchyData = d3.hierarchy(root)
      const treeData = treeLayout(hierarchyData)

      const g = svg.append('g')
        .attr('transform', 'translate(50, 50)')

      // Draw links
      g.selectAll('.link')
        .data(treeData.links())
        .enter()
        .append('path')
        .attr('class', 'link')
        .attr('d', d3.linkVertical().x(d => d.x).y(d => d.y))
        .attr('fill', 'none')
        .attr('stroke', '#E5E7EB')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '4')

      // Draw nodes
      const nodes = g.selectAll('.node')
        .data(treeData.descendants())
        .enter()
        .append('g')
        .attr('class', 'node')
        .attr('transform', d => `translate(${d.x}, ${d.y})`)

      // Node circles with shadow
      nodes.append('circle')
        .attr('r', 20)
        .attr('fill', 'white')
        .attr('stroke', 'none')
        .attr('filter', 'url(#drop-shadow)')

      // Node gradient circles
      nodes.append('circle')
        .attr('r', 16)
        .attr('class', d => d.data.type)
        
      // Node icons
      nodes.append('text')
        .attr('dy', 5)
        .attr('text-anchor', 'middle')
        .attr('font-size', '14px')
        .text(d => d.data.type === 'selected' ? '📄' : '🔗')

      // Labels
      nodes.append('text')
        .attr('dy', 35)
        .attr('text-anchor', 'middle')
        .attr('font-size', '12px')
        .attr('font-weight', '700')
        .attr('fill', '#1F2937')
        .text(d => d.data.name)

      nodes.append('text')
        .attr('dy', 50)
        .attr('text-anchor', 'middle')
        .attr('font-size', '10px')
        .attr('fill', '#6B7280')
        .text(d => d.data.title ? (d.data.title.length > 12 ? d.data.title.substring(0, 12) + '...' : d.data.title) : '')

      // Add shadow filter
      const defs = svg.append('defs')
      const filter = defs.append('filter')
        .attr('id', 'drop-shadow')
        .attr('height', '130%')
      
      filter.append('feGaussianBlur')
        .attr('in', 'SourceAlpha')
        .attr('stdDeviation', 3)
      
      filter.append('feOffset')
        .attr('dx', 0)
        .attr('dy', 2)
        .attr('result', 'offsetblur')
      
      const feMerge = filter.append('feMerge')
      feMerge.append('feMergeNode')
      feMerge.append('feMergeNode')
        .attr('in', 'SourceGraphic')
    }

    onMounted(() => {
      drawGraph()
      window.addEventListener('resize', drawGraph)
    })

    watch(() => props.sources, drawGraph, { deep: true })

    return { svgRef, containerRef, width, height }
  }
}
</script>

<style scoped>
.graph-visualization {
  width: 100%;
  overflow: hidden;
}

.viz-container {
  width: 100%;
  display: flex;
  justify-content: center;
  padding: 1rem 0;
}

.node-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.node-dot.selected {
  background: #4F46E5;
}

.node-dot.reference {
  background: #10B981;
}

:deep(.node circle.selected) {
  fill: #4F46E5;
}

:deep(.node circle.reference) {
  fill: #10B981;
}

.legend {
  display: flex;
  justify-content: center;
  gap: 2rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #F3F4F6;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: #4B5563;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
</style>
