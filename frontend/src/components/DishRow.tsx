"use client";

import { useState } from "react";
import type { Dish } from "@/lib/types";
import { formatMenuPrice } from "@/lib/format";
import { t, type Lang } from "@/lib/i18n";
import { useCart } from "./cart-context";
import { DishSheet } from "./DishSheet";
import { DishBadges } from "./DishBadges";
import { MinusIcon, PlusIcon } from "./icons";

/** В списке достаточно превью 160px — крупный файл там лишний вес. */
function thumbUrl(url: string): string {
  return url.replace("_large.webp", "_thumb.webp");
}

export function DishRow({ dish, lang }: { dish: Dish; lang: Lang }) {
  const { add, remove, qtyOf } = useCart();
  const [open, setOpen] = useState(false);
  const qty = qtyOf(dish.id);

  return (
    <li className="flex items-center gap-3 py-3.5 group transition-colors">
      {/* Тап по фото и названию открывает карточку */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex min-w-0 flex-1 items-center gap-3 text-left group-active:opacity-80 transition-opacity"
      >
        {dish.image_url ? (
          <img
            src={thumbUrl(dish.image_url)}
            alt=""
            width={84}
            height={84}
            loading="lazy"
            decoding="async"
            className="h-21 w-21 shrink-0 rounded-2xl object-cover shadow-xs border border-line/40 transition-transform group-hover:scale-[1.02]"
          />
        ) : (
          <div className="flex h-21 w-21 shrink-0 items-center justify-center rounded-2xl bg-muted border border-line/40 text-ink-faint text-xs font-medium">
            🍽️
          </div>
        )}

        <span className="min-w-0 flex-1">
          <span className="block text-base leading-snug font-semibold text-ink group-hover:text-accent transition-colors">
            {dish.name}
          </span>
          <DishBadges dish={dish} />
          {dish.description && (
            <span className="mt-0.5 line-clamp-2 block text-sm leading-snug text-ink-faint">
              {dish.description}
            </span>
          )}
          <span className="mt-1 block text-sm font-bold text-ink-muted">
            {formatMenuPrice(dish.price)}
          </span>
        </span>
      </button>

      {qty === 0 ? (
        <button
          type="button"
          onClick={() => add(dish)}
          aria-label={`${t(lang, "addToCart")}: ${dish.name}`}
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-accent text-on-accent transition-transform active:scale-90"
        >
          <PlusIcon className="h-5 w-5" />
        </button>
      ) : (
        <div className="flex h-12 shrink-0 items-center rounded-full border border-line-strong bg-raised">
          <button
            type="button"
            onClick={() => remove(dish.id)}
            aria-label={`${t(lang, "removeOne")}: ${dish.name}`}
            className="flex h-12 w-11 items-center justify-center rounded-l-full text-ink-muted active:bg-muted"
          >
            <MinusIcon className="h-4 w-4" />
          </button>
          <span className="min-w-6 text-center text-[15px] font-semibold tabular-nums text-ink">
            {qty}
          </span>
          <button
            type="button"
            onClick={() => add(dish)}
            aria-label={`${t(lang, "addMore")}: ${dish.name}`}
            className="flex h-12 w-11 items-center justify-center rounded-r-full text-accent active:bg-muted"
          >
            <PlusIcon className="h-4 w-4" />
          </button>
        </div>
      )}

      {open && (
        <DishSheet dish={dish} lang={lang} onClose={() => setOpen(false)} />
      )}
    </li>
  );
}
