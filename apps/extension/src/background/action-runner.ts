import { executeAction } from "../content/actions";

export async function runApprovedAction(action: unknown): Promise<unknown> {
  return executeAction(action);
}
