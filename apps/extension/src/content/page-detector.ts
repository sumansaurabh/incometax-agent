import { detectAdapter, FieldSchema, ValidationError } from "@itx/portal-adapters";

export type PortalPageContext = {
  page: string;
  fields: FieldSchema[];
  validationErrors: ValidationError[];
};

export function detectPage(doc: Document): PortalPageContext {
  const adapter = detectAdapter(doc);
  if (!adapter) {
    return {
      page: "unknown",
      fields: [],
      validationErrors: [],
    };
  }

  return {
    page: adapter.key,
    fields: adapter.getFormSchema(doc),
    validationErrors: adapter.readValidation(doc),
  };
}
