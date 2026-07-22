"use client";

import { useEffect } from "react";
import type { Dish } from "@/lib/types";
import { formatMenuPrice } from "@/lib/format";
import { t, type Lang } from "@/lib/i18n";
import { useCart } from "./cart-context";
import { DishBadges } from "./DishBadges";
import { CloseIcon, MinusIcon, PlusIcon } from "./icons";

/** Карточка блюда: крупное фото и полное описание. */
export function DishSheet({
  dish,
  lang,
  onClose,
}: {
  dish: Dish;
  lang: Lang;
  onClose: () => void;
}) {
  const { add, remove, qtyOf } = useCart();
  const qty = qtyOf(dish.id);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-xs motion-safe:animate-[rise_200ms_ease-out]"
        aria-hidden
      />
      <div
        role="dialog"
        aria-label={dish.name}
        className="fixed inset-x-0 bottom-0 z-50 max-h-[90vh] overflow-y-auto rounded-t-3xl bg-surface pb-[max(1.5rem,env(safe-area-inset-bottom))] shadow-2xl motion-safe:animate-[slide-up_260ms_cubic-bezier(.22,1,.36,1)]"
      >
        <div className="relative">
          {dish.image_url ? (
            <div className="relative h-72 w-full overflow-hidden rounded-t-3xl">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={dish.image_url}
                alt=""
                className="h-full w-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-surface via-transparent to-black/20" />
            </div>
          ) : (
            <div className="flex h-36 w-full items-center justify-center rounded-t-3xl bg-muted text-4xl">
              🍽️
            </div>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label={t(lang, "close")}
            className="absolute top-4 right-4 flex h-10 w-10 items-center justify-center rounded-full bg-surface/80 text-ink shadow-md backdrop-blur hover:bg-surface transition"
          >
            <CloseIcon className="h-5 w-5" />
          </button>
        </div>

        <div className="px-6 pt-4">
          <div className="flex items-start justify-between gap-3">
            <h2 className="text-2xl leading-tight font-bold text-ink">
              {dish.name}
            </h2>
          </div>
          <DishBadges dish={dish} size="md" />

          {dish.description && (
            <p className="mt-3 text-[15px] leading-relaxed text-ink-muted">
              {dish.description}
            </p>
          )}
          {dish.allergens && (
            /* Крупная карточка блюда — единственное место, где у гостя есть
               время это прочитать до того, как он нажмёт «Добавить» */
            <p className="mt-3 rounded-xl bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:bg-amber-500/15 dark:text-amber-200">
              ⚠️ Содержит: {dish.allergens}
            </p>
          )}
          <p className="mt-4 text-2xl font-extrabold text-accent tabular-nums">
            {formatMenuPrice(dish.price)}
          </p>
        </div>

        <div className="px-6 pt-5">
          {qty === 0 ? (
            <button
              type="button"
              onClick={() => {
                add(dish);
                onClose();
              }}
              className="h-14 w-full rounded-2xl bg-accent text-[17px] font-semibold text-on-accent transition active:scale-[.98] active:bg-accent-strong"
            >
              {t(lang, "addToCart")}
            </button>
          ) : (
            <div className="flex items-center gap-3">
              <div className="flex h-14 flex-1 items-center justify-between rounded-2xl border border-line-strong bg-raised px-2">
                <button
                  type="button"
                  onClick={() => remove(dish.id)}
                  aria-label={t(lang, "removeOne")}
                  className="flex h-12 w-12 items-center justify-center rounded-xl text-ink-muted active:bg-muted"
                >
                  <MinusIcon className="h-5 w-5" />
                </button>
                <span className="text-lg font-semibold tabular-nums text-ink">
                  {qty}
                </span>
                <button
                  type="button"
                  onClick={() => add(dish)}
                  aria-label={t(lang, "addMore")}
                  className="flex h-12 w-12 items-center justify-center rounded-xl text-accent active:bg-muted"
                >
                  <PlusIcon className="h-5 w-5" />
                </button>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="h-14 rounded-2xl bg-accent px-6 text-[17px] font-semibold text-on-accent transition active:bg-accent-strong"
              >
                {t(lang, "done")}
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
