"use client";

import React from "react";

export function DiffViewer({ diff, filePath }: { diff: string; filePath: string }) {
  const lines = diff.split("\n");
  return (
    <div className="overflow-hidden rounded-lg border border-[#1C2333] bg-[#080B10]">
      <div className="flex items-center justify-between border-b border-[#1C2333] bg-[#0E131D] px-2.5 py-1.5 font-mono text-[10.5px]">
        <span className="text-slate-300">{filePath}</span>
        <span className="text-emerald-400">AUTONOMOUS SECURITY PATCH</span>
      </div>
      <div className="max-h-[168px] overflow-auto p-2 font-mono text-[10.5px] leading-relaxed">
        {lines.map((line, i) => {
          let cls = "text-slate-400";
          let bg = "";
          if (line.startsWith("+++") || line.startsWith("---")) {
            cls = "text-slate-500 font-semibold";
          } else if (line.startsWith("@@")) {
            cls = "text-cyan-400";
            bg = "bg-cyan-500/5";
          } else if (line.startsWith("+")) {
            cls = "text-emerald-300";
            bg = "bg-emerald-500/10";
          } else if (line.startsWith("-")) {
            cls = "text-rose-300";
            bg = "bg-rose-500/10";
          }
          return (
            <div key={i} className={`whitespace-pre px-1.5 ${bg} ${cls}`}>
              {line || " "}
            </div>
          );
        })}
      </div>
    </div>
  );
}
