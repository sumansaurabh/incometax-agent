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

export type SubmissionSummaryData = {
  assessment_year: string;
  itr_type: string;
  regime: string;
  gross_total_income: number;
  total_deductions: number;
  taxable_income: number;
  net_tax_liability: number;
  total_tax_paid: number;
  tax_payable: number;
  refund_due: number;
  mismatch_count: number;
  can_submit: boolean;
  blocking_issues: string[];
};

export type FilingArtifacts = {
  artifact_id: string;
  ack_no?: string | null;
  itr_v_storage_uri?: string | null;
  json_export_uri?: string | null;
  evidence_bundle_uri?: string | null;
  summary_storage_uri?: string | null;
  filed_at?: string | null;
  artifact_manifest?: Record<string, unknown>;
};

export type EverificationRecord = {
  record_id: string;
  handoff_id: string;
  method: string;
  status: string;
  target_url?: string | null;
  portal_ref?: string | null;
  handoff?: Record<string, unknown>;
  created_at?: string | null;
  verified_at?: string | null;
};

export type FilingStateResponse = {
  thread_id: string;
  submission_status: string;
  submission_summary: SubmissionSummaryData | null;
  pending_submission: Record<string, unknown> | null;
  pending_everify: Record<string, unknown> | null;
  everify_handoff: Record<string, unknown> | null;
  artifacts: FilingArtifacts | null;
  summary_record: Record<string, unknown> | null;
  everification: EverificationRecord | null;
  consents: Array<Record<string, unknown>>;
  revision: Record<string, unknown> | null;
  archived: boolean;
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

export async function fetchFilingState(threadId: string): Promise<FilingStateResponse> {
  return request<FilingStateResponse>(`/api/filing/${threadId}`);
}

export async function generateSubmissionSummary(input: {
  threadId: string;
  isFinal?: boolean;
}): Promise<{
  submission_summary: SubmissionSummaryData | null;
  submission_status: string;
}> {
  return request("/api/filing/summary", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      is_final: input.isFinal ?? true,
    }),
  });
}

export async function prepareSubmissionApproval(input: {
  threadId: string;
  isFinal?: boolean;
}): Promise<{
  submission_summary: SubmissionSummaryData | null;
  pending_approvals: Array<Record<string, unknown>>;
  submission_status: string;
}> {
  return request("/api/filing/submit/prepare", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      is_final: input.isFinal ?? true,
    }),
  });
}

export async function completeSubmission(input: {
  threadId: string;
  ackNo?: string;
  portalRef?: string;
  itrVText?: string;
}): Promise<{
  submission_status: string;
  artifacts: FilingArtifacts;
}> {
  return request("/api/filing/submit/complete", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      ack_no: input.ackNo ?? null,
      portal_ref: input.portalRef ?? null,
      itr_v_text: input.itrVText ?? null,
    }),
  });
}

export async function prepareEVerifyApproval(input: {
  threadId: string;
  method: string;
}): Promise<{
  pending_approvals: Array<Record<string, unknown>>;
  submission_status: string;
}> {
  return request("/api/filing/everify/prepare", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      method: input.method,
    }),
  });
}

export async function startEVerifyHandoff(input: {
  threadId: string;
  method?: string;
}): Promise<{
  submission_status: string;
  everify_handoff: Record<string, unknown> | null;
  everification: EverificationRecord | null;
  pending_navigation?: { url?: string } | null;
}> {
  return request("/api/filing/everify/start", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      method: input.method ?? null,
    }),
  });
}

export async function completeEVerify(input: {
  threadId: string;
  handoffId: string;
  portalRef?: string;
}): Promise<{
  submission_status: string;
  everification: EverificationRecord;
  archived: boolean;
}> {
  return request("/api/filing/everify/complete", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      handoff_id: input.handoffId,
      portal_ref: input.portalRef ?? null,
    }),
  });
}

export async function createRevisionThread(input: {
  threadId: string;
  reason: string;
  revisionNumber?: number;
}): Promise<{
  base_thread_id: string;
  revision_thread_id: string;
  revision_context: Record<string, unknown>;
}> {
  return request("/api/filing/revision", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      reason: input.reason,
      revision_number: input.revisionNumber ?? 1,
    }),
  });
}

export function filingArtifactUrl(threadId: string, artifactName: "itr-v" | "offline-json" | "evidence-bundle" | "summary"): string {
  return `${BACKEND_BASE_URL}/api/filing/${threadId}/artifacts/${artifactName}`;
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