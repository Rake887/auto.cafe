"use client";

import { useEffect, useState } from "react";
import { t, type Lang } from "@/lib/i18n";

/** Гость уже отвечал на этот вопрос — второй раз не пристаём. */
const ASKED_KEY = "qrmenu_geo_asked";

/** Объяснение перед системным запросом геопозиции.
 *
 *  Без него браузер спрашивает разрешение в момент оформления заказа, без
 *  всякого контекста — и гость рефлекторно отказывает. Короткое «зачем»
 *  перед запросом повышает согласие, а заодно это честнее: человек должен
 *  понимать, что именно он разрешает и что будет, если откажет.
 *
 *  Отказ ничего не ломает: заказ примут, просто стол подтвердит официант.
 *  Обещать обратное нельзя — это было бы неправдой и давлением.
 */
export function GeoPrimer({ lang }: { lang: Lang }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function decide() {
      if (localStorage.getItem(ASKED_KEY) !== null) return;
      if (typeof navigator === "undefined" || !navigator.geolocation) return;

      // Если браузер уже решил (разрешено или запрещено), системный запрос
      // всё равно не появится — объяснять нечего.
      try {
        const status = await navigator.permissions?.query({
          name: "geolocation" as PermissionName,
        });
        if (status && status.state !== "prompt") return;
      } catch {
        // permissions.query поддержан не везде — тогда просто спросим
      }

      if (!cancelled) setOpen(true);
    }

    decide();
    return () => {
      cancelled = true;
    };
  }, []);

  function close() {
    localStorage.setItem(ASKED_KEY, "1");
    setOpen(false);
  }

  function allow() {
    // сам системный запрос: разрешение спрашивает браузер, не мы
    navigator.geolocation.getCurrentPosition(
      () => {},
      () => {},
      { timeout: 10_000, maximumAge: 300_000 },
    );
    close();
  }

  if (!open) return null;

  return (
    <>
      <div
        onClick={close}
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs"
        aria-hidden
      />
      <div
        role="dialog"
        aria-label={t(lang, "geoTitle")}
        className="fixed inset-x-0 bottom-0 z-50 rounded-t-3xl bg-surface px-6 pt-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] shadow-2xl motion-safe:animate-[slide-up_260ms_cubic-bezier(.22,1,.36,1)]"
      >
        <div className="mx-auto w-full max-w-sm text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/15 text-2xl">
            📍
          </div>
          <h2 className="mt-4 text-xl font-bold text-ink">
            {t(lang, "geoTitle")}
          </h2>
          <p className="mt-2 text-[15px] leading-relaxed text-ink-muted">
            {t(lang, "geoWhy")}
          </p>
          <p className="mt-3 text-xs leading-relaxed text-ink-faint">
            {t(lang, "geoOptional")}
          </p>

          <button
            type="button"
            onClick={allow}
            className="mt-5 h-13 w-full rounded-2xl bg-accent text-[17px] font-semibold text-on-accent transition active:scale-[.98] active:bg-accent-strong"
          >
            {t(lang, "geoAllow")}
          </button>
          <button
            type="button"
            onClick={close}
            className="mt-2 h-11 w-full rounded-2xl text-[15px] font-medium text-ink-muted"
          >
            {t(lang, "geoSkip")}
          </button>
        </div>
      </div>
    </>
  );
}
