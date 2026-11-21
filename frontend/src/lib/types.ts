export interface HealthResponse {
  status: string;
  service: string;
  sponsors: {
    daytona_mode: "daytona_cloud" | "local_sandbox";
    graphify_ready: boolean;
    graphify_cli_detected: boolean;
    graph_nodes: number;
    graph_extracted_edges: number;
    devin_api_configured: boolean;
    github_pr_ready: boolean;
    collabute_voice_endpoint: string;
  };
}

export interface ScenarioSummary {
  id: string;
  name: string;
  subtitle: string;
  dubai_time: string;
  target_account_id: string;
  amount_aed: number;
  beneficiary_iban: string;
  vulnerable_file: string;
  vulnerable_symbol: string;
  cwe: string;
  ttp_tags: string[];
}

export interface BankAccount {
  account_id: string;
  holder_name: string;
  iban: string;
  balance_aed: number;
  daily_limit_aed: number;
  daily_spent_aed: number;
  frozen: boolean;
  trusted_device_fp: string;
}

export interface BankState {
  bank_name: string;
  clock_dubai: string;
  accounts: BankAccount[];
  escrow_holds: Array<{
    hold_id: string;
    account_id: string;
    amount_aed: number;
    beneficiary_iban: string;
    incident_id: string;
    status: string;
  }>;
  shadow_transfers: Array<{
    tx_id: string;
    account_id: string;
    beneficiary_iban: string;
    amount_aed: number;
    status: string;
  }>;
  blocked_ibans: string[];
}

export interface GraphNode {
  id: string;
  label: string;
  kind: "module" | "class" | "function";
  layer: "auth" | "kyc" | "transfers" | "ledger" | string;
  file: string;
  line: number;
  hop_distance?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: "DEFINES" | "CALLS" | "IMPORTS" | string;
  confidence: "EXTRACTED" | "INFERRED" | "AMBIGUOUS" | string;
}

export interface CodeGraph {
  engine: string;
  cli_detected: boolean;
  stats: {
    node_count: number;
    edge_count: number;
    extracted_edges: number;
  };
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface IncidentEvent {
  seq: number;
  timestamp: string;
  phase: string;
  severity: "info" | "warning" | "critical" | "success";
  title: string;
  detail: string;
  payload?: Record<string, unknown>;
}

export interface RiskQuestion {
  id: string;
  question: string;
  triggered: boolean;
  weight: number;
  contribution: number;
  evidence: string;
}

export interface Incident {
  incident_id: string;
  scenario_id: string;
  scenario: ScenarioSummary;
  status: "running" | "remediated" | "failed";
  created_at: string;
  attack_trace: Array<{
    layer: string;
    status: string;
    detail: string;
  }>;
  client_shield: {
    risk_score: number;
    decision: string;
    latency_ms: number;
    summary: string;
    questions: RiskQuestion[];
    account_balance_intact_aed: number;
    escrow_hold: {
      hold_id: string;
      account_id: string;
      amount_aed: number;
      beneficiary_iban: string;
      status: string;
    };
    honeypot_capture: {
      decoy_tx_id: string;
      attacker_ip: string;
      attacker_country: string;
      device_fp: string;
      mule_iban: string;
      replayed_token: string | null;
      ttp_tags: string[];
      attacker_response_seen: Record<string, unknown>;
    };
  } | null;
  bank_immune: {
    graphify_blast_radius?: {
      root_symbol: string;
      root_node_id: string;
      root_file: string;
      root_line: number;
      confidence: string;
      affected_node_ids: string[];
      affected_files: string[];
      affected_layers: string[];
      summary: string;
    };
    sandbox_1_exploit?: {
      mode: string;
      sandbox_id: string;
      status: string;
      exit_code: number;
      logs: string;
      duration_ms: number;
      exploit_reproduced: boolean;
    };
    patch?: {
      file_path: string;
      diff: string;
      explanation: string;
      regression_test_name: string;
      generator: string;
      devin_session_url?: string | null;
    };
    sandbox_2_verify?: {
      mode: string;
      sandbox_id: string;
      status: string;
      exit_code: number;
      logs: string;
      duration_ms: number;
      exploit_blocked: boolean;
      held_out_passed: boolean;
      tests_passed: number;
      tests_total: number;
    };
    pr?: {
      branch: string;
      title: string;
      repo: string;
      url: string;
      status: "created" | "preview";
      pr_error?: string;
    };
  };
  metrics: {
    mttd_ms: number;
    mttr_ms: number;
    client_saved_aed: number;
    false_positive_rate: number;
    sandbox_mode: string;
  } | null;
  events: IncidentEvent[];
}
