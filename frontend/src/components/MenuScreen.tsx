"use client";

import { useEffect, useRef, useState } from "react";
import type { MenuResponse } from "@/lib/types";
import { formatPrice, plural } from "@/lib/format";
import { t, type Lang } from "@/lib/i18n";
import { LangSwitch } from "./LangSwitch";
import { CallWaiterButton } from "./CallWaiterButton";
import { CartProvider, useCart } from "./cart-context";
import { CartSheet } from "./CartSheet";
import { DishRow } from "./DishRow";
import { GeoPrimer } from "./GeoPrimer";

import { MenuSearchFilter } from "./MenuSearchFilter";
import { getDishBadges, type BadgeType } from "./DishBadges";

export function MenuScreen({
  menu,
  token,
  lang,
}: {
  menu: MenuResponse;
  token: string;
  lang: Lang;
}) {
  return (
    <CartProvider>
      <MenuBody menu={menu} token={token} lang={lang} />
    </CartProvider>
  );
}

function MenuBody({
  menu,
  token,
  lang,
}: {
  menu: MenuResponse;
  token: string;
  lang: Lang;
}) {
  const { count, total } = useCart();
  const [cartOpen, setCartOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState(menu.categories[0]?.id);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<BadgeType | "all">("all");
  const sectionsRef = useRef<Map<number, HTMLElement>>(new Map());

  // Точное отслеживание активной категории при скролле вверх и вниз
  useEffect(() => {
    const handleScroll = () => {
      const navOffset = 140;
      const sections = menu.categories
        .map((cat) => sectionsRef.current.get(cat.id))
        .filter((el): el is HTMLElement => el !== undefined);

      if (sections.length === 0) return;

      // У самого низа страницы принудительно активируем последнюю категорию
      const atBottom =
        window.innerHeight + window.scrollY >= document.body.offsetHeight - 25;
      if (atBottom) {
        const lastCat = menu.categories[menu.categories.length - 1];
        if (lastCat) {
          setActiveCategory(lastCat.id);
          return;
        }
      }

      // У самого верха активируем первую категорию
      if (window.scrollY < 80) {
        const firstCat = menu.categories[0];
        if (firstCat) {
          setActiveCategory(firstCat.id);
          return;
        }
      }

      let currentActiveId = menu.categories[0]?.id;
      for (const section of sections) {
        const rect = section.getBoundingClientRect();
        if (rect.top <= navOffset) {
          const catId = Number(section.getAttribute("data-cat-id"));
          if (catId) currentActiveId = catId;
        } else {
          break;
        }
      }

      if (currentActiveId) {
        setActiveCategory(currentActiveId);
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();

    return () => window.removeEventListener("scroll", handleScroll);
  }, [menu.categories]);

  // Фильтрация блюд по поисковой строке и выбранным бейджам
  const filterDish = (dish: MenuResponse["categories"][0]["dishes"][0]) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = dish.name.toLowerCase().includes(q);
      const matchDesc = dish.description?.toLowerCase().includes(q);
      if (!matchName && !matchDesc) return false;
    }
    if (activeFilter !== "all") {
      const badges = getDishBadges(dish);
      if (!badges.includes(activeFilter)) return false;
    }
    return true;
  };

  const filteredCategories = menu.categories.map((cat) => ({
    ...cat,
    dishes: cat.dishes.filter(filterDish),
  }));

  const totalFilteredDishes = filteredCategories.reduce(
    (acc, cat) => acc + cat.dishes.length,
    0
  );

  return (
    // lang здесь, а не в layout: чтение cookie в корневом layout сделало бы
    // его динамическим и убило кэш гостевого меню
    <div lang={lang} className="min-h-dvh bg-surface pb-28">
      {/* спрашиваем разрешение только если координаты заведения заданы:
          запрос ради запроса приучает отказывать не глядя */}
      {menu.geo_check_enabled && <GeoPrimer lang={lang} />}
      {/* Brand Ambient Banner Header */}
      <div className="relative bg-gradient-to-b from-accent/20 via-surface/60 to-surface px-5 pb-4 pt-[max(1.75rem,env(safe-area-inset-top))] overflow-hidden border-b border-line/30">
        <div className="flex items-start justify-between gap-3 relative z-10">
          <div className="flex items-center gap-2">
            <span className="flex h-7 items-center rounded-full bg-accent/15 px-3 text-[11px] font-bold tracking-wider text-accent uppercase">
              {t(lang, "menu")}
            </span>
            {/* Состояние берём с сервера: раньше бейдж всегда светился
                «Открыто • до 23:00», даже когда заведение закрыто */}
            <span
              className={`inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-[11px] font-semibold ${
                menu.accepting_orders
                  ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
                  : "bg-muted text-ink-muted"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  menu.accepting_orders
                    ? "animate-pulse bg-emerald-500"
                    : "bg-ink-faint"
                }`}
              />
              {t(lang, menu.accepting_orders ? "openTime" : "closedNow")}
            </span>
          </div>
          <LangSwitch current={lang} />
        </div>

        <div className="mt-4 flex items-center gap-3.5 relative z-10">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-accent text-on-accent text-2xl font-bold shadow-md">
            ☕
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl leading-tight font-extrabold text-ink">
              {menu.branch_name}
            </h1>
            <p className="text-xs text-ink-muted mt-0.5">
              Тараз • Свежие напитки и авторская кухня
            </p>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2.5 relative z-10">
          <span className="inline-flex h-10 items-center rounded-full border border-line-strong bg-raised/80 px-4 text-xs font-semibold text-ink shadow-xs backdrop-blur">
            📍 {menu.point_label}
          </span>
          <CallWaiterButton token={token} lang={lang} />
          {/* валюта названа один раз: в карточках блюд цены идут без символа */}
          <span className="text-xs text-ink-faint">{t(lang, "pricesInTenge")}</span>
        </div>
      </div>

      {/* Instant Search Bar & Filter Chips */}
      <MenuSearchFilter
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        activeFilter={activeFilter}
        onFilterChange={setActiveFilter}
        placeholder={t(lang, "searchPlaceholder")}
        allLabel={t(lang, "allDishes")}
      />

      {/* Sticky Categories Navigation */}
      <nav className="sticky top-[env(safe-area-inset-top)] z-30 border-b border-line bg-surface/90 backdrop-blur shadow-xs">
        <ul className="flex gap-2 overflow-x-auto px-5 py-2.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {menu.categories.map((cat) => {
            const isCatActive = activeCategory === cat.id;
            return (
              <li key={cat.id}>
                <a
                  href={`#cat-${cat.id}`}
                  onClick={(e) => {
                    e.preventDefault();
                    setActiveCategory(cat.id);
                    if (searchQuery || activeFilter !== "all") {
                      setSearchQuery("");
                      setActiveFilter("all");
                    }
                    setTimeout(() => {
                      const el = document.getElementById(`cat-${cat.id}`);
                      if (el) {
                        const yOffset = -110;
                        const y = el.getBoundingClientRect().top + window.pageYOffset + yOffset;
                        window.scrollTo({ top: y, behavior: "smooth" });
                      }
                    }, 10);
                  }}
                  className={`flex h-10 items-center rounded-full px-4 text-xs font-semibold whitespace-nowrap transition active:scale-95 ${
                    isCatActive
                      ? "bg-accent text-on-accent shadow-xs"
                      : "bg-muted text-ink-muted hover:text-ink"
                  }`}
                >
                  {cat.name}
                </a>
              </li>
            );
          })}
        </ul>
      </nav>

      <main className="px-5">
        {totalFilteredDishes === 0 ? (
          <div className="py-16 text-center">
            <span className="text-4xl">🔍</span>
            <p className="mt-3 text-base font-semibold text-ink">Ничего не найдено</p>
            <p className="mt-1 text-xs text-ink-faint">
              Попробуйте изменить запрос или сбросить фильтры
            </p>
            <button
              type="button"
              onClick={() => {
                setSearchQuery("");
                setActiveFilter("all");
              }}
              className="mt-4 rounded-full bg-accent/15 px-4 py-2 text-xs font-semibold text-accent hover:bg-accent/20 transition"
            >
              Сбросить поиск
            </button>
          </div>
        ) : (
          filteredCategories.map((cat) => {
            if (cat.dishes.length === 0 && (searchQuery || activeFilter !== "all")) {
              return null;
            }
            return (
              <section
                key={cat.id}
                id={`cat-${cat.id}`}
                data-cat-id={cat.id}
                ref={(el) => {
                  if (el) sectionsRef.current.set(cat.id, el);
                }}
                className="scroll-mt-28 pt-7"
              >
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-extrabold text-ink">{cat.name}</h2>
                  <span className="text-xs font-medium text-ink-faint">
                    {cat.dishes.length} {lang === "ru" ? plural(cat.dishes.length, "позиция", "позиции", "позиций") : t(lang, "dishes")}
                  </span>
                </div>
                <div className="mt-1.5 h-1 w-8 rounded-full bg-accent" />
                {cat.dishes.length === 0 ? (
                  <p className="py-4 text-sm text-ink-faint">
                    {t(lang, "emptyCategory")}
                  </p>
                ) : (
                  <ul className="mt-2 divide-y divide-line/60">
                    {cat.dishes.map((dish) => (
                      <DishRow key={dish.id} dish={dish} lang={lang} />
                    ))}
                  </ul>
                )}
              </section>
            );
          })
        )}

        {menu.menu_disclaimer && (
          /* Обычный текст, без HTML: разметка из поля ввода в кабинете —
             это XSS на гостевом экране */
          <p className="mt-10 rounded-2xl bg-muted px-4 py-3 text-xs leading-relaxed text-ink-faint">
            {menu.menu_disclaimer}
          </p>
        )}
      </main>

      {count > 0 && !cartOpen && menu.accepting_orders && (
        <div className="fixed inset-x-0 bottom-0 z-30 px-5 pb-[max(1rem,env(safe-area-inset-bottom))] pt-6 bg-gradient-to-t from-surface via-surface/95 to-transparent motion-safe:animate-[slide-up_220ms_ease-out]">
          <button
            type="button"
            onClick={() => setCartOpen(true)}
            className="flex h-14 w-full items-center justify-between rounded-2xl bg-accent px-5 text-on-accent shadow-xl transition active:scale-[.98] active:bg-accent-strong"
          >
            <span className="font-bold text-[15px]">
              {t(lang, "cart")} · {count}{" "}
              {lang === "ru"
                ? plural(count, "блюдо", "блюда", "блюд")
                : t(lang, "dishes")}
            </span>
            <span className="font-extrabold text-base tabular-nums">{formatPrice(total)} →</span>
          </button>
        </div>
      )}

      {!menu.accepting_orders && (
        <div className="fixed inset-x-0 bottom-0 z-30 px-5 pb-[max(1rem,env(safe-area-inset-bottom))] pt-6 bg-gradient-to-t from-surface via-surface/95 to-transparent">
          <p className="flex min-h-14 items-center justify-center rounded-2xl bg-muted px-5 text-center text-sm font-medium text-ink-muted">
            {menu.closed_reason ?? "Сейчас заказы не принимаем"}
          </p>
        </div>
      )}

      <CartSheet
        open={cartOpen}
        onClose={() => setCartOpen(false)}
        pointToken={token}
        lang={lang}
        geoEnabled={menu.geo_check_enabled}
      />
    </div>
  );
}

