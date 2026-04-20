import React, { useState } from "react";

/**
 * Evidence Viewer v1 — Phase 2 requirement
 * Per-fact drill-down: source document, page, snippet, confidence, extractor version
 */

type EvidenceSource = {
  documentId: string;
  documentName: string;
  documentType: "form16" | "ais" | "tis" | "form16a" | "bank_statement" | "other";
  pageNumber?: number;
  snippet?: string;
  boundingBox?: { x: number; y: number; width: number; height: number };
  thumbnailUrl?: string;
};

type TaxFact = {
  factId: string;
  fieldName: string;
  displayLabel: string;
  value: string | number;
  formattedValue: string;
  category: "income" | "deduction" | "tax_paid" | "personal" | "bank";
  confidence: number; // 0-1
  extractorVersion: string;
  sources: EvidenceSource[];
  validationStatus: "valid" | "warning" | "error" | "unverified";
  validationMessage?: string;
  lastUpdated: string;
  userOverride?: {
    originalValue: string | number;
    overrideReason: string;
    overrideTimestamp: string;
  };
};

type Props = {
  facts: TaxFact[];
  onFactSelect?: (fact: TaxFact) => void;
  onViewDocument?: (source: EvidenceSource) => void;
  onOverrideFact?: (factId: string, newValue: string | number, reason: string) => void;
};

// Confidence level thresholds
const CONFIDENCE_THRESHOLDS = {
  high: 0.9,
  medium: 0.7,
  low: 0.5,
};

function getConfidenceLevel(confidence: number): "high" | "medium" | "low" | "very-low" {
  if (confidence >= CONFIDENCE_THRESHOLDS.high) return "high";
  if (confidence >= CONFIDENCE_THRESHOLDS.medium) return "medium";
  if (confidence >= CONFIDENCE_THRESHOLDS.low) return "low";
  return "very-low";
}

function getConfidenceColor(level: string): string {
  switch (level) {
    case "high": return "#22c55e"; // green
    case "medium": return "#eab308"; // yellow
    case "low": return "#f97316"; // orange
    case "very-low": return "#ef4444"; // red
    default: return "#6b7280"; // gray
  }
}

function getValidationIcon(status: string): string {
  switch (status) {
    case "valid": return "✅";
    case "warning": return "⚠️";
    case "error": return "❌";
    default: return "❓";
  }
}

function getDocumentIcon(type: string): string {
  switch (type) {
    case "form16": return "📄";
    case "ais": return "🏛️";
    case "tis": return "📊";
    case "form16a": return "📋";
    case "bank_statement": return "🏦";
    default: return "📎";
  }
}

function ConfidenceMeter({ confidence }: { confidence: number }): JSX.Element {
  const level = getConfidenceLevel(confidence);
  const color = getConfidenceColor(level);
  const percentage = Math.round(confidence * 100);
  
  return (
    <div className="confidence-meter" title={`${percentage}% confidence`}>
      <div className="confidence-bar">
        <div 
          className="confidence-fill" 
          style={{ width: `${percentage}%`, backgroundColor: color }}
        />
      </div>
      <span className="confidence-label" style={{ color }}>
        {percentage}%
      </span>
    </div>
  );
}

function SourceCard({ 
  source, 
  onView 
}: { 
  source: EvidenceSource; 
  onView: () => void;
}): JSX.Element {
  return (
    <div className="source-card" onClick={onView}>
      <div className="source-header">
        <span className="source-icon">{getDocumentIcon(source.documentType)}</span>
        <span className="source-name">{source.documentName}</span>
        {source.pageNumber && (
          <span className="source-page">Page {source.pageNumber}</span>
        )}
      </div>
      {source.snippet && (
        <div className="source-snippet">
          <code>"{source.snippet}"</code>
        </div>
      )}
      {source.thumbnailUrl && (
        <img 
          src={source.thumbnailUrl} 
          alt="Document snippet" 
          className="source-thumbnail"
        />
      )}
    </div>
  );
}

