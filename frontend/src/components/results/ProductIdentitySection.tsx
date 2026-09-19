import React, { useState } from 'react';
import type { 
  ProductIdentity, 
  FieldEvidenceItem,
  ExternalProductVerificationPipelineResult
} from '../../types';
import { 
  ShieldCheck, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle, 
  QrCode, 
  Barcode, 
  Building, 
  Tag, 
  Calendar, 
  PhoneCall, 
  Utensils, 
  ChevronDown, 
  ChevronUp, 
  AlertOctagon, 
  FileText,
  Eye,
  Layers,
  Database,
  Info,
  ExternalLink,
  Copy,
  Check
} from 'lucide-react';

interface Props {
  identity?: ProductIdentity | null;
  externalProductVerification?: ExternalProductVerificationPipelineResult | null;
  onSelectEvidence?: (fieldKey: string, bbox?: number[] | null, imageLabel?: string | null) => void;
}

export const renderPipelineStatusBadge = (status?: string | null) => {
  if (!status) return null;
  const s = status.toUpperCase();
  switch (s) {
    case 'EXTERNALLY_VERIFIED':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
          <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-600" />
          EXTERNALLY VERIFIED
        </span>
      );
    case 'FORMAT_VALID':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-500" />
          FORMAT VALID
        </span>
      );
    case 'OCR_DETECTED':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
          <FileText className="w-3 h-3 mr-1 text-blue-600" />
          OCR DETECTED
        </span>
      );
    case 'EXTERNAL_DATA_NOT_FOUND':
    case 'NOT_FOUND':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
          <AlertTriangle className="w-3 h-3 mr-1 text-amber-600" />
          DATA NOT FOUND
        </span>
      );
    case 'EXTERNAL_LOOKUP_FAILED':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800 border border-red-300">
          <AlertOctagon className="w-3 h-3 mr-1 text-red-600" />
          LOOKUP FAILED
        </span>
      );
    case 'EXTERNAL_VERIFICATION_UNAVAILABLE':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700 border border-slate-300" title="External verification unavailable; legal metrology compliance is unaffected">
          <AlertTriangle className="w-3 h-3 mr-1 text-slate-500" />
          VERIFICATION UNAVAILABLE
        </span>
      );
    case 'MATCH':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-600" />
          MATCH
        </span>
      );
    case 'MISMATCH':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-red-100 text-red-800 border border-red-200">
          <XCircle className="w-3 h-3 mr-1 text-red-600" />
          MISMATCH
        </span>
      );
    case 'NOT_COMPARABLE':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
          NOT COMPARABLE
        </span>
      );
    case 'NOT_AVAILABLE':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200">
          NOT AVAILABLE
        </span>
      );
    case 'NOT_VERIFIED':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200">
          NOT VERIFIED
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
          {status}
        </span>
      );
  }
};

