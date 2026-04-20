export function selectorFallback(label: string): string {
  return `[aria-label*="${label}"]`;
}
