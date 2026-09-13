import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { type UserRole, type RoleInfo } from '../types';
import { useWorkspace } from './WorkspaceContext';

interface RoleContextType {
  role: UserRole;
  setRole: (role: UserRole) => void;
  isEnforcementOfficer: boolean;
  officerId: string;
  jurisdiction: string;
  roleInfo: RoleInfo;
}

export const ROLE_DEFINITIONS: Record<UserRole, RoleInfo> = {
  ENFORCEMENT_OFFICER: {
    role: 'ENFORCEMENT_OFFICER',
    label: 'Enforcement Official',
    badge: 'LEGAL METROLOGY INSPECTOR',
    officerId: 'LM-INSP-2026-IND',
    jurisdiction: 'Consumer Affairs & Legal Metrology Directorate',
    description: 'Enforcement mode: Access statutory violation clauses, show-cause notice generation, and penalty estimators under Sections 36/38.'
  },
  COMPLIANCE_INSPECTOR: {
    role: 'COMPLIANCE_INSPECTOR',
    label: 'Quality & Audit Inspector',
    badge: 'QA COMPLIANCE AUDITOR',
    officerId: 'QA-AUDIT-9921',
    jurisdiction: 'Packaging Quality & Standard Division',
    description: 'Auditor mode: Complete rule-by-rule verification, evidence bounding box mapping, and compliance scoring.'
  },
  MERCHANT_PUBLIC: {
    role: 'MERCHANT_PUBLIC',
    label: 'Brand / Merchant Mode',
    badge: 'MERCHANT PRE-FLIGHT',
    officerId: 'MERCHANT-PUB',
    jurisdiction: 'Commercial Packaging Verification',
    description: 'Merchant mode: Pre-flight packaging check before printing and retail distribution.'
  }
};

const RoleContext = createContext<RoleContextType | undefined>(undefined);

export function RoleProvider({ children }: { children: ReactNode }) {
  const { currentWorkspace, setWorkspace, officerId, jurisdiction } = useWorkspace();

  const role: UserRole = useMemo(() => {
    if (currentWorkspace === 'ENFORCEMENT') return 'ENFORCEMENT_OFFICER';
    if (currentWorkspace === 'AUDIT') return 'COMPLIANCE_INSPECTOR';
    return 'MERCHANT_PUBLIC';
  }, [currentWorkspace]);

  const setRole = (newRole: UserRole) => {
    if (newRole === 'ENFORCEMENT_OFFICER') setWorkspace('ENFORCEMENT');
    else if (newRole === 'COMPLIANCE_INSPECTOR') setWorkspace('AUDIT');
    else setWorkspace('MERCHANT');
  };

  const roleInfo = ROLE_DEFINITIONS[role] || ROLE_DEFINITIONS.MERCHANT_PUBLIC;

  return (
    <RoleContext.Provider
      value={{
        role,
        setRole,
        isEnforcementOfficer: role === 'ENFORCEMENT_OFFICER',
        officerId,
        jurisdiction,
        roleInfo
      }}
    >
      {children}
    </RoleContext.Provider>
  );
}

export function useRole(): RoleContextType {
  const context = useContext(RoleContext);
  if (!context) {
    throw new Error('useRole must be used within a RoleProvider');
  }
  return context;
}
