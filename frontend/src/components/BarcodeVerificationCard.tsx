import React, { useState, useEffect } from 'react';
import { 
  Barcode, 
  QrCode, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  Database, 
  ShieldCheck, 
  ChevronDown, 
  ChevronUp, 
  ShieldAlert, 
  ScanLine, 
  Globe, 
  Hash, 
  PackageCheck 
} from 'lucide-react';
import { getApiBaseUrl } from '../config/api';
import { tokenStore } from '../services/api';
import { type BarcodeItem } from '../types';

export type { BarcodeItem };

export interface BarcodeVerificationProps {
  barcode?: BarcodeItem | null;
  productInfo?: any;
  scanResults?: BarcodeItem[];   // Full list from barcode_scan_results (image-level scan)
  onVerifyAgain?: () => void;
}

// ── Individual barcode scan result row ───────────────────────────────────
const ScanResultRow: React.FC<{ item: BarcodeItem; index: number }> = ({ item, index }) => {
  const isQR = item.symbology.toLowerCase().includes('qr') || Boolean(item.digital_link_data);
  const hasGS1 = item.symbology.toUpperCase().includes('DIGITAL_LINK');

  return (
    <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 space-y-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded-lg ${isQR ? 'bg-purple-500/20 text-purple-400' : 'bg-blue-500/20 text-blue-400'}`}>
            {isQR ? <QrCode className="w-3.5 h-3.5" /> : <Barcode className="w-3.5 h-3.5" />}
          </div>
          <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">
            {isQR ? (hasGS1 ? 'GS1 Digital Link' : 'QR Code') : 'Barcode'} #{index + 1}
          </span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            {item.symbology}
          </span>
          {item.is_valid_checksum !== false && (
            <span className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
              <CheckCircle2 className="w-2.5 h-2.5" /> Valid
            </span>
          )}
        </div>
        {item.country_flag && (
          <span className="text-sm" title={item.country_of_origin || ''}>
            {item.country_flag}
          </span>
        )}
      </div>

      {/* Decoded Value */}
      <div className="font-mono text-sm font-bold text-emerald-400 tracking-wider break-all">
        {item.raw_value}
      </div>

      {/* Product Information if resolved */}
      {(item.product_name || item.brand_name || item.company_name) && (
        <div className="p-2.5 rounded-lg bg-indigo-950/40 border border-indigo-500/30 text-xs text-slate-200 space-y-1">
          <div className="font-bold text-white flex items-center justify-between gap-2">
            <span className="truncate">{item.product_name || item.brand_name}</span>
            {item.brand_name && item.product_name && (
              <span className="text-[10px] text-indigo-300 font-normal px-1.5 py-0.5 rounded bg-indigo-500/20 shrink-0">
                {item.brand_name}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 text-[11px] text-slate-400 flex-wrap">
            {item.company_name && <span>Mfr: <span className="text-slate-300">{item.company_name}</span></span>}
            {item.net_quantity && <span>Net Qty: <span className="text-emerald-400 font-mono font-bold">{item.net_quantity}</span></span>}
            {item.category && <span>Category: <span className="text-slate-300">{item.category}</span></span>}
          </div>
        </div>
      )}

      {/* FSSAI from barcode — highlighted */}
      {item.fssai_from_barcode && (
        <div className="flex items-center gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30">
          <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
          <div>
            <div className="text-[10px] font-semibold text-amber-400 uppercase tracking-wider">FSSAI License (from {isQR ? 'QR' : 'Barcode'} payload)</div>
            <div className="font-mono text-sm font-bold text-amber-300">{item.fssai_from_barcode}</div>
          </div>
        </div>
      )}

      {/* GS1 Digital Link AI breakdown */}
      {item.digital_link_data && (
        <div className="grid grid-cols-3 gap-2 text-[11px] font-mono">
          {item.digital_link_data.gtin && (
            <div className="p-1.5 rounded bg-purple-950/30 border border-purple-800/30">
              <div className="text-[9px] text-slate-500 uppercase">GTIN (01)</div>
              <div className="text-purple-300 font-bold">{item.digital_link_data.gtin}</div>
            </div>
          )}
          {item.digital_link_data.lot && (
            <div className="p-1.5 rounded bg-purple-950/30 border border-purple-800/30">
              <div className="text-[9px] text-slate-500 uppercase">Lot (10)</div>
              <div className="text-purple-300">{item.digital_link_data.lot}</div>
            </div>
          )}
          {item.digital_link_data.expiry_yymmdd && (
            <div className="p-1.5 rounded bg-purple-950/30 border border-purple-800/30">
              <div className="text-[9px] text-slate-500 uppercase">Expiry (17)</div>
              <div className="text-purple-300">{item.digital_link_data.expiry_yymmdd}</div>
            </div>
          )}
        </div>
      )}

      {/* Country of Origin */}
      {item.country_of_origin && (
        <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
          <Globe className="w-3 h-3" />
          <span>GS1 Prefix: <span className="text-slate-200 font-medium">{item.country_of_origin}</span>
            {item.gs1_prefix && <span className="text-slate-500"> ({item.gs1_prefix})</span>}
          </span>
        </div>
      )}
    </div>
  );
};

// ── Main component ────────────────────────────────────────────────────────
export const BarcodeVerificationCard: React.FC<BarcodeVerificationProps> = ({
  barcode,
  productInfo,
  scanResults,
}) => {
  const [loading, setLoading] = useState(false);
  const [verificationResult, setVerificationResult] = useState<any>(null);
  const [expanded, setExpanded] = useState(true);

  // Determine which barcode data to work with
  // Prefer image-level scan results if available, fall back to props.barcode
  const hasScanResults = scanResults && scanResults.length > 0;
  const primaryBarcode: BarcodeItem | null = hasScanResults
    ? scanResults[0]
    : (barcode || null);

  const [productDetails, setProductDetails] = useState<any>(
    primaryBarcode?.registered_data || (primaryBarcode?.product_name ? {
      product_name: primaryBarcode.product_name,
      brand_name: primaryBarcode.brand_name,
      company_name: primaryBarcode.company_name,
      net_quantity: primaryBarcode.net_quantity,
      category: primaryBarcode.category,
      image_url: primaryBarcode.image_url,
      country_of_origin: primaryBarcode.country_of_origin,
      source: 'Verified Product Master'
    } : null)
  );
  const [isFetchingProduct, setIsFetchingProduct] = useState(false);

  // Auto-fetch product details whenever primaryBarcode changes
  useEffect(() => {
    if (!primaryBarcode?.raw_value) return;

    if (primaryBarcode.registered_data) {
      setProductDetails(primaryBarcode.registered_data);
      return;
    }
    if (primaryBarcode.product_name) {
      setProductDetails({
        product_name: primaryBarcode.product_name,
        brand_name: primaryBarcode.brand_name,
        company_name: primaryBarcode.company_name,
        net_quantity: primaryBarcode.net_quantity,
        category: primaryBarcode.category,
        image_url: primaryBarcode.image_url,
        country_of_origin: primaryBarcode.country_of_origin,
        source: 'Verified Product Master'
      });
      return;
    }

    let isMounted = true;
    const fetchDetails = async () => {
      setIsFetchingProduct(true);
      try {
        const token = tokenStore.get();
        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const cleanVal = primaryBarcode.raw_value.replace(/\D/g, '');
        const res = await fetch(`${getApiBaseUrl()}/barcode/lookup/${cleanVal}`, { headers });
        if (res.ok && isMounted) {
          const json = await res.json();
          if (json.found && (json.data || json.record)) {
            setProductDetails(json.data || json.record);
          } else {
            setProductDetails({
              notFound: true,
              country_of_origin: json.country_of_origin,
              country_flag: json.country_flag,
              gs1_prefix: json.gs1_prefix,
              message: json.message
            });
          }
        }
      } catch (e) {
        console.debug('Product details auto-fetch failed:', e);
      } finally {
        if (isMounted) setIsFetchingProduct(false);
      }
    };

    fetchDetails();
    return () => { isMounted = false; };
  }, [primaryBarcode?.raw_value, primaryBarcode?.registered_data, primaryBarcode?.product_name]);

  // Collect all FSSAI licenses found in any scan result
  const fssaiFromBarcodes = hasScanResults
    ? scanResults.filter(b => b.fssai_from_barcode).map(b => b.fssai_from_barcode!)
    : (barcode?.fssai_from_barcode ? [barcode.fssai_from_barcode] : []);

  const uniqueFssai = [...new Set(fssaiFromBarcodes)];

  if (!hasScanResults && !barcode?.raw_value) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm text-center">
        <div className="inline-flex p-3 rounded-xl bg-slate-800/80 text-slate-400 mb-2">
          <ScanLine className="w-6 h-6 opacity-60" />
        </div>
        <p className="text-sm text-slate-300 font-medium">No Barcode / QR Code Detected</p>
        <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
          Ensure the barcode or QR code is clearly visible and well-lit on the packaging panel.
        </p>
      </div>
    );
  }

  const isQR = primaryBarcode 
    ? (primaryBarcode.symbology.toLowerCase().includes('qr') || Boolean(primaryBarcode.digital_link_data))
    : false;

  const handleVerify = async () => {
    if (!primaryBarcode) return;
    setLoading(true);
    try {
      const token = tokenStore.get();
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(`${getApiBaseUrl()}/barcode/verify`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          raw_value: primaryBarcode.raw_value,
          symbology: primaryBarcode.symbology,
          brand: productInfo?.brand,
          net_quantity: productInfo?.net_quantity,
          country_of_origin: productInfo?.country_of_origin || 'India',
          fssai_license: productInfo?.fssai_license,
          mrp: productInfo?.mrp
        })
      });
      if (res.ok) {
        const data = await res.json();
        setVerificationResult(data);
        if (data.registered_data) {
          setProductDetails(data.registered_data);
        }
      }
    } catch (e) {
      console.error('Barcode verification error:', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/90 shadow-xl overflow-hidden backdrop-blur-sm">
      {/* Header Banner */}
      <div className="px-5 py-4 bg-gradient-to-r from-indigo-950/70 via-slate-900 to-slate-900 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-500/20 border border-indigo-500/30 text-indigo-400">
            {hasScanResults && scanResults!.length > 1
              ? <ScanLine className="w-5 h-5" />
              : isQR ? <QrCode className="w-5 h-5" /> : <Barcode className="w-5 h-5" />}
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-sm font-bold text-white tracking-wide">
                {hasScanResults
                  ? `Barcode / QR Scan — ${scanResults!.length} Code${scanResults!.length > 1 ? 's' : ''} Detected`
                  : isQR ? 'GS1 Digital Link / QR Code' : 'GS1 Barcode Verification'}
              </h3>
              {primaryBarcode && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  {primaryBarcode.symbology}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Image-level detection · Legal Metrology &amp; GS1 India Data Synchronisation
            </p>
          </div>
        </div>

        <button
          onClick={() => setExpanded(!expanded)}
          className="text-slate-400 hover:text-white p-1 rounded-lg transition-colors cursor-pointer"
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {expanded && (
        <div className="p-5 space-y-4">
          {/* ── FSSAI found in barcode/QR — prominent alert ─────────────── */}
          {uniqueFssai.length > 0 && (
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/40 flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="text-sm font-bold text-amber-300">
                  FSSAI License{uniqueFssai.length > 1 ? 's' : ''} Found in {hasScanResults && scanResults!.some(b => b.fssai_from_barcode && b.symbology.toLowerCase().includes('qr')) ? 'QR Code' : 'Barcode'} Data
                </div>
                {uniqueFssai.map((lic, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Hash className="w-3.5 h-3.5 text-amber-400" />
                    <span className="font-mono text-base font-bold text-amber-200 tracking-wider">{lic}</span>
                  </div>
                ))}
                {productInfo?.fssai_license && productInfo.fssai_license !== uniqueFssai[0] && (
                  <p className="text-[11px] text-amber-500/80 mt-1">
                    ⚠ OCR-extracted FSSAI: <span className="font-mono font-bold">{productInfo.fssai_license}</span> — verify both match.
                  </p>
                )}
                {productInfo?.fssai_license === uniqueFssai[0] && (
                  <p className="text-[11px] text-emerald-400 mt-1 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Matches OCR-extracted FSSAI license.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* ── Scan Results (image-level detection) ─────────────────────── */}
          {hasScanResults ? (
            <div className="space-y-3">
              {scanResults!.map((item, i) => (
                <ScanResultRow key={i} item={item} index={i} />
              ))}
            </div>
          ) : primaryBarcode ? (
            /* ── Legacy single barcode display (OCR-extracted) ──────────── */
            <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800/80 flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <span className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Decoded Value / GTIN</span>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-lg font-bold text-emerald-400 tracking-wider">
                    {primaryBarcode.raw_value}
                  </span>
                  {(primaryBarcode.is_valid_checksum ?? productDetails?.is_valid_checksum) !== false ? (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20">
                      <CheckCircle2 className="w-3 h-3" /> Valid Checksum
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded-md border border-rose-500/20">
                      <XCircle className="w-3 h-3" /> Checksum Failed
                    </span>
                  )}
                </div>
              </div>

              {(primaryBarcode.country_of_origin || productDetails?.country_of_origin) && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-800/90 border border-slate-700/60">
                  <span className="text-base">{primaryBarcode.country_flag || productDetails?.country_flag || '🌐'}</span>
                  <div>
                    <div className="text-[10px] text-slate-400 font-medium">Country (Prefix {primaryBarcode.gs1_prefix || productDetails?.gs1_prefix || 'GS1'})</div>
                    <div className="text-xs font-semibold text-slate-200">{primaryBarcode.country_of_origin || productDetails?.country_of_origin}</div>
                  </div>
                </div>
              )}
            </div>
          ) : null}

          {/* ── Auto-Fetched / Scanned Master Product Record ──────────── */}
          {isFetchingProduct ? (
            <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center gap-2.5 text-xs text-slate-400 animate-pulse">
              <div className="w-3.5 h-3.5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
              <span>Fetching product master record from GS1 &amp; Open Product Registry...</span>
            </div>
          ) : productDetails && !productDetails.notFound ? (
            <div className="p-4 rounded-xl bg-gradient-to-br from-indigo-950/40 via-slate-950/70 to-slate-950/90 border border-indigo-500/30 space-y-3">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400">
                    <PackageCheck className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-bold text-indigo-400 tracking-wider">
                      {productDetails.source || 'Product Master Record'}
                    </span>
                    <h4 className="text-sm font-bold text-white leading-tight">
                      {productDetails.product_name || productDetails.brand_name || 'Verified Product'}
                    </h4>
                  </div>
                </div>
                {productDetails.brand_name && (
                  <span className="px-2.5 py-0.5 rounded-lg text-xs font-bold bg-indigo-600/30 text-indigo-200 border border-indigo-500/40">
                    {productDetails.brand_name}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1 text-xs">
                {productDetails.company_name && (
                  <div className="p-2 rounded-lg bg-slate-900/80 border border-slate-800">
                    <span className="text-[10px] text-slate-400 uppercase block">Manufacturer / Company</span>
                    <span className="font-semibold text-slate-200 truncate block" title={productDetails.company_name}>
                      {productDetails.company_name}
                    </span>
                  </div>
                )}
                {productDetails.net_quantity && (
                  <div className="p-2 rounded-lg bg-slate-900/80 border border-slate-800">
                    <span className="text-[10px] text-slate-400 uppercase block">Net Quantity</span>
                    <span className="font-semibold text-emerald-300 font-mono">
                      {productDetails.net_quantity}
                    </span>
                  </div>
                )}
                {productDetails.category && (
                  <div className="p-2 rounded-lg bg-slate-900/80 border border-slate-800">
                    <span className="text-[10px] text-slate-400 uppercase block">Category</span>
                    <span className="font-medium text-slate-300 truncate block">
                      {productDetails.category}
                    </span>
                  </div>
                )}
                {productDetails.mrp && (
                  <div className="p-2 rounded-lg bg-slate-900/80 border border-slate-800">
                    <span className="text-[10px] text-slate-400 uppercase block">Registered MRP</span>
                    <span className="font-semibold text-indigo-300 font-mono">
                      ₹{productDetails.mrp}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ) : productDetails?.notFound ? (
            <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 flex items-start gap-3 text-xs text-slate-300">
              <Globe className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-slate-200">
                  GS1 Jurisdiction Verified: {productDetails.country_of_origin} {productDetails.country_flag} (Prefix {productDetails.gs1_prefix || 'GS1'})
                </div>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  This GTIN has a valid GS1 structure and country allocation. Brand details can be verified against on-pack declarations or submitted for master cataloging.
                </p>
              </div>
            </div>
          ) : null}

          {/* ── GS1 Digital Link constituents if available ──────────────── */}
          {!hasScanResults && primaryBarcode?.digital_link_data && (
            <div className="p-3 rounded-xl bg-purple-950/20 border border-purple-800/40 text-xs text-purple-300 space-y-1">
              <div className="font-bold flex items-center gap-1.5 text-purple-200">
                <QrCode className="w-3.5 h-3.5" /> GS1 Digital Link Application Identifiers
              </div>
              <div className="grid grid-cols-3 gap-2 pt-1 font-mono text-[11px]">
                {primaryBarcode.digital_link_data.gtin && (
                  <div><span className="text-slate-500">(01) GTIN:</span> {primaryBarcode.digital_link_data.gtin}</div>
                )}
                {primaryBarcode.digital_link_data.lot && (
                  <div><span className="text-slate-500">(10) Lot:</span> {primaryBarcode.digital_link_data.lot}</div>
                )}
                {primaryBarcode.digital_link_data.expiry_yymmdd && (
                  <div><span className="text-slate-500">(17) Expiry:</span> {primaryBarcode.digital_link_data.expiry_yymmdd}</div>
                )}
              </div>
            </div>
          )}

          {/* ── GS1 Verification Cross-Check ─────────────────────────────── */}
          {verificationResult ? (
            <div className="space-y-3">
              <div className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 text-xs ${
                verificationResult.compliance_status === 'PASS'
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : verificationResult.compliance_status === 'FAIL'
                  ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                  : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
              }`}>
                <div className="flex items-center gap-2">
                  {verificationResult.compliance_status === 'PASS' ? (
                    <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  )}
                  <span className="font-semibold">{verificationResult.summary}</span>
                </div>
                <span className="px-2 py-0.5 rounded font-bold uppercase text-[10px] bg-slate-900/60 border border-current">
                  {verificationResult.compliance_status}
                </span>
              </div>

              {verificationResult.discrepancies?.length > 0 && (
                <div className="p-3 rounded-xl bg-rose-950/20 border border-rose-800/40 space-y-1.5">
                  <span className="text-xs font-bold text-rose-300 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-rose-400" /> Discrepancy Alerts:
                  </span>
                  <ul className="text-xs text-rose-200/90 space-y-1 pl-4 list-disc">
                    {verificationResult.discrepancies.map((d: string, idx: number) => (
                      <li key={idx}>{d}</li>
                    ))}
                  </ul>
                </div>
              )}

              {(verificationResult.registered_data || productDetails) && (
                <div className="overflow-x-auto rounded-xl border border-slate-800">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950 text-slate-400 text-[11px] uppercase border-b border-slate-800">
                      <tr>
                        <th className="px-3 py-2">Declaration Field</th>
                        <th className="px-3 py-2">Packaging Label (OCR)</th>
                        <th className="px-3 py-2">Barcode Master Record</th>
                        <th className="px-3 py-2 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 bg-slate-900/40 text-slate-200">
                      <tr>
                        <td className="px-3 py-2 font-medium text-slate-400">Net Quantity</td>
                        <td className="px-3 py-2">{productInfo?.net_quantity || '—'}</td>
                        <td className="px-3 py-2 font-semibold text-indigo-300">
                          {(verificationResult.registered_data || productDetails)?.net_quantity || '—'}
                        </td>
                        <td className="px-3 py-2 text-center">
                          {verificationResult.net_quantity_match ? (
                            <span className="text-emerald-400 font-bold">MATCH</span>
                          ) : (
                            <span className="text-rose-400 font-bold">MISMATCH</span>
                          )}
                        </td>
                      </tr>
                      <tr>
                        <td className="px-3 py-2 font-medium text-slate-400">Brand Name</td>
                        <td className="px-3 py-2">{productInfo?.brand || '—'}</td>
                        <td className="px-3 py-2 font-semibold text-indigo-300">
                          {(verificationResult.registered_data || productDetails)?.brand_name || '—'}
                        </td>
                        <td className="px-3 py-2 text-center">
                          {verificationResult.brand_match ? (
                            <span className="text-emerald-400 font-bold">MATCH</span>
                          ) : (
                            <span className="text-rose-400 font-bold">MISMATCH</span>
                          )}
                        </td>
                      </tr>
                      <tr>
                        <td className="px-3 py-2 font-medium text-slate-400">Country of Origin</td>
                        <td className="px-3 py-2">{productInfo?.country_of_origin || 'India'}</td>
                        <td className="px-3 py-2 font-semibold text-indigo-300">
                          {(verificationResult.registered_data || productDetails)?.country_of_origin || primaryBarcode?.country_of_origin || 'India'}
                        </td>
                        <td className="px-3 py-2 text-center">
                          {verificationResult.country_match !== false ? (
                            <span className="text-emerald-400 font-bold">MATCH</span>
                          ) : (
                            <span className="text-amber-400 font-bold">CHECK</span>
                          )}
                        </td>
                      </tr>
                      {((verificationResult.registered_data || productDetails)?.fssai_license) && (
                        <tr>
                          <td className="px-3 py-2 font-medium text-slate-400">FSSAI License</td>
                          <td className="px-3 py-2 font-mono">{productInfo?.fssai_license || '—'}</td>
                          <td className="px-3 py-2 font-mono font-semibold text-indigo-300">
                            {(verificationResult.registered_data || productDetails)?.fssai_license}
                          </td>
                          <td className="px-3 py-2 text-center">
                            {verificationResult.fssai_match !== false ? (
                              <span className="text-emerald-400 font-bold">MATCH</span>
                            ) : (
                              <span className="text-rose-400 font-bold">MISMATCH</span>
                            )}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : primaryBarcode ? (
            <div className="flex items-center justify-between pt-1">
              <span className="text-xs text-slate-400">
                Cross-verify GTIN against product master records &amp; Legal Metrology rules
              </span>
              <button
                type="button"
                onClick={handleVerify}
                disabled={loading}
                className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold transition-all shadow-md flex items-center gap-1.5 cursor-pointer"
              >
                {loading ? (
                  <>
                    <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Verifying...
                  </>
                ) : (
                  <>
                    <Database className="w-3.5 h-3.5" />
                    Verify Against GS1 Registry
                  </>
                )}
              </button>
            </div>
          ) : null}

          {/* Summary row when scan results present */}
          {hasScanResults && !verificationResult && primaryBarcode && (
            <div className="flex items-center justify-between pt-1 border-t border-slate-800">
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <PackageCheck className="w-4 h-4 text-indigo-400" />
                <span>
                  {scanResults!.filter(b => !b.symbology.toLowerCase().includes('qr') && !b.digital_link_data).length} barcode(s),{' '}
                  {scanResults!.filter(b => b.symbology.toLowerCase().includes('qr') || b.digital_link_data).length} QR code(s) detected from image
                </span>
              </div>
              <button
                type="button"
                onClick={handleVerify}
                disabled={loading}
                className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold transition-all shadow-md flex items-center gap-1.5 cursor-pointer"
              >
                {loading ? (
                  <>
                    <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Verifying...
                  </>
                ) : (
                  <>
                    <Database className="w-3.5 h-3.5" />
                    Verify Against GS1 Registry
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