function FactDetailModal({
  fact,
  onClose,
  onViewDocument,
  onOverride,
}: {
  fact: TaxFact;
  onClose: () => void;
  onViewDocument?: (source: EvidenceSource) => void;
  onOverride?: (factId: string, newValue: string | number, reason: string) => void;
}): JSX.Element {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(String(fact.value));
  const [editReason, setEditReason] = useState("");

  const handleSaveOverride = () => {
    if (onOverride && editReason.trim()) {
      onOverride(fact.factId, editValue, editReason);
      setIsEditing(false);
    }
  };

  return (
    <div className="fact-modal-overlay" onClick={onClose}>
      <div className="fact-modal" onClick={e => e.stopPropagation()}>
        <div className="fact-modal-header">
          <h3>{fact.displayLabel}</h3>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        
        <div className="fact-modal-body">
          {/* Value Section */}
          <div className="fact-section">
            <h4>Current Value</h4>
            {isEditing ? (
              <div className="edit-form">
                <input
                  type="text"
                  value={editValue}
                  onChange={e => setEditValue(e.target.value)}
                  className="edit-input"
                />
                <textarea
                  placeholder="Reason for override (required)"
                  value={editReason}
                  onChange={e => setEditReason(e.target.value)}
                  className="edit-reason"
                />
                <div className="edit-actions">
                  <button onClick={handleSaveOverride} disabled={!editReason.trim()}>
                    Save Override
                  </button>
                  <button onClick={() => setIsEditing(false)}>Cancel</button>
                </div>
              </div>
            ) : (
              <div className="value-display">
                <span className="value">{fact.formattedValue}</span>
                {onOverride && (
                  <button className="edit-btn" onClick={() => setIsEditing(true)}>
                    ✏️ Override
                  </button>
                )}
              </div>
            )}
            
            {fact.userOverride && (
              <div className="override-info">
                <span className="override-label">⚠️ User Override</span>
                <span>Original: {fact.userOverride.originalValue}</span>
                <span>Reason: {fact.userOverride.overrideReason}</span>
              </div>
            )}
          </div>

          {/* Confidence Section */}
          <div className="fact-section">
            <h4>Extraction Confidence</h4>
            <ConfidenceMeter confidence={fact.confidence} />
            <span className="extractor-version">
              Extractor v{fact.extractorVersion}
            </span>
          </div>

          {/* Validation Section */}
          <div className="fact-section">
            <h4>Validation Status</h4>
            <div className={`validation-status validation-${fact.validationStatus}`}>
              {getValidationIcon(fact.validationStatus)} {fact.validationStatus}
            </div>
            {fact.validationMessage && (
              <p className="validation-message">{fact.validationMessage}</p>
            )}
          </div>

          {/* Source Documents Section */}
          <div className="fact-section">
            <h4>Source Documents ({fact.sources.length})</h4>
            <div className="sources-list">
              {fact.sources.map((source, idx) => (
                <SourceCard
                  key={`${source.documentId}-${idx}`}
                  source={source}
                  onView={() => onViewDocument?.(source)}
                />
              ))}
            </div>
          </div>

          {/* Metadata Section */}
          <div className="fact-section metadata">
            <h4>Metadata</h4>
            <dl>
              <dt>Field ID</dt>
              <dd><code>{fact.factId}</code></dd>
              <dt>Category</dt>
              <dd>{fact.category}</dd>
              <dt>Last Updated</dt>
              <dd>{new Date(fact.lastUpdated).toLocaleString()}</dd>
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
}

function FactRow({
  fact,
  onSelect,
}: {
  fact: TaxFact;
  onSelect: () => void;
}): JSX.Element {
  const confidenceLevel = getConfidenceLevel(fact.confidence);
  
  return (
    <tr 
      className={`fact-row validation-${fact.validationStatus}`}
      onClick={onSelect}
    >
      <td className="fact-label">
        {getValidationIcon(fact.validationStatus)} {fact.displayLabel}
        {fact.userOverride && <span className="override-badge">⚡</span>}
      </td>
      <td className="fact-value">{fact.formattedValue}</td>
      <td className="fact-confidence">
        <span 
          className={`confidence-badge confidence-${confidenceLevel}`}
          style={{ backgroundColor: getConfidenceColor(confidenceLevel) }}
        >
          {Math.round(fact.confidence * 100)}%
        </span>
      </td>
      <td className="fact-sources">
        {fact.sources.map((s, i) => (
          <span key={i} title={s.documentName}>
            {getDocumentIcon(s.documentType)}
          </span>
        ))}
      </td>
    </tr>
  );
}

export function EvidencePane({ 
  facts, 
  onFactSelect,
  onViewDocument,
  onOverrideFact,
}: Props): JSX.Element {
  const [selectedFact, setSelectedFact] = useState<TaxFact | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [filterValidation, setFilterValidation] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState("");

  // Group facts by category
  const categories = [...new Set(facts.map(f => f.category))];
  
  // Filter facts
  const filteredFacts = facts.filter(fact => {
    if (filterCategory !== "all" && fact.category !== filterCategory) return false;
    if (filterValidation !== "all" && fact.validationStatus !== filterValidation) return false;
    if (searchTerm && !fact.displayLabel.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  // Stats
  const stats = {
    total: facts.length,
    valid: facts.filter(f => f.validationStatus === "valid").length,
    warnings: facts.filter(f => f.validationStatus === "warning").length,
    errors: facts.filter(f => f.validationStatus === "error").length,
    avgConfidence: facts.length > 0 
      ? Math.round(facts.reduce((sum, f) => sum + f.confidence, 0) / facts.length * 100)
      : 0,
  };

  const handleFactClick = (fact: TaxFact) => {
    setSelectedFact(fact);
    onFactSelect?.(fact);
  };

  return (
    <section className="evidence-pane">
      <header className="evidence-header">
        <h3>📊 Tax Facts Evidence</h3>
        <div className="evidence-stats">
          <span className="stat" title="Total facts">📝 {stats.total}</span>
          <span className="stat valid" title="Valid">✅ {stats.valid}</span>
          <span className="stat warning" title="Warnings">⚠️ {stats.warnings}</span>
          <span className="stat error" title="Errors">❌ {stats.errors}</span>
          <span className="stat confidence" title="Average confidence">
            🎯 {stats.avgConfidence}%
          </span>
        </div>
      </header>

      <div className="evidence-filters">
        <input
          type="text"
          placeholder="Search facts..."
          value={searchTerm}
          onChange={e => setSearchTerm(e.target.value)}
          className="search-input"
        />
        <select 
          value={filterCategory} 
          onChange={e => setFilterCategory(e.target.value)}
          className="filter-select"
        >
          <option value="all">All Categories</option>
          {categories.map(cat => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
        <select 
          value={filterValidation} 
          onChange={e => setFilterValidation(e.target.value)}
          className="filter-select"
        >
          <option value="all">All Status</option>
          <option value="valid">Valid</option>
          <option value="warning">Warnings</option>
          <option value="error">Errors</option>
          <option value="unverified">Unverified</option>
        </select>
      </div>

      <div className="evidence-table-container">
        <table className="evidence-table">
          <thead>
            <tr>
              <th>Fact</th>
              <th>Value</th>
              <th>Confidence</th>
              <th>Sources</th>
            </tr>
          </thead>
          <tbody>
            {filteredFacts.map(fact => (
              <FactRow
                key={fact.factId}
                fact={fact}
                onSelect={() => handleFactClick(fact)}
              />
            ))}
          </tbody>
        </table>
        
        {filteredFacts.length === 0 && (
          <div className="empty-state">
            No facts match your filters
          </div>
        )}
      </div>

      {selectedFact && (
        <FactDetailModal
          fact={selectedFact}
          onClose={() => setSelectedFact(null)}
          onViewDocument={onViewDocument}
          onOverride={onOverrideFact}
        />
      )}

      <style>{`
        .evidence-pane {
          padding: 12px;
          font-family: system-ui, -apple-system, sans-serif;
        }
        .evidence-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }
        .evidence-header h3 {
          margin: 0;
          font-size: 16px;
        }
        .evidence-stats {
          display: flex;
          gap: 8px;
          font-size: 12px;
        }
        .evidence-stats .stat {
          padding: 2px 6px;
          border-radius: 4px;
          background: #f3f4f6;
        }
        .evidence-filters {
          display: flex;
          gap: 8px;
          margin-bottom: 12px;
        }
        .search-input {
          flex: 1;
          padding: 6px 10px;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          font-size: 13px;
        }
        .filter-select {
          padding: 6px 10px;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          font-size: 13px;
        }
        .evidence-table-container {
          overflow-x: auto;
        }
        .evidence-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }
        .evidence-table th, .evidence-table td {
          padding: 8px;
          text-align: left;
          border-bottom: 1px solid #e5e7eb;
        }
        .evidence-table th {
          background: #f9fafb;
          font-weight: 600;
        }
        .fact-row {
          cursor: pointer;
          transition: background 0.15s;
        }
        .fact-row:hover {
          background: #f3f4f6;
        }
        .fact-row.validation-error {
          background: #fef2f2;
        }
        .fact-row.validation-warning {
          background: #fffbeb;
        }
        .override-badge {
          margin-left: 4px;
          font-size: 10px;
        }
        .confidence-badge {
          display: inline-block;
          padding: 2px 6px;
          border-radius: 10px;
          color: white;
          font-size: 11px;
          font-weight: 500;
        }
        .fact-sources {
          display: flex;
          gap: 4px;
        }
        .empty-state {
          padding: 24px;
          text-align: center;
          color: #6b7280;
        }
        
        /* Modal styles */
        .fact-modal-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }
        .fact-modal {
          background: white;
          border-radius: 8px;
          width: 90%;
          max-width: 500px;
          max-height: 80vh;
          overflow-y: auto;
          box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        }
        .fact-modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px;
          border-bottom: 1px solid #e5e7eb;
        }
        .fact-modal-header h3 {
          margin: 0;
          font-size: 16px;
        }
        .close-btn {
          background: none;
          border: none;
          font-size: 24px;
          cursor: pointer;
          color: #6b7280;
        }
        .fact-modal-body {
          padding: 16px;
        }
        .fact-section {
          margin-bottom: 16px;
        }
        .fact-section h4 {
          margin: 0 0 8px;
          font-size: 12px;
          text-transform: uppercase;
          color: #6b7280;
        }
        .value-display {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .value-display .value {
          font-size: 18px;
          font-weight: 600;
        }
        .edit-btn {
          padding: 4px 8px;
          font-size: 12px;
          background: #f3f4f6;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          cursor: pointer;
        }
        .confidence-meter {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .confidence-bar {
          flex: 1;
          height: 8px;
          background: #e5e7eb;
          border-radius: 4px;
          overflow: hidden;
        }
        .confidence-fill {
          height: 100%;
          transition: width 0.3s;
        }
        .confidence-label {
          font-size: 12px;
          font-weight: 600;
        }
        .extractor-version {
          font-size: 11px;
          color: #9ca3af;
          margin-top: 4px;
          display: block;
        }
        .validation-status {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 13px;
        }
        .validation-valid { background: #dcfce7; color: #166534; }
        .validation-warning { background: #fef9c3; color: #854d0e; }
        .validation-error { background: #fee2e2; color: #991b1b; }
        .validation-unverified { background: #f3f4f6; color: #4b5563; }
        .validation-message {
          margin-top: 8px;
          font-size: 13px;
          color: #6b7280;
        }
        .sources-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .source-card {
          padding: 10px;
          background: #f9fafb;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          cursor: pointer;
          transition: border-color 0.15s;
        }
        .source-card:hover {
          border-color: #3b82f6;
        }
        .source-header {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .source-icon {
          font-size: 16px;
        }
        .source-name {
          font-weight: 500;
        }
        .source-page {
          font-size: 11px;
          color: #6b7280;
          margin-left: auto;
        }
        .source-snippet {
          margin-top: 6px;
          font-size: 12px;
          color: #4b5563;
        }
        .source-snippet code {
          background: #e5e7eb;
          padding: 2px 4px;
          border-radius: 2px;
        }
        .source-thumbnail {
          margin-top: 8px;
          max-width: 100%;
          border-radius: 4px;
        }
        .metadata dl {
          display: grid;
          grid-template-columns: auto 1fr;
          gap: 4px 12px;
          font-size: 12px;
          margin: 0;
        }
        .metadata dt {
          color: #6b7280;
        }
        .metadata dd {
          margin: 0;
        }
        .metadata code {
          font-size: 11px;
          background: #f3f4f6;
          padding: 1px 4px;
          border-radius: 2px;
        }
        .edit-form {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .edit-input {
          padding: 8px;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          font-size: 14px;
        }
        .edit-reason {
          padding: 8px;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          font-size: 13px;
          min-height: 60px;
          resize: vertical;
        }
        .edit-actions {
          display: flex;
          gap: 8px;
        }
        .edit-actions button {
          padding: 6px 12px;
          border-radius: 4px;
          cursor: pointer;
        }
        .edit-actions button:first-child {
          background: #3b82f6;
          color: white;
          border: none;
        }
        .edit-actions button:first-child:disabled {
          background: #9ca3af;
        }
        .edit-actions button:last-child {
          background: white;
          border: 1px solid #d1d5db;
        }
        .override-info {
          margin-top: 8px;
          padding: 8px;
          background: #fef9c3;
          border-radius: 4px;
          font-size: 12px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .override-label {
          font-weight: 600;
        }
      `}</style>
    </section>
  );
}
