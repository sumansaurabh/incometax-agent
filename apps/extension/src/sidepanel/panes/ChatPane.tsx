import React, { useEffect, useMemo, useRef, useState } from "react";

import { ChatBubble } from "../components/ChatBubble";
import { ChatInput } from "../components/ChatInput";
import { ChatCard, ChatMessage } from "../components/chat-types";
import { FileUpload } from "../components/FileUpload";
import { MessageCard } from "../components/MessageCard";
import { TypingIndicator } from "../components/TypingIndicator";

type ProposalDecisionInput = {
  proposalId: string;
  approvalKey: string;
  approved: boolean;
  reason?: string;
};

type Props = {
  messages: ChatMessage[];
  contextualCards: ChatCard[];
  isBusy: boolean;
  isTyping: boolean;
  onSend: (message: string) => void;
  onFilesSelected: (files: File[]) => void;
  onAction: (actionId: string) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onProposalDecision?: (input: ProposalDecisionInput) => Promise<any>;
};

function dateKey(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(iso));
}

export function ChatPane({
  messages,
  contextualCards,
  isBusy,
  isTyping,
  onSend,
  onFilesSelected,
  onAction,
  onProposalDecision,
}: Props): JSX.Element {
  const listRef = useRef<HTMLDivElement | null>(null);
  const [showJump, setShowJump] = useState(false);

  const groupedMessages = useMemo(() => {
    return messages.map((message, index) => ({
      message,
      showDate: index === 0 || dateKey(messages[index - 1].createdAt) !== dateKey(message.createdAt),
    }));
  }, [messages]);

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior });
  };

  useEffect(() => {
    scrollToBottom("auto");
  }, [messages.length, contextualCards.length, isTyping]);

  return (
    <FileUpload disabled={isBusy} onFilesDropped={onFilesSelected}>
      <section className="chat-pane">
        <div
          ref={listRef}
          className="chat-transcript"
          onScroll={() => {
            const element = listRef.current;
            if (!element) return;
            setShowJump(element.scrollHeight - element.scrollTop - element.clientHeight > 120);
          }}
        >
          {groupedMessages.map(({ message, showDate }) => (
            <React.Fragment key={message.id}>
              {showDate ? <div className="date-divider">{dateKey(message.createdAt)}</div> : null}
              <ChatBubble message={message} onCardAction={onAction} onProposalDecision={onProposalDecision} />
            </React.Fragment>
          ))}
          {contextualCards.length ? (
            <div className="context-card-stack">
              {contextualCards.map((card) => (
                <MessageCard key={card.id} card={card} onAction={onAction} />
              ))}
            </div>
          ) : null}
          {isTyping ? <TypingIndicator /> : null}
        </div>
        {showJump ? (
          <button className="jump-button" type="button" onClick={() => scrollToBottom()}>
            Latest
          </button>
        ) : null}
        <ChatInput disabled={isBusy} onSend={onSend} onFilesSelected={onFilesSelected} />
      </section>
    </FileUpload>
  );
}
