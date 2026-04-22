export type ClientReviewRow = {
  threadId: string;
  pan?: string;
  name?: string;
  itrType?: string;
  assessmentYear?: string;
  canSubmit?: boolean;
  canAutofill?: boolean;
  blockingIssues: string[];
  mismatchCount?: number;
  pendingApprovalCount?: number;
  pendingSignoffCount?: number;
  accessRole?: string;
  supportMode?: string;
  lastExecution?: { success?: boolean; ended_at?: string | null } | null;
};

export type DashboardOperationsSnapshot = {
  operations?: {
    replay?: {
      totals?: {
        snapshots?: number;
        runs?: number;
        successful_runs?: number;
        failed_runs?: number;
        success_rate?: number;
      };
      top_selector_failures?: Array<{ selector: string; count: number }>;
    };
    drift?: {
      total_events?: number;
      recovery_rate?: number;
      by_severity?: Record<string, number>;
    };
    agent_observability?: {
      total_events?: number;
      average_duration_ms?: number;
      by_status?: Record<string, number>;
      recent_failures?: Array<{ thread_id?: string; node_name?: string }>;
    };
    runtime_health?: {
      status?: string;
      checks?: Array<{ name: string; status: string; detail?: string }>;
    };
    tracing?: {
      backend?: string;
      exporter?: string;
      ai_provider?: string;
    };
  };
};

export type CADashboardModel = {
  overview: {
    totalClients: number;
    readyToSubmit: number;
    blocked: number;
    guidedReview: number;
    caHandoff: number;
  };
  queues: {
    pendingApprovals: number;
    pendingSignoffs: number;
    mismatchReview: number;
  };
  operations: {
    replaySuccessRate: number;
    driftEvents: number;
    tracingBackend: string;
    aiProvider: string;
    alerts: string[];
  };
  clients: Array<{
    threadId: string;
    name: string;
    risk: "low" | "medium" | "high";
    status: string;
    recommendedAction: string;
  }>;
};

function statusLabel(row: ClientReviewRow): string {
  if (row.supportMode === "ca-handoff") return "CA handoff";
  if (row.supportMode === "guided-checklist") return "Guided review";
  if (!row.canSubmit) return "Blocked";
  return "Ready";
}

function recommendedAction(row: ClientReviewRow): string {
  if (row.supportMode === "ca-handoff") return "Prepare reviewer handoff and pause autofill";
  if ((row.pendingSignoffCount ?? 0) > 0) return "Chase reviewer sign-off";
  if ((row.pendingApprovalCount ?? 0) > 0) return "Review pending approvals";
  if ((row.mismatchCount ?? 0) > 0) return "Resolve mismatches before submission";
  if (!row.canSubmit) return "Review blockers and submission summary";
  return "Proceed with assisted filing";
}

export function summarizeRisk(row: ClientReviewRow): "low" | "medium" | "high" {
  if ((row.blockingIssues || []).length > 0 || row.supportMode === "ca-handoff") {
    return "high";
  }
  if (!row.canSubmit || (row.mismatchCount ?? 0) > 0 || (row.pendingApprovalCount ?? 0) > 0) {
    return "medium";
  }
  return "low";
}

export function buildCADashboardModel(
  clients: ClientReviewRow[],
  snapshot: DashboardOperationsSnapshot = {}
): CADashboardModel {
  const readyToSubmit = clients.filter((row) => row.canSubmit).length;
  const guidedReview = clients.filter((row) => row.supportMode === "guided-checklist").length;
  const caHandoff = clients.filter((row) => row.supportMode === "ca-handoff").length;
  const blocked = clients.length - readyToSubmit;

  const alerts: string[] = [];
  const replaySuccessRate = Number(snapshot.operations?.replay?.totals?.success_rate ?? 1);
  const driftEvents = Number(snapshot.operations?.drift?.total_events ?? 0);
  const tracingBackend = snapshot.operations?.tracing?.backend ?? "fallback";
  const aiProvider = snapshot.operations?.tracing?.ai_provider ?? "not_configured";

  if (replaySuccessRate < 0.95) {
    alerts.push(`Replay success rate is below target at ${(replaySuccessRate * 100).toFixed(1)}%`);
  }
  if (driftEvents > 0) {
    alerts.push(`${driftEvents} selector-drift events need adapter review`);
  }
  if (snapshot.operations?.agent_observability?.recent_failures?.length) {
    alerts.push("Recent agent-node failures were recorded in the observability stream");
  }
  if (snapshot.operations?.runtime_health?.status && snapshot.operations.runtime_health.status !== "ok") {
    alerts.push(`Runtime health is ${snapshot.operations.runtime_health.status}`);
  }

  return {
    overview: {
      totalClients: clients.length,
      readyToSubmit,
      blocked,
      guidedReview,
      caHandoff,
    },
    queues: {
      pendingApprovals: clients.reduce((sum, row) => sum + Number(row.pendingApprovalCount ?? 0), 0),
      pendingSignoffs: clients.reduce((sum, row) => sum + Number(row.pendingSignoffCount ?? 0), 0),
      mismatchReview: clients.reduce((sum, row) => sum + Number(row.mismatchCount ?? 0), 0),
    },
    operations: {
      replaySuccessRate,
      driftEvents,
      tracingBackend,
      aiProvider,
      alerts,
    },
    clients: clients.map((row) => ({
      threadId: row.threadId,
      name: row.name || row.pan || row.threadId,
      risk: summarizeRisk(row),
      status: statusLabel(row),
      recommendedAction: recommendedAction(row),
    })),
  };
}
