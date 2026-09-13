import React, { useState, useMemo } from 'react';
import { ShieldCheck, Search } from 'lucide-react';
import { type ComplianceCheck } from '../../types';
import StatusBadge from '../ui/StatusBadge';

interface ComplianceTableProps {
  checks: ComplianceCheck[];
  onViewEvidence: (ruleId: string, imageLabel?: string | null) => void;
  onSelectRequirement: (check: ComplianceCheck) => void;
}

const ComplianceTable: React.FC<ComplianceTableProps> = ({
  checks,
  onViewEvidence,
  onSelectRequirement,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('All');
  const [domainFilter, setDomainFilter] = useState<string>('All');

  const filteredChecks = useMemo(() => {
    return checks.filter(check => {
      const matchesSearch = 
        searchQuery === '' || 
        check.field_label.toLowerCase().includes(searchQuery.toLowerCase()) ||
        check.rule_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (check.detected_value && check.detected_value.toLowerCase().includes(searchQuery.toLowerCase()));
        
      const matchesStatus = statusFilter === 'All' || check.status === statusFilter;
      const matchesDomain = domainFilter === 'All' || (
        domainFilter === 'FSSAI' ? check.rule_id.startsWith('FSSAI') : !check.rule_id.startsWith('FSSAI')
      );

      return matchesSearch && matchesStatus && matchesDomain;
    });
  }, [checks, searchQuery, statusFilter, domainFilter]);

  const getBorderColor = (status: string) => {
    switch (status) {
      case 'PASS': return 'border-l-green-500';
      case 'NEEDS_REVIEW': return 'border-l-amber-500';
      case 'FAIL': return 'border-l-red-500';
      default: return 'border-l-slate-400';
    }
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xs mb-6 overflow-hidden">
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100 font-semibold">
            <ShieldCheck className="w-5 h-5 text-indigo-500" />
            COMPLIANCE REQUIREMENTS
          </div>
          <div className="text-sm text-slate-500 dark:text-slate-400">
            Showing {filteredChecks.length} of {checks.length}
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search rules, fields, values..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 dark:text-slate-100"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 dark:text-slate-100 cursor-pointer"
          >
            <option value="All">All Status</option>
            <option value="PASS">Pass</option>
            <option value="NEEDS_REVIEW">Needs Review</option>
            <option value="FAIL">Fail</option>
            <option value="NOT_APPLICABLE">N/A</option>
          </select>
          <select
            value={domainFilter}
            onChange={(e) => setDomainFilter(e.target.value)}
            className="px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 dark:text-slate-100 cursor-pointer"
          >
            <option value="All">All Domains</option>
            <option value="Legal Metrology">Legal Metrology</option>
            <option value="FSSAI">FSSAI</option>
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-50 dark:bg-slate-800/50 text-xs uppercase text-slate-500 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3 font-medium">Status / Rule</th>
              <th className="px-4 py-3 font-medium">Requirement</th>
              <th className="px-4 py-3 font-medium hidden sm:table-cell">Detected Value</th>
              <th className="px-4 py-3 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
            {filteredChecks.map((check) => (
              <tr 
                key={check.rule_id}
                onClick={() => onSelectRequirement(check)}
                className={`hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors cursor-pointer border-l-4 ${getBorderColor(check.status)}`}
              >
                <td className="px-4 py-3 whitespace-nowrap">
                  <div className="flex flex-col gap-1">
                    <StatusBadge status={check.status} />
                    <span className="font-mono text-[10px] text-slate-500">{check.rule_id}</span>
                  </div>
                </td>
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                  {check.field_label && check.field_label.length > 2 ? check.field_label : (check.field || check.rule_id)}
                </td>
                <td className="px-4 py-3 text-slate-500 dark:text-slate-400 max-w-[200px] truncate hidden sm:table-cell">
                  {check.detected_value || <span className="italic opacity-50">Not detected</span>}
                </td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onViewEvidence(check.rule_id, check.evidence_image_label);
                    }}
                    className="text-indigo-600 dark:text-indigo-400 font-medium hover:underline text-xs bg-transparent border-0 cursor-pointer"
                  >
                    Evidence
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredChecks.length === 0 && (
          <div className="p-8 text-center text-slate-500 dark:text-slate-400">
            No requirements match the current filters.
          </div>
        )}
      </div>
    </div>
  );
};

export default ComplianceTable;
