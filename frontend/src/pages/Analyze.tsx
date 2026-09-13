import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  UploadCloud, 
  X, 
  Settings, 
  Eye, 
  FileSearch, 
  ShieldCheck, 
  FileText, 
  Loader2, 
  ScanSearch, 
  AlertTriangle, 
  Sparkles, 
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  RefreshCw,
  Info,
  Check,
  Zap,
  Clock,
  Camera,
  SwitchCamera
} from 'lucide-react';
import { api } from '../services/api';

type SlotKey = 'front' | 'back' | 'side1' | 'side2';

interface SlotDefinition {
  key: SlotKey;
  label: string;
  requirement: 'required' | 'recommended' | 'optional';
  badgeText: string;
  description: string;
  hints: string;
}

const SLOTS: SlotDefinition[] = [
  {
    key: 'front',
    label: 'Front',
    requirement: 'required',
    badgeText: 'Required',
    description: 'Upload the front label',
    hints: 'Brand, product name, net quantity & veg/non-veg'
  },
  {
    key: 'back',
    label: 'Back',
    requirement: 'recommended',
    badgeText: 'Recommended',
    description: 'Upload the back panel',
    hints: 'MRP, date/expiry, FSSAI lic., mfg address & ingredients'
  },
  {
    key: 'side1',
    label: 'Side 1',
    requirement: 'optional',
    badgeText: 'Optional',
    description: 'Upload side panel 1',
    hints: 'Consumer care, nutritional table, batch details'
  },
  {
    key: 'side2',
    label: 'Side 2',
    requirement: 'optional',
    badgeText: 'Optional',
    description: 'Upload side panel 2',
    hints: 'Additional declarations, bar code & certifications'
  }
];

interface UploadedSlotItem {
  key: SlotKey;
  label: string;
  file: File;
  preview: string;
}

interface ConceptualStage {
  id: string;
  title: string;
  explanation: string;
  icon: React.ComponentType<{ className?: string }>;
}

const CONCEPTUAL_STAGES: ConceptualStage[] = [
  {
    id: 'images_received',
    title: 'Images Received',
    explanation: 'Package images have been received.',
    icon: UploadCloud
  },
  {
    id: 'quality_check',
    title: 'Image Quality Check',
    explanation: 'Checking image clarity and orientation.',
    icon: Eye
  },
  {
    id: 'ocr_extraction',
    title: 'OCR Text Extraction',
    explanation: 'Reading visible text from the package.',
    icon: ScanSearch
  },
  {
    id: 'declaration_extraction',
    title: 'Declaration Extraction',
    explanation: 'Identifying label declarations such as MRP, quantity and dates.',
    icon: FileSearch
  },
  {
    id: 'rules_evaluation',
    title: 'Applicable Rules Evaluation',
    explanation: 'Determining which Legal Metrology and FSSAI requirements apply.',
    icon: Settings
  },
  {
    id: 'compliance_screening',
    title: 'Compliance Screening',
    explanation: 'Comparing detected declarations with applicable requirements.',
    icon: ShieldCheck
  },
  {
    id: 'preparing_results',
    title: 'Preparing Results',
    explanation: 'Organizing findings, evidence and recommended actions.',
    icon: FileText
  }
];

const MAX_IMAGES = 4;
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

