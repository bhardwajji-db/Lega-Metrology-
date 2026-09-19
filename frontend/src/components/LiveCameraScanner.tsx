import React, { useEffect, useRef, useState, useCallback } from 'react';
import { 
  Camera, 
  FlipHorizontal, 
  Flashlight, 
  FlashlightOff, 
  Scan, 
  Barcode, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  X,
  Play,
  Square,
  Upload,
  ShieldAlert,
  CameraOff
} from 'lucide-react';
import { getApiBaseUrl } from '../config/api';
import { tokenStore } from '../services/api';
import { 
  requestCameraStream, 
  stopMediaStream, 
  checkCameraCapability, 
  formatCameraError 
} from '../utils/camera';

interface LiveDetectionBox {
  label: string;
  confidence: number;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2]
  type: string;
  color: string;
}

interface LiveFrameResult {
  detected: boolean;
  barcodes: Array<{
    raw_value: string;
    symbology: string;
    confidence: number;
    country_of_origin?: string;
    country_flag?: string;
  }>;
  hud_boxes: LiveDetectionBox[];
  fps_estimate: number;
  summary: string;
}

interface LiveCameraScannerProps {
  onCaptureSnapshot?: (blob: Blob, dataUrl: string) => void;
  onBarcodeDetected?: (barcode: any) => void;
  onClose?: () => void;
}

