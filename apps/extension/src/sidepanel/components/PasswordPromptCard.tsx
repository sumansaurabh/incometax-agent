import React, { FormEvent, useState } from "react";

import { ChatCard } from "./chat-types";

type Props = {
  card: ChatCard;
  onSubmitPassword: (input: {
    cardId: string;
    documentIds: string[];
    password: string;
    pan?: string;
    dob?: string;
  }) => Promise<void> | void;
};

function derivePassword(pan: string, dob: string): string | null {
  const panClean = pan.trim().toLowerCase();
  if (!/^[a-z]{5}[0-9]{4}[a-z]$/.test(panClean)) return null;
  const digits = dob.replace(/\D/g, "");
  if (digits.length !== 8) return null;
  return `${panClean}${digits}`;
}

export function PasswordPromptCard({ card, onSubmitPassword }: Props): JSX.Element {
  const [password, setPassword] = useState("");
  const [pan, setPan] = useState("");
  const [dob, setDob] = useState("");
  const [showBuilder, setShowBuilder] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const prompt = card.passwordPrompt;
  const isExhausted = prompt ? prompt.attemptsRemaining <= 0 : false;
  const jsonNotice = prompt?.encryptionKind === "ais_json";

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!prompt || submitting) return;
    const effective = password.trim() || derivePassword(pan, dob) || "";
    if (!effective) return;
    setSubmitting(true);
    try {
      await onSubmitPassword({
        cardId: card.id,
        documentIds: prompt.documentIds,
        password: effective,
        pan: pan.trim() || undefined,
        dob: dob.trim() || undefined,
      });
      setPassword("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <article className="message-card message-card-password_prompt">
      <div className="message-card-header">
        <strong>{card.title}</strong>
        <span>password required</span>
      </div>
      {card.body ? <p>{card.body}</p> : null}
      {jsonNotice ? (
        <p className="password-prompt-notice">
          The encrypted AIS JSON format is not supported yet. Please download the AIS
          <em> PDF </em>
          from the portal and upload that instead — it uses the same password.
        </p>
      ) : null}
      {!jsonNotice && !isExhausted ? (
        <form className="password-prompt-form" onSubmit={handleSubmit}>
          <label>
            <span>Document password</span>
            <input
              type="password"
              autoComplete="off"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="lowercase PAN + DDMMYYYY"
              disabled={submitting}
            />
          </label>
          <button
            type="button"
            className="password-builder-toggle"
            onClick={() => setShowBuilder((previous) => !previous)}
            disabled={submitting}
          >
            {showBuilder ? "Hide" : "Build from PAN + DOB instead"}
          </button>
          {showBuilder ? (
            <div className="password-builder">
              <label>
                <span>PAN</span>
                <input
                  type="text"
                  autoComplete="off"
                  value={pan}
                  onChange={(event) => setPan(event.target.value.toUpperCase())}
                  placeholder="ABCDE1234F"
                  maxLength={10}
                  disabled={submitting}
                />
              </label>
              <label>
                <span>Date of birth</span>
                <input
                  type="text"
                  autoComplete="off"
                  value={dob}
                  onChange={(event) => setDob(event.target.value)}
                  placeholder="DD/MM/YYYY"
                  disabled={submitting}
                />
              </label>
              {pan && dob ? (
                <p className="password-builder-preview">
                  Will use: <code>{derivePassword(pan, dob) ?? "(invalid combination)"}</code>
                </p>
              ) : null}
            </div>
          ) : null}
          <div className="message-card-actions">
            <button
              type="submit"
              className="chat-button primary"
              disabled={submitting || (!password.trim() && !derivePassword(pan, dob))}
            >
              {submitting ? "Unlocking..." : "Unlock"}
            </button>
          </div>
          {prompt && prompt.attemptsRemaining < 5 ? (
            <p className="password-prompt-attempts">
              {prompt.attemptsRemaining} attempt{prompt.attemptsRemaining === 1 ? "" : "s"} remaining.
            </p>
          ) : null}
        </form>
      ) : null}
      {isExhausted ? (
        <p className="password-prompt-exhausted">
          Too many incorrect attempts. Please re-upload the file with the correct password.
        </p>
      ) : null}
    </article>
  );
}
