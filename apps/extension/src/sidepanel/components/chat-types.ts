export type ChatRole = "user" | "agent" | "system" | "error";

export type ChatMessageStatus = "sending" | "sent" | "delivered" | "error";

export type ChatCardAction = {
  id: string;
  label: string;
  variant?: "primary" | "secondary" | "danger";
  disabled?: boolean;
};

export type ChatCard = {
  id: string;
  kind: "welcome" | "document" | "evidence" | "approval" | "action" | "summary" | "error";
  title: string;
  body?: string;
  meta?: Array<{ label: string; value: string }>;
  actions?: ChatCardAction[];
};

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;
  status?: ChatMessageStatus;
  cards?: ChatCard[];
  /**
   * Agent-produced fill proposals (from propose_fill). The DiffCard component renders
   * each of these inline with the assistant message so the user can review and approve
   * without leaving the chat flow.
   */
  proposals?: Array<{
    proposal_id: string;
    approval_key: string;
    status: string;
    sensitivity?: string | null;
    expires_at?: string | null;
    total_actions?: number;
    high_confidence_actions?: number;
    low_confidence_actions?: number;
    message?: string | null;
    pages: Array<{
      page_type: string;
      page_title: string;
      actions: Array<{
        action_id: string;
        field_id: string;
        field_label: string;
        selector: string;
        value: unknown;
        formatted_value: string;
        confidence: number;
        confidence_level: "high" | "medium" | "low";
        source_document?: string | null;
        requires_approval: boolean;
      }>;
    }>;
  }>;
};

export type UploadedDocument = {
  documentId: string;
  fileName: string;
  documentType: string;
  status: string;
  uploadedAt?: string | null;
  parsedAt?: string | null;
};
