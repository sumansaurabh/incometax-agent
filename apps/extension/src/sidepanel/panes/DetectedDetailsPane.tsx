import React from "react";

type DetectedField = {
  key: string;
  label: string;
  required: boolean;
  selectorHint?: string;
};

type ValidationError = {
  field: string;
  message: string;
};

type Props = {
  page: string;
  fields: DetectedField[];
  validationErrors: ValidationError[];
};

export function DetectedDetailsPane({ page, fields, validationErrors }: Props): JSX.Element {
  return (
    <section>
      <h3>Detected Step</h3>
      <p>{page}</p>
      <p>Detected fields: {fields.length}</p>
      {fields.length > 0 ? (
        <ul>
          {fields.slice(0, 6).map((field) => (
            <li key={field.key}>
              {field.label}
              {field.required ? " (required)" : ""}
            </li>
          ))}
        </ul>
      ) : null}
      {validationErrors.length > 0 ? (
        <>
          <h4>Validation Errors</h4>
          <ul>
            {validationErrors.map((error, idx) => (
              <li key={`${error.field}-${idx}`}>{error.message}</li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
