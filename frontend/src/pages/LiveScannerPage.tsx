import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Scan, 
  ArrowLeft, 
  CheckCircle2, 
  Sparkles, 
  Layers, 
  Trash2
} from 'lucide-react';
import { LiveCameraScanner } from '../components/LiveCameraScanner';
import { BarcodeVerificationCard } from '../components/BarcodeVerificationCard';
import { getApiBaseUrl } from '../config/api';
import { tokenStore } from '../services/api';

interface CapturedAngle {
  id: string;
  dataUrl: string;
  blob: Blob;
  label: string;
}

export const LiveScannerPage: React.FC = () => {
  const navigate = useNavigate();
  const [capturedAngles, setCapturedAngles] = useState<CapturedAngle[]>([]);
  const [activeBarcode, setActiveBarcode] = useState<any>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const handleCaptureSnapshot = (blob: Blob, dataUrl: string) => {
    const nextLabel = capturedAngles.length === 0 ? 'Front' : capturedAngles.length === 1 ? 'Back' : `Side ${capturedAngles.length - 1}`;
    const newAngle: CapturedAngle = {
      id: Math.random().toString(36).substring(2, 9),
      dataUrl,
      blob,
      label: nextLabel
    };
    setCapturedAngles(prev => [...prev, newAngle]);
  };

  const handleRemoveAngle = (id: string) => {
    setCapturedAngles(prev => prev.filter(a => a.id !== id));
  };

  const handleRunFullAnalysis = async () => {
    if (capturedAngles.length === 0) return;
    setIsAnalyzing(true);
    setAnalysisError(null);

    try {
      const formData = new FormData();
      const labels: string[] = [];
      capturedAngles.forEach((angle) => {
        const file = new File([angle.blob], `${angle.label.toLowerCase()}_scan.jpg`, { type: 'image/jpeg' });
        formData.append('files', file);
        labels.push(angle.label);
      });
      formData.append('labels', JSON.stringify(labels));

      const token = tokenStore.get();
      const headers: Record<string, string> = {
        'Accept': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const res = await fetch(`${getApiBaseUrl()}/analyze`, {
        method: 'POST',
        headers,
        body: formData
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Analysis request failed');
      }

      const result = await res.json();
      navigate(`/results/${result.id}`, { state: { analysisData: result } });
    } catch (err: any) {
      console.error('Batch analysis error:', err);
      setAnalysisError(err.message || 'Failed to analyze scanned images');
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Header Bar */}
      <header className="px-6 py-4 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-all cursor-pointer"
            title="Return to Dashboard"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-base font-bold text-white flex items-center gap-2">
              <Scan className="w-5 h-5 text-indigo-400" />
              Live Packaging & Barcode Scanner
            </h1>
            <p className="text-xs text-slate-400">
              Real-time packaging HUD detection & multi-angle inspection
            </p>
          </div>
        </div>

        {capturedAngles.length > 0 && (
          <button
            type="button"
            onClick={handleRunFullAnalysis}
            disabled={isAnalyzing}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white font-bold text-xs shadow-lg shadow-emerald-500/20 active:scale-95 transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
          >
            {isAnalyzing ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Analyzing {capturedAngles.length} Angle(s)...
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                Run Legal Metrology Audit ({capturedAngles.length})
              </>
            )}
          </button>
        )}
      </header>

      {/* Main Scanner Workspace */}
      <main className="flex-1 max-w-6xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Live Camera Viewport */}
        <LiveCameraScanner
          onCaptureSnapshot={handleCaptureSnapshot}
          onBarcodeDetected={(b) => setActiveBarcode(b)}
        />

        {/* Real-time Barcode Verification Card if Barcode Detected */}
        {activeBarcode && (
          <div className="space-y-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              Live Detected Barcode & Registry Lookup
            </h2>
            <BarcodeVerificationCard barcode={activeBarcode} />
          </div>
        )}

        {/* Captured Angles Strip */}
        {capturedAngles.length > 0 && (
          <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/70 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-400" />
                <h3 className="text-sm font-bold text-white">
                  Captured Packaging Angles ({capturedAngles.length})
                </h3>
              </div>
              <span className="text-xs text-slate-400">
                Capture Front, Back, and Side panels for comprehensive compliance check
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {capturedAngles.map((angle, idx) => (
                <div 
                  key={angle.id}
                  className="relative rounded-xl overflow-hidden border border-slate-700/80 bg-slate-950 group"
                >
                  <img 
                    src={angle.dataUrl} 
                    alt={`Angle ${idx + 1}`} 
                    className="w-full aspect-4/3 object-cover" 
                  />
                  <div className="absolute inset-x-0 bottom-0 p-2 bg-gradient-to-t from-black/80 via-black/40 to-transparent flex items-center justify-between text-white text-[11px] font-semibold">
                    <span>{angle.label} Panel</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveAngle(angle.id)}
                      className="p-1 rounded-lg bg-rose-500/30 hover:bg-rose-500 text-rose-200 transition-colors cursor-pointer"
                      title="Remove Angle"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {analysisError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300">
                {analysisError}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
};
