export type FieldSchema = {
  key: string;
  label: string;
  required: boolean;
};

export type ValidationError = {
  field: string;
  message: string;
};

export type PageAdapter = {
  key: string;
  detect: (doc: Document) => boolean;
  getFormSchema: (doc: Document) => FieldSchema[];
  readValidation: (doc: Document) => ValidationError[];
};
