import { useState, type ReactNode } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface Props {
  title: string | ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
  headerClassName?: string;
}

export default function Accordion({
  title,
  children,
  defaultOpen = false,
  className = '',
  headerClassName = 'py-3'
}: Props) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className={`border-b border-slate-200 dark:border-slate-800 last:border-0 ${className}`}>
      <button
        className={`w-full flex items-center justify-between text-left cursor-pointer transition-colors hover:text-slate-900 dark:hover:text-slate-100 ${headerClassName}`}
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <div className="flex-1 font-medium text-sm text-slate-800 dark:text-slate-200">
          {title}
        </div>
        <div className="shrink-0 ml-3 text-slate-400">
          {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>
      
      <div 
        className={`grid transition-all duration-200 ease-in-out ${isOpen ? 'grid-rows-[1fr] opacity-100 mb-3' : 'grid-rows-[0fr] opacity-0'}`}
      >
        <div className="overflow-hidden">
          {children}
        </div>
      </div>
    </div>
  );
}
