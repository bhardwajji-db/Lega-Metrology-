import { Server, Cpu, FileText, CheckCircle2, Sparkles, BookOpen, ShieldCheck, Layers } from 'lucide-react';
import Card from '../components/ui/Card';

export default function About() {
  const architectureComponents = [
    {
      title: 'Vite + React UI',
      desc: 'Multi-panel image inspection, interactive Evidence Viewer & high-density compliance matrix.',
      icon: FileText,
      color: 'indigo'
    },
    {
      title: 'FastAPI Backend',
      desc: 'PaddleOCR deep learning engine (PP-OCRv4), dynamic thresholding, panel combining & audit-grade ReportLab PDF.',
      icon: Server,
      color: 'blue'
    },
    {
      title: 'Statutory Rule Engine',
      desc: 'LM-001..LM-010 + FSSAI deterministic compliance evaluators with statutory source traceability.',
      icon: BookOpen,
      color: 'emerald'
    },
    {
      title: 'Corrective Action Engine',
      desc: 'Prioritized manufacturer guidance, specific verification steps & decision-support recommendations.',
      icon: Cpu,
      color: 'purple'
    }
  ];

  const futureRoadmap = [
    'Multi-language Hindi & Indic regional language optical recognition',
    'Mobile application for on-field weights & measures enforcement officers',
    'High-throughput batch catalog screening for e-commerce marketplaces',
    'Direct FSSAI FoSCoS portal verification for live licence authentication',
    'Automated Barcode / QR-code data extraction & verification synchronization',
    'Continuous active learning & edge correction from verified officer findings'
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-12 animate-in fade-in duration-300">
      {/* Hero Header */}
      <div className="text-center py-6 max-w-2xl mx-auto space-y-2">
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-50 dark:bg-indigo-950/50 border border-indigo-200 dark:border-indigo-800/60 rounded-full text-xs font-semibold text-indigo-700 dark:text-indigo-300">
          <Sparkles className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400" />
          <span>Smart India Hackathon 2026 Submission</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-slate-100 tracking-tight">
          MetrCheck AI
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
          Automated Statutory Compliance Screening &amp; Decision-Support System for Packaged Commodities under the <span className="font-semibold text-slate-700 dark:text-slate-300">Legal Metrology (Packaged Commodities) Rules, 2011</span> and <span className="font-semibold text-slate-700 dark:text-slate-300">FSSAI Packaging Regulations</span>.
        </p>
      </div>

      {/* Problem & Solution Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card title="The Problem (SIH Problem Statement)" icon={ShieldCheck}>
          <p className="text-slate-700 dark:text-slate-300 leading-relaxed text-xs">
            Manual inspection of packaged commodities for compliance with statutory labelling laws is labor-intensive, subjective, and practically impossible to scale across millions of fast-moving consumer SKUs. Manufacturers and regulatory inspectors need an objective, evidence-backed tool to instantly verify mandatory declarations (MRP, Net Quantity, Dates, Manufacturer Address, Batch Number, FSSAI Licence, and Consumer Care).
          </p>
        </Card>
        
        <Card title="Our Solution (MetrCheck Architecture)" icon={Sparkles}>
          <p className="text-slate-700 dark:text-slate-300 leading-relaxed text-xs">
            MetrCheck AI provides an end-to-end statutory screening engine combining multi-panel computer vision OCR, structured statutory declaration extraction, deterministic compliance verification against versioned rule registries, interactive visual evidence localization with bounding box overlays, prioritized corrective actions, and audit-grade PDF export dossiers.
          </p>
        </Card>
      </div>

      {/* System Architecture */}
      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 tracking-tight">Modular System Architecture</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">Core architectural components powering MetrCheck AI</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {architectureComponents.map((comp) => (
            <div 
              key={comp.title}
              className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 shadow-2xs flex flex-col justify-between hover:shadow-xs transition-shadow"
            >
              <div className="space-y-2.5">
                <div className="w-10 h-10 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                  <comp.icon className="w-5 h-5" />
                </div>
                <h4 className="font-bold text-xs sm:text-sm text-slate-900 dark:text-slate-100">{comp.title}</h4>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">{comp.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Regulatory Notice */}
      <div className="bg-amber-50/80 dark:bg-amber-950/40 border border-amber-200/90 dark:border-amber-800/60 rounded-2xl p-5 text-amber-950 dark:text-amber-200 text-xs leading-relaxed space-y-1">
        <h4 className="font-bold text-amber-900 dark:text-amber-300 text-sm">Regulatory Notice &amp; Enforcement Scope</h4>
        <p>
          MetrCheck AI is an AI-assisted compliance screening and decision-support system. It is designed to assist manufacturers, packagers, retailers, and enforcement officers in preliminary package inspections. It does not replace physical statutory inspections by authorized officers under the Legal Metrology Act, 2009 or the Food Safety and Standards Act, 2006.
        </p>
      </div>

      {/* Future Roadmap */}
      <Card title="Future Roadmap & Scalability" icon={Layers}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {futureRoadmap.map((item, i) => (
            <div key={i} className="flex items-start gap-2.5 p-3 bg-slate-50/70 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-700/60 rounded-xl">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
              <span className="text-slate-700 dark:text-slate-300 text-xs font-medium leading-snug">{item}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}