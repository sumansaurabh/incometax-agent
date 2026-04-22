import assert from "node:assert/strict";
import test from "node:test";

import { buildCADashboardModel } from "./ca-dashboard";

test("buildCADashboardModel aggregates queue and alert state", () => {
  const result = buildCADashboardModel(
    [
      {
        threadId: "thread-1",
        name: "Alice",
        canSubmit: false,
        blockingIssues: ["Need Schedule FA review"],
        pendingApprovalCount: 1,
        pendingSignoffCount: 1,
        mismatchCount: 2,
        supportMode: "ca-handoff",
      },
      {
        threadId: "thread-2",
        name: "Bob",
        canSubmit: true,
        blockingIssues: [],
        pendingApprovalCount: 0,
        pendingSignoffCount: 0,
        mismatchCount: 0,
        supportMode: "supported",
      },
    ],
    {
      operations: {
        replay: { totals: { success_rate: 0.82 } },
        drift: { total_events: 3 },
        tracing: { backend: "langfuse", ai_provider: "openai" },
        agent_observability: { recent_failures: [{ thread_id: "thread-1", node_name: "fill_plan" }] },
        runtime_health: { status: "degraded" },
      },
    },
  );

  assert.equal(result.overview.totalClients, 2);
  assert.equal(result.queues.pendingApprovals, 1);
  assert.equal(result.operations.tracingBackend, "langfuse");
  assert.equal(result.operations.aiProvider, "openai");
  assert.ok(result.operations.alerts.length >= 3);
  assert.equal(result.clients[0].risk, "high");
});