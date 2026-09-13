import React, { useState } from 'react';
import { ImageIcon, Layers } from 'lucide-react';
import { type ProductImageEvidence } from '../../types';
import api from '../../services/api';

interface PackagePreviewProps {
  images: ProductImageEvidence[];
  productName: string;
  brand?: string | null;
}

const PackagePreview: React.FC<PackagePreviewProps> = ({
  images = [],
  productName,
}) => {
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [imgErrors, setImgErrors] = useState<Record<number, boolean>>({});

  if (!images || images.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/90 dark:border-slate-800 shadow-2xs overflow-hidden mb-6 p-8 text-center">
        <div className="inline-flex p-3 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-500 mb-2">
          <ImageIcon className="w-6 h-6" />
        </div>
        <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">Package image unavailable</h4>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          This analysis does not contain a viewable package image.
        </p>
      </div>
    );
  }

  // Ensure selectedIndex is within bounds
  const activeIndex = selectedIndex >= 0 && selectedIndex < images.length ? selectedIndex : 0;
  const activeImage = images[activeIndex] || images[0];
  const isImageBroken = imgErrors[activeIndex] || !activeImage?.image_url;

  const isFront = (activeImage?.label || '').toLowerCase().includes('front') || activeIndex === 0;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/90 dark:border-slate-800 shadow-2xs overflow-hidden mb-6 transition-all">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/70 dark:bg-slate-800/40">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200/80 dark:border-indigo-800/60 text-indigo-600 dark:text-indigo-400">
            <ImageIcon className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-xs sm:text-sm text-slate-900 dark:text-slate-100 uppercase tracking-wider">
              Package Preview
            </h3>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              Primary analyzed commodity artwork
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 font-mono">
            <Layers className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            {images.length} {images.length === 1 ? 'PANEL' : 'PANELS'}
          </span>
        </div>
      </div>

      {/* Main Image Display Box */}
      <div className="p-4 sm:p-6 flex flex-col items-center">
        <div className="w-full max-w-xl min-h-[220px] max-h-[380px] bg-slate-950/5 dark:bg-slate-950/60 rounded-xl border border-slate-200/80 dark:border-slate-800 flex items-center justify-center p-3 relative overflow-hidden group">
          {!isImageBroken ? (
            <img
              src={api.getAssetUrl(activeImage.image_url)}
              alt={`${productName} - ${activeImage.label || 'Package'}`}
              className="max-h-[340px] w-auto max-w-full object-contain mx-auto rounded-lg shadow-xs transition-transform duration-200 group-hover:scale-[1.01]"
              loading="eager"
              onError={() => {
                setImgErrors(prev => ({ ...prev, [activeIndex]: true }));
              }}
            />
          ) : (
            <div className="flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 py-10 space-y-2">
              <ImageIcon className="w-10 h-10 stroke-[1.5]" />
              <span className="text-xs font-semibold">Package image preview unavailable</span>
              <span className="text-[11px] text-slate-400">Panel: {activeImage?.label || `Panel ${activeIndex + 1}`}</span>
            </div>
          )}
        </div>

        {/* Caption & Metadata */}
        <div className="mt-3.5 text-center space-y-1">
          <div className="flex items-center justify-center gap-2">
            <h4 className="font-bold text-sm text-slate-900 dark:text-slate-100">
              {activeImage.label || `Panel ${activeIndex + 1}`}
            </h4>
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
              {isFront ? 'Primary package view' : 'Secondary package view'}
            </span>
          </div>
          {activeImage.word_count !== undefined && activeImage.word_count > 0 && (
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
              {activeImage.word_count} OCR text elements detected on this panel
            </p>
          )}
        </div>

        {/* Panel Switching Tabs */}
        {images.length > 1 && (
          <div className="mt-4 pt-3.5 border-t border-slate-100 dark:border-slate-800 w-full flex items-center justify-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mr-1">
              Switch Panel:
            </span>
            {images.map((img, idx) => {
              const isSelected = activeIndex === idx;
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setSelectedIndex(idx)}
                  className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-indigo-600 text-white shadow-xs scale-105'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700'
                  }`}
                  aria-pressed={isSelected}
                >
                  <ImageIcon className="w-3.5 h-3.5" />
                  <span>{img.label || `Panel ${idx + 1}`}</span>
                  {img.word_count ? (
                    <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
                      isSelected ? 'bg-indigo-500 text-white' : 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300'
                    }`}>
                      {img.word_count}w
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default PackagePreview;
