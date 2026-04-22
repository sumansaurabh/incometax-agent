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
};

export type UploadedDocument = {
  documentId: string;
  fileName: string;
  documentType: string;
  status: string;
  uploadedAt?: string | null;
  parsedAt?: string | null;
};
