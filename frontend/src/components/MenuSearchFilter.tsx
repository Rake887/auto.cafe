"use client";

import { CloseIcon, SearchIcon } from "./icons";
import type { BadgeType } from "./DishBadges";

export function MenuSearchFilter({
  searchQuery,
  onSearchChange,
  activeFilter,
  onFilterChange,
  placeholder,
  allLabel,
}: {
  searchQuery: string;
  onSearchChange: (q: string) => void;
  activeFilter: BadgeType | "all";
  onFilterChange: (filter: BadgeType | "all") => void;
  placeholder: string;
  allLabel: string;
}) {
  const filters: { id: BadgeType | "all"; label: string; icon?: string }[] = [
    { id: "all", label: allLabel },
    { id: "popular", label: "Хиты", icon: "🔥" },
    { id: "spicy", label: "Острое", icon: "🌶️" },
    { id: "veg", label: "Без мяса", icon: "🌱" },
    { id: "chef", label: "Шеф", icon: "⭐" },
  ];

  return (
    <div className="space-y-3 px-5 pt-3 pb-2">
      {/* Search Input Bar */}
      <div className="relative flex items-center">
        <SearchIcon className="absolute left-3.5 h-4 w-4 text-ink-faint pointer-events-none" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={placeholder}
          className="h-11 w-full rounded-2xl bg-muted pl-10 pr-9 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-accent/40 transition"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => onSearchChange("")}
            className="absolute right-3 flex h-6 w-6 items-center justify-center rounded-full bg-line text-ink-muted hover:text-ink transition"
          >
            <CloseIcon className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Filter Chips Bar */}
      <div className="flex gap-2 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden py-0.5">
        {filters.map((f) => {
          const isActive = activeFilter === f.id;
          return (
            <button
              key={f.id}
              type="button"
              onClick={() => onFilterChange(f.id)}
              className={`flex h-8 items-center gap-1.5 rounded-full px-3.5 text-xs font-semibold whitespace-nowrap transition active:scale-95 ${
                isActive
                  ? "bg-ink text-surface shadow-sm dark:bg-raised dark:text-ink dark:border dark:border-line-strong"
                  : "bg-muted text-ink-muted hover:bg-line/70"
              }`}
            >
              {f.icon && <span>{f.icon}</span>}
              <span>{f.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
