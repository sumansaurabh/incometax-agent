import React, { useEffect, useState } from "react";

import { EverificationRecord, FilingArtifacts, PurgeJob, SubmissionSummaryData } from "../backend";

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
  consents: Array<Record<string, unknown>>;
  purgeJobs: PurgeJob[];
  onGenerateSummary: () => void;
  onPrepareSubmit: () => void;
  onCompleteSubmission: (ackNo: string, portalRef: string) => void;
  onPrepareEVerify: (method: string) => void;
  onStartEVerify: (method: string) => void;
  onCompleteEVerify: (portalRef: string) => void;
  onAttachOfficialArtifact: (manualText: string, ackNo: string, portalRef: string, filedAt: string) => void;
  onCaptureOfficialArtifactPage: (ackNo: string, portalRef: string, filedAt: string) => void;
  onCreateRevision: (reason: string) => void;
  onRevokeConsent: (consentId: string) => void;
  onOpenArtifact: (artifactName: "itr-v" | "offline-json" | "evidence-bundle" | "summary") => void;
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
  consents,
  purgeJobs,
  onGenerateSummary,
  onPrepareSubmit,
  onCompleteSubmission,
  onPrepareEVerify,
  onStartEVerify,
  onCompleteEVerify,
  onAttachOfficialArtifact,
  onCaptureOfficialArtifactPage,
  onCreateRevision,
  onRevokeConsent,
  onOpenArtifact,
}: Props): JSX.Element {
  const [ackNo, setAckNo] = useState(artifacts?.ack_no ?? "");
  const [portalRef, setPortalRef] = useState(everification?.portal_ref ?? "");
  const [everifyMethod, setEverifyMethod] = useState(everification?.method ?? "aadhaar_otp");
  const [revisionReason, setRevisionReason] = useState("");
  const [officialArtifactText, setOfficialArtifactText] = useState("");
  const [officialFiledAt, setOfficialFiledAt] = useState(artifacts?.filed_at ?? "");

  useEffect(() => {
    setAckNo(artifacts?.ack_no ?? "");
  }, [artifacts?.ack_no]);

  useEffect(() => {
    setPortalRef(everification?.portal_ref ?? "");
  }, [everification?.portal_ref]);

  useEffect(() => {
    setEverifyMethod(everification?.method ?? "aadhaar_otp");
  }, [everification?.method]);

  useEffect(() => {
    setOfficialFiledAt(artifacts?.filed_at ?? "");
  }, [artifacts?.filed_at]);

  const officialItrvAttached = Boolean(
    artifacts?.artifact_manifest && typeof artifacts.artifact_manifest["official_itr_v_storage_uri"] === "string"
  );

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
          <p><button disabled={isBusy} onClick={() => onOpenArtifact("summary")}>Download summary</button></p>
          <p><button disabled={isBusy} onClick={() => onOpenArtifact("offline-json")}>Download offline JSON</button></p>
          <p><button disabled={isBusy} onClick={() => onOpenArtifact("evidence-bundle")}>Download evidence bundle</button></p>
          <p><button disabled={isBusy} onClick={() => onOpenArtifact("itr-v")}>{officialItrvAttached ? "Download official ITR-V" : "Download archived ITR-V bundle"}</button></p>
        </div>
      ) : null}

      {artifacts ? (
        <div>
          <h4>Official Portal Artifact</h4>
          <textarea
            rows={5}
            value={officialArtifactText}
            onChange={(event) => setOfficialArtifactText(event.target.value)}
            placeholder="Paste the official ITR-V or acknowledgement text from the portal"
          />
          <input value={officialFiledAt} onChange={(event) => setOfficialFiledAt(event.target.value)} placeholder="Filed at (optional ISO timestamp)" />
          <p>
            <button disabled={isBusy} onClick={() => onCaptureOfficialArtifactPage(ackNo, portalRef, officialFiledAt)}>
              Capture current portal page
            </button>
          </p>
          <p>
            <button
              disabled={isBusy || !officialArtifactText.trim()}
              onClick={() => onAttachOfficialArtifact(officialArtifactText, ackNo, portalRef, officialFiledAt)}
            >
              Attach pasted official artifact
            </button>
          </p>
          <p>
            {officialItrvAttached
              ? "Official ITR-V is attached and will be used for future downloads."
              : "Current ITR-V download is still the archived placeholder until an official artifact is attached."}
          </p>
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

      <div>
        <h4>Consents</h4>
        {consents.length === 0 ? <p>No persisted consents yet.</p> : null}
        <ul>
          {consents.map((consent) => {
            const consentId = String(consent.consent_id ?? consent.id ?? "");
            const revokedAt = consent.revoked_at ? String(consent.revoked_at) : null;
            return (
              <li key={consentId}>
                {String(consent.purpose ?? "unknown")} / {revokedAt ? `revoked ${revokedAt}` : "active"}
                {!revokedAt ? (
                  <button disabled={isBusy} onClick={() => onRevokeConsent(consentId)}>
                    Revoke and purge
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      </div>

      <div>
        <h4>Purge Jobs</h4>
        {purgeJobs.length === 0 ? <p>No purge jobs queued.</p> : null}
        <ul>
          {purgeJobs.map((job) => (
            <li key={job.job_id}>
              {job.reason} / {job.status}
            </li>
          ))}
        </ul>
      </div>

      {archived ? <p>Thread archived after verification.</p> : null}
    </section>
  );
}