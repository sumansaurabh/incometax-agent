import { clickTarget } from "./click";
import { fillField } from "./fill";
import { readField } from "./read";
import { getValidationErrors } from "./validation";

type Action =
  | { type: "fill"; selector: string; value: string }
  | { type: "click"; selector: string }
  | { type: "read"; selector: string }
  | { type: "get_validation_errors" };

export function executeAction(action: unknown): unknown {
  const parsed = action as Action;
  switch (parsed.type) {
    case "fill":
      return fillField(parsed.selector, parsed.value);
    case "click":
      return clickTarget(parsed.selector);
    case "read":
      return readField(parsed.selector);
    case "get_validation_errors":
      return getValidationErrors();
    default:
      throw new Error("Unsupported action type");
  }
}
