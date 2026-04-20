import React from "react";

type Evidence = {
  label: string;
  source: string;
};

type Props = {
  items: Evidence[];
};

export function EvidencePane({ items }: Props): JSX.Element {
  return (
    <section>
      <h3>Evidence</h3>
      <ul>
        {items.map((item) => (
          <li key={`${item.label}:${item.source}`}>
            {item.label} - {item.source}
          </li>
        ))}
      </ul>
    </section>
  );
}
