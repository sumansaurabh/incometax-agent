import React from "react";

type Props = {
  actions: string[];
};

export function PendingActionsPane({ actions }: Props): JSX.Element {
  return (
    <section>
      <h3>Pending Actions</h3>
      <ul>
        {actions.map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>
    </section>
  );
}
