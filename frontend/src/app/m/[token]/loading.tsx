/** Скелетоны вместо спиннера — экран сразу выглядит как меню. */
export default function Loading() {
  return (
    <div className="min-h-dvh animate-pulse bg-surface px-5 pt-7">
      <div className="h-3 w-12 rounded bg-muted" />
      <div className="mt-2 h-8 w-2/3 rounded-lg bg-muted" />
      <div className="mt-2.5 h-7 w-24 rounded-full bg-muted" />

      <div className="mt-6 flex gap-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-9 w-28 rounded-full bg-muted" />
        ))}
      </div>

      <div className="mt-6 space-y-4">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="h-20 w-20 shrink-0 rounded-xl bg-muted" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-3/4 rounded bg-muted" />
              <div className="h-3 w-full rounded bg-muted" />
              <div className="h-3 w-20 rounded bg-muted" />
            </div>
            <div className="h-11 w-11 shrink-0 rounded-full bg-muted" />
          </div>
        ))}
      </div>
    </div>
  );
}
