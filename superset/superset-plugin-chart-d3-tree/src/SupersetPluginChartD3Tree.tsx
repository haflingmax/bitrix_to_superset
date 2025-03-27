import React, { useEffect, useRef } from 'react';
import { styled } from '@superset-ui/core';
import { SupersetPluginChartD3TreeProps } from './types';
import * as d3 from 'd3';

const Styles = styled.div`
  .node circle {
    fill: #69b3a2;
    stroke: #fff;
    stroke-width: 1.5px;
  }
  .node text {
    font-size: 12px;
  }
  .link {
    fill: none;
    stroke: #ccc;
    stroke-width: 2px;
  }
`;

export default function SupersetPluginChartD3Tree(props: SupersetPluginChartD3TreeProps) {
  const { data, height, width } = props;
  const rootRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!rootRef.current || !data || data.length === 0) return;

    const svg = d3.select(rootRef.current)
      .attr('width', width)
      .attr('height', height);
    svg.selectAll('*').remove();

    const stratify = d3.stratify()
      .id((d: any) => String(d.id))
      .parentId((d: any) => d.parent_id ? String(d.parent_id) : null);
    const treeData = stratify(data);

    const treeLayout = d3.tree().size([height - 50, width - 50]);
    const rootNode = d3.hierarchy(treeData);
    treeLayout(rootNode);

    const g = svg.append('g').attr('transform', 'translate(25, 25)');

    g.selectAll('.link')
      .data(rootNode.links())
      .enter()
      .append('path')
      .attr('class', 'link')
      .attr('d', d3.linkHorizontal()
        .x((d: any) => d.y)
        .y((d: any) => d.x));

    const node = g.selectAll('.node')
      .data(rootNode.descendants())
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', (d: any) => `translate(${d.y},${d.x})`);

    node.append('circle')
      .attr('r', 5);

    node.append('text')
      .attr('dy', '.35em')
      .attr('x', (d: any) => (d.children ? -10 : 10))
      .attr('text-anchor', (d: any) => (d.children ? 'end' : 'start'))
      .text((d: any) => d.data.data.title);

  }, [data, height, width]);

  return (
    <Styles>
      <svg ref={rootRef} />
    </Styles>
  );
}