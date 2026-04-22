import React, { KeyboardEvent, useRef, useState } from "react";

type Props = {
  disabled: boolean;
  onSend: (message: string) => void;
  onFilesSelected: (files: File[]) => void;
};

export function ChatInput({ disabled, onSend, onFilesSelected }: Props): JSX.Element {
  const [value, setValue] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const send = () => {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  };

  return (
    <form
      className="chat-input-bar"
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
    >
      <button
        className="icon-button"
        type="button"
        title="Attach documents"
        aria-label="Attach documents"
        disabled={disabled}
        onClick={() => fileInputRef.current?.click()}
      >
        +
      </button>
      <textarea
        rows={1}
        value={value}
        disabled={disabled}
        placeholder="Ask IncomeTax Agent to file, search, or explain..."
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <button className="send-button" type="submit" disabled={disabled || !value.trim()} aria-label="Send message">
        &gt;
      </button>
      <input
        ref={fileInputRef}
        className="visually-hidden"
        type="file"
        multiple
        accept=".pdf,.png,.jpg,.jpeg,.csv,.json,.txt,application/pdf,image/png,image/jpeg,text/csv,application/json,text/plain"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          if (files.length) {
            onFilesSelected(files);
          }
          event.currentTarget.value = "";
        }}
      />
    </form>
  );
}
