import React from "react";

import { ChatCard } from "./chat-types";
import { PasswordPromptCard } from "./PasswordPromptCard";

type PasswordSubmit = (input: {
  cardId: string;
  documentIds: string[];
  password: string;
  pan?: string;
  dob?: string;
}) => Promise<void> | void;

type Props = {
  card: ChatCard;
  onAction: (actionId: string) => void;
  onSubmitPassword?: PasswordSubmit;
};

export function MessageCard({ card, onAction, onSubmitPassword }: Props): JSX.Element {
  if (card.kind === "password_prompt" && card.passwordPrompt && onSubmitPassword) {
    return <PasswordPromptCard card={card} onSubmitPassword={onSubmitPassword} />;
  }
  return (
    <article className={`message-card message-card-${card.kind}`}>
      <div className="message-card-header">
        <strong>{card.title}</strong>
        <span>{card.kind.replace("-", " ")}</span>
      </div>
      {card.body ? <p>{card.body}</p> : null}
      {card.meta?.length ? (
        <dl className="message-card-meta">
          {card.meta.map((item) => (
            <div key={`${card.id}-${item.label}`}>
              <dt>{item.label}</dt>
              <dd>{item.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {card.actions?.length ? (
        <div className="message-card-actions">
          {card.actions.map((action) => (
            <button
              key={action.id}
              className={`chat-button ${action.variant ?? "secondary"}`}
              type="button"
              disabled={action.disabled}
              onClick={() => onAction(action.id)}
            >
              {action.label}
            </button>
          ))}
        </div>
      ) : null}
    </article>
  );
}
