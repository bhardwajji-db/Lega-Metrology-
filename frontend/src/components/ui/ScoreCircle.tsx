interface Props {
  score: number;
  size?: number;
  strokeWidth?: number;
  className?: string;
  showOutOf?: boolean;
  decimalPlaces?: number;
}

export default function ScoreCircle({ 
  score, 
  size = 120, 
  strokeWidth, 
  className = '',
  showOutOf = true,
  decimalPlaces
}: Props) {
  const safeScore = Math.min(100, Math.max(0, Number(score) || 0));
  const actualStroke = strokeWidth || Math.max(3.5, Math.round(size * 0.085));
  const radius = (size - actualStroke) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (safeScore / 100) * circumference;

  let strokeColor = 'text-red-500 stroke-red-500';
  let trackColor = 'text-red-100 dark:text-red-950/60 stroke-red-100/70 dark:stroke-red-950/70';
  let scoreColor = 'text-slate-900 dark:text-slate-100';

  if (safeScore >= 90) {
    strokeColor = 'text-emerald-500 stroke-emerald-500';
    trackColor = 'text-emerald-100 dark:text-emerald-950/60 stroke-emerald-100/70 dark:stroke-emerald-950/70';
  } else if (safeScore >= 70) {
    strokeColor = 'text-amber-500 stroke-amber-500';
    trackColor = 'text-amber-100 dark:text-amber-950/60 stroke-amber-100/70 dark:stroke-amber-950/70';
  }

  const displayScore = decimalPlaces !== undefined 
    ? Number(safeScore).toFixed(decimalPlaces) 
    : Math.round(safeScore);

  const shouldShowOutOf = showOutOf && size >= 80;
  const numFontSize = size >= 140 
    ? (decimalPlaces ? 'text-3xl' : 'text-4xl') 
    : size >= 100 
      ? (decimalPlaces ? 'text-2xl' : 'text-3xl') 
      : size >= 70 
        ? 'text-lg' 
        : size >= 48 
          ? 'text-xs font-bold' 
          : 'text-[11px] font-black';

  return (
    <div className={`relative inline-flex items-center justify-center shrink-0 ${className}`} style={{ width: size, height: size }}>
      <svg className="transform -rotate-90 w-full h-full" viewBox={`0 0 ${size} ${size}`}>
        {/* Background Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={actualStroke}
          fill="none"
          className={trackColor}
        />
        {/* Progress Arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={actualStroke}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={`transition-all duration-1000 ease-out ${strokeColor}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center select-none">
        <span className={`${numFontSize} font-extrabold ${scoreColor} tracking-tight leading-none`}>
          {displayScore}
        </span>
        {shouldShowOutOf && (
          <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mt-1">
            out of 100
          </span>
        )}
      </div>
    </div>
  );
}
