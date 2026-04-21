export const BACKEND_BASE_URL = "http://localhost:8000";

export type DetectedField = {
  key: string;
  label: string;
  required: boolean;
  selectorHint?: string;
};

export type ValidationError = {
  field: string;
  message: string;
  parsed_reason?: string;
  parsedReason?: string;
};

export type PortalState = {
  page: string;
  fields: Record<string, { value: unknown; fieldKey?: string; label?: string; required?: boolean }>;
  validationErrors: ValidationError[];
};

export type PageContextPayload = {
  page: string;
  title: string;
  url: string;
  fields: DetectedField[];
  validationErrors: ValidationError[];
  portalState: PortalState;
};

export type FillAction = {
  action_id: string;
  field_id: string;
  field_label: string;
  selector: string;
  value: unknown;
  formatted_value?: string;
  source_fact_id?: string;
  source_document?: string;
  page_type?: string;
  confidence?: number;
  confidence_level?: string;
  requires_approval?: boolean;
};

export type FillPlanPage = {
  page_type: string;
  page_title?: string;
  actions: FillAction[];
};

export type FillPlan = {
  plan_id: string;
  total_actions: number;
  high_confidence_actions?: number;
  low_confidence_actions?: number;
  pages: FillPlanPage[];
};

export type ApprovalItem = {
  approvalId: string;
  description: string;
  status: string;
  kind: string;
  actionIds: string[];
  expiresAt?: string | null;
  proposalId?: string | null;
};

export type ExecutedAction = FillAction & {
  result: string;
  read_after_write?: {
    ok: boolean;
    observed_value: unknown;
    previous_value: unknown;
  };
};

export type ExecutionRecord = {
  execution_id: string;
  execution_kind: string;
  success: boolean;
  ended_at?: string | null;
  results: {
    executed_actions: ExecutedAction[];
    blocked_actions?: FillAction[];
    validation_errors?: ValidationError[];
  };
};

export type ThreadActionsResponse = {
  thread_id: string;
  proposals: Array<Record<string, unknown>>;
  approvals: Array<Record<string, unknown>>;
  executions: ExecutionRecord[];
  pending_approvals: Array<Record<string, unknown>>;
  approved_actions: string[];
  fill_plan: FillPlan | null;
};

export type TaxFactsResponse = {
  thread_id: string;
  facts: Record<string, unknown>;
  fact_evidence: Record<string, Array<Record<string, unknown>>>;
  reconciliation: Record<string, unknown>;
};

type RequestInitWithJson = RequestInit & {
  body?: string;
};

async function request<T>(path: string, init?: RequestInitWithJson): Promise<T> {
  const response = await fetch(`${BACKEND_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`Backend request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function ensureThread(userId: string, threadId?: string | null): Promise<{ thread_id: string; user_id: string }> {
  return request<{ thread_id: string; user_id: string }>("/api/threads/ensure", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, thread_id: threadId ?? null }),
  });
}

export async function fetchThreadActions(threadId: string): Promise<ThreadActionsResponse> {
  return request<ThreadActionsResponse>(`/api/actions/thread/${threadId}`);
}

export async function fetchTaxFacts(threadId: string): Promise<TaxFactsResponse> {
  return request<TaxFactsResponse>(`/api/tax-facts/${threadId}`);
}

export async function createProposal(input: {
  threadId: string;
  pageType?: string | null;
  fieldId?: string | null;
  portalState?: PortalState | null;
}): Promise<{ fill_plan: FillPlan | null; pending_approvals: Array<Record<string, unknown>>; action_proposal_id?: string }> {
  return request("/api/actions/proposal", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      page_type: input.pageType ?? null,
      field_id: input.fieldId ?? null,
      portal_state: input.portalState ?? null,
    }),
  });
}

export async function decideApproval(input: {
  threadId: string;
  approvalId: string;
  approved: boolean;
  rejectionReason?: string;
}): Promise<{ approval_status: string; approved_actions: string[] }> {
  return request("/api/actions/decision", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      approval_id: input.approvalId,
      approved: input.approved,
      consent_acknowledged: true,
      rejection_reason: input.rejectionReason,
    }),
  });
}

export async function recordExecution(input: {
  threadId: string;
  portalStateBefore: PortalState;
  portalStateAfter: PortalState;
  executionResults: ExecutedAction[];
  validationErrors: ValidationError[];
}): Promise<{
  execution_id: string;
  executed_actions: ExecutedAction[];
  validation_summary: { executed: number; blocked: number; readback_failures: number };
  portal_state: PortalState;
}> {
  return request("/api/actions/execute", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      portal_state_before: input.portalStateBefore,
      portal_state_after: input.portalStateAfter,
      execution_results: input.executionResults,
      validation_errors: input.validationErrors,
    }),
  });
}

export async function undoExecution(input: {
  threadId: string;
  executionId: string;
  portalState: PortalState;
}): Promise<{ execution_id: string; portal_state: PortalState }> {
  return request("/api/actions/undo", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      execution_id: input.executionId,
      portal_state: input.portalState,
    }),
  });
}

export function normalizeApprovalItems(payload: ThreadActionsResponse): ApprovalItem[] {
  const approvals = payload.approvals.length > 0 ? payload.approvals : payload.pending_approvals;
  return approvals.map((approval) => ({
    approvalId: String(approval.approval_id ?? approval.approvalId ?? ""),
    description: String(approval.description ?? "Approval required"),
    status: String(approval.status ?? "pending"),
    kind: String(approval.kind ?? approval.approval_type ?? "fill_plan"),
    actionIds: Array.isArray(approval.action_ids) ? (approval.action_ids as string[]) : [],
    expiresAt: (approval.expires_at as string | null | undefined) ?? null,
    proposalId: (approval.proposal_id as string | null | undefined) ?? null,
  }));
}