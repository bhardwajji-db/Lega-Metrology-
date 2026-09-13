import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ClipboardCheck,
  FileText,
  Sparkles,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Info,
  ShieldCheck,
  Building2,
  Scale,
  Tag,
  Phone,
  Mail,
  Loader2,
  Calculator,
  ChevronDown,
  ChevronUp,
  Apple,
  Package,
  Layers,
} from 'lucide-react';
import { api } from '../services/api';
import Card from '../components/ui/Card';

type ProductType = 'FOOD' | 'NON_FOOD';
type InputMode = 'STRUCTURED' | 'RAW_TEXT';

interface StructuredFormData {
  productType: ProductType;
  brand: string;
  productName: string;
  genericName: string;
  category: string;
  netQtyAmount: string;
  netQtyUnit: string;
  mrp: string;
  unitSalePrice: string;
  batchNumber: string;
  mfgDate: string;
  expiryDate: string;
  countryOfOrigin: string;
  // Manufacturer & Marketer
  manufacturerName: string;
  manufacturerAddress: string;
  marketerSameAsMfg: boolean;
  marketerName: string;
  marketerAddress: string;
  // Consumer Care
  consumerCarePhone: string;
  consumerCareEmail: string;
  consumerCareAddress: string;
  // Food Declarations
  fssaiLicense: string;
  ingredients: string;
  allergenInfo: string;
  // Nutrition Facts
  nutritionBasis: string;
  energyKcal: string;
  proteinG: string;
  carbsG: string;
  totalSugarG: string;
  addedSugarG: string;
  dietaryFibreG: string;
  totalFatG: string;
  saturatedFatG: string;
  transFatG: string;
  cholesterolMg: string;
  sodiumMg: string;
}

const INITIAL_FORM: StructuredFormData = {
  productType: 'FOOD',
  brand: '',
  productName: '',
  genericName: '',
  category: '',
  netQtyAmount: '',
  netQtyUnit: 'g',
  mrp: '',
  unitSalePrice: '',
  batchNumber: '',
  mfgDate: '',
  expiryDate: '',
  countryOfOrigin: 'India',
  manufacturerName: '',
  manufacturerAddress: '',
  marketerSameAsMfg: true,
  marketerName: '',
  marketerAddress: '',
  consumerCarePhone: '',
  consumerCareEmail: '',
  consumerCareAddress: '',
  fssaiLicense: '',
  ingredients: '',
  allergenInfo: '',
  nutritionBasis: 'Per 100g',
  energyKcal: '',
  proteinG: '',
  carbsG: '',
  totalSugarG: '',
  addedSugarG: '',
  dietaryFibreG: '',
  totalFatG: '',
  saturatedFatG: '',
  transFatG: '',
  cholesterolMg: '',
  sodiumMg: '',
};

const SAMPLE_FOOD_FORM: StructuredFormData = {
  productType: 'FOOD',
  brand: 'Alpino Health Foods',
  productName: 'Alpino Super High Protein Rolled Oats - Dark Chocolate',
  genericName: 'Rolled Oats with Added Whey Protein',
  category: 'Packaged Food / Breakfast Cereals',
  netQtyAmount: '400',
  netQtyUnit: 'g',
  mrp: '299.00',
  unitSalePrice: 'Rs. 747.50 / kg',
  batchNumber: 'BATCH-ALP-2026-10',
  mfgDate: '10/2026',
  expiryDate: '12 months from date of manufacture',
  countryOfOrigin: 'India',
  manufacturerName: 'Alpino Health Foods Pvt. Ltd.',
  manufacturerAddress: 'Plot No. 12, GIDC Industrial Estate, Surat, Gujarat - 395007',
  marketerSameAsMfg: true,
  marketerName: 'Alpino Health Foods Pvt. Ltd.',
  marketerAddress: 'Plot No. 12, GIDC Industrial Estate, Surat, Gujarat - 395007',
  consumerCarePhone: '1800-123-4567',
  consumerCareEmail: 'care@alpino.store',
  consumerCareAddress: 'Plot No. 12, GIDC Industrial Estate, Surat, Gujarat - 395007',
  fssaiLicense: '10716022000249',
  ingredients: 'Rolled Oats (75%), Whey Protein Isolate (15%), Cocoa Powder (7%), Natural Sweetener (Stevia).',
  allergenInfo: 'Contains Gluten and Milk. Processed in a facility that also handles nuts and soy.',
  nutritionBasis: 'Per 100g',
  energyKcal: '412',
  proteinG: '30.5',
  carbsG: '54.2',
  totalSugarG: '3.1',
  addedSugarG: '0',
  dietaryFibreG: '9.8',
  totalFatG: '7.2',
  saturatedFatG: '1.4',
  transFatG: '0',
  cholesterolMg: '0',
  sodiumMg: '140',
};

