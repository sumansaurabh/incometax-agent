import React, { useEffect, useState } from "react";

import {
  fetchMyThreads,
  RegimePreview,
  SupportAssessment,
  SupportReason,
  ThreadSummary,
  VerdictCardData,
} from "../backend";
import { UploadedDocument } from "./chat-types";
import { VerdictCard } from "./VerdictCard";

type Props = {
  open: boolean;
  email: string;
  threadId?: string | null;
  trustMessage?: string | null;
  documentCount: number;
  parsedCount?: number;
  indexedCount?: number;
  factCount?: number;
  documents?: UploadedDocument[];
  supportAssessment?: SupportAssessment | null;
  regimePreview?: RegimePreview | null;
  isBusy: boolean;
  onClose: () => void;
  onNewConversation: () => void;
  onSwitchThread: (threadId: string) => void;
  onSignOut: () => void;
  onSearchDocuments?: () => void;
  onCompareRegimes?: () => void;
  onOpenDocument?: (documentId: string) => void;
  onResolveVerdictItem?: (input: {
    code: string;
    itemId: string;
    status: "open" | "acknowledged" | "resolved";
    actionKind?: string;
    note?: string;
  }) => Promise<void> | void;
  onVerdictAction?: (kind: string, code: string) => void;
};

function reasonToVerdictCard(reason: SupportReason, mode: string, modeTrigger: string | null | undefined): VerdictCardData {
  return {
    verdict: {
      code: reason.code,
      title: reason.title,
      detail: reason.detail,
      severity: reason.severity,
      mode_impact: mode,
      is_mode_trigger: Boolean(modeTrigger && reason.code === modeTrigger),
    },
    evidence: reason.evidence ?? [],
    actions: reason.actions ?? [],
    trail: reason.trail ?? [],
  };
}

function formatInr(value: number): string {
  return `INR ${Math.round(value).toLocaleString("en-IN")}`;
}

