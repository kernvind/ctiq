export default function Loading() {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-40 animate-pulse rounded-lg bg-muted" />
      ))}
    </div>
  );
}
