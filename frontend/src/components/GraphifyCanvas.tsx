"use client";

import React, { useMemo, useState } from "react";
import type { CodeGraph, GraphNode } from "@/lib/types";

interface Props {
  graph: CodeGraph | null;
  rootNodeId?: string | null;
  affectedNodeIds?: string[];
  patched?: boolean;
}

const LAYERS = [
  { id: "auth", title: "L1 · Auth", x: 78 },
  { id: "kyc", title: "L2 · KYC", x: 222 },
  { id: "transfers", title: "L3 · Transfer", x: 368 },
  { id: "ledger", title: "Core · Ledger", x: 514 },
];

export function GraphifyCanvas({
  graph,
  rootNodeId,
  affectedNodeIds = [],
  patched = false,
}: Props) {
  const [hovered, setHovered] = useState<GraphNode | null>(null);
  const affectedSet = useMemo(() => new Set(affectedNodeIds), [affectedNodeIds]);

  const layout = useMemo(() => {
    if (!graph) return { positions: new Map<string, { x: number; y: number }>(), visibleNodes: [] as GraphNode[] };

    // Keep graph sharp and scannable: show modules + functions + key classes
    const visibleNodes = graph.nodes.filter(
      (n) => n.kind === "function" || n.kind === "module" || n.label === "KYCService" || n.label === "BankLedger"
    );

    const byLayer: Record<string, GraphNode[]> = { auth: [], kyc: [], transfers: [], ledger: [] };
    for (const n of visibleNodes) {
      const bucket = byLayer[n.layer] ? n.layer : "ledger";
      byLayer[bucket].push(n);
    }

    const positions = new Map<string, { x: number; y: number }>();
    for (const col of LAYERS) {
      const items = byLayer[col.id] || [];
      // Put module at top, then functions
      items.sort((a, b) => (a.kind === "module" ? -1 : b.kind === "module" ? 1 : a.line - b.line));
      const count = Math.max(items.length, 1);
      const top = 46;
      const span = 228;
      items.forEach((node, idx) => {
        const y = count === 1 ? top + span / 2 : top + (idx * span) / (count - 1);
        positions.set(node.id, { x: col.x, y });
      });
    }
    return { positions, visibleNodes };
  }, [graph]);

  if (!graph) {
    return (
      <div className="flex h-[290px] items-center justify-center rounded-lg border border-[#1C2333] bg-[#090C12] text-xs text-slate-500">
        Loading Graphify AST knowledge graph…
      </div>
    );
  }

  return (
    <div className="relative rounded-lg border border-[#1C2333] bg-[#090C12] p-2">
      <div className="mb-1.5 flex items-center justify-between px-1 text-[11px]">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded bg-cyan-500/10 px-1.5 py-0.5 font-mono text-[10px] text-cyan-300 ring-1 ring-cyan-500/30">
            GRAPHIFY AST
          </span>
          <span className="font-mono text-slate-400 tabular-nums">
            {graph.stats.node_count} nodes · {graph.stats.extracted_edges} EXTRACTED edges
          </span>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-slate-400">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-rose-500" /> Root CVE
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-amber-400" /> Blast Radius
          </span>
          {patched && (
            <span className="flex items-center gap-1 text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400" /> Patched
            </span>
          )}
        </div>
      </div>

      <svg viewBox="0 0 592 300" className="h-[265px] w-full select-none">
        {/* Layer column headers */}
        {LAYERS.map((col) => (
          <g key={col.id}>
            <line
              x1={col.x}
              y1={24}
              x2={col.x}
              y2={290}
              stroke="#151C2B"
              strokeDasharray="3 4"
            />
            <text
              x={col.x}
              y={16}
              textAnchor="middle"
              className="fill-slate-500 font-mono text-[9.5px] uppercase tracking-wider"
            >
              {col.title}
            </text>
          </g>
        ))}

        {/* Edges */}
        {graph.edges.map((edge, idx) => {
          const s = layout.positions.get(edge.source);
          const t = layout.positions.get(edge.target);
          if (!s || !t) return null;

          const isHot = affectedSet.has(edge.source) && affectedSet.has(edge.target);
          const isCall = edge.relation === "CALLS";
          const mx = (s.x + t.x) / 2;
          const my = (s.y + t.y) / 2 + (s.x === t.x ? 0 : -14);

          const stroke = isHot
            ? patched
              ? "#10B981"
              : "#F43F5E"
            : isCall
              ? "#2563EB55"
              : "#1E293B";

          return (
            <path
              key={`${edge.source}-${edge.target}-${idx}`}
              d={`M ${s.x} ${s.y} Q ${mx} ${my} ${t.x} ${t.y}`}
              fill="none"
              stroke={stroke}
              strokeWidth={isHot ? 1.8 : isCall ? 1.15 : 0.8}
              strokeDasharray={edge.relation === "IMPORTS" ? "3 3" : undefined}
              opacity={isHot ? 0.95 : 0.65}
            />
          );
        })}

        {/* Nodes */}
        {layout.visibleNodes.map((node) => {
          const pos = layout.positions.get(node.id);
          if (!pos) return null;

          const isRoot = node.id === rootNodeId;
          const isAffected = affectedSet.has(node.id);
          const isModule = node.kind === "module";

          const fill = isRoot
            ? patched
              ? "#064E3B"
              : "#4C0519"
            : isAffected
              ? patched
                ? "#052E2B"
                : "#451A03"
              : isModule
                ? "#0F172A"
                : "#111827";

          const stroke = isRoot
            ? patched
              ? "#10B981"
              : "#F43F5E"
            : isAffected
              ? patched
                ? "#34D399"
                : "#F59E0B"
              : "#28354D";

          const textFill = isRoot
            ? patched
              ? "#6EE7B7"
              : "#FDA4AF"
            : isAffected
              ? "#FDE68A"
              : "#CBD5E1";

          const width = Math.min(122, Math.max(72, node.label.length * 6.2 + 16));

          return (
            <g
              key={node.id}
              transform={`translate(${pos.x}, ${pos.y})`}
              className="cursor-pointer"
              onMouseEnter={() => setHovered(node)}
              onMouseLeave={() => setHovered(null)}
            >
              {isRoot && !patched && (
                <rect
                  x={-width / 2 - 4}
                  y={-15}
                  width={width + 8}
                  height={30}
                  rx={8}
                  fill="none"
                  stroke="#F43F5E"
                  strokeWidth={1.5}
                  opacity={0.7}
                  className="pulse-ring"
                />
              )}
              <rect
                x={-width / 2}
                y={-11}
                width={width}
                height={22}
                rx={isModule ? 4 : 11}
                fill={fill}
                stroke={stroke}
                strokeWidth={isRoot ? 1.8 : 1}
              />
              <text
                x={0}
                y={3.5}
                textAnchor="middle"
                fill={textFill}
                className="font-mono text-[9.5px] font-medium"
              >
                {node.label.length > 18 ? node.label.slice(0, 17) + "…" : node.label}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Bottom hover / legend bar */}
      <div className="mt-1 flex items-center justify-between border-t border-[#161E2E] px-1 pt-1.5 font-mono text-[10px] text-slate-400">
        {hovered ? (
          <span>
            <span className="text-cyan-300">{hovered.label}</span> · {hovered.file}:{hovered.line} ({hovered.kind})
          </span>
        ) : (
          <span>Hover any symbol to inspect AST source location · 100% deterministic tree-sitter/AST edges</span>
        )}
        <span className="text-slate-500">graphify-out/graph.json</span>
      </div>
    </div>
  );
}
