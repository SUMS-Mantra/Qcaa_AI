export default function SkeletonCard() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 animate-pulse">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="h-4 bg-gray-200 rounded w-2/3" />
        <div className="h-6 w-12 bg-gray-200 rounded-lg" />
      </div>
      <div className="h-1.5 bg-gray-200 rounded-full mb-3 w-full" />
      <div className="space-y-2">
        <div className="h-3 bg-gray-200 rounded w-full" />
        <div className="h-3 bg-gray-200 rounded w-5/6" />
        <div className="h-3 bg-gray-200 rounded w-4/6" />
      </div>
    </div>
  );
}
