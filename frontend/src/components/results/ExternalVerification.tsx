import React from 'react';
import { BadgeCheck, CheckCircle, XCircle } from 'lucide-react';
import { type FSSAIVerificationResult, type GS1VerificationResult } from '../../types';

interface ExternalVerificationProps {
  fssaiVerification: FSSAIVerificationResult | null | undefined;
  gs1Verification: GS1VerificationResult | null | undefined;
  fssaiLicense: string | null | undefined;
}

const VerificationCard: React.FC<{
  title: string;
  value: string;
  isValid: boolean;
  statusText?: string;
  message: string;
  provider: string;
  type: 'FORMAT' | 'LIVE';
}> = ({ title, value, isValid, statusText, message, provider, type }) => (
  <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
    <div className="flex items-start justify-between mb-3">
      <div>
        <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">{title}</div>
        <div className="font-mono text-sm text-slate-900 dark:text-slate-100">{value}</div>
      </div>
      <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold ${
        isValid ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
      }`}>
        {isValid ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
        {statusText || (isValid ? 'VALID' : 'INVALID')}
      </div>
    </div>
    
    <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">
      {message}
    </div>
    
    <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wider text-slate-400 mt-3 pt-3 border-t border-slate-200 dark:border-slate-700">
      <span>{provider}</span>
      <span className={type === 'LIVE' ? 'text-indigo-500 dark:text-indigo-400' : 'text-amber-500 dark:text-amber-400'}>
        {type === 'LIVE' ? 'LIVE REGISTRY VERIFICATION' : 'FORMAT VALIDATION'}
      </span>
    </div>
  </div>
);

const ExternalVerification: React.FC<ExternalVerificationProps> = ({
  fssaiVerification,
  gs1Verification,
  fssaiLicense
}) => {
  if (!fssaiVerification && !gs1Verification && !fssaiLicense) return null;

  const fssaiNumber = fssaiVerification?.licence_number || fssaiLicense || 'Not detected';
  const fssaiValid = fssaiVerification ? fssaiVerification.status === 'VERIFIED' : (fssaiLicense ? fssaiLicense.length === 14 : false);
  const fssaiMsg = fssaiVerification?.message || (fssaiLicense && fssaiLicense.length === 14 ? 'Format verified (14 digits)' : 'Licence format invalid');
  const fssaiProvider = fssaiVerification?.provider || 'FoSCoS Public Registry API';

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xs mb-6 overflow-hidden">
      <div className="bg-slate-50 dark:bg-slate-800/50 p-4 border-b border-slate-200 dark:border-slate-800 flex items-center gap-2">
        <BadgeCheck className="w-5 h-5 text-indigo-500" />
        <span className="font-semibold text-slate-900 dark:text-slate-100">EXTERNAL REGISTRY VERIFICATION</span>
      </div>
      
      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        {(fssaiLicense || fssaiVerification) && (
          <VerificationCard
            title="FSSAI / FoSCoS"
            value={fssaiNumber}
            isValid={fssaiValid}
            statusText={fssaiVerification?.status || (fssaiValid ? 'VALID' : 'INVALID')}
            message={fssaiMsg}
            provider={fssaiProvider}
            type={fssaiVerification?.is_live ? 'LIVE' : 'FORMAT'}
          />
        )}
        
        {gs1Verification && (
          <VerificationCard
            title="GS1 / GTIN"
            value={gs1Verification.gtin || 'Not detected'}
            isValid={gs1Verification.status === 'VERIFIED'}
            statusText={gs1Verification.status}
            message={gs1Verification.message || 'Verification completed'}
            provider={gs1Verification.provider || 'GS1 Global Data Hub'}
            type={gs1Verification.is_live ? 'LIVE' : 'FORMAT'}
          />
        )}
      </div>
    </div>
  );
};

export default ExternalVerification;
