"use client";

import type { Dish } from "@/lib/types";

export type BadgeType = "popular" | "spicy" | "veg" | "chef";

/** Метки блюда. Читаем только то, что владелец проставил руками в кабинете.
 *
 *  Раньше они угадывались по словам в названии и описании, и «Салат с авокадо
 *  и креветками» выходил к гостю с меткой «Веган». Про еду догадки недопустимы:
 *  по этой метке человек решает, можно ли ему это есть.
 */
export function getDishBadges(dish: Dish): BadgeType[] {
  const badges: BadgeType[] = [];
  if (dish.is_spicy) badges.push("spicy");
  if (dish.is_veg) badges.push("veg");
  if (dish.is_chef) badges.push("chef");
  if (dish.is_hit) badges.push("popular");
  return badges;
}

export function DishBadges({ dish, size = "sm" }: { dish: Dish; size?: "sm" | "md" }) {
  const badges = getDishBadges(dish);
  if (badges.length === 0) return null;

  const isMd = size === "md";

  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-1">
      {badges.map((badge) => {
        if (badge === "spicy") {
          return (
            <span
              key={badge}
              className={`inline-flex items-center gap-1 rounded-full bg-red-500/10 font-medium text-red-600 dark:bg-red-500/20 dark:text-red-400 ${
                isMd ? "px-2.5 py-0.5 text-xs" : "px-2 py-0.5 text-[11px]"
              }`}
            >
              <span>🌶️</span>
              <span>Острое</span>
            </span>
          );
        }
        if (badge === "veg") {
          return (
            <span
              key={badge}
              className={`inline-flex items-center gap-1 rounded-full bg-emerald-500/10 font-medium text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400 ${
                isMd ? "px-2.5 py-0.5 text-xs" : "px-2 py-0.5 text-[11px]"
              }`}
            >
              <span>🌱</span>
              {/* не «Веган»: кафе ручается за отсутствие мяса, за молоко
                  и яйца в том же блюде — уже нет */}
              <span>Без мяса</span>
            </span>
          );
        }
        if (badge === "chef") {
          return (
            <span
              key={badge}
              className={`inline-flex items-center gap-1 rounded-full bg-amber-500/10 font-medium text-amber-700 dark:bg-amber-500/20 dark:text-amber-300 ${
                isMd ? "px-2.5 py-0.5 text-xs" : "px-2 py-0.5 text-[11px]"
              }`}
            >
              <span>⭐</span>
              <span>Шеф</span>
            </span>
          );
        }
        if (badge === "popular") {
          return (
            <span
              key={badge}
              className={`inline-flex items-center gap-1 rounded-full bg-accent/15 font-medium text-accent ${
                isMd ? "px-2.5 py-0.5 text-xs" : "px-2 py-0.5 text-[11px]"
              }`}
            >
              <span>🔥</span>
              <span>Хит</span>
            </span>
          );
        }
        return null;
      })}
    </div>
  );
}
