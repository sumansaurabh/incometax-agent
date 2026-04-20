export function getValidationErrors(): string[] {
  const nodes = Array.from(document.querySelectorAll(".error, .validation-error"));
  return nodes.map((n) => n.textContent?.trim() ?? "").filter(Boolean);
}
