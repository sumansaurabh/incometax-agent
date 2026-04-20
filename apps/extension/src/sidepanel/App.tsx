import React, { useEffect, useState } from "react";
import { ChatPane } from "./panes/ChatPane";
import { DetectedDetailsPane } from "./panes/DetectedDetailsPane";
import { PendingActionsPane } from "./panes/PendingActionsPane";
import { EvidencePane } from "./panes/EvidencePane";

export default function App(): JSX.Element {
  const [messages, setMessages] = useState<string[]>(["IncomeTax Agent ready."]);
  const [page, setPage] = useState("unknown");
  const [facts] = useState([
    {
      factId: "sample-gross-salary",
      fieldName: "gross_salary",
      displayLabel: "Gross Salary",
      value: 0,
      formattedValue: "₹0.00",
      category: "income" as const,
      confidence: 0.95,
      extractorVersion: "1.0.0",
      sources: [
        {
          documentId: "sample-doc",
          documentName: "Sample",
          documentType: "other" as const,
          snippet: "No evidence yet"
        }
      ],
      validationStatus: "unverified" as const,
      lastUpdated: new Date().toISOString()
    }
  ]);

  useEffect(() => {
    const listener = (msg: { type?: string; payload?: any }) => {
      if (msg.type === "backend_message") {
        setMessages((prev) => [...prev, `Agent: ${JSON.stringify(msg.payload)}`]);
      }
      if (msg.type === "page_detected") {
        setPage(msg.payload?.page ?? "unknown");
      }
    };

    chrome.runtime.onMessage.addListener(listener);
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, []);

  const sendMessage = (text: string) => {
    setMessages((prev) => [...prev, `You: ${text}`]);
    chrome.runtime.sendMessage({
      type: "chat_message",
      payload: {
        text,
        page
      }
    });
  };

  return (
    <main>
      <h2>IncomeTax Agent</h2>
      <DetectedDetailsPane page={page} />
      <ChatPane onSend={sendMessage} messages={messages} />
      <PendingActionsPane actions={["No pending write actions"]} />
      <EvidencePane facts={facts} />
    </main>
  );
}