export const LiveCameraScanner: React.FC<LiveCameraScannerProps> = ({
  onCaptureSnapshot,
  onBarcodeDetected,
  onClose
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const activeRequestIdRef = useRef<number>(0);

  const [stream, setStream] = useState<MediaStream | null>(null);
  const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment');
  const [isTorchOn, setIsTorchOn] = useState(false);
  const [hasTorch, setHasTorch] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isInspecting, setIsInspecting] = useState(true);
  const [fps, setFps] = useState<number>(0);
  const [latencyMs, setLatencyMs] = useState<number>(0);
  const [detectedBarcodes, setDetectedBarcodes] = useState<any[]>([]);
  const [lastSummary, setLastSummary] = useState<string>('Initializing Live Scanner...');
  const [isCapturing, setIsCapturing] = useState(false);
  const [flashEffect, setFlashEffect] = useState(false);
  const [staticPhotoUrl, setStaticPhotoUrl] = useState<string | null>(null);

  const inspectingRef = useRef(isInspecting);
  inspectingRef.current = isInspecting;

  // Stop camera helper
  const stopCurrentStream = useCallback(() => {
    if (streamRef.current) {
      stopMediaStream(streamRef.current);
      streamRef.current = null;
    }
    if (videoRef.current) {
      try {
        videoRef.current.pause();
        videoRef.current.srcObject = null;
      } catch (e) {
        // ignore pause error
      }
    }
    setStream(null);
    setHasTorch(false);
    setIsTorchOn(false);
  }, []);

  // Initialize camera stream with robust capability check & race-condition cancellation
  const startCamera = useCallback(async (mode: 'environment' | 'user') => {
    const requestId = ++activeRequestIdRef.current;
    setError(null);
    setStaticPhotoUrl(null);
    stopCurrentStream();

    // 1. Verify capability before requesting hardware
    const capability = checkCameraCapability();
    if (!capability.supported) {
      setError(capability.errorMessage || 'Camera access is not supported in this environment.');
      return;
    }

    try {
      const mediaStream = await requestCameraStream({
        facingMode: mode,
        idealWidth: 1280,
        idealHeight: 720
      });

      // If a subsequent request was launched or component unmounted while awaiting, discard this stream immediately
      if (activeRequestIdRef.current !== requestId) {
        stopMediaStream(mediaStream);
        return;
      }

      streamRef.current = mediaStream;
      setStream(mediaStream);

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        videoRef.current.play().catch(playErr => {
          // Play request may be interrupted if component re-rendered or paused
          console.debug('[Camera] Video play interrupted:', playErr);
        });
      }

      // Check torch capability
      const videoTrack = mediaStream.getVideoTracks()[0];
      if (videoTrack && typeof videoTrack.getCapabilities === 'function') {
        const capabilities = videoTrack.getCapabilities() as any;
        setHasTorch(Boolean(capabilities?.torch));
      }
    } catch (err: any) {
      if (activeRequestIdRef.current !== requestId) return;
      console.error('[Camera] Access error:', err);
      setError(formatCameraError(err));
    }
  }, [stopCurrentStream]);

  // Lifecycle effect: start camera on mount and when facingMode changes; clean up on unmount
  useEffect(() => {
    startCamera(facingMode);

    return () => {
      activeRequestIdRef.current++;
      stopCurrentStream();
    };
  }, [facingMode, startCamera, stopCurrentStream]);

  // Toggle Torch/Flashlight
  const toggleTorch = async () => {
    if (!stream) return;
    const track = stream.getVideoTracks()[0] as any;
    if (track && hasTorch) {
      try {
        const nextTorch = !isTorchOn;
        await track.applyConstraints({ advanced: [{ torch: nextTorch }] });
        setIsTorchOn(nextTorch);
      } catch (e) {
        console.warn('[Camera] Could not toggle torch:', e);
      }
    }
  };

  // Flip Camera
  const toggleFacingMode = () => {
    setFacingMode(prev => (prev === 'environment' ? 'user' : 'environment'));
  };

  // Process a frame image base64 through backend live analyzer
  const processFrameData = useCallback(async (b64: string, w: number, h: number) => {
    const t0 = performance.now();
    try {
      const token = tokenStore.get();
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(`${getApiBaseUrl()}/barcode/live-frame`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ image_base64: b64, include_text_boxes: true })
      });

      if (res.ok) {
        const data: LiveFrameResult = await res.json();
        const elapsed = Math.round(performance.now() - t0);
        setLatencyMs(elapsed);
        setFps(data.fps_estimate);
        setLastSummary(data.summary);

        if (data.barcodes && data.barcodes.length > 0) {
          setDetectedBarcodes(data.barcodes);
          if (onBarcodeDetected) {
            onBarcodeDetected(data.barcodes[0]);
          }
        }

        // Render HUD Bounding Boxes on Overlay Canvas
        renderOverlay(data.hud_boxes, w, h);
      }
    } catch (err) {
      // Silently ignore drop frames in continuous inspection loop
    }
  }, [onBarcodeDetected]);

  // Continuous inspection loop: grab frame from live video and inspect
  useEffect(() => {
    let animationFrameId: number;
    let isProcessing = false;
    let lastProcessTime = 0;

    const processLoop = async (now: number) => {
      const video = videoRef.current;
      const isReady = video && video.readyState >= 2 && video.videoWidth > 0 && !video.paused;

      if (inspectingRef.current && !isProcessing && isReady) {
        // Send frame roughly every 750ms for low network pressure and high responsiveness
        if (now - lastProcessTime > 750) {
          isProcessing = true;
          lastProcessTime = now;

          try {
            const captureCanvas = canvasRef.current;
            if (captureCanvas && video) {
              const w = 960;
              const h = Math.round((video.videoHeight / Math.max(video.videoWidth, 1)) * w) || 540;
              captureCanvas.width = w;
              captureCanvas.height = h;
              const ctx = captureCanvas.getContext('2d');
              if (ctx) {
                ctx.drawImage(video, 0, 0, w, h);

                // Check for native BarcodeDetector if supported in browser
                if ('BarcodeDetector' in window) {
                  try {
                    const BarcodeDetectorClass = (window as any).BarcodeDetector;
                    const detector = new BarcodeDetectorClass({
                      formats: ['qr_code', 'ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39', 'data_matrix']
                    });
                    const barcodes = await detector.detect(captureCanvas);
                    if (barcodes && barcodes.length > 0) {
                      const first = barcodes[0];
                      const detected = {
                        raw_value: first.rawValue,
                        symbology: first.format.toUpperCase().replace('_', '-'),
                        confidence: 0.99
                      };
                      setDetectedBarcodes([detected]);
                      if (onBarcodeDetected) {
                        onBarcodeDetected(detected);
                      }
                    }
                  } catch (clientDetectErr) {
                    // Fallback to server inspection
                  }
                }

                const b64 = captureCanvas.toDataURL('image/jpeg', 0.6);
                await processFrameData(b64, w, h);
              }
            }
          } catch (err) {
            // Silently drop
          } finally {
            isProcessing = false;
          }
        }
      }
      animationFrameId = requestAnimationFrame(processLoop);
    };

    animationFrameId = requestAnimationFrame(processLoop);
    return () => cancelAnimationFrame(animationFrameId);
  }, [processFrameData, onBarcodeDetected]);

  // Draw bounding boxes over video stream
  const renderOverlay = (boxes: LiveDetectionBox[], srcW: number, srcH: number) => {
    const overlay = overlayCanvasRef.current;
    const video = videoRef.current;
    if (!overlay) return;

    const vW = video ? video.clientWidth : overlay.clientWidth;
    const vH = video ? video.clientHeight : overlay.clientHeight;
    overlay.width = vW;
    overlay.height = vH;

    const ctx = overlay.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, vW, vH);

    const scaleX = vW / Math.max(srcW, 1);
    const scaleY = vH / Math.max(srcH, 1);

    for (const b of boxes) {
      const [x1, y1, x2, y2] = b.bbox;
      const rx = x1 * scaleX;
      const ry = y1 * scaleY;
      const rw = (x2 - x1) * scaleX;
      const rh = (y2 - y1) * scaleY;

      // Draw box
      ctx.strokeStyle = b.color || '#10b981';
      ctx.lineWidth = 2.5;
      ctx.setLineDash(b.type === 'barcode' ? [] : [6, 4]);
      ctx.strokeRect(rx, ry, rw, rh);
      ctx.setLineDash([]);

      // Draw corner brackets
      const cornerLen = Math.min(14, rw * 0.3);
      ctx.lineWidth = 3.5;
      ctx.beginPath();
      ctx.moveTo(rx, ry + cornerLen);
      ctx.lineTo(rx, ry);
      ctx.lineTo(rx + cornerLen, ry);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(rx + rw, ry + rh - cornerLen);
      ctx.lineTo(rx + rw, ry + rh);
      ctx.lineTo(rx + rw - cornerLen, ry + rh);
      ctx.stroke();

      // Label background
      ctx.font = 'bold 11px system-ui, sans-serif';
      const textWidth = ctx.measureText(b.label).width;
      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      ctx.fillRect(rx, Math.max(0, ry - 20), textWidth + 12, 18);

      // Label text
      ctx.fillStyle = b.color || '#10b981';
      ctx.fillText(b.label, rx + 6, Math.max(14, ry - 6));
    }
  };

  // High-Resolution Snapshot Capture from Video with Instant Barcode Scanning & Data Fetching
  const handleSnapPhoto = () => {
    if (!videoRef.current) return;
    setIsCapturing(true);
    setFlashEffect(true);
    setTimeout(() => setFlashEffect(false), 200);

    const video = videoRef.current;
    const captureCanvas = document.createElement('canvas');
    captureCanvas.width = video.videoWidth || 1280;
    captureCanvas.height = video.videoHeight || 720;
    const ctx = captureCanvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
      const dataUrl = captureCanvas.toDataURL('image/jpeg', 0.92);

      captureCanvas.toBlob(async (blob) => {
        // 1. Deliver snapshot to parent for packaging angles
        if (blob && onCaptureSnapshot) {
          onCaptureSnapshot(blob, dataUrl);
        }

        // 2. Immediately scan the high-resolution photo for barcodes & fetch product data
        try {
          const token = tokenStore.get();
          const headers: Record<string, string> = {};
          if (token) headers['Authorization'] = `Bearer ${token}`;

          const formData = new FormData();
          if (blob) {
            formData.append('file', blob, 'snapshot.jpg');
          }

          setLastSummary('Scanning captured photo for barcode & product data...');

          const res = await fetch(`${getApiBaseUrl()}/barcode/scan`, {
            method: 'POST',
            headers,
            body: formData
          });

          if (res.ok) {
            const barcodes: any[] = await res.json();
            if (barcodes && barcodes.length > 0) {
              setDetectedBarcodes(barcodes);
              const first = barcodes[0];
              const desc = first.product_name || first.brand_name || first.country_of_origin || first.symbology;
              setLastSummary(`✓ Detected ${first.raw_value} (${desc})`);
              if (onBarcodeDetected) {
                onBarcodeDetected(first);
              }
            } else {
              setLastSummary('Photo saved. No barcode detected in this angle.');
            }
          }
        } catch (scanErr) {
          console.error('[LiveCameraScanner] Error scanning captured photo:', scanErr);
          setLastSummary('Photo saved to angles strip.');
        } finally {
          setIsCapturing(false);
        }
      }, 'image/jpeg', 0.92);
    }
  };

  // Fallback / Alternate File Upload when Camera is not available or user selects file
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (evt) => {
      const dataUrl = evt.target?.result as string;
      if (!dataUrl) return;

      setStaticPhotoUrl(dataUrl);
      setError(null);
      setIsCapturing(true);
      setLastSummary('Scanning uploaded photo for barcode...');

      // 1. Deliver snapshot
      if (onCaptureSnapshot) {
        onCaptureSnapshot(file, dataUrl);
      }

      // 2. Process uploaded image directly via full-res /barcode/scan endpoint
      try {
        const token = tokenStore.get();
        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch(`${getApiBaseUrl()}/barcode/scan`, {
          method: 'POST',
          headers,
          body: formData
        });

        if (res.ok) {
          const barcodes: any[] = await res.json();
          if (barcodes && barcodes.length > 0) {
            setDetectedBarcodes(barcodes);
            const first = barcodes[0];
            const desc = first.product_name || first.brand_name || first.country_of_origin || first.symbology;
            setLastSummary(`✓ Detected ${first.raw_value} (${desc})`);
            if (onBarcodeDetected) {
              onBarcodeDetected(first);
            }
          } else {
            setLastSummary('Uploaded photo saved. No barcode detected.');
          }
        }
      } catch (uploadErr) {
        console.error('[LiveCameraScanner] File upload barcode scan error:', uploadErr);
      } finally {
        setIsCapturing(false);
      }
    };
    reader.readAsDataURL(file);
  };

  return (
    <div className="relative w-full max-w-4xl mx-auto rounded-3xl overflow-hidden bg-slate-950 border border-slate-800 shadow-2xl flex flex-col">
      {/* Hidden processing canvas & file input */}
      <canvas ref={canvasRef} className="hidden" />
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFileUpload}
      />

      {/* Camera Viewfinder Header */}
      <div className="absolute top-0 inset-x-0 z-30 p-4 bg-gradient-to-b from-slate-950/90 via-slate-950/40 to-transparent flex items-center justify-between text-white">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-indigo-500/20 border border-indigo-500/40 text-indigo-400">
            <Scan className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h3 className="text-sm font-bold tracking-wide flex items-center gap-2">
              Live Packaging Inspection
              {!error && (
                <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                  LIVE
                </span>
              )}
            </h3>
            <p className="text-[11px] text-slate-400">
              {error ? (
                'Camera offline'
              ) : latencyMs > 0 ? (
                `${latencyMs}ms latency · ~${fps} FPS · ${lastSummary}`
              ) : (
                'Point camera at product packaging or barcode'
              )}
            </p>
          </div>
        </div>

        {/* Action Controls in Top Bar */}
        <div className="flex items-center gap-2">
          {hasTorch && !error && (
            <button
              onClick={toggleTorch}
              className={`p-2 rounded-xl border transition-all cursor-pointer ${
                isTorchOn
                  ? 'bg-amber-500 text-slate-950 border-amber-400 shadow-lg shadow-amber-500/20'
                  : 'bg-slate-900/80 text-slate-300 border-slate-700 hover:bg-slate-800'
              }`}
              title="Toggle Flashlight"
            >
              {isTorchOn ? <Flashlight className="w-4 h-4" /> : <FlashlightOff className="w-4 h-4" />}
            </button>
          )}

          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-2 rounded-xl bg-slate-900/80 text-slate-300 border border-slate-700 hover:bg-slate-800 transition-all cursor-pointer"
            title="Upload Packaging Photo / Frame"
          >
            <Upload className="w-4 h-4" />
          </button>

          <button
            onClick={toggleFacingMode}
            disabled={Boolean(error)}
            className="p-2 rounded-xl bg-slate-900/80 text-slate-300 border border-slate-700 hover:bg-slate-800 transition-all cursor-pointer disabled:opacity-40"
            title="Switch Camera (Front / Back)"
          >
            <FlipHorizontal className="w-4 h-4" />
          </button>

          {onClose && (
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-slate-900/80 text-slate-400 hover:text-white border border-slate-700 hover:bg-slate-800 transition-all cursor-pointer"
              title="Close Scanner"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Video Viewport & Overlays */}
      <div className="relative w-full aspect-4/3 sm:aspect-16/9 bg-black flex items-center justify-center overflow-hidden">
        {error ? (
          <div className="p-6 text-center max-w-md space-y-4 z-20">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400">
              {error.includes('permission') ? (
                <ShieldAlert className="w-7 h-7" />
              ) : error.includes('HTTPS') ? (
                <AlertCircle className="w-7 h-7" />
              ) : (
                <CameraOff className="w-7 h-7" />
              )}
            </div>
            
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-slate-200">Camera Unavailable</h4>
              <p className="text-xs text-rose-200 font-medium leading-relaxed">{error}</p>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => startCamera(facingMode)}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all inline-flex items-center gap-2 cursor-pointer shadow-lg shadow-indigo-600/25"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Retry Camera
              </button>

              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-bold transition-all inline-flex items-center gap-2 cursor-pointer"
              >
                <Upload className="w-3.5 h-3.5" /> Upload Photo Instead
              </button>
            </div>
          </div>
        ) : staticPhotoUrl ? (
          <div className="relative w-full h-full flex items-center justify-center">
            <img src={staticPhotoUrl} alt="Static Scan" className="w-full h-full object-contain" />
            <canvas
              ref={overlayCanvasRef}
              className="absolute inset-0 w-full h-full pointer-events-none z-10"
            />
          </div>
        ) : (
          <>
            <video
              ref={videoRef}
              playsInline
              muted
              autoPlay
              className="w-full h-full object-cover"
            />
            {/* Real-time Bounding Box Canvas Overlay */}
            <canvas
              ref={overlayCanvasRef}
              className="absolute inset-0 w-full h-full pointer-events-none z-10"
            />

            {/* Packaging Target Reticle / Alignment Guide */}
            <div className="absolute inset-x-8 inset-y-12 border-2 border-indigo-500/30 rounded-2xl pointer-events-none z-10 flex flex-col justify-between p-4">
              <div className="flex justify-between">
                <span className="w-4 h-4 border-t-2 border-l-2 border-indigo-400 rounded-tl-sm" />
                <span className="w-4 h-4 border-t-2 border-r-2 border-indigo-400 rounded-tr-sm" />
              </div>
              <div className="text-center">
                <span className="px-3 py-1 rounded-full bg-slate-950/70 border border-indigo-500/30 text-[11px] text-indigo-300 font-medium backdrop-blur-md">
                  Align barcode or product label within frame
                </span>
              </div>
              <div className="flex justify-between">
                <span className="w-4 h-4 border-b-2 border-l-2 border-indigo-400 rounded-bl-sm" />
                <span className="w-4 h-4 border-b-2 border-r-2 border-indigo-400 rounded-br-sm" />
              </div>
            </div>

            {/* Flash Effect on Capture */}
            {flashEffect && (
              <div className="absolute inset-0 bg-white z-40 animate-out fade-out duration-200" />
            )}
          </>
        )}
      </div>

      {/* Bottom Control & Inspection Bar */}
      <div className="p-4 bg-slate-900 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4 z-20">
        {/* Detection Status Pills */}
        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          {detectedBarcodes.length > 0 ? (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span className="font-mono font-bold">{detectedBarcodes[0].raw_value}</span>
              <span className="text-[10px] text-emerald-400/80">({detectedBarcodes[0].symbology})</span>
              {detectedBarcodes[0].country_flag && (
                <span title={detectedBarcodes[0].country_of_origin}>{detectedBarcodes[0].country_flag}</span>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-800/80 border border-slate-700/60 text-slate-400 text-xs">
              <Barcode className="w-4 h-4 text-slate-500 shrink-0" />
              <span>{error ? 'Camera standby' : 'Searching for Barcode / Declarations...'}</span>
            </div>
          )}

          {/* Toggle Continuous Inspection */}
          {!error && (
            <button
              onClick={() => setIsInspecting(!isInspecting)}
              className={`px-3 py-1.5 rounded-xl border text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                isInspecting
                  ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-300'
                  : 'bg-slate-800 border-slate-700 text-slate-400'
              }`}
            >
              {isInspecting ? <Square className="w-3 h-3 text-indigo-400" /> : <Play className="w-3 h-3" />}
              {isInspecting ? 'Auto-HUD Active' : 'Auto-HUD Paused'}
            </button>
          )}
        </div>

        {/* Big Snapshot Capture Button */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSnapPhoto}
            disabled={isCapturing || Boolean(error)}
            className="px-6 py-2.5 rounded-2xl bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 text-white font-bold text-sm shadow-lg shadow-indigo-500/25 active:scale-95 transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
          >
            <Camera className="w-4 h-4" />
            <span>Capture & Inspect</span>
          </button>
        </div>
      </div>
    </div>
  );
};
