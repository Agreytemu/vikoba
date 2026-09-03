import { FC } from "react";

const SkeletonBase: FC<{ className?: string }> = ({ className = "" }) => (
  <div className={`animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800 ${className}`} />
);

export const SkeletonCard: FC = () => (
  <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
    <SkeletonBase className="h-4 w-24" />
    <SkeletonBase className="mt-3 h-7 w-32" />
    <SkeletonBase className="mt-2 h-3 w-40" />
  </div>
);

export const SkeletonRow: FC = () => (
  <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
    <SkeletonBase className="h-10 w-10 rounded-full" />
    <div className="flex-1 space-y-2">
      <SkeletonBase className="h-4 w-3/4" />
      <SkeletonBase className="h-3 w-1/2" />
    </div>
  </div>
);

export const SkeletonTable: FC<{ rows?: number }> = ({ rows = 5 }) => (
  <div className="space-y-3">
    {Array.from({ length: rows }).map((_, i) => (
      <SkeletonRow key={i} />
    ))}
  </div>
);

export const SkeletonGrid: FC<{ count?: number }> = ({ count = 6 }) => (
  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {Array.from({ length: count }).map((_, i) => (
      <SkeletonCard key={i} />
    ))}
  </div>
);

export const SkeletonProfile: FC = () => (
  <div className="space-y-6">
    <div className="flex items-center gap-4">
      <SkeletonBase className="h-20 w-20 rounded-full" />
      <div className="space-y-2">
        <SkeletonBase className="h-5 w-32" />
        <SkeletonBase className="h-3 w-48" />
      </div>
    </div>
    <SkeletonBase className="h-32 w-full" />
    <SkeletonBase className="h-48 w-full" />
  </div>
);

export const SkeletonPage: FC = () => (
  <div className="mx-auto max-w-4xl space-y-4 p-4">
    <SkeletonBase className="h-8 w-48" />
    <SkeletonBase className="h-4 w-72" />
    <div className="grid gap-4 sm:grid-cols-3">
      <SkeletonCard />
      <SkeletonCard />
      <SkeletonCard />
    </div>
    <SkeletonBase className="h-64 w-full" />
  </div>
);

export default SkeletonBase;
