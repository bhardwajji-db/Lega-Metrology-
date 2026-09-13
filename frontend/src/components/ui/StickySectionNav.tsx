import { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import {
  LayoutDashboard,
  Package,
  AlertTriangle,
  ClipboardCheck,
  ShieldCheck,
  Database,
  Ruler,
  BadgeCheck,
  Eye,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export interface Section {
  id: string;
  label: string;
}

interface Props {
  sections: Section[];
  className?: string;
  offset?: number;
}

// Authoritative mapping of section IDs to icons
const SECTION_ICONS: Record<string, LucideIcon> = {
  'section-summary': LayoutDashboard,
  'section-preview': Package,
  'section-attention': AlertTriangle,
  'section-actions': ClipboardCheck,
  'section-requirements': ShieldCheck,
  'section-package-data': Database,
  'section-rule12': Ruler,
  'section-verification': BadgeCheck,
  'section-evidence': Eye,
};

// Logical grouping of sections
const SECTION_GROUPS = [
  {
    name: 'core',
    label: 'Core Review',
    ids: ['section-summary', 'section-preview', 'section-attention', 'section-actions'],
  },
  {
    name: 'compliance',
    label: 'Compliance',
    ids: ['section-requirements', 'section-package-data', 'section-rule12', 'section-verification'],
  },
  {
    name: 'evidence',
    label: 'Evidence',
    ids: ['section-evidence'],
  },
];

/**
 * Returns the actual scrolling container element for the page.
 */
export function getResultsScrollContainer(): HTMLElement | null {
  const main = document.querySelector('main');
  if (main && (main.scrollHeight > main.clientHeight || getComputedStyle(main).overflowY === 'auto' || getComputedStyle(main).overflowY === 'scroll')) {
    return main;
  }
  return (document.scrollingElement as HTMLElement) || document.documentElement || document.body;
}

/**
 * Robustly scrolls the application scroll container to the target section ID.
 */
export function scrollToSectionId(id: string, offset = 64): boolean {
  const target = document.getElementById(id);
  if (!target) return false;

  const container = getResultsScrollContainer();
  if (!container || container === document.documentElement || container === document.body) {
    const targetRect = target.getBoundingClientRect();
    const top = window.scrollY + targetRect.top - offset;
    window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
  } else {
    const containerRect = container.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const top = targetRect.top - containerRect.top + container.scrollTop - offset;
    container.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
  }
  return true;
}

export default function StickySectionNav({ sections, className = '', offset = 64 }: Props) {
  // Always initialize strictly to the first section (section-summary)
  const [activeSection, setActiveSection] = useState<string>(() => sections[0]?.id || 'section-summary');
  const isUserClicking = useRef<string | null>(null);
  const clickTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navContainerRef = useRef<HTMLDivElement>(null);
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  // Group the incoming sections while preserving order
  const groupedSections = useMemo(() => {
    if (!sections || sections.length === 0) return [];
    
    const sectionMap = new Map(sections.map(s => [s.id, s]));
    const assignedIds = new Set<string>();
    
    const groups = SECTION_GROUPS.map(group => {
      const items = group.ids
        .filter(id => sectionMap.has(id))
        .map(id => {
          assignedIds.add(id);
          return sectionMap.get(id)!;
        });
      return { ...group, items };
    }).filter(g => g.items.length > 0);

    // Any remaining sections not in predefined groups
    const remaining = sections.filter(s => !assignedIds.has(s.id));
    if (remaining.length > 0) {
      groups.push({
        name: 'other',
        label: 'Other',
        ids: remaining.map(r => r.id),
        items: remaining,
      });
    }

    return groups;
  }, [sections]);

  // Evaluate active section based on scroll container position
  const updateActiveSectionFromScroll = useCallback(() => {
    if (isUserClicking.current) return;
    if (!sections || sections.length === 0) return;

    const container = getResultsScrollContainer();
    if (!container) return;

    const isWindowScroll = container === document.documentElement || container === document.body;
    const scrollTop = isWindowScroll ? window.scrollY : container.scrollTop;
    const scrollHeight = isWindowScroll ? document.documentElement.scrollHeight : container.scrollHeight;
    const clientHeight = isWindowScroll ? window.innerHeight : container.clientHeight;

    // 1. Near the very top: strictly select the first section (Summary)
    if (scrollTop < 60) {
      setActiveSection(sections[0].id);
      return;
    }

    // 2. Near the very bottom: strictly select the last available section (Evidence)
    if (scrollTop + clientHeight >= scrollHeight - 30) {
      const lastSec = sections[sections.length - 1];
      if (lastSec) {
        setActiveSection(lastSec.id);
        return;
      }
    }

    // 3. Find the section closest to/passing the reading line
    const containerTop = isWindowScroll ? 0 : container.getBoundingClientRect().top;
    let matchingSectionId = sections[0].id;

    for (const sec of sections) {
      const el = document.getElementById(sec.id);
      if (el) {
        const rect = el.getBoundingClientRect();
        const relTop = isWindowScroll ? rect.top : (rect.top - containerTop);
        // If the top of this section has scrolled up to or past the reading threshold
        if (relTop <= offset + 30) {
          matchingSectionId = sec.id;
        } else {
          // Since sections are in DOM order, subsequent sections are further down
          break;
        }
      }
    }

    setActiveSection(matchingSectionId);
  }, [sections, offset]);

  // Set up scroll event listener on the actual scrolling container
  useEffect(() => {
    if (!sections || sections.length === 0) return;

    const container = getResultsScrollContainer();
    const handleScroll = () => {
      updateActiveSectionFromScroll();
    };

    // Initial check on mount / sections change
    updateActiveSectionFromScroll();

    if (container && container !== document.documentElement && container !== document.body) {
      container.addEventListener('scroll', handleScroll, { passive: true });
    }
    window.addEventListener('scroll', handleScroll, { passive: true });

    return () => {
      if (container && container !== document.documentElement && container !== document.body) {
        container.removeEventListener('scroll', handleScroll);
      }
      window.removeEventListener('scroll', handleScroll);
      if (clickTimeoutRef.current) clearTimeout(clickTimeoutRef.current);
    };
  }, [sections, updateActiveSectionFromScroll]);

  // Auto-center the active tab within the HORIZONTAL navigation container ONLY
  useEffect(() => {
    if (activeSection && tabRefs.current[activeSection] && navContainerRef.current) {
      const container = navContainerRef.current;
      const tab = tabRefs.current[activeSection];
      if (tab) {
        const containerWidth = container.clientWidth;
        const tabLeft = tab.offsetLeft;
        const tabWidth = tab.clientWidth;
        const targetScrollLeft = tabLeft - (containerWidth / 2) + (tabWidth / 2);
        container.scrollTo({
          left: Math.max(0, targetScrollLeft),
          behavior: 'smooth',
        });
      }
    }
  }, [activeSection]);

  const handleTabClick = (id: string) => {
    setActiveSection(id);
    isUserClicking.current = id;
    if (clickTimeoutRef.current) clearTimeout(clickTimeoutRef.current);
    clickTimeoutRef.current = setTimeout(() => {
      isUserClicking.current = null;
    }, 850);

    scrollToSectionId(id, offset);
  };

  if (!sections || sections.length === 0) return null;

  return (
    <div
      className={`sticky -top-4 sm:-top-6 lg:-top-8 z-20 pt-4 sm:pt-6 lg:pt-8 pb-2 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 bg-slate-50/95 dark:bg-slate-950/95 backdrop-blur-md transition-colors ${className}`}
    >
      <nav
        aria-label="Results sections navigation"
        className="bg-slate-900 dark:bg-slate-900 border border-slate-800 rounded-xl shadow-md p-1 max-w-7xl mx-auto"
      >
        <div
          ref={navContainerRef}
          role="tablist"
          className="flex items-center overflow-x-auto no-scrollbar scrollbar-none gap-1 w-full max-w-full"
        >
          {groupedSections.map((group, groupIdx) => (
            <div key={group.name} className="flex items-center gap-1 shrink-0">
              {groupIdx > 0 && (
                <div
                  className="h-4 w-px bg-slate-800 mx-1 shrink-0"
                  aria-hidden="true"
                />
              )}
              {group.items.map((section) => {
                const isActive = activeSection === section.id;
                const Icon = SECTION_ICONS[section.id] || LayoutDashboard;

                return (
                  <button
                    key={section.id}
                    ref={el => { tabRefs.current[section.id] = el; }}
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    aria-controls={section.id}
                    onClick={() => handleTabClick(section.id)}
                    className={`h-9 px-3 sm:px-3.5 whitespace-nowrap text-xs sm:text-[13px] rounded-lg transition-all duration-150 inline-flex items-center gap-2 shrink-0 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 ${
                      isActive
                        ? 'bg-purple-950/50 text-purple-200 font-semibold border-b-2 border-purple-500 shadow-2xs'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border-b-2 border-transparent font-medium'
                    }`}
                  >
                    <Icon
                      className={`w-3.5 h-3.5 shrink-0 transition-colors ${
                        isActive ? 'text-purple-400' : 'text-slate-400'
                      }`}
                    />
                    <span>{section.label}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </nav>
    </div>
  );
}
