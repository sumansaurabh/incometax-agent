import { AuthSession, ensureFreshAuthSession } from "../shared/auth-session";
import { BACKEND_BASE_URL } from "../shared/backend-config";

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
  reviewerStatus?: string | null;
  reviewerEmail?: string | null;
  reviewerNote?: string | null;
  clientNote?: string | null;
  signoffId?: string | null;
};

export type ReviewerSignoff = {
  signoff_id: string;
  thread_id: string;
  approval_key: string;
  proposal_id?: string | null;
  owner_user_id: string;
  reviewer_email: string;
  reviewer_user_id?: string | null;
  status: string;
  request_note?: string | null;
  reviewer_note?: string | null;
  client_note?: string | null;
  client_consent_key?: string | null;
  details: Record<string, unknown>;
  approval_kind?: string | null;
  approval_description?: string | null;
  approval_status?: string | null;
  created_at?: string | null;
  reviewed_at?: string | null;
  client_decided_at?: string | null;
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
  reviewer_signoffs: ReviewerSignoff[];
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

export type YearOverYearDelta = {
  current: number;
  prior: number;
  delta: number;
};

export type YearOverYearComparison = {
  thread_id: string;
  current_assessment_year?: string | null;
  prior_thread_id?: string | null;
  prior_assessment_year?: string | null;
  regime: {
    current: string;
    prior?: string | null;
    changed: boolean;
  };
  metrics: Record<string, YearOverYearDelta>;
  deductions: Record<string, YearOverYearDelta>;
  highlights: string[];
};

export type YearOverYearRecord = {
  record_id: string;
  thread_id: string;
  user_id: string;
  current_assessment_year?: string | null;
  prior_thread_id?: string | null;
  prior_assessment_year?: string | null;
  comparison: YearOverYearComparison;
  created_at?: string | null;
};

export type NextAyChecklistItem = {
  code: string;
  title: string;
  reason: string;
  category: string;
  priority: string;
  due_by: string;
  recommended_documents: string[];
  status: string;
};

export type NextAyChecklistRecord = {
  record_id: string;
  thread_id: string;
  user_id: string;
  current_assessment_year?: string | null;
  target_assessment_year: string;
  items: NextAyChecklistItem[];
  summary: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type NoticePreparationRecord = {
  record_id: string;
  thread_id: string;
  user_id: string;
  notice_type: string;
  assessment_year?: string | null;
  source_storage_uri?: string | null;
  extracted: Record<string, unknown>;
  explanation_md: string;
  suggested_response: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type RefundStatusRecord = {
  record_id: string;
  thread_id: string;
  user_id: string;
  assessment_year?: string | null;
  status: string;
  refund_amount?: number | null;
  portal_ref?: string | null;
  issued_at?: string | null;
  processed_at?: string | null;
  refund_mode?: string | null;
  bank_masked?: string | null;
  source: string;
  observation: Record<string, unknown>;
  observed_at?: string | null;
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
  purge_jobs: Array<Record<string, unknown>>;
  revision: Record<string, unknown> | null;
  year_over_year: YearOverYearRecord | null;
  next_ay_checklist: NextAyChecklistRecord | null;
  notices: NoticePreparationRecord[];
  refund_status: RefundStatusRecord | null;
  itr_u: ItrURecord | null;
  archived: boolean;
};

export type AuthIdentity = {
  user_id: string;
  email: string;
  device_id: string;
  session_id: string;
  sessions: Array<Record<string, unknown>>;
};

export type PurgeJob = {
  job_id: string;
  thread_id: string;
  reason: string;
  requested_by: string;
  status: string;
  requested_at?: string | null;
  due_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  details?: Record<string, unknown>;
};

export type ConsentCatalogItem = {
  purpose: string;
  title: string;
  required: boolean;
  category?: string;
  depends_on?: string[];
  description: string;
  consent_text: string;
  scope: Record<string, unknown>;
};

export type ValidationHelpItem = {
  field: string;
  field_label: string;
  message: string;
  plain_english: string;
  suggested_fix: string;
  question: string;
  severity: string;
  suggested_value?: string | null;
  page_type: string;
  recovery_mode?: string;
  recovery_actions?: string[];
  page_drift_count?: number;
};

export type RegimeProjection = {
  regime: string;
  gross_total_income: number;
  total_deductions: number;
  taxable_income: number;
  net_tax_liability: number;
  total_tax_paid: number;
  tax_payable: number;
  refund_due: number;
  effective_result: number;
};

export type RegimePreview = {
  thread_id: string;
  current_regime: string;
  recommended_regime: string;
  delta_vs_current: number;
  old_regime: RegimeProjection;
  new_regime: RegimeProjection;
  rationale: string[];
};

export type SupportReason = {
  code: string;
  title: string;
  detail: string;
  severity: string;
};

export type ReviewHandoff = {
  handoff_id: string;
  thread_id: string;
  requested_by_user_id: string;
  support_mode: string;
  status: string;
  reason?: string | null;
  reasons: SupportReason[];
  checklist: string[];
  summary: Record<string, unknown>;
  package_storage_uri?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type SecurityStatus = {
  quarantined: boolean;
  reason?: string | null;
  requested_by?: string | null;
  details?: Record<string, unknown>;
  quarantined_at?: string | null;
  resumed_at?: string | null;
  resumed_by?: string | null;
  resume_note?: string | null;
};

export type SupportAssessment = {
  thread_id: string;
  mode: string;
  can_autofill: boolean;
  can_submit: boolean;
  reason_count: number;
  reasons: SupportReason[];
  checklist: string[];
  blocking_issues: string[];
  mismatch_count: number;
  pending_approval_count: number;
  handoffs: ReviewHandoff[];
  security_status?: SecurityStatus;
};

type RequestInitWithJson = RequestInit & {
  body?: string;
};

async function authenticatedFetch(path: string, auth: AuthSession, init?: RequestInitWithJson): Promise<Response> {
  return fetch(`${BACKEND_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${auth.accessToken}`,
      "X-ITX-Device-ID": auth.deviceId,
      ...(init?.headers ?? {}),
    },
    ...init,
  });
}

function extractThreadId(path: string, body?: string): string | null {
  const pathMatch =
    path.match(/^\/api\/actions\/thread\/([^/]+)/)?.[1] ??
    path.match(/^\/api\/filing\/([^/]+)/)?.[1] ??
    path.match(/^\/api\/tax-facts\/([^/]+)/)?.[1] ??
    path.match(/^\/api\/ca\/client\/([^/]+)\/support$/)?.[1] ??
    path.match(/^\/api\/security\/quarantine\/([^/]+)/)?.[1] ??
    null;
  if (pathMatch) {
    return pathMatch;
  }
  if (!body) {
    return null;
  }
  try {
    const parsed = JSON.parse(body) as { thread_id?: unknown; threadId?: unknown };
    if (typeof parsed.thread_id === "string") {
      return parsed.thread_id;
    }
    if (typeof parsed.threadId === "string") {
      return parsed.threadId;
    }
  } catch {
    return null;
  }
  return null;
}

async function maybeAutoQuarantine(path: string, init: RequestInitWithJson | undefined, auth: AuthSession, response: Response): Promise<void> {
  if (response.headers.get("X-Anomaly-Detected") !== "true") {
    return;
  }
  if (path.startsWith("/api/security/quarantine")) {
    return;
  }
  const threadId = extractThreadId(path, init?.body);
  if (!threadId) {
    return;
  }
  await authenticatedFetch("/api/security/quarantine", auth, {
    method: "POST",
    body: JSON.stringify({
      thread_id: threadId,
      reason: "anomaly_detected",
      details: { path },
    }),
  }).catch(() => undefined);
}

export class BackendError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null) {
    super(message);
    this.name = "BackendError";
    this.status = status;
    this.code = code;
  }

  isAuthFailure(): boolean {
    return this.status === 401 || this.status === 403;
  }
}

