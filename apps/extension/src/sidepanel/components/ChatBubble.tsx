import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ChatMessage } from "./chat-types";
import { DiffCard, ProposalCard } from "./DiffCard";
import { MessageCard } from "./MessageCard";

type DecisionInput = {
  proposalId: string;
  approvalKey: string;
  approved: boolean;
  reason?: string;
};

type PasswordSubmit = (input: {
  cardId: string;
  documentIds: string[];
  password: string;
  pan?: string;
  dob?: string;
}) => Promise<void> | void;

type Props = {
  message: ChatMessage;
  onCardAction: (actionId: string) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onProposalDecision?: (input: DecisionInput) => Promise<any>;
  onSubmitPassword?: PasswordSubmit;
};

function formatRelativeTime(iso: string): string {
  const elapsed = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(elapsed) || elapsed < 60_000) return "just now";
  const minutes = Math.floor(elapsed / 60_000);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short" }).format(new Date(iso));
}

const SAFE_URL_SCHEMES = /^(https?:|mailto:|tel:)/i;

function safeUrl(url: string): string {
  const trimmed = url.trim();
  if (trimmed.startsWith("/") || trimmed.startsWith("#") || trimmed.startsWith(".")) {
    return trimmed;
  }
  return SAFE_URL_SCHEMES.test(trimmed) ? trimmed : "";
}

function MessageMarkdown({ content }: { content: string }): JSX.Element {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      urlTransform={safeUrl}
      components={{
        a: ({ children, href, ...rest }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" {...rest}>
            {children}
          </a>
        ),
        table: ({ children }) => (
          <div className="markdown-table-wrap">
            <table className="markdown-table">{children}</table>
          </div>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

export function ChatBubble({ message, onCardAction, onProposalDecision, onSubmitPassword }: Props): JSX.Element {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";
  const canCopy = message.role === "agent" && message.content.trim().length > 0;
  const proposals = message.proposals ?? [];

  return (
    <div className={`chat-row ${message.role}`}>
      <div className="chat-bubble">
        {message.content ? <MessageMarkdown content={message.content} /> : null}
        {message.cards?.map((card) => (
          <MessageCard
            key={card.id}
            card={card}
            onAction={onCardAction}
            onSubmitPassword={onSubmitPassword}
          />
        ))}
        {proposals.length && onProposalDecision
          ? proposals.map((proposal) => (
              <DiffCard
                key={proposal.proposal_id}
                proposal={proposal as ProposalCard}
                onDecision={onProposalDecision}
              />
            ))
          : null}
        <div className="message-footer">
          <span>{formatRelativeTime(message.createdAt)}</span>
          {isUser ? <span className={`message-status ${message.status ?? "sent"}`}>{message.status ?? "sent"}</span> : null}
          {canCopy ? (
            <button
              className="copy-button"
              type="button"
              onClick={async () => {
                await navigator.clipboard.writeText(message.content);
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1200);
              }}
            >
              {copied ? "Copied" : "Copy"}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
