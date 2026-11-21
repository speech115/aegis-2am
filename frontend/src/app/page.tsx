"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ExternalLink,
  GitPullRequest,
  Lock,
  Mic,
  Play,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  Zap,
} from "lucide-react";
import { DiffViewer } from "@/components/DiffViewer";
import { GraphifyCanvas } from "@/components/GraphifyCanvas";
import type {
  BankState,
  CodeGraph,
  HealthResponse,
  Incident,
  IncidentEvent,
  ScenarioSummary,
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function formatAED(amount: number) {
  return `AED ${amount.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export default function WarRoomPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [bankState, setBankState] = useState<BankState | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selectedScenario, setSelectedScenario] = useState("2am_kyc_replay_ato");
  const [createLivePR, setCreateLivePR] = useState(false);
  const [graph, setGraph] = useState<CodeGraph | null>(null);

  const [incident, setIncident] = useState<Incident | null>(null);
  const [events, setEvents] = useState<IncidentEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);

  const [voiceInput, setVoiceInput] = useState("");
  const [voiceFeedback, setVoiceFeedback] = useState<string | null>(null);
  const [decisionMsg, setDecisionMsg] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const timelineEndRef = useRef<HTMLDivElement | null>(null);

  const loadBootstrap = useCallback(async () => {
    try {
      const [hRes, bRes, sRes, gRes] = await Promise.all([
        fetch(`${API_BASE}/api/health`),
        fetch(`${API_BASE}/api/bank/state`),
        fetch(`${API_BASE}/api/scenarios`),
        fetch(`${API_BASE}/api/graph`),
      ]);
      if (!hRes.ok) throw new Error("Backend unreachable");
      setHealth(await hRes.json());
      setBankState(await bRes.json());
      const sData = await sRes.json();
      setScenarios(sData.scenarios || []);
      setGraph(await gRes.json());
      setBackendError(null);
    } catch {
      setBackendError(
        `Backend not reachable at ${API_BASE}. Run: .venv/bin/uvicorn backend.api.app:app --reload --port 8000`
      );
    }
  }, []);

  useEffect(() => {
    loadBootstrap();
    return () => {
      eventSourceRef.current?.close();
    };
  }, [loadBootstrap]);

  useEffect(() => {
    timelineEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const refreshIncident = useCallback(async (incidentId: string) => {
    const [iRes, bRes] = await Promise.all([
      fetch(`${API_BASE}/api/incidents/${incidentId}`),
      fetch(`${API_BASE}/api/bank/state`),
    ]);
    if (iRes.ok) setIncident(await iRes.json());
    if (bRes.ok) setBankState(await bRes.json());
  }, []);

  const subscribeToIncident = useCallback(
    (incidentId: string) => {
      eventSourceRef.current?.close();
      const es = new EventSource(`${API_BASE}/api/incidents/${incidentId}/stream`);
      eventSourceRef.current = es;

      es.onmessage = async (msg) => {
        try {
          const ev: IncidentEvent = JSON.parse(msg.data);
          if (ev.phase === "heartbeat") return;
          setEvents((prev) => {
            if (prev.some((e) => e.seq === ev.seq)) return prev;
            return [...prev, ev];
          });
          await refreshIncident(incidentId);
          if (ev.phase === "complete") {
            setRunning(false);
            es.close();
          }
        } catch {
          // ignore malformed frame
        }
      };

      es.onerror = async () => {
        es.close();
        await refreshIncident(incidentId);
        setRunning(false);
      };
    },
    [refreshIncident]
  );

  const launchAttack = useCallback(
    async (scenarioOverride?: string) => {
      setRunning(true);
      setEvents([]);
      setDecisionMsg(null);
      try {
        const res = await fetch(`${API_BASE}/api/demo/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            scenario_id: scenarioOverride || selectedScenario,
            create_github_pr: createLivePR,
            step_delay_ms: 420,
          }),
        });
        if (!res.ok) throw new Error("Failed to start simulation");
        const data = await res.json();
        subscribeToIncident(data.incident_id);
      } catch (err) {
        setRunning(false);
        setBackendError(String(err));
      }
    },
    [selectedScenario, createLivePR, subscribeToIncident]
  );

  const resetAll = useCallback(async () => {
    eventSourceRef.current?.close();
    setRunning(false);
    setIncident(null);
    setEvents([]);
    setDecisionMsg(null);
    setVoiceFeedback(null);
    await fetch(`${API_BASE}/api/bank/reset`, { method: "POST" });
    await loadBootstrap();
  }, [loadBootstrap]);

  const handleClientDecision = async (action: "confirm_fraud" | "approve_transfer") => {
    if (!incident) return;
    const res = await fetch(`${API_BASE}/api/incidents/${incident.incident_id}/client-decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    if (res.ok) {
      const data = await res.json();
      setDecisionMsg(data.message);
      await refreshIncident(incident.incident_id);
    }
  };

  const handleVoiceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!voiceInput.trim()) return;
    const res = await fetch(`${API_BASE}/api/voice/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript: voiceInput }),
    });
    if (res.ok) {
      const data = await res.json();
      setVoiceFeedback(data.response_text);
      setVoiceInput("");
      if (data.action_taken === "demo_started" && data.data?.incident_id) {
        setRunning(true);
        setEvents([]);
        subscribeToIncident(data.data.incident_id);
      } else if (data.action_taken === "bank_reset") {
        setIncident(null);
        setEvents([]);
        await loadBootstrap();
      } else if (incident) {
        await refreshIncident(incident.incident_id);
      }
    }
  };

  const activeScenarioObj =
    scenarios.find((s) => s.id === (incident?.scenario_id || selectedScenario)) || scenarios[0];

  const targetAccount =
    bankState?.accounts.find((a) => a.account_id === activeScenarioObj?.target_account_id) ||
    bankState?.accounts[0];

  const shield = incident?.client_shield;
  const immune = incident?.bank_immune;
  const patched = immune?.sandbox_2_verify?.status === "VERIFIED_PASS";

  return (
    <div className="min-h-screen px-4 py-3 text-slate-100">
      {/* === TOP COMMAND BAR === */}
      <header className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#1C2333] bg-[#0D1119]/95 px-4 py-2.5 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500/20 to-emerald-500/20 ring-1 ring-cyan-400/40">
            <ShieldCheck className="h-5 w-5 text-cyan-300" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-semibold tracking-tight text-white">
                AEGIS 2AM
              </h1>
              <span className="rounded bg-rose-500/15 px-1.5 py-0.5 font-mono text-[10px] font-medium text-rose-300 ring-1 ring-rose-500/30">
                <Clock className="mr-1 inline h-3 w-3" />
                {activeScenarioObj?.dubai_time || "02:04 AM GMT+4 (Dubai)"}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Autonomous Banking Immune System · Client Shield + Self-Healing Bank
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectedScenario}
            onChange={(e) => setSelectedScenario(e.target.value)}
            disabled={running}
            className="rounded-lg border border-[#243047] bg-[#090C12] px-2.5 py-1.5 font-mono text-xs text-slate-200 focus:border-cyan-400 focus:outline-none"
          >
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({formatAED(s.amount_aed)})
              </option>
            ))}
          </select>

          <label className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-[#1E293B] bg-[#090C12] px-2.5 py-1.5 text-[11px] text-slate-300">
            <input
              type="checkbox"
              checked={createLivePR}
              onChange={(e) => setCreateLivePR(e.target.checked)}
              className="accent-emerald-500"
            />
            Live GitHub PR
          </label>

          <button
            onClick={() => launchAttack()}
            disabled={running}
            className="inline-flex items-center gap-1.5 rounded-lg bg-rose-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-lg shadow-rose-950/50 transition hover:bg-rose-500 disabled:opacity-50"
          >
            <Play className="h-3.5 w-3.5 fill-current" />
            {running ? "Defending Live…" : "Launch 2:00 AM Attack"}
          </button>

          <button
            onClick={resetAll}
            className="inline-flex items-center gap-1 rounded-lg border border-[#243047] bg-[#090C12] px-2.5 py-1.5 text-xs text-slate-300 transition hover:border-slate-500 hover:text-white"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </button>
        </div>
      </header>

      {/* === SPONSOR STACK + COLLABUTE VOICE BAR === */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#171E2E] bg-[#0B0F17] px-3.5 py-2">
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
            Sponsor Stack:
          </span>
          <span className="inline-flex items-center gap-1 rounded-md bg-cyan-500/10 px-2 py-0.5 font-mono text-cyan-300 ring-1 ring-cyan-500/25">
            Graphify AST · {health?.sponsors.graph_nodes ?? 23} nodes / {health?.sponsors.graph_extracted_edges ?? 35} EXTRACTED
          </span>
          <span
            className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-mono ring-1 ${
              health?.sponsors.daytona_mode === "daytona_cloud"
                ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30"
                : "bg-amber-500/10 text-amber-300 ring-amber-500/25"
            }`}
          >
            Daytona Dual-Sandbox · {health?.sponsors.daytona_mode === "daytona_cloud" ? "CLOUD LIVE" : "LOCAL ISOLATED"}
          </span>
          <span className="inline-flex items-center gap-1 rounded-md bg-indigo-500/10 px-2 py-0.5 font-mono text-indigo-300 ring-1 ring-indigo-500/25">
            Devin · {health?.sponsors.devin_api_configured ? "API ACTIVE" : "SKILL + PR"}
          </span>
          <span className="inline-flex items-center gap-1 rounded-md bg-fuchsia-500/10 px-2 py-0.5 font-mono text-fuchsia-300 ring-1 ring-fuchsia-500/25">
            Collabute Voice Ready
          </span>
        </div>

        {/* Collabute Voice Input */}
        <form onSubmit={handleVoiceSubmit} className="flex items-center gap-1.5">
          <div className="relative flex items-center">
            <Mic className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-fuchsia-400" />
            <input
              type="text"
              value={voiceInput}
              onChange={(e) => setVoiceInput(e.target.value)}
              placeholder='Dictate via Collabute: "Launch 2 AM attack" or "Confirm fraud"'
              className="w-[330px] rounded-lg border border-[#243047] bg-[#07090E] py-1 pl-8 pr-2.5 text-xs text-slate-200 placeholder:text-slate-500 focus:border-fuchsia-400 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            className="rounded-lg border border-fuchsia-500/40 bg-fuchsia-500/15 px-2.5 py-1 text-xs font-medium text-fuchsia-200 hover:bg-fuchsia-500/25"
          >
            Run Voice
          </button>
        </form>
      </div>

      {voiceFeedback && (
        <div className="mb-3 flex items-center justify-between rounded-lg border border-fuchsia-500/30 bg-fuchsia-500/10 px-3 py-1.5 text-xs text-fuchsia-200">
          <span>
            <Mic className="mr-1.5 inline h-3.5 w-3.5" />
            <strong>Collabute Voice Action:</strong> {voiceFeedback}
          </span>
          <button onClick={() => setVoiceFeedback(null)} className="text-[10px] underline">
            dismiss
          </button>
        </div>
      )}

      {backendError && (
        <div className="mb-3 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 font-mono text-xs text-rose-200">
          {backendError}
        </div>
      )}

      {/* === KPI STRIP === */}
      <div className="mb-3 grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        <div className="rounded-xl border border-[#1C2333] bg-[#0D1119] px-3.5 py-2.5">
          <div className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
            Customer Funds Saved (Track 1)
          </div>
          <div className="mt-0.5 font-mono text-xl font-bold text-emerald-400 tabular-nums">
            {incident?.metrics ? formatAED(incident.metrics.client_saved_aed) : "AED 0.00"}
          </div>
          <div className="text-[10.5px] text-slate-500">
            {shield ? `0 AED lost · Escrow ${shield.escrow_hold.hold_id}` : "Standing guard during 00:00–05:00"}
          </div>
        </div>

        <div className="rounded-xl border border-[#1C2333] bg-[#0D1119] px-3.5 py-2.5">
          <div className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
            Detection Latency (MTTD)
          </div>
          <div className="mt-0.5 font-mono text-xl font-bold text-cyan-300 tabular-nums">
            {shield ? `${shield.latency_ms.toFixed(2)} ms` : "—"}
          </div>
          <div className="text-[10.5px] text-slate-500">
            7 explainable Question-Bottleneck signals
          </div>
        </div>

        <div className="rounded-xl border border-[#1C2333] bg-[#0D1119] px-3.5 py-2.5">
          <div className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
            Autonomous Patch & Verify (MTTR)
          </div>
          <div className="mt-0.5 font-mono text-xl font-bold text-white tabular-nums">
            {incident?.metrics ? `${(incident.metrics.mttr_ms / 1000).toFixed(2)} s` : "—"}
          </div>
          <div className="text-[10.5px] text-slate-500">
            Graphify AST + Daytona Dual-Sandbox
          </div>
        </div>

        <div className="rounded-xl border border-[#1C2333] bg-[#0D1119] px-3.5 py-2.5">
          <div className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
            Clean Sandbox #2 Held-Out Proof
          </div>
          <div className="mt-0.5 font-mono text-xl font-bold tabular-nums">
            {immune?.sandbox_2_verify ? (
              <span className="text-emerald-400">
                {immune.sandbox_2_verify.tests_passed}/{immune.sandbox_2_verify.tests_total} PASS
              </span>
            ) : (
              <span className="text-slate-500">Awaiting Run</span>
            )}
          </div>
          <div className="text-[10.5px] text-slate-500">
            {immune?.sandbox_2_verify?.exploit_blocked
              ? "Exploit blocked · 0 regressions"
              : "Unseen legitimate banking test suite"}
          </div>
        </div>
      </div>

      {/* === 3-COLUMN WAR ROOM === */}
      <main className="grid grid-cols-1 gap-3 xl:grid-cols-12">
        {/* === COLUMN 1: TRACK 1 — CLIENT SHIELD («THE LITTLE GUY») === */}
        <section className="flex flex-col gap-3 xl:col-span-4">
          <div className="rounded-xl border border-[#1C2333] bg-[#0D1119] p-3.5">
            <div className="mb-2.5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lock className="h-4 w-4 text-emerald-400" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
                  Track 1 · Client Shield («The Little Guy»)
                </h2>
              </div>
              <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 font-mono text-[10px] text-emerald-300">
                {shield ? shield.decision : "MONITORING"}
              </span>
            </div>

            {/* Sleeping Customer Card */}
            {targetAccount && (
              <div className="mb-3 rounded-lg border border-[#1E293B] bg-[#080B10] p-3">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-xs font-semibold text-white">
                      {targetAccount.holder_name}
                    </div>
                    <div className="font-mono text-[10.5px] text-slate-400">
                      {targetAccount.iban} · {targetAccount.account_id}
                    </div>
                  </div>
                  <span className="rounded-full bg-indigo-500/15 px-2 py-0.5 font-mono text-[10px] text-indigo-300">
                    SLEEPING · 02:00 AM
                  </span>
                </div>
                <div className="mt-2.5 flex items-baseline justify-between border-t border-[#151C2B] pt-2">
                  <div>
                    <div className="text-[10px] text-slate-500">Protected Balance</div>
                    <div className="font-mono text-lg font-bold text-emerald-400 tabular-nums">
                      {formatAED(targetAccount.balance_aed)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] text-slate-500">Escrow Status</div>
                    <div className="font-mono text-xs font-semibold text-amber-300">
                      {shield
                        ? `${shield.escrow_hold.hold_id} · ${shield.escrow_hold.status}`
                        : "NO ACTIVE HOLD"}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 3-Layer Breach Stepper */}
            <div className="mb-3 grid grid-cols-3 gap-1.5">
              {[
                { idx: 0, label: "L1 · Auth" },
                { idx: 1, label: "L2 · KYC" },
                { idx: 2, label: "L3 · Transfer" },
              ].map((step) => {
                const trace = incident?.attack_trace[step.idx];
                const isIntercepted = trace?.status === "INTERCEPTED_BY_AEGIS";
                const isBreached = trace?.status === "BREACHED";
                return (
                  <div
                    key={step.label}
                    className={`rounded-lg border px-2 py-1.5 text-center font-mono text-[10px] ${
                      isIntercepted
                        ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
                        : isBreached
                          ? "border-rose-500/40 bg-rose-500/15 text-rose-300"
                          : "border-[#1C2333] bg-[#080B10] text-slate-500"
                    }`}
                  >
                    <div className="font-semibold">{step.label}</div>
                    <div className="mt-0.5 text-[9px]">
                      {isIntercepted ? "AEGIS SHIELD" : isBreached ? "BREACHED" : "IDLE"}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Question-Bottleneck Risk Engine */}
            <div className="mb-3">
              <div className="mb-1.5 flex items-center justify-between text-[11px]">
                <span className="font-medium text-slate-300">
                  Explainable Question-Bottleneck Risk
                </span>
                <span className="font-mono font-bold text-rose-400 tabular-nums">
                  {shield ? `${Math.round(shield.risk_score * 100)}% RISK` : "0%"}
                </span>
              </div>
              <div className="space-y-1.5">
                {(shield?.questions || []).map((q) => (
                  <div
                    key={q.id}
                    className={`rounded-md border px-2.5 py-1.5 text-[11px] ${
                      q.triggered
                        ? "border-rose-500/30 bg-rose-500/10"
                        : "border-[#161E2E] bg-[#080B10]/60 opacity-55"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className={q.triggered ? "font-medium text-rose-200" : "text-slate-400"}>
                        {q.triggered ? "● " : "○ "}
                        {q.question}
                      </span>
                      <span className="shrink-0 font-mono text-[10px] text-rose-300 tabular-nums">
                        +{Math.round(q.contribution * 100)}%
                      </span>
                    </div>
                    {q.triggered && (
                      <div className="mt-0.5 font-mono text-[10px] text-slate-400">
                        {q.evidence}
                      </div>
                    )}
                  </div>
                ))}
                {!shield && (
                  <div className="rounded-lg border border-dashed border-[#1E293B] py-5 text-center text-xs text-slate-500">
                    Click <strong>Launch 2:00 AM Attack</strong> to trigger real-time scoring
                  </div>
                )}
              </div>
            </div>

            {/* Shadow Honeypot Capture */}
            {shield && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="flex items-center gap-1.5 font-mono text-[11px] font-semibold text-amber-300">
                    <ShieldAlert className="h-3.5 w-3.5" />
                    SHADOW HONEYPOT DECOY ACTIVE
                  </span>
                  <span className="font-mono text-[10px] text-amber-200">
                    {shield.honeypot_capture.decoy_tx_id}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-1.5 font-mono text-[10.5px] text-slate-300">
                  <div>
                    <span className="text-slate-500">Attacker IP: </span>
                    {shield.honeypot_capture.attacker_ip} ({shield.honeypot_capture.attacker_country})
                  </div>
                  <div>
                    <span className="text-slate-500">Device: </span>
                    {shield.honeypot_capture.device_fp}
                  </div>
                  <div className="col-span-2">
                    <span className="text-slate-500">Mule IBAN: </span>
                    <span className="text-rose-300">{shield.honeypot_capture.mule_iban}</span>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {shield.honeypot_capture.ttp_tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded bg-amber-500/15 px-1.5 py-0.5 font-mono text-[9.5px] text-amber-200"
                    >
                      {tag}
                    </span>
                  ))}
                </div>

                {/* Morning User Actions */}
                <div className="mt-2.5 flex items-center gap-2 border-t border-amber-500/20 pt-2.5">
                  <button
                    onClick={() => handleClientDecision("confirm_fraud")}
                    disabled={shield.escrow_hold.status !== "HELD"}
                    className="flex-1 rounded-md bg-rose-600/90 px-2 py-1.5 text-[11px] font-semibold text-white hover:bg-rose-500 disabled:opacity-40"
                  >
                    8:00 AM: Confirm Fraud & Blacklist
                  </button>
                  <button
                    onClick={() => handleClientDecision("approve_transfer")}
                    disabled={shield.escrow_hold.status !== "HELD"}
                    className="rounded-md border border-slate-700 bg-[#0B0F17] px-2.5 py-1.5 text-[11px] text-slate-300 hover:border-slate-500 disabled:opacity-40"
                  >
                    Release Escrow
                  </button>
                </div>
                {decisionMsg && (
                  <div className="mt-2 rounded bg-emerald-500/15 px-2 py-1 text-[11px] text-emerald-200">
                    {decisionMsg}
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        {/* === COLUMN 2: GRAPHIFY AST + LIVE SSE TIMELINE === */}
        <section className="flex flex-col gap-3 xl:col-span-4">
          <div className="rounded-xl border border-[#1C2333] bg-[#0D1119] p-3.5">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-cyan-400" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
                  Graphify Code Graph & Blast Radius
                </h2>
              </div>
              {immune?.graphify_blast_radius && (
                <span className="font-mono text-[10px] text-cyan-300">
                  {immune.graphify_blast_radius.root_file}:{immune.graphify_blast_radius.root_line}
                </span>
              )}
            </div>

            <GraphifyCanvas
              graph={graph}
              rootNodeId={immune?.graphify_blast_radius?.root_node_id}
              affectedNodeIds={immune?.graphify_blast_radius?.affected_node_ids}
              patched={patched}
            />

            {immune?.graphify_blast_radius && (
              <div className="mt-2 rounded-lg border border-cyan-500/25 bg-cyan-500/5 px-2.5 py-2 text-[11px] text-cyan-100">
                {immune.graphify_blast_radius.summary}
              </div>
            )}
          </div>

          {/* Live SSE Telemetry Feed */}
          <div className="flex flex-1 flex-col rounded-xl border border-[#1C2333] bg-[#0D1119] p-3.5">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-cyan-400" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
                  Real-Time Autonomous Defense Stream
                </h2>
              </div>
              <span className="font-mono text-[10px] text-slate-400 tabular-nums">
                {events.length} events
              </span>
            </div>

            <div className="max-h-[340px] flex-1 space-y-1.5 overflow-y-auto pr-1">
              {events.length === 0 ? (
                <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-[#1E293B] text-xs text-slate-500">
                  SSE telemetry channel standing by…
                </div>
              ) : (
                events.map((ev) => {
                  const badgeColor =
                    ev.severity === "critical"
                      ? "bg-rose-500/15 text-rose-300 ring-rose-500/30"
                      : ev.severity === "warning"
                        ? "bg-amber-500/15 text-amber-300 ring-amber-500/30"
                        : ev.severity === "success"
                          ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30"
                          : "bg-cyan-500/15 text-cyan-300 ring-cyan-500/30";
                  return (
                    <div
                      key={ev.seq}
                      className="rounded-lg border border-[#161E2E] bg-[#080B10] px-2.5 py-1.5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`rounded px-1.5 py-0.5 font-mono text-[9.5px] uppercase ring-1 ${badgeColor}`}
                          >
                            {ev.phase}
                          </span>
                          <span className="text-[11.5px] font-medium text-slate-100">
                            {ev.title}
                          </span>
                        </div>
                        <span className="font-mono text-[9.5px] text-slate-500 tabular-nums">
                          #{String(ev.seq).padStart(2, "0")}
                        </span>
                      </div>
                      <p className="mt-0.5 font-mono text-[10.5px] text-slate-400">
                        {ev.detail}
                      </p>
                    </div>
                  );
                })
              )}
              <div ref={timelineEndRef} />
            </div>
          </div>
        </section>

        {/* === COLUMN 3: TRACK 2 — BANK IMMUNE SYSTEM («THE BIG GUY») === */}
        <section className="flex flex-col gap-3 xl:col-span-4">
          <div className="rounded-xl border border-[#1C2333] bg-[#0D1119] p-3.5">
            <div className="mb-2.5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal className="h-4 w-4 text-amber-400" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
                  Track 2 · Bank Immune System («The Big Guy»)
                </h2>
              </div>
              <span className="font-mono text-[10px] text-slate-400">
                DUAL-SANDBOX PROOF
              </span>
            </div>

            {/* Sandbox #1: Exploit Reproduction */}
            <div className="mb-3 rounded-lg border border-[#1C2333] bg-[#080B10] p-2.5">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="flex items-center gap-1.5 font-mono text-[11px] font-semibold text-slate-200">
                  <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />
                  Daytona Sandbox #1 · Exploit Repro
                </span>
                {immune?.sandbox_1_exploit ? (
                  <span className="rounded bg-rose-500/20 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-rose-300">
                    🔴 {immune.sandbox_1_exploit.status} · {immune.sandbox_1_exploit.duration_ms}ms
                  </span>
                ) : (
                  <span className="font-mono text-[10px] text-slate-500">IDLE</span>
                )}
              </div>
              <pre className="max-h-[96px] overflow-auto rounded bg-[#05070B] p-2 font-mono text-[10px] leading-relaxed text-rose-200/90">
                {immune?.sandbox_1_exploit
                  ? `$ sandbox=${immune.sandbox_1_exploit.sandbox_id} (${immune.sandbox_1_exploit.mode})\n${immune.sandbox_1_exploit.logs}`
                  : "// Spins up ephemeral sandbox #1 to prove exploitability against unpatched bank core"}
              </pre>
            </div>

            {/* Autonomous Patch Diff */}
            <div className="mb-3">
              {immune?.patch ? (
                <>
                  <div className="mb-1.5 flex items-center justify-between text-[11px]">
                    <span className="font-medium text-slate-200">
                      Autonomous Patch ({immune.patch.generator})
                    </span>
                    {immune.patch.devin_session_url && (
                      <a
                        href={immune.patch.devin_session_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 font-mono text-[10px] text-indigo-300 underline"
                      >
                        Devin Session <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                  <p className="mb-1.5 text-[11px] text-slate-400">
                    {immune.patch.explanation}
                  </p>
                  <DiffViewer diff={immune.patch.diff} filePath={immune.patch.file_path} />
                </>
              ) : (
                <div className="rounded-lg border border-dashed border-[#1E293B] py-6 text-center font-mono text-[11px] text-slate-500">
                  Unified security patch diff will appear here
                </div>
              )}
            </div>

            {/* Sandbox #2: Clean Held-Out Verification */}
            <div className="mb-3 rounded-lg border border-[#1C2333] bg-[#080B10] p-2.5">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="flex items-center gap-1.5 font-mono text-[11px] font-semibold text-slate-200">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  Daytona Sandbox #2 · Clean Held-Out Verify
                </span>
                {immune?.sandbox_2_verify ? (
                  <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-emerald-300">
                    🟢 {immune.sandbox_2_verify.tests_passed}/{immune.sandbox_2_verify.tests_total} PASS ·{" "}
                    {immune.sandbox_2_verify.duration_ms}ms
                  </span>
                ) : (
                  <span className="font-mono text-[10px] text-slate-500">IDLE</span>
                )}
              </div>
              <pre className="max-h-[125px] overflow-auto rounded bg-[#05070B] p-2 font-mono text-[10px] leading-relaxed text-emerald-200/90">
                {immune?.sandbox_2_verify
                  ? `$ sandbox=${immune.sandbox_2_verify.sandbox_id} (${immune.sandbox_2_verify.mode})\n${immune.sandbox_2_verify.logs}`
                  : "// Spins up brand-new sandbox #2 with unseen held-out banking regression suite"}
              </pre>
            </div>

            {/* CISO Morning GitHub PR Card */}
            {immune?.pr && (
              <div className="rounded-lg border border-emerald-500/35 bg-emerald-500/10 p-3">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-200">
                    <GitPullRequest className="h-4 w-4 text-emerald-400" />
                    CISO Morning Pull Request ({immune.pr.status.toUpperCase()})
                  </span>
                  <a
                    href={immune.pr.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] text-emerald-200 hover:bg-emerald-500/30"
                  >
                    Open on GitHub <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
                <div className="mt-1 text-[11.5px] font-medium text-white">
                  {immune.pr.title}
                </div>
                <div className="mt-0.5 font-mono text-[10px] text-emerald-300/80">
                  branch: {immune.pr.branch} · repo: {immune.pr.repo}
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