export default function Analyze() {
  const navigate = useNavigate();
  
  // Dedicated file inputs for each slot (Gallery & Native Camera)
  const frontInputRef = useRef<HTMLInputElement>(null);
  const backInputRef = useRef<HTMLInputElement>(null);
  const side1InputRef = useRef<HTMLInputElement>(null);
  const side2InputRef = useRef<HTMLInputElement>(null);

  const slotInputRefs: Record<SlotKey, React.RefObject<HTMLInputElement | null>> = {
    front: frontInputRef,
    back: backInputRef,
    side1: side1InputRef,
    side2: side2InputRef
  };

  const frontCameraInputRef = useRef<HTMLInputElement>(null);
  const backCameraInputRef = useRef<HTMLInputElement>(null);
  const side1CameraInputRef = useRef<HTMLInputElement>(null);
  const side2CameraInputRef = useRef<HTMLInputElement>(null);

  const slotCameraInputRefs: Record<SlotKey, React.RefObject<HTMLInputElement | null>> = {
    front: frontCameraInputRef,
    back: backCameraInputRef,
    side1: side1CameraInputRef,
    side2: side2CameraInputRef
  };
  // General multi-file input for bulk drag & drop
  const generalFileInputRef = useRef<HTMLInputElement>(null);

  const [slotItems, setSlotItems] = useState<Record<SlotKey, UploadedSlotItem | null>>({
    front: null,
    back: null,
    side1: null,
    side2: null
  });

  const [isProcessing, setIsProcessing] = useState(false);
  const [activeStageIndex, setActiveStageIndex] = useState<number>(0);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOverSlot, setDragOverSlot] = useState<SlotKey | 'general' | null>(null);
  const [demoActiveCase, setDemoActiveCase] = useState<number | null>(null);

  // Top-level Mode Switcher: "image" (default) or "text" (Product Listing text)
  const [scanMode, setScanMode] = useState<'image' | 'text'>('image');
  const [listingText, setListingText] = useState<string>('');

  // Live Camera Scanner State & Handlers
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [activeCameraSlot, setActiveCameraSlot] = useState<SlotKey>('front');
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isCameraReady, setIsCameraReady] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const startCamera = async (slot: SlotKey) => {
    setActiveCameraSlot(slot);
    setCameraError(null);
    setIsCameraReady(false);
    setIsCameraOpen(true);
    try {
      if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: facingMode }, width: { ideal: 1920 }, height: { ideal: 1080 } }
      });
      setCameraStream(stream);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current?.play();
          setIsCameraReady(true);
        };
      }
    } catch (err: any) {
      setCameraError("Camera access denied or unavailable. Please enable camera permissions in your browser.");
    }
  };

  const stopCamera = () => {
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop());
      setCameraStream(null);
    }
    setIsCameraOpen(false);
  };

  const captureSnapshot = () => {
    if (!videoRef.current) return;
    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob) return;
      const file = new File([blob], `${activeCameraSlot}_live_snapshot.jpg`, { type: 'image/jpeg' });
      handleSlotFileSelected(activeCameraSlot, file);
      stopCamera();
    }, 'image/jpeg', 0.95);
  };
  const toggleFacingMode = async () => {
    const nextMode = facingMode === 'environment' ? 'user' : 'environment';
    setFacingMode(nextMode);
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop());
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: nextMode }, width: { ideal: 1920 }, height: { ideal: 1080 } }
      });
      setCameraStream(stream);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current?.play();
        };
      }
    } catch (err) {
      // Fallback
    }
  };
  const stageIntervalRef = useRef<number | null>(null);

  // Clean up object URLs and timers on unmount
  useEffect(() => {
    return () => {
      if (stageIntervalRef.current) clearInterval(stageIntervalRef.current);
      Object.values(slotItems).forEach(item => {
        if (item?.preview) URL.revokeObjectURL(item.preview);
      });
    };
  }, []);

  const stagedItems = SLOTS
    .map(slot => slotItems[slot.key])
    .filter((item): item is UploadedSlotItem => item !== null);

  const stagedCount = stagedItems.length;

  const validateFile = (file: File): string | null => {
    if (!ALLOWED_TYPES.includes(file.type) && !/\.(jpe?g|png|webp)$/i.test(file.name)) {
      return `"${file.name}" is not a supported format. Please upload JPG, PNG, or WEBP images.`;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      return `"${file.name}" exceeds the 10MB file size limit.`;
    }
    return null;
  };

  const handleSlotFileSelected = (slotKey: SlotKey, file: File) => {
    setError(null);
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }

    // Revoke previous preview if replacing
    if (slotItems[slotKey]?.preview) {
      URL.revokeObjectURL(slotItems[slotKey]!.preview);
    }

    const slotDef = SLOTS.find(s => s.key === slotKey)!;
    const previewUrl = URL.createObjectURL(file);

    setSlotItems(prev => ({
      ...prev,
      [slotKey]: {
        key: slotKey,
        label: slotDef.label,
        file,
        preview: previewUrl
      }
    }));
  };

  const handleBulkFiles = (files: FileList | File[]) => {
    setError(null);
    const fileArray = Array.from(files);

    if (fileArray.length > MAX_IMAGES) {
      setError(`You can upload a maximum of ${MAX_IMAGES} images per package.`);
      return;
    }

    // Find available empty slots in order: front -> back -> side1 -> side2
    const emptySlotKeys = SLOTS
      .map(s => s.key)
      .filter(key => slotItems[key] === null);

    if (emptySlotKeys.length === 0 && fileArray.length > 0) {
      setError('All 4 image slots are already occupied. Remove or replace existing images to add new ones.');
      return;
    }

    const newSlots = { ...slotItems };
    for (let i = 0; i < fileArray.length; i++) {
      const file = fileArray[i];
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }

      const targetKey = emptySlotKeys[i] || (SLOTS[i] ? SLOTS[i].key : null);
      if (targetKey) {
        if (newSlots[targetKey]?.preview) {
          URL.revokeObjectURL(newSlots[targetKey]!.preview);
        }
        const slotDef = SLOTS.find(s => s.key === targetKey)!;
        newSlots[targetKey] = {
          key: targetKey,
          label: slotDef.label,
          file,
          preview: URL.createObjectURL(file)
        };
      }
    }

    setSlotItems(newSlots);
  };

  const handleSlotInputChange = (slotKey: SlotKey, e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleSlotFileSelected(slotKey, e.target.files[0]);
      e.target.value = '';
    }
  };

  const removeSlotItem = (slotKey: SlotKey) => {
    setSlotItems(prev => {
      const current = prev[slotKey];
      if (current?.preview) {
        URL.revokeObjectURL(current.preview);
      }
      return {
        ...prev,
        [slotKey]: null
      };
    });
  };

  const clearAll = () => {
    Object.values(slotItems).forEach(item => {
      if (item?.preview) URL.revokeObjectURL(item.preview);
    });
    setSlotItems({
      front: null,
      back: null,
      side1: null,
      side2: null
    });
    setError(null);
  };

  // Drag and drop handlers for specific slots
  const handleSlotDragOver = (slotKey: SlotKey, e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverSlot(slotKey);
  };

  const handleSlotDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverSlot(null);
  };

  const handleSlotDrop = (slotKey: SlotKey, e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverSlot(null);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      if (e.dataTransfer.files.length === 1) {
        handleSlotFileSelected(slotKey, e.dataTransfer.files[0]);
      } else {
        handleBulkFiles(e.dataTransfer.files);
      }
    }
  };

  const startPipelineAnimation = (isDemo = false) => {
    if (stageIntervalRef.current) clearInterval(stageIntervalRef.current);
    
    // Immediately start with Stage 0 (Images Received) completed, Stage 1 (Quality Check) active
    setActiveStageIndex(1);
    setIsComplete(false);

    const stepDuration = isDemo ? 220 : 650;

    // Cycle through conceptual stages up to stage 5 (Compliance Screening),
    // holding at stage 5 until the real API call finishes.
    stageIntervalRef.current = window.setInterval(() => {
      setActiveStageIndex(prev => {
        if (prev < 5) return prev + 1;
        return prev;
      });
    }, stepDuration);
  };

  const finishPipelineAndNavigate = async (result: any, isDemo = false, caseNum?: number) => {
    if (stageIntervalRef.current) clearInterval(stageIntervalRef.current);

    // Fast-forward to final stage (Preparing Results)
    setActiveStageIndex(6);
    setIsComplete(true);

    // Brief smooth transition before navigating to results
    await new Promise(resolve => setTimeout(resolve, isDemo ? 250 : 450));

    navigate(`/results/${result.id}`, { 
      state: { 
        analysisData: result,
        isDemo,
        demoCaseId: caseNum 
      } 
    });
  };

  const startAnalysis = async () => {
    if (stagedCount === 0 || isProcessing) return;
    
    setIsProcessing(true);
    setError(null);
    setDemoActiveCase(null);
    startPipelineAnimation(false);

    try {
      const payload = stagedItems.map(item => ({ file: item.file, label: item.label }));
      const result = await api.analyzeProducts(payload);
      await finishPipelineAndNavigate(result, false);
    } catch (err: any) {
      if (stageIntervalRef.current) clearInterval(stageIntervalRef.current);
      console.error('Analysis submission error:', err);
      const serverMsg = err?.message || 'Analysis could not be completed. Something went wrong while processing the package. Please try again.';
      setError(serverMsg);
      setIsProcessing(false);
    }
  };

  const SAMPLE_LISTING_TEXT = `Product Name: Premium Roasted California Almonds (Lightly Salted)
Brand: NutriHarvest Organics
Category: Packaged Food / Dry Fruits
Net Quantity: 500 g (0.5 kg)
Maximum Retail Price (MRP): Rs. 499.00 (Inclusive of all taxes)
Unit Sale Price: Rs. 0.998 / g
Date of Manufacture: 08/2026
Best Before: 9 months from date of manufacture
Batch Number: NH-ALM-2026-08B
FSSAI License No.: 10020011000123
Country of Origin: India

Manufactured & Packed by:
NutriHarvest Foods India Pvt. Ltd.
Plot No. 45, Sector 8, Industrial Estate,
Manesar, Gurugram, Haryana - 122050

Marketed by:
NutriHarvest Global Brands LLP
12th Floor, Tower B, Cyber City, DLF Phase 2,
Gurugram, Haryana - 122002

Consumer Care Cell:
Customer Support Manager, NutriHarvest Foods India Pvt. Ltd.
Toll-Free Phone: 1800-200-8899
Email: care@nutriharvest.in
Website: https://www.nutriharvest.in

Ingredients:
California Almonds (98%), Edible Common Salt (1.5%), Refined Sunflower Oil (0.5%).

Nutritional Information (per 100g):
Energy: 579 kcal, Protein: 21.2g, Carbohydrates: 21.6g, Total Fat: 49.9g, Sodium: 380mg.`;

  const handleAnalyzeText = async () => {
    const trimmed = listingText.trim();
    if (!trimmed) {
      setError('Please paste or enter product listing / label text before analyzing.');
      return;
    }

    setIsProcessing(true);
    setError(null);
    setDemoActiveCase(null);
    startPipelineAnimation(false);

    try {
      const result = await api.analyzeText(trimmed);
      await finishPipelineAndNavigate(result, false);
    } catch (err: unknown) {
      if (stageIntervalRef.current) clearInterval(stageIntervalRef.current);
      console.error('Text analysis submission error:', err);
      const errorMsg = err instanceof Error ? err.message : 'Listing analysis could not be completed. Something went wrong while processing the text. Please try again.';
      setError(errorMsg);
      setIsProcessing(false);
    }
  };


  const runDemo = async (caseNum: number) => {
    if (isProcessing) return;
    setIsProcessing(true);
    setError(null);
    setDemoActiveCase(caseNum);
    startPipelineAnimation(true);

    try {
      const result = await api.getDemoCase(caseNum);
      await finishPipelineAndNavigate(result, true, caseNum);
    } catch (err: any) {
      if (stageIntervalRef.current) clearInterval(stageIntervalRef.current);
      console.error('Demo analysis error:', err);
      const errorMsg = err?.message || 'Benchmark demonstration could not be loaded. Please try again.';
      setError(errorMsg);
      setIsProcessing(false);
    }
  };


  const handleBackToAnalyze = () => {
    if (stageIntervalRef.current) clearInterval(stageIntervalRef.current);
    setIsProcessing(false);
    setError(null);
    setIsComplete(false);
    setActiveStageIndex(0);
  };

  const currentStage = CONCEPTUAL_STAGES[activeStageIndex] || CONCEPTUAL_STAGES[0];
  const ActiveIcon = currentStage.icon;

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in duration-300">
      {/* Hidden File Inputs */}
      {/* Hidden File & Camera Inputs */}
      {SLOTS.map(slot => (
        <React.Fragment key={slot.key}>
          {/* Standard Gallery / File Picker */}
          <input 
            type="file" 
            ref={slotInputRefs[slot.key]} 
            onChange={(e) => handleSlotInputChange(slot.key, e)} 
            accept="image/jpeg,image/png,image/webp" 
            className="hidden" 
            aria-label={`Upload ${slot.label} Image from Files`}
          />
          {/* Native Mobile Camera Snap */}
          <input 
            type="file" 
            ref={slotCameraInputRefs[slot.key]} 
            onChange={(e) => handleSlotInputChange(slot.key, e)} 
            accept="image/*" 
            capture="environment"
            className="hidden" 
            aria-label={`Take live photo with camera for ${slot.label}`}
          />
        </React.Fragment>
      ))}
      <input 
        type="file" 
        ref={generalFileInputRef} 
        onChange={(e) => {
          if (e.target.files) handleBulkFiles(e.target.files);
          e.target.value = '';
        }} 
        accept="image/jpeg,image/png,image/webp" 
        multiple
        className="hidden" 
        aria-label="Upload multiple packaging images"
      />
      {/* Top-Level Mode Toggle (Image Scan vs Listing Text) */}
      {!isProcessing && (
        <div className="flex items-center justify-center">
          <div className="inline-flex p-1 rounded-xl bg-slate-100 dark:bg-slate-800/90 border border-slate-200/90 dark:border-slate-700 shadow-2xs">
            <button
              type="button"
              onClick={() => { setScanMode('image'); setError(null); }}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs sm:text-sm font-bold transition-all cursor-pointer ${
                scanMode === 'image'
                  ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs border border-slate-200/80 dark:border-slate-700'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              <Camera className="w-4 h-4" />
              <span>Image Scan</span>
            </button>
            <button
              type="button"
              onClick={() => { setScanMode('text'); setError(null); }}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs sm:text-sm font-bold transition-all cursor-pointer ${
                scanMode === 'text'
                  ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs border border-slate-200/80 dark:border-slate-700'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Listing Text</span>
            </button>
          </div>
        </div>
      )}

      {/* Error Alert Banner when not on processing screen */}
      {!isProcessing && error && (
        <div 
          role="alert"
          className="p-4 rounded-xl bg-red-50/95 dark:bg-red-950/60 border border-red-200 dark:border-red-800/80 text-red-900 dark:text-red-200 flex items-start gap-3 text-sm shadow-2xs"
        >
          <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
          <div className="flex-1 space-y-1">
            <p className="font-semibold text-red-950 dark:text-red-100">Action Needed</p>
            <p className="text-xs text-red-800 dark:text-red-300 leading-relaxed">{error}</p>
          </div>
          {(scanMode === 'image' ? stagedCount > 0 : Boolean(listingText.trim())) && (
            <button
              onClick={scanMode === 'image' ? startAnalysis : handleAnalyzeText}
              className="px-2.5 py-1 bg-red-100 dark:bg-red-900/60 hover:bg-red-200 dark:hover:bg-red-800/60 text-red-900 dark:text-red-100 rounded-lg text-xs font-semibold flex items-center gap-1 transition-colors cursor-pointer"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Retry</span>
            </button>
          )}
          <button 
            onClick={() => setError(null)} 
            className="p-1 text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-200 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors cursor-pointer"
            aria-label="Dismiss error"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {!isProcessing ? (
        scanMode === 'image' ? (
          <>
          {/* Main Hero & Upload Workflow Section */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/90 dark:border-slate-800 shadow-2xs overflow-hidden">
            {/* Header / Hero */}
            <div className="p-6 sm:p-8 border-b border-slate-100 dark:border-slate-800 bg-gradient-to-b from-slate-50/50 dark:from-slate-800/40 to-white dark:to-slate-900 text-center sm:text-left">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1.5 max-w-2xl">
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200/80 dark:border-indigo-800/80 mb-1 shadow-2xs">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                    <span>AI-Assisted Compliance Screening</span>
                  </div>
                  <h2 className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-slate-100 tracking-tight">
                    Analyze Package
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                    Upload clear images of the package to screen its label declarations for compliance.
                  </p>
                </div>

                {/* Clear All Action */}
                {stagedCount > 0 && (
                  <div className="flex items-center justify-center sm:justify-end shrink-0">
                    <button 
                      onClick={clearAll}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/50 rounded-lg border border-slate-200 dark:border-slate-700 transition-colors cursor-pointer"
                      aria-label="Clear all uploaded images"
                    >
                      <X className="w-3.5 h-3.5" />
                      <span>Clear All ({stagedCount})</span>
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Upload Instructions Banner */}
            <div className="px-6 py-4 bg-slate-50/70 dark:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
                <Info className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
                <span className="font-semibold text-slate-900 dark:text-slate-100">Upload 1–4 images of the same package.</span>
              </div>
              <div className="flex flex-wrap items-center gap-2 font-medium">
                <span className="px-2 py-0.5 rounded-md bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/80 text-[11px] font-semibold">
                  Front — Required
                </span>
                <span className="px-2 py-0.5 rounded-md bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800/80 text-[11px] font-semibold">
                  Back — Recommended
                </span>
                <span className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 text-[11px]">
                  Side 1 — Optional
                </span>
                <span className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 text-[11px]">
                  Side 2 — Optional
                </span>
              </div>
            </div>

            {/* 4-Slot Upload Grid */}
            <div className="p-6 sm:p-8">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
                {SLOTS.map((slot) => {
                  const item = slotItems[slot.key];
                  const isHovered = dragOverSlot === slot.key;

                  return (
                    <div
                      key={slot.key}
                      onDragOver={(e) => handleSlotDragOver(slot.key, e)}
                      onDragLeave={handleSlotDragLeave}
                      onDrop={(e) => handleSlotDrop(slot.key, e)}
                      className={`relative rounded-2xl border transition-all duration-200 flex flex-col justify-between overflow-hidden ${
                        item 
                          ? 'border-slate-200/90 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-2xs hover:border-indigo-300 dark:hover:border-indigo-500' 
                          : isHovered
                            ? 'border-indigo-500 bg-indigo-50/70 dark:bg-indigo-950/50 shadow-sm scale-[0.99]'
                            : 'border-dashed border-slate-300 dark:border-slate-700 bg-slate-50/40 dark:bg-slate-800/30 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:border-indigo-300 dark:hover:border-indigo-500'
                      }`}
                    >
                      {/* Slot Header */}
                      <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/40">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                            {slot.label}
                          </span>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                            slot.requirement === 'required'
                              ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800/80'
                              : slot.requirement === 'recommended'
                                ? 'bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-800/80'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700'
                          }`}>
                            {slot.badgeText}
                          </span>
                        </div>

                        {/* Status badge when uploaded */}
                        {item && (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded-md border border-emerald-200 dark:border-emerald-800/80">
                            <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                            <span>Image added</span>
                          </span>
                        )}
                      </div>

                      {/* Slot Content Body */}
                      <div className="p-4 flex-1 flex flex-col justify-center">
                        {item ? (
                          /* Uploaded State: Image Preview & Details */
                          <div className="space-y-3">
                            <div className="relative w-full h-44 bg-slate-900/5 dark:bg-slate-950 rounded-xl border border-slate-200/80 dark:border-slate-700 overflow-hidden flex items-center justify-center">
                              <img 
                                src={item.preview} 
                                alt={`${slot.label} label preview`}
                                className="w-full h-full object-contain p-1"
                              />
                            </div>

                            <div className="flex items-center justify-between gap-2 pt-1 text-xs">
                              <div className="min-w-0 flex-1">
                                <p className="font-semibold text-slate-900 dark:text-slate-100 truncate" title={item.file.name}>
                                  {item.file.name}
                                </p>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                                  {(item.file.size / (1024 * 1024)).toFixed(2)} MB
                                </p>
                              </div>

                              <div className="flex items-center gap-1.5 shrink-0">
                                <button
                                  type="button"
                                  onClick={() => {
                                    if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
                                      slotCameraInputRefs[slot.key].current?.click();
                                    } else {
                                      startCamera(slot.key);
                                    }
                                  }}
                                  className="p-1.5 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/60 rounded-lg border border-indigo-200 dark:border-indigo-800 transition-colors cursor-pointer"
                                  title="Retake live photo with camera"
                                >
                                  <Camera className="w-4 h-4" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => slotInputRefs[slot.key].current?.click()}
                                  className="px-2.5 py-1 text-xs font-semibold text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-750 border border-slate-200 dark:border-slate-700 rounded-lg transition-colors cursor-pointer"
                                  aria-label={`Replace ${slot.label} from Gallery`}
                                >
                                  Gallery
                                </button>
                                <button
                                  type="button"
                                  onClick={() => removeSlotItem(slot.key)}
                                  className="px-2.5 py-1 text-xs font-semibold text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-950/60 border border-slate-200 dark:border-slate-700 rounded-lg transition-colors cursor-pointer"
                                  aria-label={`Remove ${slot.label} image`}
                                >
                                  Remove
                                </button>
                              </div>
                            </div>
                          </div>
                        ) : (
                          /* Empty State: Dropzone & Choose Button */
                          <div 
                            onClick={() => slotInputRefs[slot.key].current?.click()}
                            className="py-6 px-4 text-center cursor-pointer flex flex-col items-center justify-center space-y-2.5 focus:outline-none"
                            tabIndex={0}
                            role="button"
                            aria-label={`Upload ${slot.label} image: ${slot.description}`}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault();
                                slotInputRefs[slot.key].current?.click();
                              }
                            }}
                          >
                            <div className="w-12 h-12 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-center text-slate-500 dark:text-slate-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                              <UploadCloud className="w-6 h-6" />
                            </div>

                            <div className="space-y-0.5">
                              <p className="text-xs font-bold text-slate-800 dark:text-slate-200">
                                {slot.description}
                              </p>
                              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight max-w-xs mx-auto">
                                {slot.hints}
                              </p>
                            </div>

                            <div className="mt-3 flex flex-col sm:flex-row items-center gap-2 w-full max-w-xs justify-center" onClick={(e) => e.stopPropagation()}>
                              {/* Option 1: Live Camera Button */}
                              <button
                                type="button"
                                onClick={() => {
                                  if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
                                    slotCameraInputRefs[slot.key].current?.click();
                                  } else {
                                    startCamera(slot.key);
                                  }
                                }}
                                className="w-full sm:w-auto flex-1 inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-xs transition-all cursor-pointer active:scale-95"
                                title={`Take live photo with camera for ${slot.label}`}
                              >
                                <Camera className="w-4 h-4" />
                                <span>Live Camera</span>
                              </button>

                              {/* Option 2: Gallery / Files Picker */}
                              <button
                                type="button"
                                onClick={() => slotInputRefs[slot.key].current?.click()}
                                className="w-full sm:w-auto flex-1 inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-750 border border-slate-300 dark:border-slate-700 rounded-xl transition-colors cursor-pointer"
                                title={`Choose photo from phone gallery or files`}
                              >
                                <UploadCloud className="w-4 h-4 text-slate-500" />
                                <span>Gallery / Files</span>
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Bottom Action / CTA Bar */}
              <div className="mt-8 pt-6 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
                {/* Validation / Helper Status */}
                <div className="text-xs">
                  {stagedCount === 0 ? (
                    <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
                      <Info className="w-4 h-4 text-amber-500 dark:text-amber-400 shrink-0" />
                      <span>Add at least one package image to continue.</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400 font-medium">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                      <span>
                        {stagedCount} {stagedCount === 1 ? 'image' : 'images'} staged for compliance screening
                        {stagedCount === 1 && ' (Front + Back recommended)'}
                      </span>
                    </div>
                  )}
                </div>

                {/* Primary CTA Button */}
                <button 
                  type="button"
                  onClick={startAnalysis}
                  disabled={stagedCount === 0 || isProcessing}
                  className={`px-8 py-3 rounded-xl font-bold text-xs sm:text-sm shadow-2xs transition-all flex items-center justify-center gap-2 cursor-pointer ${
                    stagedCount === 0 || isProcessing
                      ? 'bg-slate-200 dark:bg-slate-800 text-slate-400 dark:text-slate-600 cursor-not-allowed shadow-none border border-transparent dark:border-slate-700/50'
                      : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-500/25 active:scale-98'
                  }`}
                  aria-label="Analyze Package"
                >
                  <ScanSearch className="w-4 h-4" />
                  <span>Analyze Package {stagedCount > 0 ? `(${stagedCount} Image${stagedCount > 1 ? 's' : ''})` : ''}</span>
                </button>
              </div>
            </div>
          </div>

          {/* Guidance & Specifications Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Image Quality Guidance */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/90 dark:border-slate-800 p-5 shadow-2xs space-y-3">
              <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100 font-bold text-xs uppercase tracking-wider">
                <ShieldCheck className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                <span>For Better Screening Accuracy</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 dark:text-slate-300">
                <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800/60 p-2 rounded-lg border border-slate-100 dark:border-slate-700/60">
                  <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                  <span>Keep package flat</span>
                </div>
                <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800/60 p-2 rounded-lg border border-slate-100 dark:border-slate-700/60">
                  <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                  <span>Use good lighting</span>
                </div>
                <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800/60 p-2 rounded-lg border border-slate-100 dark:border-slate-700/60">
                  <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                  <span>Avoid glare &amp; reflections</span>
                </div>
                <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800/60 p-2 rounded-lg border border-slate-100 dark:border-slate-700/60">
                  <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                  <span>Capture complete label</span>
                </div>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed pt-1">
                For best results, ensure declarations like MRP, Net Quantity, Batch, and FSSAI License are in sharp focus.
              </p>
            </div>

            {/* Supported Formats & Guidelines */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/90 dark:border-slate-800 p-5 shadow-2xs space-y-3 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100 font-bold text-xs uppercase tracking-wider mb-3">
                  <Info className="w-4 h-4 text-sky-600 dark:text-sky-400" />
                  <span>File Specifications</span>
                </div>
                <div className="space-y-1.5 text-xs text-slate-600 dark:text-slate-300">
                  <p><strong className="text-slate-900 dark:text-slate-100">Supported formats:</strong> JPG, JPEG, PNG, WEBP</p>
                  <p><strong className="text-slate-900 dark:text-slate-100">File size limit:</strong> Up to 10 MB per image</p>
                  <p><strong className="text-slate-900 dark:text-slate-100">Capacity:</strong> 1 to 4 images per package</p>
                </div>
              </div>
              <div className="pt-2 text-[11px] text-slate-400 dark:text-slate-500 border-t border-slate-100 dark:border-slate-800">
                Statutory analysis is evaluated under Legal Metrology Rules 2011 &amp; FSSAI Regulations.
              </div>
            </div>
          </div>

          {/* Quick-Launch Demonstration Benchmarks */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-500" />
                <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                  Instant Demonstration Benchmarks (SIH 2026)
                </h3>
              </div>
              <button
                type="button"
                onClick={() => navigate('/demo')}
                className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 flex items-center gap-1 transition-colors cursor-pointer"
              >
                <span>Full Benchmark Guide</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
              <div 
                onClick={() => runDemo(1)} 
                className="p-4 rounded-xl border border-emerald-200 dark:border-emerald-800/60 bg-white dark:bg-slate-900 hover:bg-emerald-50/40 dark:hover:bg-emerald-950/30 transition-all text-left flex flex-col justify-between shadow-2xs group cursor-pointer"
                role="button"
                tabIndex={0}
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-emerald-100 dark:bg-emerald-950/80 text-emerald-800 dark:text-emerald-300">
                      COMPLIANT (95.5%)
                    </span>
                    <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <h4 className="font-bold text-xs sm:text-sm text-slate-900 dark:text-slate-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                    Basmati Rice (1kg)
                  </h4>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                    Full statutory compliance across all Legal Metrology &amp; FSSAI mandatory declarations.
                  </p>
                </div>
                <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                  <span>Load Benchmark</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </div>

              <div 
                onClick={() => runDemo(2)} 
                className="p-4 rounded-xl border border-amber-200 dark:border-amber-800/60 bg-white dark:bg-slate-900 hover:bg-amber-50/40 dark:hover:bg-amber-950/30 transition-all text-left flex flex-col justify-between shadow-2xs group cursor-pointer"
                role="button"
                tabIndex={0}
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-amber-100 dark:bg-amber-950/80 text-amber-800 dark:text-amber-300">
                      REVIEW REQUIRED (76.9%)
                    </span>
                    <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                  </div>
                  <h4 className="font-bold text-xs sm:text-sm text-slate-900 dark:text-slate-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                    Mixed Fruit Juice (1L)
                  </h4>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                    Demonstrates expiry date review and customer care contact verification.
                  </p>
                </div>
                <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs font-semibold text-amber-700 dark:text-amber-400">
                  <span>Load Benchmark</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </div>

              <div 
                onClick={() => runDemo(3)} 
                className="p-4 rounded-xl border border-red-200 dark:border-red-800/60 bg-white dark:bg-slate-900 hover:bg-red-50/40 dark:hover:bg-red-950/30 transition-all text-left flex flex-col justify-between shadow-2xs group cursor-pointer"
                role="button"
                tabIndex={0}
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-red-100 dark:bg-red-950/80 text-red-800 dark:text-red-300">
                      NON-COMPLIANT (37.9%)
                    </span>
                    <X className="w-4 h-4 text-red-600 dark:text-red-400" />
                  </div>
                  <h4 className="font-bold text-xs sm:text-sm text-slate-900 dark:text-slate-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                    Instant Noodles (70g)
                  </h4>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                    Critical missing declarations with prioritized manufacturer corrective actions.
                  </p>
                </div>
                <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs font-semibold text-red-700 dark:text-red-400">
                  <span>Load Benchmark</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </div>
            </div>
          </div>
          </>
        ) : (
          <>
            {/* Main Listing Text Scanning Section */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/90 dark:border-slate-800 shadow-2xs overflow-hidden">
              {/* Header / Hero */}
              <div className="p-6 sm:p-8 border-b border-slate-100 dark:border-slate-800 bg-gradient-to-b from-slate-50/50 dark:from-slate-800/40 to-white dark:to-slate-900 text-center sm:text-left">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="space-y-1.5 max-w-2xl">
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200/80 dark:border-indigo-800/80 mb-1 shadow-2xs">
                      <Sparkles className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                      <span>AI-Assisted Listing Text Screening</span>
                    </div>
                    <h2 className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-slate-100 tracking-tight">
                      Analyze Product Listing
                    </h2>
                    <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                      Paste e-commerce catalog text or product label descriptions to screen mandatory Legal Metrology &amp; FSSAI declarations.
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center justify-center sm:justify-end gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => {
                        setListingText(SAMPLE_LISTING_TEXT);
                        setError(null);
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 rounded-lg border border-indigo-200 dark:border-indigo-800/80 transition-colors cursor-pointer"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Load Sample</span>
                    </button>
                    {listingText && (
                      <button
                        type="button"
                        onClick={() => {
                          setListingText('');
                          setError(null);
                        }}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/50 rounded-lg border border-slate-200 dark:border-slate-700 transition-colors cursor-pointer"
                      >
                        <X className="w-3.5 h-3.5" />
                        <span>Clear</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Text Input Content */}
              <div className="p-6 sm:p-8 space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                    <label htmlFor="listing-text-input" className="font-semibold text-slate-700 dark:text-slate-300">
                      Product Listing / Label Content
                    </label>
                    <span className="font-mono text-[11px]">
                      {listingText.length} characters • {listingText.trim() ? listingText.trim().split(/\s+/).length : 0} words
                    </span>
                  </div>
                  <textarea
                    id="listing-text-input"
                    value={listingText}
                    onChange={(e) => {
                      setListingText(e.target.value);
                      if (error) setError(null);
                    }}
                    rows={10}
                    placeholder={`Paste product listing or packaging text here...\n\nExample:\nProduct Name: Roasted California Almonds\nBrand: NutriHarvest Organics\nNet Quantity: 500 g\nMRP: Rs. 499.00 (incl. of all taxes)\nDate of Mfg: 08/2026\nBest Before: 9 months from mfg\nBatch No: NH-ALM-2026-08B\nFSSAI Lic: 10020011000123\nCountry of Origin: India\nMfg by: NutriHarvest Foods India Pvt. Ltd., Manesar, Haryana\nCustomer Care: 1800-200-8899, care@nutriharvest.in`}
                    className="w-full p-4 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/40 text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all font-mono text-xs sm:text-sm resize-y leading-relaxed"
                  />
                </div>

                {/* Example Hint */}
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-700/80 flex items-start gap-3 text-xs text-slate-600 dark:text-slate-300">
                  <Info className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-semibold text-slate-900 dark:text-slate-100">Recommended Declarations to Include:</p>
                    <p className="text-slate-500 dark:text-slate-400 leading-relaxed">
                      Product name, brand, net quantity, MRP (inclusive of all taxes), unit sale price, manufacturing/packaging/expiry dates, batch number, FSSAI license, complete manufacturer &amp; marketer addresses, customer care telephone &amp; email, country of origin, ingredients, and nutrition facts.
                    </p>
                  </div>
                </div>

                {/* Bottom Action Bar */}
                <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
                  <div className="text-xs">
                    {!listingText.trim() ? (
                      <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
                        <Info className="w-4 h-4 text-amber-500 dark:text-amber-400 shrink-0" />
                        <span>Paste or enter listing text above, or click "Load Sample".</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400 font-medium">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                        <span>Ready for Legal Metrology &amp; FSSAI compliance evaluation</span>
                      </div>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={handleAnalyzeText}
                    disabled={!listingText.trim() || isProcessing}
                    className={`px-8 py-3 rounded-xl font-bold text-xs sm:text-sm shadow-2xs transition-all flex items-center justify-center gap-2 cursor-pointer ${
                      !listingText.trim() || isProcessing
                        ? 'bg-slate-200 dark:bg-slate-800 text-slate-400 dark:text-slate-600 cursor-not-allowed shadow-none border border-transparent dark:border-slate-700/50'
                        : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-500/25 active:scale-98'
                    }`}
                    aria-label="Analyze Listing"
                  >
                    <ScanSearch className="w-4 h-4" />
                    <span>Analyze Listing</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Statutory Guidance Grid for Listing Text Mode */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/90 dark:border-slate-800 p-5 shadow-2xs space-y-3">
                <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100 font-bold text-xs uppercase tracking-wider">
                  <ShieldCheck className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                  <span>Statutory Coverage (PS 26034)</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 dark:text-slate-300">
                  <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800/60 p-2 rounded-lg border border-slate-100 dark:border-slate-700/60">
                    <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                    <span>Legal Metrology (PCR) 2011</span>
                  </div>
                  <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800/60 p-2 rounded-lg border border-slate-100 dark:border-slate-700/60">
                    <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                    <span>FSSAI Labelling 2020</span>
                  </div>
                  <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800/60 p-2 rounded-lg border border-slate-100 dark:border-slate-700/60">
                    <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                    <span>Unit Sale Price &amp; MRP</span>
                  </div>
                  <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800/60 p-2 rounded-lg border border-slate-100 dark:border-slate-700/60">
                    <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                    <span>Consumer Care Contact</span>
                  </div>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed pt-1">
                  Evaluates mandatory declaration fields, formatting requirements, and calculates statutory penalty estimates for non-compliance.
                </p>
              </div>

              <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/90 dark:border-slate-800 p-5 shadow-2xs space-y-3 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100 font-bold text-xs uppercase tracking-wider mb-3">
                    <Info className="w-4 h-4 text-sky-600 dark:text-sky-400" />
                    <span>Listing Text Guidelines</span>
                  </div>
                  <div className="space-y-1.5 text-xs text-slate-600 dark:text-slate-300">
                    <p><strong className="text-slate-900 dark:text-slate-100">Input formats:</strong> Plain text, key-value specifications, catalog descriptions</p>
                    <p><strong className="text-slate-900 dark:text-slate-100">Recommended fields:</strong> MRP, Net Quantity, Mfg Date, FSSAI Lic, Origin</p>
                    <p><strong className="text-slate-900 dark:text-slate-100">Audit trail:</strong> Saved permanently to screening history database</p>
                  </div>
                </div>
                <div className="pt-2 text-[11px] text-slate-400 dark:text-slate-500 border-t border-slate-100 dark:border-slate-800">
                  Screening outputs include prioritized corrective actions and legal notices.
                </div>
              </div>
            </div>
          </>
        )
      ) : (
        /* ========================================================================= */
        /* PHASE 2: PROFESSIONAL PROCESSING / SCANNING SCREEN                        */
        /* ========================================================================= */
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/90 dark:border-slate-800 shadow-sm overflow-hidden animate-in fade-in zoom-in-98 duration-200">
          {/* Top Processing Header */}
          <div className="p-6 sm:p-8 border-b border-slate-100 dark:border-slate-800 bg-gradient-to-b from-slate-50/50 dark:from-slate-800/50 to-white dark:to-slate-900">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1.5 max-w-2xl">
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200/80 dark:border-indigo-800/80 mb-1 shadow-2xs">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                  <span>AI-Assisted Compliance Screening</span>
                </div>
                <h2 className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-slate-100 tracking-tight flex items-center gap-3">
                  <span>{error ? 'Screening Paused' : isComplete ? 'Screening Complete' : 'Analyzing Package'}</span>
                  {!error && !isComplete && (
                    <Loader2 className="w-6 h-6 text-indigo-600 dark:text-indigo-400 animate-spin shrink-0" />
                  )}
                  {isComplete && (
                    <CheckCircle2 className="w-6 h-6 text-emerald-600 dark:text-emerald-400 shrink-0" />
                  )}
                </h2>
                <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                  {error 
                    ? 'An issue was encountered during package analysis.' 
                    : isComplete 
                      ? 'Organizing findings and opening statutory results...' 
                      : 'MetrCheck AI is screening the uploaded package images and checking label declarations.'}
                </p>
              </div>

              {/* Status Badge */}
              <div className="flex items-center gap-2 shrink-0">
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 shadow-2xs">
                  <Zap className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                  <span>
                    {demoActiveCase 
                      ? `SIH Demo Case ${demoActiveCase}` 
                      : `Analyzing ${stagedCount} package image${stagedCount > 1 ? 's' : ''}`}
                  </span>
                </span>
              </div>
            </div>
          </div>

          {/* Processing Screen Content or Error Card */}
          {error ? (
            /* Error State */
            <div className="p-8 sm:p-12 text-center max-w-lg mx-auto space-y-6">
              <div className="w-16 h-16 rounded-2xl bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800/80 flex items-center justify-center mx-auto text-red-600 dark:text-red-400">
                <AlertTriangle className="w-8 h-8" />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-slate-100">
                  Analysis could not be completed
                </h3>
                <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                  {error}
                </p>
                {stagedCount > 0 && (
                  <p className="text-xs text-slate-400 dark:text-slate-500">
                    {stagedCount} package image{stagedCount > 1 ? 's' : ''} remain staged in memory.
                  </p>
                )}
              </div>

              <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={demoActiveCase ? () => runDemo(demoActiveCase) : startAnalysis}
                  className="w-full sm:w-auto px-6 py-2.5 rounded-xl font-semibold bg-indigo-600 hover:bg-indigo-700 text-white text-xs sm:text-sm flex items-center justify-center gap-2 shadow-2xs cursor-pointer active:scale-98 transition-all"
                >
                  <RefreshCw className="w-4 h-4" />
                  <span>Try Again</span>
                </button>
                <button
                  type="button"
                  onClick={handleBackToAnalyze}
                  className="w-full sm:w-auto px-6 py-2.5 rounded-xl font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 text-xs sm:text-sm flex items-center justify-center gap-2 cursor-pointer transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>Back to Analyze</span>
                </button>
              </div>
            </div>
          ) : (
            /* Main 2-Column Processing View */
            <div className="p-6 sm:p-8">
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
                
                {/* Left Column: Package Previews & Dynamic Stage Explanation */}
                <div className="lg:col-span-5 space-y-4">
                  <div className="p-4 rounded-2xl bg-slate-50/80 dark:bg-slate-800/50 border border-slate-200/90 dark:border-slate-700/80 shadow-2xs space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                        Package Being Analyzed
                      </span>
                      <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 font-mono">
                        {demoActiveCase ? 'Demo Benchmark' : `${stagedCount} Panel${stagedCount > 1 ? 's' : ''}`}
                      </span>
                    </div>

                    {/* Previews Grid */}
                    <div className={`grid gap-2.5 ${stagedCount === 1 ? 'grid-cols-1' : 'grid-cols-2'}`}>
                      {stagedCount > 0 ? (
                        stagedItems.map((item) => (
                          <div 
                            key={item.key} 
                            className="relative rounded-xl border border-slate-200/90 dark:border-slate-700 bg-slate-950/5 dark:bg-slate-950 overflow-hidden flex items-center justify-center group"
                            style={{ height: stagedCount === 1 ? '220px' : '130px' }}
                          >
                            <img 
                              src={item.preview} 
                              alt={`${item.label} packaging panel`}
                              className="w-full h-full object-contain p-1"
                            />
                            {/* Panel Label Pill */}
                            <span className="absolute bottom-1.5 left-1.5 text-[10px] font-bold px-2 py-0.5 rounded-md bg-slate-900/85 text-white backdrop-blur-xs">
                              {item.label}
                            </span>
                            {/* Scanning Light Line Overlay */}
                            <div 
                              className="absolute inset-x-0 h-0.5 bg-gradient-to-r from-transparent via-indigo-500 to-transparent shadow-[0_0_8px_rgba(99,102,241,0.8)] motion-reduce:hidden animate-pulse pointer-events-none"
                              style={{ top: `${((activeStageIndex + 1) * 14) % 90}%` }}
                            />
                          </div>
                        ))
                      ) : (
                        /* Fallback when running benchmark without upload state */
                        <div className="h-36 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 space-y-1">
                          <ScanSearch className="w-8 h-8 text-indigo-500 animate-pulse" />
                          <span className="text-xs font-semibold">Benchmark Package Panels</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Active Stage Callout Card */}
                  <div className="p-4 rounded-2xl bg-indigo-50/80 dark:bg-indigo-950/60 border border-indigo-200/90 dark:border-indigo-800/80 shadow-2xs space-y-2">
                    <div className="flex items-center gap-2 text-indigo-900 dark:text-indigo-200">
                      <div className="w-6 h-6 rounded-lg bg-indigo-600 text-white flex items-center justify-center shrink-0">
                        {isComplete ? (
                          <Check className="w-3.5 h-3.5" />
                        ) : (
                          <ActiveIcon className="w-3.5 h-3.5" />
                        )}
                      </div>
                      <span className="text-xs font-bold uppercase tracking-wider">
                        {isComplete ? 'Screening Complete' : currentStage.title}
                      </span>
                    </div>
                    <p className="text-xs text-indigo-950 dark:text-indigo-200 font-medium leading-relaxed">
                      {isComplete 
                        ? 'Findings, evidence and recommended actions have been structured.' 
                        : currentStage.explanation}
                    </p>
                  </div>
                </div>

                {/* Right Column: Conceptual Processing Pipeline Timeline */}
                <div className="lg:col-span-7 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/90 dark:border-slate-800 p-5 sm:p-6 shadow-2xs space-y-5">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                      <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
                        Compliance Screening Pipeline
                      </h3>
                    </div>
                    <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 font-mono">
                      Stage {activeStageIndex + 1} of {CONCEPTUAL_STAGES.length}
                    </span>
                  </div>

                  {/* Vertical Timeline */}
                  <div className="space-y-3 relative">
                    {CONCEPTUAL_STAGES.map((stage, idx) => {
                      const StageIcon = stage.icon;
                      const isPast = idx < activeStageIndex;
                      const isCurrent = idx === activeStageIndex;

                      return (
                        <div 
                          key={stage.id} 
                          className="flex items-start gap-3.5 relative"
                          aria-label={`${stage.title} — ${isPast ? 'completed' : isCurrent ? 'currently processing' : 'waiting'}`}
                        >
                          {/* Connector Line */}
                          {idx < CONCEPTUAL_STAGES.length - 1 && (
                            <div 
                              className={`absolute left-4 top-8 w-0.5 h-7 -ml-[1px] transition-colors duration-300 ${
                                isPast ? 'bg-emerald-400 dark:bg-emerald-600' : 'bg-slate-200 dark:bg-slate-700'
                              }`} 
                            />
                          )}

                          {/* Stage Status Icon Indicator */}
                          <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 border transition-all duration-300 z-10 ${
                            isPast 
                              ? 'bg-emerald-500 border-emerald-500 text-white shadow-2xs' 
                              : isCurrent 
                                ? 'bg-indigo-600 border-indigo-600 text-white shadow-sm ring-4 ring-indigo-100 dark:ring-indigo-900/60 animate-pulse' 
                                : 'bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-300 dark:text-slate-600'
                          }`}>
                            {isPast ? (
                              <Check className="w-4 h-4" />
                            ) : isCurrent ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <StageIcon className="w-4 h-4" />
                            )}
                          </div>

                          {/* Stage Information */}
                          <div className="flex-1 min-w-0 pt-0.5">
                            <div className="flex items-center justify-between gap-2">
                              <h4 className={`text-xs transition-colors ${
                                isCurrent 
                                  ? 'font-bold text-indigo-950 dark:text-indigo-300 text-sm' 
                                  : isPast 
                                    ? 'font-semibold text-slate-900 dark:text-slate-100' 
                                    : 'font-medium text-slate-400 dark:text-slate-500'
                              }`}>
                                {stage.title}
                              </h4>

                              {/* Stage Status Tag */}
                              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border shrink-0 ${
                                isPast 
                                  ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/80' 
                                  : isCurrent 
                                    ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800/80' 
                                    : 'bg-slate-50 dark:bg-slate-800 text-slate-400 dark:text-slate-500 border-slate-200 dark:border-slate-700'
                              }`}>
                                {isPast ? 'Completed' : isCurrent ? 'In Progress' : 'Pending'}
                              </span>
                            </div>

                            <p className={`text-[11px] mt-0.5 transition-colors ${
                              isCurrent ? 'text-indigo-800 dark:text-indigo-300 font-medium' : isPast ? 'text-slate-500 dark:text-slate-400' : 'text-slate-400 dark:text-slate-500'
                            }`}>
                              {stage.explanation}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Informational Privacy & System Pipeline Footer */}
              <div className="mt-8 pt-4 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                  <span>Images are processed by the MetrCheck AI screening pipeline.</span>
                </div>
                <div className="font-mono text-[11px] text-slate-400 dark:text-slate-500">
                  Legal Metrology Rules 2011 &amp; FSSAI
                </div>
              </div>
            </div>
          )}
        </div>
      )}
      {/* Live Camera Scanner Modal */}
      {isCameraOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/90 backdrop-blur-md p-4 animate-in fade-in duration-200">
          <div className="bg-slate-900 rounded-3xl shadow-2xl max-w-2xl w-full p-5 sm:p-6 space-y-4 border border-slate-700 flex flex-col items-center">
            {/* Header */}
            <div className="w-full flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
                  <Camera className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-white">Live Packaging Camera</h3>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 uppercase">
                      Target: {SLOTS.find(s => s.key === activeCameraSlot)?.label} Panel
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">Position the commodity label flat inside the guide frame</p>
                </div>
              </div>
              <button
                type="button"
                onClick={stopCamera}
                className="p-1.5 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Target Slot Selector within Camera */}
            <div className="flex items-center gap-1.5 bg-slate-950/80 p-1 rounded-xl border border-slate-800 self-center">
              {SLOTS.map(s => (
                <button
                  key={s.key}
                  type="button"
                  onClick={() => setActiveCameraSlot(s.key)}
                  className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    activeCameraSlot === s.key 
                      ? 'bg-indigo-600 text-white shadow-xs' 
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>

            {/* Video Viewfinder Container */}
            <div className="relative w-full aspect-[4/3] max-h-[55vh] bg-black rounded-2xl overflow-hidden border border-slate-700 shadow-inner flex items-center justify-center">
              {cameraError ? (
                <div className="p-6 text-center text-red-400 text-xs space-y-2 max-w-sm">
                  <AlertTriangle className="w-8 h-8 mx-auto text-red-500" />
                  <p className="font-bold text-white">Camera Error</p>
                  <p>{cameraError}</p>
                  <button
                    type="button"
                    onClick={() => startCamera(activeCameraSlot)}
                    className="mt-2 px-3 py-1.5 bg-red-950/60 hover:bg-red-900 border border-red-700 text-red-200 rounded-lg text-xs font-bold"
                  >
                    Retry Permission
                  </button>
                </div>
              ) : (
                <>
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    className="w-full h-full object-cover"
                  />
                  
                  {/* Packaging Guide Overlay Frame */}
                  <div className="absolute inset-6 sm:inset-10 border-2 border-dashed border-emerald-400/70 rounded-2xl pointer-events-none flex flex-col justify-between p-3">
                    <div className="flex justify-between">
                      <div className="w-5 h-5 border-t-4 border-l-4 border-emerald-400 -mt-1 -ml-1" />
                      <div className="w-5 h-5 border-t-4 border-r-4 border-emerald-400 -mt-1 -mr-1" />
                    </div>
                    <div className="text-center">
                      <span className="bg-slate-900/80 backdrop-blur-xs text-emerald-300 font-mono text-[10px] font-bold px-2.5 py-1 rounded-full border border-emerald-500/40">
                        Align MRP / Net Qty / FSSAI Text Here
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <div className="w-5 h-5 border-b-4 border-l-4 border-emerald-400 -mb-1 -ml-1" />
                      <div className="w-5 h-5 border-b-4 border-r-4 border-emerald-400 -mb-1 -mr-1" />
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Controls Bar */}
            <div className="w-full flex items-center justify-between px-4 pt-1">
              <button
                type="button"
                onClick={toggleFacingMode}
                className="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold border border-slate-700 transition cursor-pointer"
                title="Switch between front and back camera"
              >
                <SwitchCamera className="w-4 h-4 text-indigo-400" />
                <span className="hidden sm:inline">Flip Camera</span>
              </button>

              {/* Big Shutter Capture Button */}
              <button
                type="button"
                onClick={captureSnapshot}
                disabled={!isCameraReady && !cameraStream}
                className="w-14 h-14 rounded-full bg-white border-4 border-indigo-600 hover:scale-105 active:scale-95 shadow-lg shadow-indigo-500/40 flex items-center justify-center transition-all cursor-pointer disabled:opacity-40"
                title="Capture Frame"
              >
                <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center text-white">
                  <Camera className="w-5 h-5" />
                </div>
              </button>

              <button
                type="button"
                onClick={stopCamera}
                className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold border border-slate-700 transition cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
