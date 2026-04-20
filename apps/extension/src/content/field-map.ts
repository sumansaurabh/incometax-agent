export function findFieldSelector(label: string): string | null {
  const normalized = label.trim().toLowerCase();
  const labels = Array.from(document.querySelectorAll("label"));

  for (const node of labels) {
    if (node.textContent?.trim().toLowerCase() === normalized) {
      const forId = node.getAttribute("for");
      if (forId) {
        return `#${forId}`;
      }
    }
  }

  return null;
}
