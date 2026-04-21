import React from "react";

type SupportReason = {
  code: string;
  title: string;
  detail: string;
  severity: string;
};

type ReviewHandoff = {
  handoff_id: string;
  support_mode: string;
  status: string;
  created_at?: string | null;
};

type SupportAssessment = {
  mode: string;
  can_autofill: boolean;
  can_submit: boolean;
  reasons: SupportReason[];
  checklist: string[];
  handoffs: ReviewHandoff[];
  security_status?: {
    quarantined: boolean;
    reason?: string | null;
    quarantined_at?: string | null;
  };
};

type Props = {
  supportAssessment: SupportAssessment | null;
  isBusy: boolean;
  onPrepareHandoff: () => void;
  onOpenHandoff: (handoffId: string) => void;
  onResumeQuarantine: () => void;
};

function modeLabel(mode: string): string {
  if (mode === "ca-handoff") return "CA handoff required";
  if (mode === "guided-checklist") return "Guided checklist mode";
  return "Assisted mode";
}

export function SupportPane({ supportAssessment, isBusy, onPrepareHandoff, onOpenHandoff, onResumeQuarantine }: Props): JSX.Element {
  if (!supportAssessment) {
    return <section><h3>Support Status</h3><p>Loading support assessment…</p></section>;
  }

  return (
    <section>
      <h3>Support Status</h3>
      <p>{modeLabel(supportAssessment.mode)}</p>
      <p>Autofill: {supportAssessment.can_autofill ? "allowed" : "paused"}</p>
      <p>Submit: {supportAssessment.can_submit ? "allowed" : "paused"}</p>
      {supportAssessment.security_status?.quarantined ? (
        <>
          <p>Thread quarantine is active.</p>
          <button disabled={isBusy} onClick={onResumeQuarantine}>
            Resume automation after review
          </button>
        </>
      ) : null}

      {supportAssessment.reasons.length > 0 ? (
        <>
          <h4>Why This Needs Review</h4>
          <ul>
            {supportAssessment.reasons.map((reason) => (
              <li key={reason.code}>
                <strong>{reason.title}:</strong> {reason.detail}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p>No unsupported-flow flags are active for this thread.</p>
      )}

      <h4>Checklist</h4>
      <ul>
        {supportAssessment.checklist.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>

      <button disabled={isBusy || supportAssessment.mode === "supported"} onClick={onPrepareHandoff}>
        Prepare CA handoff package
      </button>

      {supportAssessment.handoffs.length > 0 ? (
        <>
          <h4>Prepared Handoffs</h4>
          <ul>
            {supportAssessment.handoffs.map((handoff) => (
              <li key={handoff.handoff_id}>
                {handoff.support_mode} / {handoff.status} / {handoff.created_at ? new Date(handoff.created_at).toLocaleString() : "pending"}
                <button disabled={isBusy} onClick={() => onOpenHandoff(handoff.handoff_id)}>
                  Open package
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}