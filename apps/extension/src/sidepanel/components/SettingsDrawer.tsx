import React from "react";

type Props = {
  open: boolean;
  email: string;
  threadId?: string | null;
  trustMessage?: string | null;
  documentCount: number;
  isBusy: boolean;
  onClose: () => void;
  onNewConversation: () => void;
  onSignOut: () => void;
};

export function SettingsDrawer({
  open,
  email,
  threadId,
  trustMessage,
  documentCount,
  isBusy,
  onClose,
  onNewConversation,
  onSignOut,
}: Props): JSX.Element | null {
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
            <dt>Thread</dt>
            <dd>{threadId ? threadId.slice(0, 8) : "Not started"}</dd>
          </div>
          <div>
            <dt>Portal trust</dt>
            <dd>{trustMessage ?? "Unknown"}</dd>
          </div>
          <div>
            <dt>Documents</dt>
            <dd>{documentCount} uploaded</dd>
          </div>
          <div>
            <dt>Consent mode</dt>
            <dd>Pilot auto-allow</dd>
          </div>
        </dl>
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