function translateAuthCode(code: string | null | undefined): string | null {
  if (!code) return null;
  return AUTH_ERROR_MESSAGES[code] ?? null;
}

async function throwBackendError(response: Response): Promise<never> {
  const errorPayload = (await response.json().catch(() => null)) as { detail?: string; error?: string } | null;
  const code = errorPayload?.detail ?? errorPayload?.error ?? null;
  const friendly = translateAuthCode(code);
  const message = friendly ?? code ?? `Backend request failed: ${response.status}`;
  throw new BackendError(message, response.status, code);
}

async function request<T>(path: string, init?: RequestInitWithJson): Promise<T> {
  const auth = await ensureFreshAuthSession();
  const response = await authenticatedFetch(path, auth, init);
  await maybeAutoQuarantine(path, init, auth, response);

  if (!response.ok) {
    await throwBackendError(response);
  }

  return response.json() as Promise<T>;
}

async function unauthenticatedRequest<T>(path: string, init?: RequestInitWithJson): Promise<T> {
  const response = await fetch(`${BACKEND_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    await throwBackendError(response);
  }
  return response.json() as Promise<T>;
}

const AUTH_ERROR_MESSAGES: Record<string, string> = {
  invalid_credentials: "Incorrect email or password.",
  invalid_email: "Enter a valid email address.",
  password_too_short: "Password must be at least 8 characters.",
  password_too_long: "Password is too long (max 128 characters).",
  password_required: "Password is required.",
  email_already_registered: "An account with this email already exists. Sign in instead.",
  device_id_required: "Browser device could not be identified. Please reload the extension.",
  authorization_required: "Please sign in to continue.",
  session_not_found: "Your session has ended. Sign in again.",
  session_revoked: "This session was revoked. Sign in again.",
  access_token_expired: "Your session expired. Sign in again.",
  refresh_token_expired: "Your session expired. Sign in again.",
  device_mismatch: "This session is bound to a different browser.",
  invalid_token: "Session is invalid. Sign in again.",
};

export async function loginToBackend(input: {
  email: string;
  password: string;
  deviceId: string;
  deviceName: string;
}): Promise<AuthSession> {
  const payload = await unauthenticatedRequest<{
    user_id: string;
    email: string;
    device_id: string;
    session_id: string;
    access_token: string;
    refresh_token: string;
    access_expires_at: string;
    refresh_expires_at: string;
  }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email: input.email,
      password: input.password,
      device_id: input.deviceId,
      device_name: input.deviceName,
    }),
  });
  return {
    userId: payload.user_id,
    email: payload.email,
    deviceId: payload.device_id,
    sessionId: payload.session_id,
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    accessExpiresAt: payload.access_expires_at,
    refreshExpiresAt: payload.refresh_expires_at,
  };
}

export async function fetchCurrentIdentity(): Promise<AuthIdentity> {
  return request<AuthIdentity>("/api/auth/me");
}

export async function revokeCurrentSession(): Promise<void> {
  await request<{ status: string }>("/api/auth/revoke", { method: "POST" });
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
  targetValue?: unknown;
  portalState?: PortalState | null;
}): Promise<{ fill_plan: FillPlan | null; pending_approvals: Array<Record<string, unknown>>; action_proposal_id?: string }> {
  return request("/api/actions/proposal", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      page_type: input.pageType ?? null,
      field_id: input.fieldId ?? null,
      target_value: input.targetValue ?? null,
      portal_state: input.portalState ?? null,
    }),
  });
}

export async function fetchValidationHelp(input: {
  threadId: string;
  pageType?: string | null;
  portalState?: PortalState | null;
  validationErrors: ValidationError[];
}): Promise<{ items: ValidationHelpItem[] }> {
  return request("/api/actions/validation-help", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      page_type: input.pageType ?? null,
      portal_state: input.portalState ?? null,
      validation_errors: input.validationErrors,
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

export async function generateYearOverYearComparison(threadId: string): Promise<YearOverYearRecord> {
  return request("/api/filing/year-over-year", {
    method: "POST",
    body: JSON.stringify({ thread_id: threadId }),
  });
}

export async function generateNextAyChecklist(threadId: string): Promise<NextAyChecklistRecord> {
  return request("/api/filing/next-ay-checklist", {
    method: "POST",
    body: JSON.stringify({ thread_id: threadId }),
  });
}

export async function prepareNoticeResponse(input: {
  threadId: string;
  noticeText: string;
  noticeType?: string;
}): Promise<NoticePreparationRecord> {
  return request("/api/filing/notices/prepare", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      notice_text: input.noticeText,
      notice_type: input.noticeType ?? "143(1)",
    }),
  });
}

export async function captureRefundStatus(input: {
  threadId: string;
  pageType?: string | null;
  pageTitle?: string | null;
  pageUrl?: string | null;
  portalState?: PortalState | null;
  manualStatus?: string | null;
  manualPortalRef?: string | null;
  manualRefundAmount?: string | number | null;
  manualIssuedAt?: string | null;
  manualProcessedAt?: string | null;
  manualRefundMode?: string | null;
  manualBankMasked?: string | null;
}): Promise<RefundStatusRecord> {
  return request("/api/filing/refund-status/capture", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      page_type: input.pageType ?? null,
      page_title: input.pageTitle ?? null,
      page_url: input.pageUrl ?? null,
      portal_state: input.portalState ?? null,
      manual_status: input.manualStatus ?? null,
      manual_portal_ref: input.manualPortalRef ?? null,
      manual_refund_amount: input.manualRefundAmount ?? null,
      manual_issued_at: input.manualIssuedAt ?? null,
      manual_processed_at: input.manualProcessedAt ?? null,
      manual_refund_mode: input.manualRefundMode ?? null,
      manual_bank_masked: input.manualBankMasked ?? null,
    }),
  });
}

export async function attachOfficialArtifact(input: {
  threadId: string;
  artifactKind?: string;
  pageType?: string | null;
  pageTitle?: string | null;
  pageUrl?: string | null;
  portalState?: PortalState | null;
  manualText?: string | null;
  ackNo?: string | null;
  portalRef?: string | null;
  filedAt?: string | null;
}): Promise<{
  artifacts: FilingArtifacts;
  official_artifact: Record<string, unknown>;
}> {
  return request("/api/filing/artifacts/official", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      artifact_kind: input.artifactKind ?? "itr_v",
      page_type: input.pageType ?? null,
      page_title: input.pageTitle ?? null,
      page_url: input.pageUrl ?? null,
      portal_state: input.portalState ?? null,
      manual_text: input.manualText ?? null,
      ack_no: input.ackNo ?? null,
      portal_ref: input.portalRef ?? null,
      filed_at: input.filedAt ?? null,
    }),
  });
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

export async function revokeConsent(input: {
  threadId: string;
  consentId: string;
  reason?: string;
}): Promise<{ consent: Record<string, unknown>; purge_job: PurgeJob }> {
  return request("/api/filing/consents/revoke", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      consent_id: input.consentId,
      reason: input.reason ?? "user_revoked_consent",
      process_immediately: true,
    }),
  });
}

export async function fetchConsentCatalog(): Promise<{ items: ConsentCatalogItem[] }> {
  return request("/api/filing/consents/catalog");
}

export async function grantOnboardingConsents(input: {
  threadId: string;
  purposes: string[];
}): Promise<{
  thread_id: string;
  user_id: string;
  granted: Array<Record<string, unknown>>;
  consents: Array<Record<string, unknown>>;
  required_purposes: string[];
}> {
  return request("/api/filing/consents/grant", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      items: input.purposes.map((purpose) => ({ purpose })),
    }),
  });
}

export async function fetchRegimePreview(threadId: string): Promise<RegimePreview> {
  return request("/api/filing/regime-preview", {
    method: "POST",
    body: JSON.stringify({ thread_id: threadId }),
  });
}

export async function fetchSupportAssessment(threadId: string): Promise<SupportAssessment> {
  return request(`/api/ca/client/${threadId}/support`);
}

export async function prepareReviewHandoff(input: {
  threadId: string;
  reason?: string;
}): Promise<ReviewHandoff> {
  return request("/api/ca/handoffs/prepare", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      reason: input.reason ?? "unsupported_or_guided_case",
    }),
  });
}

export async function requestReviewerSignoff(input: {
  threadId: string;
  approvalId: string;
  reviewerEmail: string;
  note?: string;
}): Promise<ReviewerSignoff> {
  return request("/api/ca/reviewers/signoff/request", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      approval_id: input.approvalId,
      reviewer_email: input.reviewerEmail,
      note: input.note ?? null,
    }),
  });
}

export async function counterConsentReviewerSignoff(input: {
  signoffId: string;
  approved?: boolean;
  note?: string;
}): Promise<ReviewerSignoff> {
  return request(`/api/ca/reviewers/signoff/${input.signoffId}/counter-consent`, {
    method: "POST",
    body: JSON.stringify({
      approved: input.approved ?? true,
      note: input.note ?? null,
    }),
  });
}

export async function quarantineThread(input: {
  threadId: string;
  reason?: string;
  details?: Record<string, unknown>;
}): Promise<{ thread_id: string; security_status: SecurityStatus }> {
  return request("/api/security/quarantine", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      reason: input.reason ?? "manual_quarantine",
      details: input.details ?? {},
    }),
  });
}

export async function resumeThreadQuarantine(input: {
  threadId: string;
  note?: string;
}): Promise<{ thread_id: string; security_status: SecurityStatus }> {
  return request(`/api/security/quarantine/${input.threadId}/resume`, {
    method: "POST",
    body: JSON.stringify({ note: input.note ?? "user_reviewed_anomaly" }),
  });
}

// ---------------------------------------------------------------------------
// ITR-U (Updated Return) types and API functions
// ---------------------------------------------------------------------------

export type ItrUEligibility = {
  eligible: boolean;
  assessment_year?: string | null;
  ay_end_date?: string | null;
  deadline_date?: string | null;
  as_of_date: string;
  submission_status: string;
  blockers: string[];
  warnings: string[];
  original_ack_no?: string | null;
};

export type ItrUEscalation = {
  thread_id: string;
  reason_code: string;
  reason_label: string;
  reason_detail: string;
  eligibility: ItrUEligibility;
  escalation_required: boolean;
  escalation_md: string;
  valid_reason_codes: Record<string, string>;
};

export type ItrURecord = {
  id: string;
  base_thread_id: string;
  itr_u_thread_id?: string | null;
  status: string;
  reason_code: string;
  reason_detail: string;
  base_ack_no?: string | null;
  eligibility: ItrUEligibility;
  escalation_confirmed_at?: string | null;
  escalation_confirmed_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export async function prepareItrU(input: {
  threadId: string;
  reasonCode: string;
  reasonDetail?: string;
}): Promise<ItrUEscalation> {
  return request<ItrUEscalation>("/api/filing/itr-u/prepare", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      reason_code: input.reasonCode,
      reason_detail: input.reasonDetail ?? "",
    }),
  });
}

export async function confirmItrU(input: {
  threadId: string;
  reasonCode: string;
  reasonDetail?: string;
  confirmedBy?: string;
}): Promise<{
  base_thread_id: string;
  itr_u_thread_id: string;
  itr_u_record: ItrURecord;
  escalation_md: string;
  seed_tax_facts: Record<string, unknown>;
}> {
  return request("/api/filing/itr-u/confirm", {
    method: "POST",
    body: JSON.stringify({
      thread_id: input.threadId,
      reason_code: input.reasonCode,
      reason_detail: input.reasonDetail ?? "",
      confirmed_by: input.confirmedBy ?? null,
    }),
  });
}

export async function fetchItrUState(threadId: string): Promise<ItrURecord> {
  return request<ItrURecord>(`/api/filing/itr-u/${threadId}`);
}

export function filingArtifactUrl(
  threadId: string,
  artifactName: "itr-v" | "offline-json" | "evidence-bundle" | "summary",
  auth: AuthSession,
): string {
  const params = new URLSearchParams({
    access_token: auth.accessToken,
    device_id: auth.deviceId,
  });
  return `${BACKEND_BASE_URL}/api/filing/${threadId}/artifacts/${artifactName}?${params.toString()}`;
}

export function reviewHandoffPackageUrl(
  threadId: string,
  handoffId: string,
  auth: AuthSession,
): string {
  const params = new URLSearchParams({
    access_token: auth.accessToken,
    device_id: auth.deviceId,
  });
  return `${BACKEND_BASE_URL}/api/ca/handoffs/${threadId}/${handoffId}/package?${params.toString()}`;
}

export function normalizeApprovalItems(payload: ThreadActionsResponse): ApprovalItem[] {
  const approvals = payload.approvals.length > 0 ? payload.approvals : payload.pending_approvals;
  const signoffByApprovalId = new Map((payload.reviewer_signoffs ?? []).map((signoff) => [signoff.approval_key, signoff]));
  return approvals.map((approval) => {
    const approvalId = String(approval.approval_id ?? approval.approvalId ?? "");
    const signoff = signoffByApprovalId.get(approvalId);
    return {
      approvalId,
      description: String(approval.description ?? "Approval required"),
      status: String(approval.status ?? "pending"),
      kind: String(approval.kind ?? approval.approval_type ?? "fill_plan"),
      actionIds: Array.isArray(approval.action_ids) ? (approval.action_ids as string[]) : [],
      expiresAt: (approval.expires_at as string | null | undefined) ?? null,
      proposalId: (approval.proposal_id as string | null | undefined) ?? null,
      reviewerStatus: signoff?.status ?? null,
      reviewerEmail: signoff?.reviewer_email ?? null,
      reviewerNote: signoff?.reviewer_note ?? signoff?.request_note ?? null,
      clientNote: signoff?.client_note ?? null,
      signoffId: signoff?.signoff_id ?? null,
    };
  });
}