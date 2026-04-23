import React, { useEffect, useState } from "react";

import { fetchMyThreads, ThreadSummary } from "../backend";

type Props = {
  open: boolean;
  email: string;
  threadId?: string | null;
  trustMessage?: string | null;
  documentCount: number;
  parsedCount?: number;
  indexedCount?: number;
  factCount?: number;
  isBusy: boolean;
  onClose: () => void;
  onNewConversation: () => void;
  onSwitchThread: (threadId: string) => void;
  onSignOut: () => void;
  onSearchDocuments?: () => void;
};

export function SettingsDrawer({
  open,
  email,
  threadId,
  trustMessage,
  documentCount,
  parsedCount = 0,
  indexedCount = 0,
  factCount = 0,
  isBusy,
  onClose,
  onNewConversation,
  onSwitchThread,
  onSignOut,
  onSearchDocuments,
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

  return (
    <aside className="settings-backdrop" onClick={onClose}>
      <section className="settings-drawer" onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <p>Settings</p>
            <h2>{email}</h2>
          </div>
          <button className="icon-button" type="button" aria-label="Close settings" onClick={onClose}>
            x
          </button>
        </header>
        <dl>
          <div>
            <dt>Active thread</dt>
            <dd>{threadId ? threadId.slice(0, 8) : "Not started"}</dd>
          </div>
          <div>
            <dt>Portal trust</dt>
            <dd>{trustMessage ?? "Unknown"}</dd>
          </div>
          <div>
            <dt>Documents</dt>
            <dd>
              {documentCount} uploaded · {parsedCount} parsed · {indexedCount} indexed · {factCount} facts
            </dd>
          </div>
          <div>
            <dt>Consent mode</dt>
            <dd>Pilot auto-allow</dd>
          </div>
        </dl>

        {documentCount > 0 && onSearchDocuments ? (
          <button className="chat-button secondary" type="button" disabled={isBusy} onClick={onSearchDocuments}>
            Search documents
          </button>
        ) : null}

        <div className="thread-picker">
          <p className="thread-picker-label">Switch thread</p>
          {loadingThreads && <p className="thread-picker-loading">Loading threads...</p>}
          {!loadingThreads && threads.length === 0 && (
            <p className="thread-picker-empty">No threads found.</p>
          )}
          {!loadingThreads && threads.length > 0 && (
            <ul className="thread-list">
              {threads.map((thread) => {
                const isActive = thread.thread_id === threadId;
                return (
                  <li key={thread.thread_id} className={`thread-item${isActive ? " active" : ""}${thread.archived ? " archived" : ""}`}>
                    <button
                      className="thread-item-button"
                      type="button"
                      disabled={isActive || isBusy}
                      onClick={() => onSwitchThread(thread.thread_id)}
                    >
                      <span className="thread-item-id">{thread.thread_id.slice(0, 8)}</span>
                      <span className="thread-item-meta">
                        {thread.itr_type} · {thread.submission_status}
                        {thread.document_count > 0 ? ` · ${thread.document_count} doc${thread.document_count !== 1 ? "s" : ""}` : ""}
                        {thread.archived ? " · archived" : ""}
                      </span>
                      {isActive && <span className="thread-item-active-badge">active</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <button className="chat-button secondary" type="button" disabled={isBusy} onClick={onNewConversation}>
          New conversation
        </button>
        <button className="chat-button danger" type="button" disabled={isBusy} onClick={onSignOut}>
          Sign out
        </button>
      </section>
    </aside>
  );
}
