import React, { useEffect, useState } from "react";

import {
  NextAyChecklistRecord,
  NoticePreparationRecord,
  RefundStatusRecord,
  YearOverYearRecord,
} from "../backend";

type ManualRefundInput = {
  status: string;
  portalRef?: string;
  refundAmount?: string;
  issuedAt?: string;
  processedAt?: string;
  refundMode?: string;
  bankMasked?: string;
};

type Props = {
  currentPage: string;
  yearOverYear: YearOverYearRecord | null;
  nextAyChecklist: NextAyChecklistRecord | null;
  notices: NoticePreparationRecord[];
  refundStatus: RefundStatusRecord | null;
  isBusy: boolean;
  onGenerateYearOverYear: () => void;
  onGenerateNextAyChecklist: () => void;
  onPrepareNotice: (noticeText: string) => void;
  onCaptureRefundStatusPage: () => void;
  onSaveManualRefundStatus: (input: ManualRefundInput) => void;
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

function labelForMetric(key: string): string {
  return key.replace(/_/g, " ");
}

export function PostFilingPane({
  currentPage,
  yearOverYear,
  nextAyChecklist,
  notices,
  refundStatus,
  isBusy,
  onGenerateYearOverYear,
  onGenerateNextAyChecklist,
  onPrepareNotice,
  onCaptureRefundStatusPage,
  onSaveManualRefundStatus,
}: Props): JSX.Element {
  const [noticeText, setNoticeText] = useState("");
  const [manualRefundStatus, setManualRefundStatus] = useState(refundStatus?.status ?? "");
  const [manualPortalRef, setManualPortalRef] = useState(refundStatus?.portal_ref ?? "");
  const [manualRefundAmount, setManualRefundAmount] = useState(
    refundStatus?.refund_amount != null ? String(refundStatus.refund_amount) : ""
  );
  const [manualIssuedAt, setManualIssuedAt] = useState(refundStatus?.issued_at ?? "");
  const [manualProcessedAt, setManualProcessedAt] = useState(refundStatus?.processed_at ?? "");
  const [manualRefundMode, setManualRefundMode] = useState(refundStatus?.refund_mode ?? "");
  const [manualBankMasked, setManualBankMasked] = useState(refundStatus?.bank_masked ?? "");

  useEffect(() => {
    setManualRefundStatus(refundStatus?.status ?? "");
    setManualPortalRef(refundStatus?.portal_ref ?? "");
    setManualRefundAmount(refundStatus?.refund_amount != null ? String(refundStatus.refund_amount) : "");
    setManualIssuedAt(refundStatus?.issued_at ?? "");
    setManualProcessedAt(refundStatus?.processed_at ?? "");
    setManualRefundMode(refundStatus?.refund_mode ?? "");
    setManualBankMasked(refundStatus?.bank_masked ?? "");
  }, [refundStatus]);

  const latestNotice = notices[0] ?? null;

  return (
    <section>
      <h3>Post-Filing</h3>

      <div>
        <h4>Year-over-Year Comparison</h4>
        <button disabled={isBusy} onClick={onGenerateYearOverYear}>
          Generate Trend View
        </button>
        {yearOverYear ? (
          <>
            <p>
              Current AY {yearOverYear.current_assessment_year ?? "unknown"}
              {yearOverYear.prior_assessment_year ? ` / Prior AY ${yearOverYear.prior_assessment_year}` : " / No prior filing found"}
            </p>
            <p>
              Regime: {yearOverYear.comparison.regime.current}
              {yearOverYear.comparison.regime.prior ? ` / Prior ${yearOverYear.comparison.regime.prior}` : ""}
            </p>
            <ul>
              {Object.entries(yearOverYear.comparison.metrics).map(([key, value]) => (
                <li key={key}>
                  {labelForMetric(key)}: current {formatCurrency(value.current)} / prior {formatCurrency(value.prior)} / delta {formatCurrency(value.delta)}
                </li>
              ))}
            </ul>
            <ul>
              {yearOverYear.comparison.highlights.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          </>
        ) : (
          <p>No trend view generated yet.</p>
        )}
      </div>

      <div>
        <h4>Next-AY Readiness</h4>
        <button disabled={isBusy} onClick={onGenerateNextAyChecklist}>
          Build Next-AY Checklist
        </button>
        {nextAyChecklist ? (
          <>
            <p>{String(nextAyChecklist.summary.headline ?? `Checklist for AY ${nextAyChecklist.target_assessment_year}`)}</p>
            <ul>
              {nextAyChecklist.items.map((item) => (
                <li key={item.code}>
                  <strong>{item.title}</strong> / {item.priority} / {item.due_by}
                  <div>{item.reason}</div>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p>No proactive checklist generated yet.</p>
        )}
      </div>

      <div>
        <h4>Notice-Response Prep</h4>
        <textarea
          value={noticeText}
          onChange={(event) => setNoticeText(event.target.value)}
          placeholder="Paste the 143(1) intimation or notice text here"
          rows={8}
        />
        <button disabled={isBusy || !noticeText.trim()} onClick={() => onPrepareNotice(noticeText)}>
          Prepare Notice Explanation
        </button>
        {latestNotice ? (
          <>
            <p>
              Latest notice: {latestNotice.notice_type} / AY {latestNotice.assessment_year ?? "unknown"}
            </p>
            <pre>{latestNotice.explanation_md}</pre>
          </>
        ) : (
          <p>No notice explanation prepared yet.</p>
        )}
      </div>

      <div>
        <h4>Refund Status</h4>
        <p>Current portal page: {currentPage}</p>
        <button disabled={isBusy} onClick={onCaptureRefundStatusPage}>
          Capture Current Refund Status Page
        </button>
        <div>
          <input
            value={manualRefundStatus}
            onChange={(event) => setManualRefundStatus(event.target.value)}
            placeholder="Status"
          />
          <input value={manualPortalRef} onChange={(event) => setManualPortalRef(event.target.value)} placeholder="Reference" />
          <input
            value={manualRefundAmount}
            onChange={(event) => setManualRefundAmount(event.target.value)}
            placeholder="Refund amount"
          />
          <input value={manualIssuedAt} onChange={(event) => setManualIssuedAt(event.target.value)} placeholder="Issued at" />
          <input
            value={manualProcessedAt}
            onChange={(event) => setManualProcessedAt(event.target.value)}
            placeholder="Processed at"
          />
          <input value={manualRefundMode} onChange={(event) => setManualRefundMode(event.target.value)} placeholder="Refund mode" />
          <input value={manualBankMasked} onChange={(event) => setManualBankMasked(event.target.value)} placeholder="Bank account" />
          <button
            disabled={isBusy || !manualRefundStatus.trim()}
            onClick={() =>
              onSaveManualRefundStatus({
                status: manualRefundStatus,
                portalRef: manualPortalRef,
                refundAmount: manualRefundAmount,
                issuedAt: manualIssuedAt,
                processedAt: manualProcessedAt,
                refundMode: manualRefundMode,
                bankMasked: manualBankMasked,
              })
            }
          >
            Save Manual Refund Status
          </button>
        </div>
        {refundStatus ? (
          <ul>
            <li>Status: {refundStatus.status}</li>
            <li>Amount: {refundStatus.refund_amount != null ? formatCurrency(refundStatus.refund_amount) : "unknown"}</li>
            <li>Reference: {refundStatus.portal_ref ?? "not recorded"}</li>
            <li>Mode: {refundStatus.refund_mode ?? "not recorded"}</li>
            <li>Bank: {refundStatus.bank_masked ?? "not recorded"}</li>
            <li>Source: {refundStatus.source}</li>
          </ul>
        ) : (
          <p>No refund status captured yet.</p>
        )}
      </div>
    </section>
  );
}