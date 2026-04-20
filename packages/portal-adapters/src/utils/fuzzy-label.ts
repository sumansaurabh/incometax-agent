export function fuzzyMatchLabel(input: string, candidate: string): boolean {
  const a = input.toLowerCase().replace(/\s+/g, " ").trim();
  const b = candidate.toLowerCase().replace(/\s+/g, " ").trim();
  return a === b || a.includes(b) || b.includes(a);
}
