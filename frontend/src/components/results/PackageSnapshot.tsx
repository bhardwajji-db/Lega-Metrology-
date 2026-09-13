import React, { useState } from 'react';
import { FileSearch, ChevronDown, ChevronUp } from 'lucide-react';
import { type ProductInfo } from '../../types';

interface PackageSnapshotProps {
  productInfo: ProductInfo;
}

const DataField: React.FC<{ label: string, value: string | null | undefined, truncate?: boolean }> = ({ label, value, truncate }) => {
  if (!value) return null;
  return (
    <div className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-lg border border-slate-100 dark:border-slate-800">
      <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1 uppercase tracking-wider">{label}</div>
      <div className={`text-sm font-medium text-slate-900 dark:text-slate-100 ${truncate ? 'truncate' : 'break-words'}`} title={truncate ? value : undefined}>
        {value}
      </div>
    </div>
  );
};

const PackageSnapshot: React.FC<PackageSnapshotProps> = ({ productInfo = {} as any }) => {
  const [expanded, setExpanded] = useState(false);
  const info = productInfo || ({} as any);

  const consumerCare = [info.consumer_care_phone, info.consumer_care_email, info.consumer_care]
    .filter(Boolean)
    .filter((v, i, a) => a.indexOf(v) === i)
    .join(' | ');

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xs mb-6 overflow-hidden">
      <div className="bg-slate-50 dark:bg-slate-800/50 p-4 border-b border-slate-200 dark:border-slate-800 flex items-center gap-2">
        <FileSearch className="w-5 h-5 text-indigo-500" />
        <span className="font-semibold text-slate-900 dark:text-slate-100">PACKAGE SNAPSHOT</span>
      </div>
      
      <div className="p-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        <DataField label="Brand" value={info.brand} />
        <DataField label="Product Name" value={info.product_name} truncate />
        <DataField label="Net Quantity" value={info.net_quantity} />
        <DataField label="MRP" value={info.mrp} />
        <DataField label="Batch/Lot" value={info.batch_number} />
        <DataField label="Expiry/Best Before" value={info.expiry_date || info.best_before} />
        <DataField label="Manufacturer" value={info.manufacturer} truncate />
        <DataField label="FSSAI Lic No" value={info.fssai_license} />
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full border-t border-slate-100 dark:border-slate-800 p-3 text-xs font-medium text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800/30 flex items-center justify-center gap-1 transition-colors cursor-pointer"
      >
        {expanded ? (
          <><ChevronUp className="w-4 h-4" /> Hide Additional Fields</>
        ) : (
          <><ChevronDown className="w-4 h-4" /> Show Additional Fields</>
        )}
      </button>

      {expanded && (
        <div className="p-4 pt-0 grid grid-cols-1 md:grid-cols-2 gap-3 border-t border-slate-100 dark:border-slate-800">
          <DataField label="Country of Origin" value={info.country_of_origin} />
          <DataField label="Marketed By" value={info.marketed_by} />
          <DataField label="Customer Care" value={consumerCare || undefined} />
          <DataField label="Ingredients" value={info.ingredients} />
          <DataField label="Nutritional Info" value={info.nutritional_info ? 'Detected' : undefined} />
          <DataField label="Allergen Info" value={info.allergen_info} />
        </div>
      )}
    </div>
  );
};

export default PackageSnapshot;
