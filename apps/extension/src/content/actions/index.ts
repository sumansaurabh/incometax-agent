import { detectAdapter } from "@itx/portal-adapters";

import { clickTarget } from "./click";
import { fillField } from "./fill";
import { readField } from "./read";
import { getValidationErrors } from "./validation";

export type Action =
  | { type: "fill"; selector: string; value: string }
  | { type: "click"; selector: string }
  | { type: "read"; selector: string }
  | { type: "get_form_schema" }
  | { type: "get_validation_errors" };

type ActionBatchResult = {
  action: Action;
  output: unknown;
  readAfterWrite?: {
    ok: boolean;
    observedValue: string;
  };
};

export function executeAction(action: unknown): unknown {
  const parsed = action as Action;
  const adapter = detectAdapter(document);

  switch (parsed.type) {
    case "fill":
      return fillField(parsed.selector, parsed.value);
    case "click":
      return clickTarget(parsed.selector);
    case "read":
      return readField(parsed.selector);
    case "get_form_schema":
      return adapter?.getFormSchema(document) ?? [];
    case "get_validation_errors":
      return adapter?.readValidation(document) ?? getValidationErrors().map((message) => ({ field: "unknown", message }));
    default:
      throw new Error("Unsupported action type");
  }
}

export async function executeActionBatch(actions: unknown[]): Promise<{
  results: ActionBatchResult[];
  validationErrors: Array<{ field: string; message: string }>;
}> {
  const parsedActions = actions as Action[];
  const results: ActionBatchResult[] = [];

  for (const action of parsedActions) {
    const output = executeAction(action);
    if (action.type === "fill") {
      const observedValue = String(readField(action.selector) ?? "");
      results.push({
        action,
        output,
        readAfterWrite: {
          ok: observedValue === String(action.value),
          observedValue,
        },
      });
      continue;
    }

    results.push({ action, output });
  }

  return {
    results,
    validationErrors:
      (executeAction({ type: "get_validation_errors" }) as Array<{ field: string; message: string }>) ?? [],
  };
}