export const ProductIdentitySection: React.FC<Props> = ({ 
  identity, 
  externalProductVerification,
  onSelectEvidence 
}) => {
  const [showAllFields, setShowAllFields] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'all' | 'layers' | 'identity'>('all');
  const [copiedFssai, setCopiedFssai] = useState<boolean>(false);
  const [copiedBarcode, setCopiedBarcode] = useState<boolean>(false);

  const copyToClipboard = (text: string, type: 'fssai' | 'barcode') => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text);
    }
    if (type === 'fssai') {
      setCopiedFssai(true);
      setTimeout(() => setCopiedFssai(false), 2000);
    } else {
      setCopiedBarcode(true);
      setTimeout(() => setCopiedBarcode(false), 2000);
    }
  };

  if (!identity && !externalProductVerification) {
    return null;
  }

  const cv = identity?.cross_validation;
  const hasConflicts = cv?.has_conflicts || (cv?.conflicts && cv.conflicts.length > 0);
  const conflicts = cv?.conflicts || [];
  const isFood = identity?.food_declarations?.is_food;

  const epv = externalProductVerification;
  const fExt = epv?.fssai_extraction;
  const extFssai = epv?.external_fssai;
  const bcExts = epv?.barcode_extractions || [];
  const primaryBc = bcExts[0];
  const extProd = epv?.external_product;
  const comparisons = epv?.cross_source_comparisons || [];

  const getStatusBadge = (field?: FieldEvidenceItem | null, isConflicted: boolean = false) => {
    if (!field) return null;

    if (isConflicted || field.status === 'REVIEW_REQUIRED' || field.status === 'VERIFICATION_FAILED') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800 border border-red-200">
          <AlertTriangle className="w-3 h-3 mr-1 text-red-600" />
          {field.status === 'REVIEW_REQUIRED' ? 'Review Required' : field.status === 'VERIFICATION_FAILED' ? 'Verification Failed' : 'Conflict'}
        </span>
      );
    }
    if (field.status === 'VERIFIED') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-600" />
          Verified
        </span>
      );
    }
    if (field.status === 'FOUND') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
          <CheckCircle2 className="w-3 h-3 mr-1 text-blue-600" />
          Detected
        </span>
      );
    }
    if (field.status === 'LOW_CONFIDENCE') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200">
          <AlertTriangle className="w-3 h-3 mr-1 text-amber-600" />
          Low Conf ({Math.round(field.confidence || 0)}%)
        </span>
      );
    }
    if (field.status === 'NOT_APPLICABLE') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
          N/A (Non-Food)
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200">
        <XCircle className="w-3 h-3 mr-1 text-slate-400" />
        Not Found
      </span>
    );
  };

  const renderProvenanceBadge = (label?: string | null) => {
    const norm = (label || '').toLowerCase();
    if (norm.includes('externally verified') || norm.includes('active')) {
      return (
        <span className="text-[10px] font-bold px-1.5 py-0.5 bg-emerald-100 text-emerald-800 rounded border border-emerald-200 inline-flex items-center">
          <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-600" />
          Externally verified
        </span>
      );
    }
    if (norm.includes('extracted from package') || norm.includes('detected') || norm.includes('label declared')) {
      return (
        <span className="text-[10px] font-medium px-1.5 py-0.5 bg-blue-100 text-blue-800 rounded border border-blue-200 inline-flex items-center">
          <CheckCircle2 className="w-3 h-3 mr-1 text-blue-600" />
          Extracted from package
        </span>
      );
    }
    if (norm.includes('unavailable') || norm.includes('unconfigured')) {
      return (
        <span className="text-[10px] font-medium px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded border border-amber-200 inline-flex items-center">
          <AlertTriangle className="w-3 h-3 mr-1 text-amber-600" />
          Verification unavailable
        </span>
      );
    }
    return (
      <span className="text-[10px] font-medium px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded inline-flex items-center">
        <XCircle className="w-3 h-3 mr-1 text-slate-400" />
        Not found
      </span>
    );
  };

  const renderFieldRow = (
    label: string, 
    field?: FieldEvidenceItem | null, 
    extraAction?: React.ReactNode,
    fieldKey?: string
  ) => {
    const isConflicted = conflicts.some(c => 
      c.field_name.toLowerCase().includes(label.toLowerCase()) || 
      (field?.value && (c.value_a.includes(field.value) || c.value_b.includes(field.value)))
    );

    const hasValue = Boolean(field?.value && field.value.trim());

    return (
      <div 
        className={`flex items-start justify-between py-2 border-b border-slate-100 last:border-b-0 transition-colors ${
          isConflicted ? 'bg-red-50/70 px-2 rounded-md -mx-2' : ''
        }`}
      >
        <div className="flex-1 pr-3">
          <div className="flex items-center space-x-1.5">
            <span className="text-xs font-medium text-slate-600">{label}</span>
            {getStatusBadge(field, isConflicted)}
          </div>
          <div className="mt-0.5">
            {hasValue ? (
              <span className={`text-sm ${isConflicted ? 'font-semibold text-red-900' : 'text-slate-900 font-medium'}`}>
                {field?.value}
              </span>
            ) : (
              <span className="text-xs text-slate-400 italic">
                {field?.status === 'NOT_APPLICABLE' ? 'Not applicable for this product category' : 'Not detected on package label'}
              </span>
            )}
          </div>
          {field?.explanation && (
            <p className="text-[11px] text-slate-500 mt-0.5">{field.explanation}</p>
          )}
        </div>

        <div className="flex items-center space-x-2 pt-0.5">
          {field?.bounding_box && onSelectEvidence && (
            <button
              onClick={() => onSelectEvidence(fieldKey || label, field.bounding_box, field.image_id)}
              className="px-1.5 py-0.5 text-[11px] font-medium text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 rounded border border-indigo-200 transition-colors inline-flex items-center gap-1"
              title="Locate visual evidence on packaging"
            >
              <Eye className="w-3 h-3" />
              Locate
            </button>
          )}
          {extraAction}
        </div>
      </div>
    );
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-8">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-6 h-6 text-indigo-600" />
            <h2 className="text-lg font-bold text-slate-900">
              Intelligent Product Identity & Multi-Source Verification
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Automated statutory aggregation, 1D/2D symbology decoding, FSSAI verification & cross-evidence validation.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Image Quality Badge */}
          {identity?.image_quality_status === 'REVIEW_REQUIRED' ? (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
              <AlertTriangle className="w-3.5 h-3.5 mr-1 text-amber-600" />
              Image Quality: Review Required
            </span>
          ) : identity?.image_quality_status ? (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
              <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-600" />
              Image Quality: Clear
            </span>
          ) : null}

          {/* Pipeline / Conflict Status */}
          {epv ? (
            renderPipelineStatusBadge(epv.overall_pipeline_status)
          ) : hasConflicts ? (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-300 animate-pulse">
              <AlertOctagon className="w-3.5 h-3.5 mr-1 text-red-600" />
              Data Conflicts Detected ({conflicts.length})
            </span>
          ) : (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
              <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-600" />
              Sources Consistent
            </span>
          )}
        </div>
      </div>

      {/* View Switcher Tabs (if epv present) */}
      {epv && (
        <div className="flex items-center space-x-2 mt-4 pb-2 border-b border-slate-100">
          <button
            onClick={() => setActiveTab('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === 'all' 
                ? 'bg-indigo-600 text-white shadow-xs' 
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            All Verification Views
          </button>
          <button
            onClick={() => setActiveTab('layers')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold inline-flex items-center gap-1.5 transition-colors ${
              activeTab === 'layers' 
                ? 'bg-indigo-600 text-white shadow-xs' 
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            3-Layer External Verification Dossier
          </button>
          {identity && (
            <button
              onClick={() => setActiveTab('identity')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                activeTab === 'identity' 
                  ? 'bg-indigo-600 text-white shadow-xs' 
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              Identity Declarations
            </button>
          )}
        </div>
      )}

      {/* Image Quality Warning Banner */}
      {identity?.quality_reasons && identity.quality_reasons.length > 0 && (
        <div className="mt-4 p-3.5 bg-amber-50 rounded-lg border border-amber-200 text-xs text-amber-900 flex items-start space-x-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold">Image Capture Notice:</span>{' '}
            {identity.quality_reasons.join(' | ')}. Fine statutory declarations should be physically verified.
          </div>
        </div>
      )}

      {/* Conflict Resolution Banner */}
      {hasConflicts && (
        <div className="mt-4 p-4 bg-red-50 rounded-lg border border-red-200">
          <div className="flex items-center space-x-2 text-red-900 font-bold text-sm mb-2">
            <AlertOctagon className="w-4 h-4 text-red-600" />
            <span>Cross-Source Discrepancies Requiring Review</span>
          </div>
          <div className="space-y-2.5">
            {conflicts.map((c, i) => (
              <div key={i} className="p-2.5 bg-white/80 rounded border border-red-200 text-xs">
                <div className="flex items-center justify-between font-semibold text-red-900">
                  <span>{c.field_name} Conflict ({c.severity} Severity)</span>
                  <span className="text-[10px] px-1.5 py-0.5 bg-red-100 text-red-700 rounded uppercase">
                    Requires Human Signoff
                  </span>
                </div>
                <p className="text-slate-700 mt-1">{c.description}</p>
                <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  <div className="bg-slate-50 p-1.5 rounded border border-slate-200">
                    <span className="text-[11px] font-semibold text-slate-500">{c.source_a}:</span>{' '}
                    <span className="font-bold text-slate-900">{c.value_a}</span>
                  </div>
                  <div className="bg-slate-50 p-1.5 rounded border border-slate-200">
                    <span className="text-[11px] font-semibold text-slate-500">{c.source_b}:</span>{' '}
                    <span className="font-bold text-red-700">{c.value_b}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* THREE-LAYER EXTERNAL VERIFICATION DOSSIER                     */}
      {/* ══════════════════════════════════════════════════════════════ */}
      {epv && (activeTab === 'all' || activeTab === 'layers') && (
        <div className="mt-6 p-5 bg-gradient-to-br from-slate-50 to-indigo-50/20 rounded-xl border border-indigo-100/80 shadow-xs space-y-6">
          <div className="flex items-center justify-between pb-3 border-b border-indigo-100">
            <div className="flex items-center space-x-2">
              <Layers className="w-5 h-5 text-indigo-600" />
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
                  External Product & Licence Verification Pipeline
                </h3>
                <p className="text-[11px] text-slate-500">
                  Three distinct audit layers: Package OCR Data, External Master Registries, and Cross-Source Comparison.
                </p>
              </div>
            </div>
            <div>
              {renderPipelineStatusBadge(epv.overall_pipeline_status)}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* LAYER 1: Package OCR Data */}
            <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-2xs">
              <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-100">
                <div className="flex items-center space-x-2">
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-blue-100 text-blue-800">
                    LAYER 1
                  </span>
                  <h4 className="text-xs font-bold text-slate-800 uppercase">Package OCR Data</h4>
                </div>
                <span className="text-[10px] text-slate-500 font-medium">Extracted from physical package</span>
              </div>

              {/* FSSAI Package OCR Details */}
              <div className="mb-3.5 p-2.5 bg-slate-50/80 rounded-md border border-slate-200">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-slate-700 flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5 text-indigo-600" />
                    FSSAI Number (Label Declared)
                  </span>
                  {fExt?.bounding_box && onSelectEvidence && (
                    <button
                      onClick={() => onSelectEvidence('fssai_license', fExt.bounding_box)}
                      className="px-2 py-0.5 text-[11px] font-medium text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 rounded border border-indigo-200 transition-colors inline-flex items-center gap-1"
                      title="Locate FSSAI number on package"
                    >
                      <Eye className="w-3 h-3" />
                      Locate
                    </button>
                  )}
                </div>
                <div className="mt-1 flex items-baseline justify-between">
                  <span className="font-mono text-sm font-bold text-slate-900">
                    {fExt?.number || identity?.fssai_license_number?.value || 'Not detected'}
                  </span>
                  {fExt && renderPipelineStatusBadge(fExt.format_valid ? 'FORMAT_VALID' : 'OCR_DETECTED')}
                </div>
                {fExt && (
                  <div className="mt-1.5 grid grid-cols-2 gap-1 text-[10px] text-slate-500 pt-1.5 border-t border-slate-200">
                    <span>OCR Conf: <b>{Math.round(fExt.confidence * 100)}%</b></span>
                    <span>State: <b>{fExt.state_name || 'N/A'}</b></span>
                  </div>
                )}
              </div>

              {/* Barcode Package OCR Details */}
              <div className="p-2.5 bg-slate-50/80 rounded-md border border-slate-200">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-slate-700 flex items-center gap-1">
                    <Barcode className="w-3.5 h-3.5 text-indigo-600" />
                    Decoded Barcode / GTIN
                  </span>
                  {primaryBc?.bounding_box && onSelectEvidence && (
                    <button
                      onClick={() => onSelectEvidence('barcode', primaryBc.bounding_box)}
                      className="px-2 py-0.5 text-[11px] font-medium text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 rounded border border-indigo-200 transition-colors inline-flex items-center gap-1"
                      title="Locate barcode on package"
                    >
                      <Eye className="w-3 h-3" />
                      Locate
                    </button>
                  )}
                </div>
                <div className="mt-1 flex items-baseline justify-between">
                  <span className="font-mono text-sm font-bold text-slate-900">
                    {primaryBc?.value || identity?.barcode_gtin || 'Not detected'}
                  </span>
                  {primaryBc && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-slate-200 text-slate-800 rounded font-medium">
                      {primaryBc.type}
                    </span>
                  )}
                </div>
                {primaryBc && (
                  <div className="mt-1.5 flex items-center justify-between text-[10px] text-slate-500 pt-1.5 border-t border-slate-200">
                    <span>Origin: <b>{primaryBc.country_of_origin || 'India'}</b></span>
                    <span className={primaryBc.checksum_valid ? 'text-emerald-600 font-bold' : 'text-slate-600'}>
                      {primaryBc.checksum_valid ? 'Valid Checksum' : 'Format Checked'}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* LAYER 2: External Verification Data */}
            <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-2xs">
              <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-100">
                <div className="flex items-center space-x-2">
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-emerald-100 text-emerald-800">
                    LAYER 2
                  </span>
                  <h4 className="text-xs font-bold text-slate-800 uppercase">External Verification Data</h4>
                </div>
                <span className="text-[10px] text-slate-500 font-medium">Authoritative External Registries</span>
              </div>

              {/* FSSAI Live Registry Findings */}
              <div className="mb-3.5 p-2.5 bg-slate-50/80 rounded-md border border-slate-200">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] font-bold text-slate-700 flex items-center gap-1">
                    <Database className="w-3.5 h-3.5 text-emerald-600" />
                    FoSCoS Licence Registry
                  </span>
                  {extFssai && renderPipelineStatusBadge(extFssai.status)}
                </div>
                {extFssai?.status === 'EXTERNALLY_VERIFIED' ? (
                  <div className="space-y-1 text-xs mt-2">
                    <div className="text-slate-900 font-bold">{extFssai.business_name}</div>
                    {extFssai.registered_address && (
                      <div className="text-[11px] text-slate-600">{extFssai.registered_address}</div>
                    )}
                    <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-200">
                      <span>Status: <b className="text-emerald-700">{extFssai.licence_status || 'Active'}</b></span>
                      {extFssai.valid_upto && <span>Valid Upto: <b>{extFssai.valid_upto}</b></span>}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2 mt-1">
                    <p className="text-[11px] text-slate-500">
                      {extFssai?.failure_reason || (extFssai?.status === 'EXTERNAL_VERIFICATION_UNAVAILABLE' 
                        ? 'FoSCoS registry automated verification is unconfigured or blocked by portal CAPTCHA. Legal Metrology declarations remain valid.' 
                        : 'No live external licence record retrieved.')}
                    </p>

                    {/* Manual Fallback Verification Box */}
                    <div className="p-2 bg-amber-50/80 border border-amber-200 rounded text-[11px] text-amber-900 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-amber-950 flex items-center gap-1 text-[11px]">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                          Manual Verification on FoSCoS
                        </span>
                        {fExt?.number && (
                          <button
                            onClick={() => copyToClipboard(fExt.number!, 'fssai')}
                            className="px-1.5 py-0.5 text-[10px] font-medium bg-amber-100 hover:bg-amber-200 text-amber-800 rounded border border-amber-300 inline-flex items-center gap-1 transition-colors"
                            title="Copy licence number to clipboard"
                          >
                            {copiedFssai ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                            {copiedFssai ? 'Copied' : 'Copy Number'}
                          </button>
                        )}
                      </div>
                      <p className="text-[10px] text-amber-800 leading-tight">
                        Verify this licence manually on the official Government of India FoSCoS portal:
                      </p>
                      <a
                        href={extFssai?.manual_verification_url || "https://foscos.fssai.gov.in"}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-700 hover:text-indigo-900 underline"
                      >
                        <span>Official FoSCoS Portal (foscos.fssai.gov.in)</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                )}
                <div className="mt-1.5 flex items-center justify-between text-[9px] text-slate-400">
                  <span>Source: {extFssai?.source || 'FoSCoS Official Registry API'}</span>
                  <span>Provenance: <b className="text-slate-600">{extFssai?.provenance || (extFssai?.status === 'EXTERNALLY_VERIFIED' ? 'REAL_EXTERNAL' : 'UNAVAILABLE')}</b></span>
                </div>
              </div>

              {/* GS1 Master Product Data */}
              <div className="p-2.5 bg-slate-50/80 rounded-md border border-slate-200">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] font-bold text-slate-700 flex items-center gap-1">
                    <Database className="w-3.5 h-3.5 text-blue-600" />
                    GS1 India / DataKart Master Data
                  </span>
                  {extProd && renderPipelineStatusBadge(extProd.status)}
                </div>
                {extProd?.status === 'EXTERNALLY_VERIFIED' ? (
                  <div className="space-y-1 text-xs mt-2">
                    <div className="text-slate-900 font-bold">{extProd.product_name}</div>
                    <div className="text-[11px] text-slate-700">
                      Brand: <b>{extProd.brand || '—'}</b> | Mfr: <b>{extProd.manufacturer || '—'}</b>
                    </div>
                    {extProd.net_quantity && (
                      <div className="text-[10px] text-slate-600">Net Quantity: <b>{extProd.net_quantity}</b></div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-2 mt-1">
                    <p className="text-[11px] text-slate-500">
                      {extProd?.failure_reason || (extProd?.status === 'EXTERNAL_VERIFICATION_UNAVAILABLE' 
                        ? 'GS1 registry lookup is unconfigured or offline. Barcode is validated via Mod-10 checksum.' 
                        : 'No external product catalog record retrieved.')}
                    </p>

                    {/* Manual Fallback Verification Box */}
                    <div className="p-2 bg-blue-50/80 border border-blue-200 rounded text-[11px] text-blue-900 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-blue-950 flex items-center gap-1 text-[11px]">
                          <Info className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                          Manual Verification on GS1
                        </span>
                        {primaryBc?.value && (
                          <button
                            onClick={() => copyToClipboard(primaryBc.value, 'barcode')}
                            className="px-1.5 py-0.5 text-[10px] font-medium bg-blue-100 hover:bg-blue-200 text-blue-800 rounded border border-blue-300 inline-flex items-center gap-1 transition-colors"
                            title="Copy GTIN to clipboard"
                          >
                            {copiedBarcode ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                            {copiedBarcode ? 'Copied' : 'Copy GTIN'}
                          </button>
                        )}
                      </div>
                      <p className="text-[10px] text-blue-800 leading-tight">
                        Verify this GTIN barcode manually on the official GS1 India portal:
                      </p>
                      <a
                        href={extProd?.manual_verification_url || "https://www.gs1india.org"}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-700 hover:text-indigo-900 underline"
                      >
                        <span>Official GS1 Portal (gs1india.org)</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                )}
                <div className="mt-1.5 flex items-center justify-between text-[9px] text-slate-400">
                  <span>Source: {extProd?.source || 'GS1 India DataKart / Verified Registry'}</span>
                  <span>Provenance: <b className="text-slate-600">{extProd?.provenance || (extProd?.status === 'EXTERNALLY_VERIFIED' ? 'REAL_EXTERNAL' : 'UNAVAILABLE')}</b></span>
                </div>
              </div>
            </div>
          </div>

          {/* LAYER 3: Cross-Source Comparison Table */}
          <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-2xs">
            <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-purple-100 text-purple-800">
                  LAYER 3
                </span>
                <h4 className="text-xs font-bold text-slate-800 uppercase">
                  Cross-Source Verification (Package OCR vs External Master Data)
                </h4>
              </div>
              <span className="text-[10px] text-slate-500 font-medium">Automated Consistency Evaluation</span>
            </div>

            {comparisons.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-bold">
                      <th className="py-2 px-3">Field</th>
                      <th className="py-2 px-3">Package (OCR) Value</th>
                      <th className="py-2 px-3">External Source Value</th>
                      <th className="py-2 px-3 text-center">Comparison Result</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {comparisons.map((c, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-2 px-3 font-semibold text-slate-800">{c.field}</td>
                        <td className="py-2 px-3 text-slate-700 font-mono text-[11px]">{c.package_value || '—'}</td>
                        <td className="py-2 px-3 text-slate-700 font-mono text-[11px]">{c.external_value || '—'}</td>
                        <td className="py-2 px-3 text-center">
                          {renderPipelineStatusBadge(c.result)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-3 px-4 bg-slate-50 rounded text-center text-xs text-slate-500">
                External lookup was unavailable or returned no comparable fields. Package OCR declarations are evaluated independently.
              </div>
            )}

            {/* Legal Limitations Notice */}
            <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-start gap-2 text-[11px] text-slate-500 italic">
              <Info className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
              <span>
                Notice: External verification depends on registry availability. Unverified status does not imply non-compliance or counterfeit status.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* 6 MODULAR IDENTITY CARDS                                      */}
      {/* ══════════════════════════════════════════════════════════════ */}
      {identity && (activeTab === 'all' || activeTab === 'identity') && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mt-6">
          
          {/* 1. Product & Brand Card */}
          <div className="bg-slate-50/70 rounded-lg p-4 border border-slate-200">
            <div className="flex items-center space-x-2 mb-3 pb-2 border-b border-slate-200">
              <Tag className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wide">
                Product & Brand Identity
              </h3>
            </div>
            <div className="space-y-1">
              {renderFieldRow('Product Name', identity.product_name, null, 'product_name')}
              {renderFieldRow('Brand Name', identity.brand_name, null, 'brand_name')}
              {renderFieldRow('Variant / Flavor', identity.product_variant, null, 'variant')}
              {renderFieldRow('Category', identity.product_category, null, 'category')}
            </div>
          </div>

          {/* 2. Manufacturer & Supply Chain Card */}
          <div className="bg-slate-50/70 rounded-lg p-4 border border-slate-200">
            <div className="flex items-center space-x-2 mb-3 pb-2 border-b border-slate-200">
              <Building className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wide">
                Manufacturer & Origin
              </h3>
            </div>
            <div className="space-y-1">
              {renderFieldRow('Manufacturer', identity.manufacturer, null, 'manufacturer_name')}
              {renderFieldRow('Packer', identity.packer, null, 'packer_name')}
              {renderFieldRow('Country of Origin', identity.country_of_origin, null, 'country_of_origin')}
              {renderFieldRow('Complete Address', identity.complete_address, null, 'complete_address')}
            </div>
          </div>

          {/* 3. FSSAI Food Licensing Card */}
          <div className="bg-slate-50/70 rounded-lg p-4 border border-slate-200">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-200">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-indigo-600" />
                <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wide">
                  FSSAI Statutory License
                </h3>
              </div>
              {renderProvenanceBadge(
                identity.fssai_provenance_label || 
                (identity.fssai_external_verified ? 'Externally verified' : (identity.fssai_license_number?.value ? 'Extracted from package' : 'Not found'))
              )}
            </div>
            <div className="space-y-1">
              {renderFieldRow('Licence Number', identity.fssai_license_number, null, 'fssai_license')}
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100 text-xs">
                <span className="text-slate-500 font-medium">State Jurisdiction</span>
                <span className="text-slate-900 font-semibold">{identity.fssai_state_name || fExt?.state_name || 'N/A'}</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100 text-xs">
                <span className="text-slate-500 font-medium">License Tier</span>
                <span className="text-slate-900 font-semibold">{identity.fssai_license_type || fExt?.registration_type || 'N/A'}</span>
              </div>
              <div className="flex items-center justify-between py-1.5 text-xs">
                <span className="text-slate-500 font-medium">Provenance Status</span>
                <span className="font-semibold text-slate-800">
                  {identity.fssai_provenance_label || (identity.fssai_external_verified ? 'Externally verified' : (identity.fssai_license_number?.value ? 'Extracted from package' : 'Not found'))}
                </span>
              </div>
              {(identity.fssai_verification_details?.business_name || extFssai?.business_name) && (
                <div className="mt-2 p-2 bg-emerald-50 rounded border border-emerald-200 text-[11px] text-emerald-900">
                  <span className="font-bold">FoSCoS Registered Entity:</span> {identity.fssai_verification_details?.business_name || extFssai?.business_name}
                  {(identity.fssai_verification_details?.valid_upto || extFssai?.valid_upto) && (
                    <div className="text-[10px] text-emerald-700 mt-0.5">
                      Valid Upto: {identity.fssai_verification_details?.valid_upto || extFssai?.valid_upto}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* 4. Retail Barcode Intelligence Card */}
          <div className="bg-slate-50/70 rounded-lg p-4 border border-slate-200">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-200">
              <div className="flex items-center space-x-2">
                <Barcode className="w-4 h-4 text-indigo-600" />
                <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wide">
                  1D Retail Barcodes ({(identity.barcodes?.length || 0) + (primaryBc ? 1 : 0) > 0 ? (identity.barcodes?.length || 1) : 0})
                </h3>
              </div>
              {renderProvenanceBadge(
                identity.barcode_provenance_label || 
                (identity.barcode_external_verified ? 'Externally verified' : (identity.barcodes && identity.barcodes.length > 0 ? 'Extracted from package' : 'Not found'))
              )}
            </div>
            {identity.barcodes && identity.barcodes.length > 0 ? (
              <div className="space-y-2">
                {identity.barcodes.map((bc, idx) => (
                  <div key={idx} className="p-2 bg-white rounded border border-slate-200 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-slate-900">{bc.raw_value}</span>
                      <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 rounded text-slate-700 font-medium">
                        {bc.symbology}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-slate-600">
                      <span>Origin: {bc.country_flag} {bc.country_of_origin || 'Unknown'}</span>
                      <span className={bc.is_valid_checksum ? 'text-emerald-600 font-medium' : 'text-red-600 font-semibold'}>
                        {bc.is_valid_checksum ? 'Valid Mod-10' : 'Checksum Error'}
                      </span>
                    </div>
                    {(bc.registered_brand || bc.registered_product) ? (
                      <div className="mt-2 pt-1.5 border-t border-emerald-100 bg-emerald-50/60 p-1.5 rounded text-[11px] text-emerald-950">
                        <div className="font-semibold text-emerald-900 flex items-center">
                          <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-600" />
                          GS1 Registered Details:
                        </div>
                        <div className="mt-0.5 text-slate-800">
                          <b>Brand:</b> {bc.registered_brand} | <b>Product:</b> {bc.registered_product}
                        </div>
                        {bc.registered_net_quantity && (
                          <div className="text-slate-700"><b>Master Net Weight:</b> {bc.registered_net_quantity}</div>
                        )}
                        {bc.registered_company && (
                          <div className="text-slate-600 text-[10px]"><b>Entity:</b> {bc.registered_company}</div>
                        )}
                      </div>
                    ) : (
                      <div className="mt-1 text-[10px] text-slate-400 italic">
                        Provenance: {bc.provenance_label || 'Extracted from package'} (No external registry data fabricated)
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : primaryBc ? (
              <div className="p-2 bg-white rounded border border-slate-200 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-slate-900">{primaryBc.value}</span>
                  <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 rounded text-slate-700 font-medium">
                    {primaryBc.type}
                  </span>
                </div>
                <div className="mt-1 flex items-center justify-between text-[11px] text-slate-600">
                  <span>Origin: 🇮🇳 {primaryBc.country_of_origin || 'India'}</span>
                  <span className={primaryBc.checksum_valid ? 'text-emerald-600 font-medium' : 'text-slate-600'}>
                    {primaryBc.checksum_valid ? 'Valid Checksum' : 'Decoded Value'}
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic py-3">No 1D retail barcodes detected on scanned surfaces.</p>
            )}
          </div>

          {/* 5. 2D QR Code Intelligence Card */}
          <div className="bg-slate-50/70 rounded-lg p-4 border border-slate-200">
            <div className="flex items-center space-x-2 mb-3 pb-2 border-b border-slate-200">
              <QrCode className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wide">
                2D QR Codes ({identity.qr_codes?.length || 0})
              </h3>
            </div>
            {identity.qr_codes && identity.qr_codes.length > 0 ? (
              <div className="space-y-2">
                {identity.qr_codes.map((qr, idx) => (
                  <div key={idx} className="p-2 bg-white rounded border border-slate-200 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-semibold text-indigo-700 uppercase">
                        {(qr.content_type || 'TEXT').replace('_', ' ')}
                      </span>
                      {qr.is_safe_url ? (
                        <span className="text-[10px] px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded border border-emerald-200">
                          Safe Link
                        </span>
                      ) : (
                        <span className="text-[10px] px-1.5 py-0.5 bg-red-100 text-red-800 rounded border border-red-200 font-bold">
                          SSRF / Unsafe
                        </span>
                      )}
                    </div>
                    <div className="mt-1 font-mono text-[11px] text-slate-800 break-all">
                      {qr.raw_value.length > 60 ? `${qr.raw_value.slice(0, 60)}...` : qr.raw_value}
                    </div>
                    {qr.gs1_ai_data && Object.keys(qr.gs1_ai_data).length > 0 && (
                      <div className="mt-1 pt-1 border-t border-slate-100 text-[10px] text-slate-500">
                        GS1 Data: {JSON.stringify(qr.gs1_ai_data)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic py-3">No 2D QR codes detected on scanned surfaces.</p>
            )}
          </div>

          {/* 6. Legal Metrology Core Card */}
          <div className="bg-slate-50/70 rounded-lg p-4 border border-slate-200">
            <div className="flex items-center space-x-2 mb-3 pb-2 border-b border-slate-200">
              <Calendar className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wide">
                Metrology & Dates
              </h3>
            </div>
            <div className="space-y-1">
              {renderFieldRow('MRP (₹)', identity.mrp, null, 'mrp')}
              {renderFieldRow('Net Quantity', identity.net_quantity, null, 'net_quantity')}
              {renderFieldRow('Batch Number', identity.batch_number, null, 'batch_number')}
              {renderFieldRow('Mfg Date', identity.dates?.date_of_manufacture, null, 'manufacturing_date')}
              {renderFieldRow('Best Before / Expiry', identity.dates?.best_before?.value ? identity.dates.best_before : identity.dates?.expiry_date, null, 'best_before')}
            </div>
          </div>

        </div>
      )}

      {/* Accordion / Secondary Sections (Food Declarations & Consumer Care) */}
      {identity && (
        <div className="mt-5 pt-4 border-t border-slate-200 flex items-center justify-between">
          <button
            onClick={() => setShowAllFields(!showAllFields)}
            className="inline-flex items-center text-xs font-bold text-indigo-600 hover:text-indigo-800"
          >
            {showAllFields ? <ChevronUp className="w-4 h-4 mr-1" /> : <ChevronDown className="w-4 h-4 mr-1" />}
            {showAllFields ? 'Hide Extended Statutory Details' : 'Show Extended Statutory Details (Food, Consumer Care, Allergens)'}
          </button>
          <span className="text-[11px] text-slate-400">
            Rule 6 & Rule 12 Statutory Declarations Active
          </span>
        </div>
      )}

      {showAllFields && identity && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-4">
          
          {/* Food Details */}
          <div className="p-4 bg-slate-50/50 rounded-lg border border-slate-200">
            <div className="flex items-center space-x-2 mb-3 pb-1 border-b border-slate-200">
              <Utensils className="w-4 h-4 text-emerald-600" />
              <h4 className="text-xs font-bold text-slate-800 uppercase">Food Information Declarations</h4>
            </div>
            {isFood ? (
              <div className="space-y-2 text-xs">
                <div>
                  <span className="font-semibold text-slate-600">Veg / Non-Veg:</span>{' '}
                  <span className="font-medium text-slate-900">{identity.food_declarations?.veg_nonveg_status?.value || 'Not detected'}</span>
                </div>
                <div>
                  <span className="font-semibold text-slate-600">Ingredients ({identity.food_declarations?.ingredients?.length || 0}):</span>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {identity.food_declarations?.ingredients && identity.food_declarations.ingredients.length > 0 ? (
                      identity.food_declarations.ingredients.map((ing: any, i: number) => (
                        <span key={i} className="px-2 py-0.5 bg-white rounded border border-slate-200 text-[11px] text-slate-700">
                          {typeof ing === 'string' ? ing : ing?.value || String(ing)}
                        </span>
                      ))
                    ) : (
                      <span className="text-slate-400 italic">No ingredient tokens detected</span>
                    )}
                  </div>
                </div>
                {identity.food_declarations?.allergens && identity.food_declarations.allergens.length > 0 && (
                  <div>
                    <span className="font-semibold text-amber-700">Allergen Advice:</span>{' '}
                    <span className="text-slate-800">{identity.food_declarations.allergens.join(', ')}</span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic py-2">Product is categorized as non-food. Food declarations are not applicable.</p>
            )}
          </div>

          {/* Consumer Care */}
          <div className="p-4 bg-slate-50/50 rounded-lg border border-slate-200">
            <div className="flex items-center space-x-2 mb-3 pb-1 border-b border-slate-200">
              <PhoneCall className="w-4 h-4 text-blue-600" />
              <h4 className="text-xs font-bold text-slate-800 uppercase">Consumer Grievance Redressal</h4>
            </div>
            <div className="space-y-1">
              {renderFieldRow('Helpline Phone', identity.customer_care?.phone, null, 'consumer_care_phone')}
              {renderFieldRow('Helpline Email', identity.customer_care?.email, null, 'consumer_care_email')}
              {renderFieldRow('Grievance Address', identity.customer_care?.address, null, 'consumer_care_address')}
            </div>
          </div>

        </div>
      )}

    </div>
  );
};