export function SettingsDrawer({
  open,
  email,
  threadId,
  trustMessage,
  documentCount,
  parsedCount = 0,
  indexedCount = 0,
  factCount = 0,
  documents = [],
  supportAssessment,
  regimePreview,
  isBusy,
  onClose,
  onNewConversation,
  onSwitchThread,
  onSignOut,
  onSearchDocuments,
  onCompareRegimes,
  onOpenDocument,
  onResolveVerdictItem,
  onVerdictAction,
}: Props): JSX.Element | null {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [loadingThreads, setLoadingThreads] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoadingThreads(true);
    fetchMyThreads()
      .then((result) => setThreads(result.threads))
      .catch(() => setThreads([]))
      .finally(() => setLoadingThreads(false));
  }, [open]);

  if (!open) return null;

  const supportBlocked =
    supportAssessment && (!supportAssessment.can_autofill || !supportAssessment.can_submit);

  return (
    <aside className="settings-backdrop" onClick={onClose}>
      <section
        className="settings-drawer"
        role="dialog"
        aria-label="Settings"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="settings-header">
          <div className="settings-header-text">
            <p className="settings-eyebrow">Account</p>
            <h2>{email}</h2>
            {threadId ? <span className="settings-thread-chip">Thread {threadId.slice(0, 8)}</span> : null}
          </div>
          <button className="icon-button" type="button" aria-label="Close settings" onClick={onClose}>
            ×
          </button>
        </header>

        <div className="settings-scroll">
          <section className="settings-section">
            <h3>Status</h3>
            <ul className="settings-status-list">
              <li>
                <span>Portal trust</span>
                <strong>{trustMessage ?? "Unknown"}</strong>
              </li>
              <li>
                <span>Consent mode</span>
                <strong>Pilot auto-allow</strong>
              </li>
            </ul>
          </section>

          {/* <section className="settings-section">
            <div className="settings-section-head">
              <h3>Documents</h3>
              {onSearchDocuments && documentCount > 0 ? (
                <button
                  className="settings-link-button"
                  type="button"
                  disabled={isBusy}
                  onClick={onSearchDocuments}
                >
                  Search
                </button>
              ) : null}
            </div>
            {documentCount === 0 ? (
              <p className="settings-empty">
                No documents yet. Upload Form 16, AIS, TIS, or proofs from the chat.
              </p>
            ) : (
              <>
                <div className="settings-metric-grid">
                  <div className="settings-metric">
                    <span>Uploaded</span>
                    <strong>{documentCount}</strong>
                  </div>
                  <div className="settings-metric">
                    <span>Parsed</span>
                    <strong>{parsedCount}</strong>
                  </div>
                  <div className="settings-metric">
                    <span>Indexed</span>
                    <strong>{indexedCount}</strong>
                  </div>
                  <div className="settings-metric">
                    <span>Facts</span>
                    <strong>{factCount}</strong>
                  </div>
                </div>
                {documents.length > 0 ? (
                  <ul className="settings-doc-list">
                    {documents.slice(0, 6).map((document) => (
                      <li key={document.documentId}>
                        <button
                          type="button"
                          className="settings-doc-item"
                          disabled={isBusy || !onOpenDocument}
                          onClick={() => onOpenDocument?.(document.documentId)}
                        >
                          <span className="settings-doc-name">{document.fileName}</span>
                          <span className={`settings-doc-status settings-doc-status-${document.status}`}>
                            {document.status}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </>
            )}
          </section> */}

          <section className="settings-section">
            <div className="settings-section-head">
              <h3>Regime</h3>
              {onCompareRegimes ? (
                <button
                  className="settings-link-button"
                  type="button"
                  disabled={isBusy}
                  onClick={onCompareRegimes}
                >
                  {regimePreview ? "Refresh" : "Compare"}
                </button>
              ) : null}
            </div>
            {regimePreview ? (
              <div className="settings-regime">
                <p className="settings-regime-recommend">
                  Recommended: <strong>{regimePreview.recommended_regime}</strong>
                </p>
                {regimePreview.rationale[0] ? (
                  <p className="settings-regime-rationale">{regimePreview.rationale[0]}</p>
                ) : null}
                <div className="settings-metric-grid">
                  <div className="settings-metric">
                    <span>Old regime tax</span>
                    <strong>{formatInr(regimePreview.old_regime.net_tax_liability)}</strong>
                  </div>
                  <div className="settings-metric">
                    <span>New regime tax</span>
                    <strong>{formatInr(regimePreview.new_regime.net_tax_liability)}</strong>
                  </div>
                </div>
              </div>
            ) : (
              <p className="settings-empty">Compare old vs new regime once facts are extracted.</p>
            )}
          </section>

          {supportBlocked ? (
            <section className="settings-section settings-section-alert">
              <h3>Review needed</h3>
              <ul className="settings-status-list">
                <li>
                  <span>Mode</span>
                  <strong>{supportAssessment?.mode}</strong>
                </li>
                <li>
                  <span>Triggered by</span>
                  <strong>{supportAssessment?.mode_trigger ?? "—"}</strong>
                </li>
                <li>
                  <span>Blockers</span>
                  <strong>{supportAssessment?.blocking_issues.length ?? 0}</strong>
                </li>
              </ul>
              <div className="verdict-card-stack">
                {(supportAssessment?.reasons ?? []).map((reason) => (
                  <VerdictCard
                    key={reason.code}
                    data={reasonToVerdictCard(reason, supportAssessment?.mode ?? "", supportAssessment?.mode_trigger ?? null)}
                    onResolve={onResolveVerdictItem ? async (input) => {
                      await onResolveVerdictItem(input);
                    } : undefined}
                    onAction={onVerdictAction}
                    busy={isBusy}
                  />
                ))}
                {(supportAssessment?.reasons ?? []).length === 0 ? (
                  <p className="settings-alert-title">The filing thread has a support blocker but no reasons were returned.</p>
                ) : null}
              </div>
            </section>
          ) : null}

          <section className="settings-section">
            <h3>Threads</h3>
            {loadingThreads && <p className="settings-empty">Loading threads…</p>}
            {!loadingThreads && threads.length === 0 && (
              <p className="settings-empty">No threads found.</p>
            )}
            {!loadingThreads && threads.length > 0 && (
              <ul className="thread-list">
                {threads.map((thread) => {
                  const isActive = thread.thread_id === threadId;
                  return (
                    <li
                      key={thread.thread_id}
                      className={`thread-item${isActive ? " active" : ""}${thread.archived ? " archived" : ""}`}
                    >
                      <button
                        className="thread-item-button"
                        type="button"
                        disabled={isActive || isBusy}
                        onClick={() => onSwitchThread(thread.thread_id)}
                      >
                        <span className="thread-item-id">{thread.thread_id.slice(0, 8)}</span>
                        <span className="thread-item-meta">
                          {thread.itr_type} · {thread.submission_status}
                          {thread.document_count > 0
                            ? ` · ${thread.document_count} doc${thread.document_count !== 1 ? "s" : ""}`
                            : ""}
                          {thread.archived ? " · archived" : ""}
                        </span>
                        {isActive && <span className="thread-item-active-badge">active</span>}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>

        <footer className="settings-footer">
          <button
            className="chat-button secondary"
            type="button"
            disabled={isBusy}
            onClick={onNewConversation}
          >
            New conversation
          </button>
          <button className="chat-button danger" type="button" disabled={isBusy} onClick={onSignOut}>
            Sign out
          </button>
        </footer>
      </section>
    </aside>
  );
}