const SAMPLE_LISTING_TEXT = `Product Name: Premium Roasted California Almonds (Lightly Salted)
Brand: NutriHarvest Organics
Category: Packaged Food / Dry Fruits
Net Quantity: 500 g
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
Helpline Phone: 1800-200-8899
Email: care@nutriharvest.in
Address: Plot No. 45, Sector 8, Manesar, Gurugram, Haryana - 122050

Ingredients:
California Almonds (98%), Edible Common Salt (1.5%), Refined Sunflower Oil (0.5%).

Nutritional Information (per 100g):
Energy: 579 kcal, Protein: 21.2g, Carbohydrates: 21.6g (Dietary Fiber: 12.5g, Total Sugars: 4.4g, Added Sugars: 0g), Total Fat: 49.9g (Saturated Fat: 3.8g, Trans Fat: 0g, Cholesterol: 0mg), Sodium: 380mg.

Allergen Declaration:
Contains Tree Nuts (Almonds). Processed in a facility that also handles peanuts, walnuts, and soy.`;

export default function AnalyzeListing() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<InputMode>('STRUCTURED');
  const [formData, setFormData] = useState<StructuredFormData>(INITIAL_FORM);
  const [rawText, setRawText] = useState('');
  const [showNutrition, setShowNutrition] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Update form field helper
  const updateField = <K extends keyof StructuredFormData>(field: K, value: StructuredFormData[K]) => {
    setFormData((prev) => {
      const next = { ...prev, [field]: value };
      if (field === 'manufacturerName' && prev.marketerSameAsMfg) {
        next.marketerName = value as string;
      }
      if (field === 'manufacturerAddress' && prev.marketerSameAsMfg) {
        next.marketerAddress = value as string;
      }
      return next;
    });
    if (validationError) setValidationError(null);
  };

  // Unit Sale Price Auto-Calculator
  const handleCalculateUSP = () => {
    const qty = parseFloat(formData.netQtyAmount);
    const mrp = parseFloat(formData.mrp.replace(/[^0-9.]/g, ''));
    if (isNaN(qty) || qty <= 0 || isNaN(mrp) || mrp <= 0) {
      setValidationError('Please enter a valid numeric Net Quantity and MRP to calculate Unit Sale Price.');
      return;
    }

    const unit = formData.netQtyUnit.toLowerCase().trim();
    let calculated = '';

    if (unit === 'g') {
      if (qty >= 1000) {
        const kg = qty / 1000;
        const rate = (mrp / kg).toFixed(2);
        calculated = `Rs. ${rate} / kg`;
      } else {
        const ratePerKg = ((mrp / qty) * 1000).toFixed(2);
        const ratePerG = (mrp / qty).toFixed(2);
        calculated = `Rs. ${ratePerKg} / kg (Rs. ${ratePerG} / g)`;
      }
    } else if (unit === 'kg') {
      const rate = (mrp / qty).toFixed(2);
      calculated = `Rs. ${rate} / kg`;
    } else if (unit === 'ml') {
      if (qty >= 1000) {
        const l = qty / 1000;
        const rate = (mrp / l).toFixed(2);
        calculated = `Rs. ${rate} / L`;
      } else {
        const ratePerL = ((mrp / qty) * 1000).toFixed(2);
        const ratePerMl = (mrp / qty).toFixed(2);
        calculated = `Rs. ${ratePerL} / L (Rs. ${ratePerMl} / ml)`;
      }
    } else if (unit === 'l' || unit === 'ltr' || unit === 'liter') {
      const rate = (mrp / qty).toFixed(2);
      calculated = `Rs. ${rate} / L`;
    } else {
      const rate = (mrp / qty).toFixed(2);
      calculated = `Rs. ${rate} / ${unit || 'unit'}`;
    }

    updateField('unitSalePrice', calculated);
    setValidationError(null);
  };

  // Build statutory text payload from structured form
  const buildPayloadFromForm = (f: StructuredFormData): string => {
    const lines: string[] = [];

    if (f.productName || f.brand) {
      lines.push(`Product Name: ${f.productName || f.brand}`);
    }
    if (f.brand) {
      lines.push(`Brand: ${f.brand}`);
    }
    if (f.genericName) {
      lines.push(`Generic Name: ${f.genericName}`);
    }
    if (f.category) {
      lines.push(`Category: ${f.category}`);
    }
    if (f.netQtyAmount) {
      lines.push(`Net Quantity: ${f.netQtyAmount} ${f.netQtyUnit}`);
    }
    if (f.mrp) {
      const mrpVal = f.mrp.startsWith('Rs.') || f.mrp.startsWith('₹') ? f.mrp : `Rs. ${f.mrp}`;
      lines.push(`Maximum Retail Price (MRP): ${mrpVal} (Inclusive of all taxes)`);
    }
    if (f.unitSalePrice) {
      lines.push(`Unit Sale Price: ${f.unitSalePrice}`);
    }
    if (f.mfgDate) {
      lines.push(`Date of Manufacture: ${f.mfgDate}`);
    }
    if (f.expiryDate) {
      lines.push(`Best Before: ${f.expiryDate}`);
    }
    if (f.batchNumber) {
      lines.push(`Batch Number: ${f.batchNumber}`);
    }
    if (f.countryOfOrigin) {
      lines.push(`Country of Origin: ${f.countryOfOrigin}`);
    }

    // Manufacturer
    if (f.manufacturerName || f.manufacturerAddress) {
      lines.push('');
      lines.push('Manufactured & Packed by:');
      if (f.manufacturerName) lines.push(f.manufacturerName);
      if (f.manufacturerAddress) lines.push(f.manufacturerAddress);
    }

    // Marketer
    const marketerName = f.marketerSameAsMfg ? f.manufacturerName : f.marketerName;
    const marketerAddr = f.marketerSameAsMfg ? f.manufacturerAddress : f.marketerAddress;
    if (marketerName || marketerAddr) {
      lines.push('');
      lines.push('Marketed by:');
      if (marketerName) lines.push(marketerName);
      if (marketerAddr) lines.push(marketerAddr);
    }

    // Consumer Care
    if (f.consumerCarePhone || f.consumerCareEmail || f.consumerCareAddress) {
      lines.push('');
      lines.push('Consumer Care Cell:');
      if (f.consumerCarePhone) lines.push(`Helpline Phone: ${f.consumerCarePhone}`);
      if (f.consumerCareEmail) lines.push(`Email: ${f.consumerCareEmail}`);
      if (f.consumerCareAddress) lines.push(`Address: ${f.consumerCareAddress}`);
    }

    // Food specific
    if (f.productType === 'FOOD') {
      if (f.fssaiLicense) {
        lines.push('');
        lines.push(`FSSAI License No.: ${f.fssaiLicense}`);
      }
      if (f.ingredients) {
        lines.push('');
        lines.push('Ingredients:');
        lines.push(f.ingredients);
      }
      if (f.allergenInfo) {
        lines.push('');
        lines.push('Allergen Declaration:');
        lines.push(f.allergenInfo);
      }

      // Nutrition facts
      const nutParts: string[] = [];
      if (f.energyKcal) nutParts.push(`Energy: ${f.energyKcal} kcal`);
      if (f.proteinG) nutParts.push(`Protein: ${f.proteinG} g`);
      if (f.carbsG) {
        let carbStr = `Carbohydrates: ${f.carbsG} g`;
        const subCarbs: string[] = [];
        if (f.totalSugarG) subCarbs.push(`Total Sugars: ${f.totalSugarG} g`);
        if (f.addedSugarG) subCarbs.push(`Added Sugars: ${f.addedSugarG} g`);
        if (f.dietaryFibreG) subCarbs.push(`Dietary Fibre: ${f.dietaryFibreG} g`);
        if (subCarbs.length > 0) {
          carbStr += ` (${subCarbs.join(', ')})`;
        }
        nutParts.push(carbStr);
      }
      if (f.totalFatG) {
        let fatStr = `Total Fat: ${f.totalFatG} g`;
        const subFats: string[] = [];
        if (f.saturatedFatG) subFats.push(`Saturated Fat: ${f.saturatedFatG} g`);
        if (f.transFatG) subFats.push(`Trans Fat: ${f.transFatG} g`);
        if (f.cholesterolMg) subFats.push(`Cholesterol: ${f.cholesterolMg} mg`);
        if (subFats.length > 0) {
          fatStr += ` (${subFats.join(', ')})`;
        }
        nutParts.push(fatStr);
      }
      if (f.sodiumMg) nutParts.push(`Sodium: ${f.sodiumMg} mg`);

      if (nutParts.length > 0) {
        lines.push('');
        lines.push(`Nutritional Information (${f.nutritionBasis || 'per 100g'}):`);
        lines.push(nutParts.join(', ') + '.');
      }
    }

    return lines.join('\n');
  };

  const handleLoadSample = () => {
    if (mode === 'STRUCTURED') {
      setFormData(SAMPLE_FOOD_FORM);
    } else {
      setRawText(SAMPLE_LISTING_TEXT);
    }
    setValidationError(null);
    setError(null);
  };

  const handleClear = () => {
    if (mode === 'STRUCTURED') {
      setFormData(INITIAL_FORM);
    } else {
      setRawText('');
    }
    setValidationError(null);
    setError(null);
  };

  const handleRunCompliance = async () => {
    let payloadText = '';

    if (mode === 'STRUCTURED') {
      if (!formData.productName.trim() && !formData.brand.trim()) {
        setValidationError('Please enter at least the Product Name or Brand Name to begin screening.');
        return;
      }
      payloadText = buildPayloadFromForm(formData);
    } else {
      payloadText = rawText.trim();
      if (!payloadText) {
        setValidationError('Please paste or enter listing text before running compliance check.');
        return;
      }
    }

    setValidationError(null);
    setError(null);
    setLoading(true);
    setLoadingStep('Running Legal Metrology & FSSAI rules engine…');

    try {
      const result = await api.analyzeText(payloadText);
      // Navigate seamlessly to existing unified Results page with full analysis payload
      navigate(`/results/${result.id}`, { state: { analysisData: result } });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to analyze declarations. Please verify the backend API is active.';
      setError(message);
    } finally {
      setLoading(false);
      setLoadingStep(null);
    }
  };

  // Declaration coverage items for pre-flight checklist
  const coverageItems = [
    { label: 'Product Name / Brand', entered: Boolean(formData.productName || formData.brand) },
    { label: 'Net Quantity', entered: Boolean(formData.netQtyAmount) },
    { label: 'Maximum Retail Price (MRP)', entered: Boolean(formData.mrp) },
    { label: 'Unit Sale Price (USP)', entered: Boolean(formData.unitSalePrice) },
    { label: 'Date of Mfg / Packing', entered: Boolean(formData.mfgDate) },
    { label: 'Expiry / Best Before', entered: Boolean(formData.expiryDate) },
    { label: 'Batch / Lot Number', entered: Boolean(formData.batchNumber) },
    { label: 'Country of Origin', entered: Boolean(formData.countryOfOrigin) },
    { label: 'Manufacturer Details', entered: Boolean(formData.manufacturerName && formData.manufacturerAddress) },
    { label: 'Consumer Care Helpline/Email', entered: Boolean(formData.consumerCarePhone || formData.consumerCareEmail) },
    ...(formData.productType === 'FOOD'
      ? [
          { label: 'FSSAI License No. (14 digits)', entered: Boolean(formData.fssaiLicense) },
          { label: 'Ingredients List', entered: Boolean(formData.ingredients) },
          { label: 'Allergen Declaration', entered: Boolean(formData.allergenInfo) },
          { label: 'Nutritional Information', entered: Boolean(formData.energyKcal || formData.proteinG || formData.carbsG) },
        ]
      : []),
  ];

  const enteredCount = coverageItems.filter((i) => i.entered).length;
  const coveragePercent = Math.round((enteredCount / coverageItems.length) * 100);

  return (
    <div className="space-y-6 pb-16 animate-in fade-in duration-300">
      {/* ── Page Header ───────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800/80 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20">
              <ShieldCheck className="w-3.5 h-3.5" />
              PREVENT
            </span>
            <span className="text-xs text-slate-400 dark:text-slate-500">&bull;</span>
            <span className="text-xs font-semibold text-slate-600 dark:text-slate-400">
              Merchant Workspace
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight flex items-center gap-2.5">
            <ClipboardCheck className="w-7 h-7 text-indigo-600 dark:text-indigo-400" />
            <span>Pre-Flight Packaging Check</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-1 max-w-2xl">
            Enter the declarations printed on your package to identify compliance issues before publishing or selling.
          </p>
          <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
            Fast declaration screening for Legal Metrology (Packaged Commodities) Rules, 2011 and FSSAI statutory standards.
          </p>
        </div>

        {/* Header Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5 shrink-0">
          <button
            type="button"
            onClick={handleLoadSample}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200/80 dark:border-indigo-800/80 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Load Sample Package</span>
          </button>
          <button
            type="button"
            onClick={handleClear}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer disabled:opacity-50"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Clear</span>
          </button>
          <button
            type="button"
            onClick={handleRunCompliance}
            disabled={loading}
            className="inline-flex items-center gap-2 px-4.5 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm shadow-indigo-950/30 transition-all cursor-pointer disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Screening…</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Run Compliance Check</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* ── Mode Switcher & Navigation Tabs ────────────────────────── */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setMode('STRUCTURED')}
            className={`px-4 py-2.5 text-xs font-bold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              mode === 'STRUCTURED'
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            <ClipboardCheck className="w-4 h-4" />
            <span>Structured Entry (Recommended)</span>
          </button>
          <button
            type="button"
            onClick={() => setMode('RAW_TEXT')}
            className={`px-4 py-2.5 text-xs font-bold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              mode === 'RAW_TEXT'
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Paste Listing Text</span>
          </button>
        </div>
      </div>

      {/* ── Validation / Alert Messages ───────────────────────────── */}
      {validationError && (
        <div className="p-3.5 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 rounded-xl text-xs text-amber-800 dark:text-amber-300 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600 dark:text-amber-400" />
          <span>{validationError}</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 rounded-xl text-xs text-red-800 dark:text-red-300 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-red-600 dark:text-red-400" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={handleRunCompliance}
            className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded-lg font-bold text-xs shrink-0 cursor-pointer"
          >
            Retry Check
          </button>
        </div>
      )}

      {/* ── Loading Overlay / Progress ────────────────────────────── */}
      {loading && (
        <div className="p-6 bg-indigo-50/70 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900/60 rounded-2xl flex items-center gap-4">
          <Loader2 className="w-6 h-6 text-indigo-600 dark:text-indigo-400 animate-spin shrink-0" />
          <div className="space-y-0.5">
            <h4 className="text-xs font-bold text-indigo-950 dark:text-indigo-200">
              {loadingStep || 'Evaluating Statutory Compliance…'}
            </h4>
            <p className="text-[11px] text-indigo-700 dark:text-indigo-300">
              Screening 14+ mandatory declarations against Legal Metrology Rules and FSSAI standards. Directing to Results...
            </p>
          </div>
        </div>
      )}

      {/* ── STRUCTURED ENTRY MODE ─────────────────────────────────── */}
      {mode === 'STRUCTURED' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Main Form (Left 8 Cols) */}
          <div className="lg:col-span-8 space-y-6">
            {/* Product Type Toggle */}
            <Card
              title="Product Classification"
              subtitle="Select commodity domain to enable relevant statutory declaration fields"
              icon={Package}
              iconColor="text-indigo-600 dark:text-indigo-400"
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label
                  className={`flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${
                    formData.productType === 'FOOD'
                      ? 'bg-indigo-50/60 dark:bg-indigo-950/40 border-indigo-300 dark:border-indigo-700 ring-2 ring-indigo-500/20'
                      : 'border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40'
                  }`}
                >
                  <input
                    type="radio"
                    name="productType"
                    checked={formData.productType === 'FOOD'}
                    onChange={() => updateField('productType', 'FOOD')}
                    className="mt-1 text-indigo-600 focus:ring-indigo-500"
                  />
                  <div>
                    <div className="flex items-center gap-1.5 font-bold text-xs text-slate-900 dark:text-slate-100">
                      <Apple className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                      <span>Food Product (FSSAI + Legal Metrology)</span>
                    </div>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      Enables FSSAI license, ingredients, allergen declaration, and nutritional facts evaluation.
                    </p>
                  </div>
                </label>

                <label
                  className={`flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${
                    formData.productType === 'NON_FOOD'
                      ? 'bg-indigo-50/60 dark:bg-indigo-950/40 border-indigo-300 dark:border-indigo-700 ring-2 ring-indigo-500/20'
                      : 'border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40'
                  }`}
                >
                  <input
                    type="radio"
                    name="productType"
                    checked={formData.productType === 'NON_FOOD'}
                    onChange={() => updateField('productType', 'NON_FOOD')}
                    className="mt-1 text-indigo-600 focus:ring-indigo-500"
                  />
                  <div>
                    <div className="flex items-center gap-1.5 font-bold text-xs text-slate-900 dark:text-slate-100">
                      <Layers className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                      <span>Non-Food Commodity (Legal Metrology Only)</span>
                    </div>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      Screen standard packaged goods (detergents, electronics, stationery, apparel, etc.).
                    </p>
                  </div>
                </label>
              </div>
            </Card>

            {/* Section 1: Product Identification & Physical Declarations */}
            <Card
              title="1. Product Information & Pricing"
              subtitle="Core statutory declarations printed on the primary display panel"
              icon={Tag}
              iconColor="text-indigo-600 dark:text-indigo-400"
            >
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Brand Name <span className="text-slate-400 font-normal">(Optional)</span>
                    </label>
                    <input
                      type="text"
                      value={formData.brand}
                      onChange={(e) => updateField('brand', e.target.value)}
                      placeholder="e.g. Alpino Health Foods"
                      className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Product / Commodity Name <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.productName}
                      onChange={(e) => updateField('productName', e.target.value)}
                      placeholder="e.g. Super High Protein Rolled Oats - Dark Chocolate"
                      className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Generic / Common Name
                    </label>
                    <input
                      type="text"
                      value={formData.genericName}
                      onChange={(e) => updateField('genericName', e.target.value)}
                      placeholder="e.g. Rolled Oats with Added Whey Protein"
                      className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Category
                    </label>
                    <input
                      type="text"
                      value={formData.category}
                      onChange={(e) => updateField('category', e.target.value)}
                      placeholder="e.g. Packaged Food / Breakfast Cereals"
                      className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                    />
                  </div>
                </div>

                {/* Net Quantity + MRP + USP */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2 border-t border-slate-100 dark:border-slate-800">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Net Quantity <span className="text-red-500">*</span>
                    </label>
                    <div className="flex gap-1.5">
                      <input
                        type="text"
                        value={formData.netQtyAmount}
                        onChange={(e) => updateField('netQtyAmount', e.target.value)}
                        placeholder="e.g. 400"
                        className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                      />
                      <select
                        value={formData.netQtyUnit}
                        onChange={(e) => updateField('netQtyUnit', e.target.value)}
                        className="text-xs px-2.5 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 outline-none"
                      >
                        <option value="g">g</option>
                        <option value="kg">kg</option>
                        <option value="ml">ml</option>
                        <option value="L">L</option>
                        <option value="pieces">pieces</option>
                        <option value="units">units</option>
                        <option value="tablets">tablets</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      MRP (₹) <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <span className="absolute left-3 top-2.5 text-xs text-slate-400 font-bold">₹</span>
                      <input
                        type="text"
                        value={formData.mrp}
                        onChange={(e) => updateField('mrp', e.target.value)}
                        placeholder="299.00"
                        className="w-full text-xs pl-7 pr-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                      />
                    </div>
                    <span className="block text-[10px] text-slate-400 dark:text-slate-500 mt-1">
                      Includes all taxes
                    </span>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                        Unit Sale Price (USP)
                      </label>
                      <button
                        type="button"
                        onClick={handleCalculateUSP}
                        className="text-[11px] font-bold text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-0.5 cursor-pointer"
                        title="Auto-calculate USP from Net Quantity and MRP"
                      >
                        <Calculator className="w-3 h-3" />
                        <span>Calc</span>
                      </button>
                    </div>
                    <input
                      type="text"
                      value={formData.unitSalePrice}
                      onChange={(e) => updateField('unitSalePrice', e.target.value)}
                      placeholder="e.g. Rs. 747.50 / kg"
                      className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                    />
                    <span className="block text-[10px] text-slate-400 dark:text-slate-500 mt-1">
                      Required by Rule 6(1)(e)
                    </span>
                  </div>
                </div>

                {/* Batch + Dates + Country of Origin */}
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 pt-2 border-t border-slate-100 dark:border-slate-800">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Batch / Lot No.
                    </label>
                    <input
                      type="text"
                      value={formData.batchNumber}
                      onChange={(e) => updateField('batchNumber', e.target.value)}
                      placeholder="BATCH-2026-10"
                      className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Mfg / Packing Date
                    </label>
                    <input
                      type="text"
                      value={formData.mfgDate}
                      onChange={(e) => updateField('mfgDate', e.target.value)}
                      placeholder="e.g. 10/2026"
                      className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Best Before / Expiry
                    </label>
                    <input
                      type="text"
                      value={formData.expiryDate}
                      onChange={(e) => updateField('expiryDate', e.target.value)}
                      placeholder="e.g. 12 months"
                      className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Country of Origin
                    </label>
                    <input
                      type="text"
                      value={formData.countryOfOrigin}
                      onChange={(e) => updateField('countryOfOrigin', e.target.value)}
                      placeholder="India"
                      className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                    />
                  </div>
                </div>
              </div>
            </Card>

            {/* Section 2: Manufacturer, Packer & Customer Care */}
            <Card
              title="2. Manufacturer, Packer & Consumer Care"
              subtitle="Statutory entity identity, physical address and consumer grievance contact details"
              icon={Building2}
              iconColor="text-indigo-600 dark:text-indigo-400"
            >
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Manufacturer / Packer Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.manufacturerName}
                    onChange={(e) => updateField('manufacturerName', e.target.value)}
                    placeholder="e.g. Alpino Health Foods Pvt. Ltd."
                    className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Manufacturer Complete Address <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    rows={2}
                    value={formData.manufacturerAddress}
                    onChange={(e) => updateField('manufacturerAddress', e.target.value)}
                    placeholder="Plot No. 12, GIDC Industrial Estate, Surat, Gujarat - 395007"
                    className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none resize-y"
                  />
                </div>

                {/* Marketer Checkbox */}
                <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200/80 dark:border-slate-800 space-y-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.marketerSameAsMfg}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        updateField('marketerSameAsMfg', checked);
                        if (checked) {
                          updateField('marketerName', formData.manufacturerName);
                          updateField('marketerAddress', formData.manufacturerAddress);
                        }
                      }}
                      className="rounded text-indigo-600 focus:ring-indigo-500"
                    />
                    <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                      Marketed by same entity as Manufacturer / Packer
                    </span>
                  </label>

                  {!formData.marketerSameAsMfg && (
                    <div className="space-y-3 pt-2 border-t border-slate-200 dark:border-slate-700">
                      <div>
                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                          Marketer Name
                        </label>
                        <input
                          type="text"
                          value={formData.marketerName}
                          onChange={(e) => updateField('marketerName', e.target.value)}
                          placeholder="e.g. Alpino Global Brands LLP"
                          className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                          Marketer Address
                        </label>
                        <textarea
                          rows={2}
                          value={formData.marketerAddress}
                          onChange={(e) => updateField('marketerAddress', e.target.value)}
                          placeholder="Corporate address of marketing firm..."
                          className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 outline-none resize-y"
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Consumer Grievance Details */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100 dark:border-slate-800">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Consumer Care Helpline Phone <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <Phone className="w-3.5 h-3.5 absolute left-3 top-3 text-slate-400" />
                      <input
                        type="text"
                        value={formData.consumerCarePhone}
                        onChange={(e) => updateField('consumerCarePhone', e.target.value)}
                        placeholder="1800-123-4567"
                        className="w-full text-xs pl-8 pr-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Consumer Care Email <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <Mail className="w-3.5 h-3.5 absolute left-3 top-3 text-slate-400" />
                      <input
                        type="email"
                        value={formData.consumerCareEmail}
                        onChange={(e) => updateField('consumerCareEmail', e.target.value)}
                        placeholder="care@alpino.store"
                        className="w-full text-xs pl-8 pr-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Consumer Care Officer / Physical Postal Address
                  </label>
                  <input
                    type="text"
                    value={formData.consumerCareAddress}
                    onChange={(e) => updateField('consumerCareAddress', e.target.value)}
                    placeholder="Plot No. 12, GIDC Industrial Estate, Surat, Gujarat - 395007"
                    className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                  />
                </div>
              </div>
            </Card>

            {/* Section 3: Food Specific Declarations (FSSAI, Ingredients, Nutrition) */}
            {formData.productType === 'FOOD' && (
              <Card
                title="3. Mandatory Food Safety Declarations"
                subtitle="FSSAI 14-digit licence number, statutory ingredient list, allergens and nutrition table"
                icon={Apple}
                iconColor="text-emerald-600 dark:text-emerald-400"
              >
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      FSSAI Licence Number (14 Digits) <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <ShieldCheck className="w-3.5 h-3.5 absolute left-3 top-3 text-slate-400" />
                      <input
                        type="text"
                        value={formData.fssaiLicense}
                        onChange={(e) => updateField('fssaiLicense', e.target.value)}
                        placeholder="10716022000249"
                        maxLength={14}
                        className="w-full text-xs pl-8 pr-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none font-mono"
                      />
                    </div>
                    <span className="block text-[10px] text-slate-400 dark:text-slate-500 mt-1">
                      Statutory 14-digit license number format verified under FSSAI Labelling Regulations.
                    </span>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Ingredients List (Descending by weight / volume) <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      rows={2}
                      value={formData.ingredients}
                      onChange={(e) => updateField('ingredients', e.target.value)}
                      placeholder="e.g. Rolled Oats (75%), Whey Protein Isolate (15%), Cocoa Powder (7%), Natural Sweetener (Stevia)."
                      className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none resize-y"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Allergen Declaration
                    </label>
                    <input
                      type="text"
                      value={formData.allergenInfo}
                      onChange={(e) => updateField('allergenInfo', e.target.value)}
                      placeholder="e.g. Contains Gluten and Milk. Processed in a facility that also handles nuts and soy."
                      className="w-full text-xs p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                    />
                  </div>

                  {/* Expandable Nutrition Facts Panel */}
                  <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
                    <button
                      type="button"
                      onClick={() => setShowNutrition(!showNutrition)}
                      className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between text-left cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <Scale className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                        <div>
                          <span className="font-bold text-xs text-slate-900 dark:text-slate-100 block">
                            Nutritional Facts Panel
                          </span>
                          <span className="text-[10px] text-slate-500 dark:text-slate-400">
                            Energy, Protein, Sugars, Fats & Sodium parameters
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 text-xs text-indigo-600 dark:text-indigo-400 font-bold">
                        <span>{showNutrition ? 'Collapse' : 'Expand Form'}</span>
                        {showNutrition ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </div>
                    </button>

                    {showNutrition && (
                      <div className="p-4 space-y-4 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 animate-in fade-in duration-200">
                        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                          <div>
                            <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                              Energy (kcal)
                            </label>
                            <input
                              type="text"
                              value={formData.energyKcal}
                              onChange={(e) => updateField('energyKcal', e.target.value)}
                              placeholder="412"
                              className="w-full text-xs p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                              Protein (g)
                            </label>
                            <input
                              type="text"
                              value={formData.proteinG}
                              onChange={(e) => updateField('proteinG', e.target.value)}
                              placeholder="30.5"
                              className="w-full text-xs p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                              Carbohydrates (g)
                            </label>
                            <input
                              type="text"
                              value={formData.carbsG}
                              onChange={(e) => updateField('carbsG', e.target.value)}
                              placeholder="54.2"
                              className="w-full text-xs p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                              Added Sugars (g)
                            </label>
                            <input
                              type="text"
                              value={formData.addedSugarG}
                              onChange={(e) => updateField('addedSugarG', e.target.value)}
                              placeholder="0"
                              className="w-full text-xs p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 outline-none"
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-2 border-t border-slate-100 dark:border-slate-800">
                          <div>
                            <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                              Total Fat (g)
                            </label>
                            <input
                              type="text"
                              value={formData.totalFatG}
                              onChange={(e) => updateField('totalFatG', e.target.value)}
                              placeholder="7.2"
                              className="w-full text-xs p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                              Saturated Fat (g)
                            </label>
                            <input
                              type="text"
                              value={formData.saturatedFatG}
                              onChange={(e) => updateField('saturatedFatG', e.target.value)}
                              placeholder="1.4"
                              className="w-full text-xs p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                              Trans Fat (g)
                            </label>
                            <input
                              type="text"
                              value={formData.transFatG}
                              onChange={(e) => updateField('transFatG', e.target.value)}
                              placeholder="0"
                              className="w-full text-xs p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                              Sodium (mg)
                            </label>
                            <input
                              type="text"
                              value={formData.sodiumMg}
                              onChange={(e) => updateField('sodiumMg', e.target.value)}
                              placeholder="140"
                              className="w-full text-xs p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 outline-none"
                            />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            )}
          </div>

          {/* Right Side: Sticky Declaration Coverage Panel (4 Cols) */}
          <div className="lg:col-span-4 space-y-4 lg:sticky lg:top-20">
            <Card
              title="Declaration Coverage"
              subtitle="Pre-flight data entry readiness tracker"
              icon={Layers}
              iconColor="text-indigo-600 dark:text-indigo-400"
            >
              <div className="space-y-4">
                {/* Progress bar */}
                <div>
                  <div className="flex items-center justify-between text-xs font-bold mb-1.5">
                    <span className="text-slate-700 dark:text-slate-300">Form Readiness</span>
                    <span className="text-indigo-600 dark:text-indigo-400 font-mono">{coveragePercent}%</span>
                  </div>
                  <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-indigo-600 dark:bg-indigo-500 h-full rounded-full transition-all duration-300"
                      style={{ width: `${coveragePercent}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-slate-500 dark:text-slate-400 mt-1 block">
                    {enteredCount} of {coverageItems.length} statutory declarations entered
                  </span>
                </div>

                {/* Checklist */}
                <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800 max-h-[380px] overflow-y-auto pr-1">
                  {coverageItems.map((item, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between py-1.5 text-xs border-b border-slate-50 dark:border-slate-800/40 last:border-0"
                    >
                      <span className="text-slate-700 dark:text-slate-300 pr-2 leading-tight">
                        {item.label}
                      </span>
                      {item.entered ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-600 dark:text-emerald-400 shrink-0">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Entered</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 dark:text-slate-500 shrink-0">
                          <span className="w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-700" />
                          <span>Not entered</span>
                        </span>
                      )}
                    </div>
                  ))}
                </div>

                {/* Disclaimer Note */}
                <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed flex items-start gap-2 border border-slate-200/60 dark:border-slate-800">
                  <Info className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />
                  <span>
                    This checklist tracks data entry completeness. The authoritative statutory compliance verdict is computed by the Legal Metrology and FSSAI rules engine.
                  </span>
                </div>

                {/* Primary CTA */}
                <button
                  type="button"
                  onClick={handleRunCompliance}
                  disabled={loading}
                  className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold text-xs shadow-md shadow-indigo-950/20 flex items-center justify-center gap-2 cursor-pointer transition-all disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Screening Declarations…</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 fill-current" />
                      <span>Run Compliance Check</span>
                    </>
                  )}
                </button>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* ── RAW TEXT / PASTE LISTING MODE ──────────────────────────── */}
      {mode === 'RAW_TEXT' && (
        <div className="space-y-6">
          <Card
            title="Product Listing / Label Text"
            subtitle="Paste complete product catalogue text, e-commerce listing, or OCR transcript"
            icon={FileText}
            iconColor="text-indigo-600 dark:text-indigo-400"
          >
            <div className="space-y-4">
              <textarea
                value={rawText}
                onChange={(e) => {
                  setRawText(e.target.value);
                  if (validationError && e.target.value.trim()) {
                    setValidationError(null);
                  }
                }}
                placeholder="Paste statutory declaration text here (e.g. Product Name, Net Qty, MRP, Unit Sale Price, Manufacturer address, Dates, FSSAI Number, Consumer Care Helpline, Ingredients)..."
                rows={12}
                disabled={loading}
                className={`w-full font-mono text-xs sm:text-sm p-4 rounded-xl border bg-slate-50/50 dark:bg-slate-950/50 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 transition-all resize-y ${
                  validationError
                    ? 'border-red-300 dark:border-red-800 focus:ring-red-500/20 focus:border-red-500'
                    : 'border-slate-200 dark:border-slate-800 focus:ring-indigo-500/20 focus:border-indigo-500'
                }`}
              />

              <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100 dark:border-slate-800">
                <div className="text-xs text-slate-500 dark:text-slate-400">
                  {rawText.trim() ? (
                    <span>{rawText.trim().split(/\s+/).length} words &bull; {rawText.length} characters</span>
                  ) : (
                    <span>Paste plain text or click &ldquo;Load Sample Package&rdquo; above</span>
                  )}
                </div>

                <button
                  type="button"
                  onClick={handleRunCompliance}
                  disabled={loading}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-xs text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm shadow-indigo-950/30 transition-all cursor-pointer disabled:opacity-60"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Evaluating Declarations…</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 fill-current" />
                      <span>Run Compliance Check</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
