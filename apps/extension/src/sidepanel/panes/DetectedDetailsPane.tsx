import React from "react";

type Props = {
  page: string;
};

export function DetectedDetailsPane({ page }: Props): JSX.Element {
  return (
    <section>
      <h3>Detected Step</h3>
      <p>{page}</p>
    </section>
  );
}
