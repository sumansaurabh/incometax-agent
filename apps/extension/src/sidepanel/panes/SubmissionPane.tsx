import React, { useEffect, useState } from "react";

import { EverificationRecord, FilingArtifacts, SubmissionSummaryData } from "../backend";

type Props = {
  submissionStatus: string;
  submissionSummary: SubmissionSummaryData | null;
  artifacts: FilingArtifacts | null;
  everification: EverificationRecord | null;
  archived: boolean;
  isBusy: boolean;
  submitApprovalApproved: boolean;
  everifyApprovalApproved: boolean;
  nextRevisionNumber: number;
  onGenerateSummary: () => void;
  onPrepareSubmit: () => void;
  onCompleteSubmission: (ackNo: string, portalRef: string) => void;
  onPrepareEVerify: (method: string) => void;
  onStartEVerify: (method: string) => void;
  onCompleteEVerify: (portalRef: string) => void;
  onCreateRevision: (reason: string) => void;
  getArtifactUrl: (artifactName: "itr-v" | "offline-json" | "evidence-bundle" | "summary") => string;
};

const EVERIFY_METHODS = [
  { value: "aadhaar_otp", label: "Aadhaar OTP" },
  { value: "net_banking", label: "Net Banking" },
  { value: "bank_atm", label: "Bank ATM / EVC" },
  { value: "demat", label: "Demat Account" },
  { value: "dsc", label: "DSC" },
  { value: "physical", label: "Physical ITR-V" },
];

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function SubmissionPane({
  submissionStatus,
  submissionSummary,
  artifacts,
  everification,
  archived,
  isBusy,
  submitApprovalApproved,
  everifyApprovalApproved,
  nextRevisionNumber,
  onGenerateSummary,
  onPrepareSubmit,
  onCompleteSubmission,
  onPrepareEVerify,
  onStartEVerify,
  onCompleteEVerify,
  onCreateRevision,
  getArtifactUrl,
}: Props): JSX.Element {
  const [ackNo, setAckNo] = useState(artifacts?.ack_no ?? "");
  const [portalRef, setPortalRef] = useState(everification?.portal_ref ?? "");
  const [everifyMethod, setEverifyMethod] = useState(everification?.method ?? "aadhaar_otp");
  const [revisionReason, setRevisionReason] = useState("");

  useEffect(() => {
    setAckNo(artifacts?.ack_no ?? "");
  }, [artifacts?.ack_no]);

  useEffect(() => {
    setPortalRef(everification?.portal_ref ?? "");
  }, [everification?.portal_ref]);

  useEffect(() => {
    setEverifyMethod(everification?.method ?? "aadhaar_otp");
  }, [everification?.method]);

  return (
    <section>
      <h3>Completion Flow</h3>
      <p>Status: {submissionStatus}</p>

      <button disabled={isBusy} onClick={onGenerateSummary}>
        Generate Submission Summary
      </button>

      {submissionSummary ? (
        <>
          <p>
            AY {submissionSummary.assessment_year} / {submissionSummary.itr_type} / {submissionSummary.regime}
          </p>
          <ul>
            <li>Gross total income: {formatCurrency(submissionSummary.gross_total_income)}</li>
            <li>Total deductions: {formatCurrency(submissionSummary.total_deductions)}</li>
            <li>Net liability: {formatCurrency(submissionSummary.net_tax_liability)}</li>
            <li>Refund due: {formatCurrency(submissionSummary.refund_due)}</li>
            <li>Tax payable: {formatCurrency(submissionSummary.tax_payable)}</li>
            <li>Mismatches: {submissionSummary.mismatch_count}</li>
          </ul>
          {submissionSummary.blocking_issues.length > 0 ? (
            <ul>
              {submissionSummary.blocking_issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          ) : null}
          <button disabled={isBusy || !submissionSummary.can_submit} onClick={onPrepareSubmit}>
            Request Submit Approval
          </button>
        </>
      ) : (
        <p>No submission summary generated yet.</p>
      )}

      <div>
        <h4>Manual Portal Submit</h4>
        <input value={ackNo} onChange={(event) => setAckNo(event.target.value)} placeholder="Acknowledgement number" />
        <input value={portalRef} onChange={(event) => setPortalRef(event.target.value)} placeholder="Portal reference" />
        <button disabled={isBusy || !submitApprovalApproved} onClick={() => onCompleteSubmission(ackNo, portalRef)}>
          I Completed Portal Submit
        </button>
      </div>

      {artifacts ? (
        <div>
          <h4>Filed Artifacts</h4>
          <ul>
            <li>Ack No: {artifacts.ack_no ?? "not provided"}</li>
            <li>Filed at: {artifacts.filed_at ?? "pending"}</li>
          </ul>
          <p><a href={getArtifactUrl("summary")} target="_blank" rel="noreferrer">Download summary</a></p>
          <p><a href={getArtifactUrl("offline-json")} target="_blank" rel="noreferrer">Download offline JSON</a></p>
          <p><a href={getArtifactUrl("evidence-bundle")} target="_blank" rel="noreferrer">Download evidence bundle</a></p>
          <p><a href={getArtifactUrl("itr-v")} target="_blank" rel="noreferrer">Download archived ITR-V bundle</a></p>
        </div>
      ) : null}

      <div>
        <h4>E-Verify</h4>
        <select value={everifyMethod} onChange={(event) => setEverifyMethod(event.target.value)}>
          {EVERIFY_METHODS.map((method) => (
            <option key={method.value} value={method.value}>{method.label}</option>
          ))}
        </select>
        <button disabled={isBusy || !artifacts} onClick={() => onPrepareEVerify(everifyMethod)}>
          Request E-Verify Approval
        </button>
        <button disabled={isBusy || !everifyApprovalApproved} onClick={() => onStartEVerify(everifyMethod)}>
          Start E-Verify Handoff
        </button>
        <button disabled={isBusy || !everification} onClick={() => onCompleteEVerify(portalRef)}>
          Mark E-Verify Complete
        </button>
        {everification ? (
          <p>
            Method: {everification.method} / Status: {everification.status}
          </p>
        ) : null}
      </div>

      <div>
        <h4>Revised Return</h4>
        <input
          value={revisionReason}
          onChange={(event) => setRevisionReason(event.target.value)}
          placeholder="Reason for revision"
        />
        <button disabled={isBusy || !revisionReason.trim()} onClick={() => onCreateRevision(revisionReason)}>
          Create Revision Branch #{nextRevisionNumber}
        </button>
      </div>

      {archived ? <p>Thread archived after verification.</p> : null}
    </section>
  );
}