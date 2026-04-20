import React, { useState } from "react";

type Props = {
  onSend: (message: string) => void;
  messages: string[];
};

export function ChatPane({ onSend, messages }: Props): JSX.Element {
  const [text, setText] = useState("");

  return (
    <section>
      <h3>Chat</h3>
      <div>
        {messages.map((msg, idx) => (
          <p key={idx}>{msg}</p>
        ))}
      </div>
      <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask anything" />
      <button
        onClick={() => {
          if (!text.trim()) return;
          onSend(text);
          setText("");
        }}
      >
        Send
      </button>
    </section>
  );
}
