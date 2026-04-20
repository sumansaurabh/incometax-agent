export type ClientReviewRow = {
  threadId: string;
  pan?: string;
  name?: string;
  itrType?: string;
  assessmentYear?: string;
  canSubmit?: boolean;
  blockingIssues: string[];
};

export function summarizeRisk(row: ClientReviewRow): "low" | "medium" | "high" {
  if ((row.blockingIssues || []).length > 0) {
    return "high";
  }
  if (!row.canSubmit) {
    return "medium";
  }
  return "low";
}
