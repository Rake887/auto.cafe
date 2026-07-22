"use client";

import { useState } from "react";
import { adminMutate } from "@/lib/api";
import type { AdminCategory, AdminDish, AdminMenu } from "@/lib/types";
import { MenuImport } from "./MenuImport";
import { PlusIcon } from "./icons";

/** Значения формы блюда: то, что владелец правит руками. */
interface DishValues {
  name: string;
  name_kk: string | null;
  description_kk: string | null;
  price: number;
  cost_price: number | null;
  description: string | null;
  allergens: string | null;
  is_veg: boolean;
  is_spicy: boolean;
  is_hit: boolean;
  is_chef: boolean;
  category_id?: number;
}

type Run = (action: () => Promise<unknown>) => Promise<void>;

/** Метки блюда. Ставит владелец: угадывать их по описанию нельзя — по этим
 *  значкам гость решает, можно ли ему это есть. */
const TAGS = [
  { key: "is_veg", label: "🌱 Без мяса" },
  { key: "is_spicy", label: "🌶️ Острое" },
  { key: "is_hit", label: "🔥 Хит" },
  { key: "is_chef", label: "⭐ Шеф" },
] as const;

/** «12:00:00» → «12:00»: input[type=time] длиннее не принимает. */
function toInputTime(value: string | null): string {
  return value === null ? "" : value.slice(0, 5);
}

/** Доля себестоимости в цене. Выше 40 % — блюдо почти не зарабатывает. */
function foodCost(price: number, cost: number | null): number | null {
  if (cost === null || price <= 0) return null;
  return Math.round((cost / price) * 100);
}

export function MenuEditor({ initial }: { initial: AdminMenu }) {
  const [menu, setMenu] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState<number | null>(null);
  const [newCategory, setNewCategory] = useState(false);
  const [query, setQuery] = useState("");

  /** После любой правки перечитываем меню целиком — оно небольшое,
   *  зато экран гарантированно совпадает с базой. */
  async function reload() {
    const fresh = await fetch("/api/admin/menu", { cache: "no-store" });
    if (fresh.ok) setMenu(await fresh.json());
  }

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  // список для «перенести блюдо в другую категорию»
  const categoryOptions = menu.categories.map((c) => ({
    id: c.id,
    name: c.name,
  }));

  const needle = query.trim().toLowerCase();
  const matches = (dish: AdminDish) =>
    needle === "" || dish.name.toLowerCase().includes(needle);

  return (
    <div className="mt-6 space-y-6">
      {error !== null && (
        <p className="rounded-xl bg-muted px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Найти блюдо"
        aria-label="Поиск по меню"
        className="h-11 w-full rounded-2xl border border-line bg-raised px-4 text-[15px] text-ink focus:border-accent focus:outline-none"
      />

      {menu.categories.map((category, index) => (
        <CategorySection
          key={category.id}
          category={category}
          first={index === 0}
          last={index === menu.categories.length - 1}
          dishes={category.dishes.filter(matches)}
          hiddenByQuery={needle !== "" && !category.dishes.some(matches)}
          // при поиске раскрываем всё: иначе найденное блюдо осталось бы
          // спрятанным внутри свёрнутой категории
          forceOpen={needle !== ""}
          categories={categoryOptions}
          adding={adding === category.id}
          onAdd={() => setAdding(category.id)}
          onCancelAdd={() => setAdding(null)}
          onSubmitAdd={async (values) => {
            await run(() =>
              adminMutate("/admin/dishes", {
                method: "POST",
                body: JSON.stringify({ ...values, category_id: category.id }),
              }),
            );
            setAdding(null);
          }}
          onRun={run}
        />
      ))}

      {newCategory ? (
        <CategoryForm
          onCancel={() => setNewCategory(false)}
          onSubmit={async (name) => {
            await run(() =>
              adminMutate("/admin/categories", {
                method: "POST",
                body: JSON.stringify({ name }),
              }),
            );
            setNewCategory(false);
          }}
        />
      ) : (
        <button
          type="button"
          onClick={() => setNewCategory(true)}
          className="flex h-12 w-full items-center justify-center rounded-2xl border border-line bg-raised font-medium text-ink"
        >
          Добавить категорию
        </button>
      )}

      <MenuImport onDone={reload} />
    </div>
  );
}

/** Категория целиком. Свёрнута по умолчанию: при сорока позициях развёрнутое
 *  меню превращается в простыню, по которой не попасть в нужное блюдо. */
function CategorySection({
  category,
  first,
  last,
  dishes,
  hiddenByQuery,
  forceOpen,
  categories,
  adding,
  onAdd,
  onCancelAdd,
  onSubmitAdd,
  onRun,
}: {
  category: AdminCategory;
  first: boolean;
  last: boolean;
  dishes: AdminDish[];
  hiddenByQuery: boolean;
  forceOpen: boolean;
  categories: { id: number; name: string }[];
  adding: boolean;
  onAdd: () => void;
  onCancelAdd: () => void;
  onSubmitAdd: (values: DishValues) => Promise<void>;
  onRun: Run;
}) {
  const [open, setOpen] = useState(false);
  const expanded = open || forceOpen || adding;

  if (hiddenByQuery) return null;

  return (
    <section>
      <CategoryHead
        category={category}
        first={first}
        last={last}
        count={category.dishes.length}
        expanded={expanded}
        onToggle={() => setOpen((v) => !v)}
        onRun={onRun}
      />

      {expanded && (
        <>
          <ul className="mt-3 space-y-2">
            {dishes.map((dish) => (
              <DishCard
                key={dish.id}
                dish={dish}
                categoryId={category.id}
                categories={categories}
                first={dish.id === category.dishes[0]?.id}
                last={
                  dish.id === category.dishes[category.dishes.length - 1]?.id
                }
                onRun={onRun}
              />
            ))}
          </ul>

          {adding ? (
            <DishForm
              submitLabel="Добавить"
              onCancel={onCancelAdd}
              onSubmit={onSubmitAdd}
            />
          ) : (
            <button
              type="button"
              onClick={onAdd}
              className="mt-2 flex h-11 w-full items-center justify-center gap-1.5 rounded-2xl border border-dashed border-line text-sm text-ink-muted"
            >
              <PlusIcon className="h-4 w-4" /> Добавить блюдо
            </button>
          )}
        </>
      )}
    </section>
  );
}

/** Заголовок категории: сворачивание, переименование, часы показа,
 *  перестановка и снятие с меню. */
function CategoryHead({
  category,
  first,
  last,
  count,
  expanded,
  onToggle,
  onRun,
}: {
  category: AdminCategory;
  first: boolean;
  last: boolean;
  count: number;
  expanded: boolean;
  onToggle: () => void;
  onRun: Run;
}) {
  const [renaming, setRenaming] = useState(false);
  const [scheduling, setScheduling] = useState(false);
  const [name, setName] = useState(category.name);

  function saveName() {
    const value = name.trim();
    setRenaming(false);
    if (value === "" || value === category.name) {
      setName(category.name);
      return;
    }
    onRun(() =>
      adminMutate(`/admin/categories/${category.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name: value }),
      }),
    );
  }

  if (renaming) {
    return (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          saveName();
        }}
        className="flex gap-2"
      >
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-label="Название категории"
          autoFocus
          className="h-11 flex-1 rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          className="h-11 rounded-xl bg-accent px-4 font-semibold text-on-accent"
        >
          Сохранить
        </button>
        <button
          type="button"
          onClick={() => {
            setName(category.name);
            setRenaming(false);
          }}
          className="h-11 rounded-xl bg-muted px-3 text-ink-muted"
        >
          Отмена
        </button>
      </form>
    );
  }

  const scheduled =
    category.available_from !== null || category.available_to !== null;

  return (
    <>
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <span
            aria-hidden
            className={`text-ink-faint transition ${expanded ? "rotate-90" : ""}`}
          >
            ▶
          </span>
          <h2 className="min-w-0 truncate text-lg font-bold text-ink">
            {category.name}
          </h2>
          <span className="shrink-0 text-sm text-ink-faint tabular-nums">
            {count}
          </span>
        </button>

        <div className="flex h-9 shrink-0 items-center gap-1 rounded-full border border-line px-1">
          <button
            type="button"
            disabled={first}
            aria-label={`Категорию «${category.name}» выше`}
            onClick={() =>
              onRun(() =>
                adminMutate(`/admin/categories/${category.id}/move?direction=up`, {
                  method: "POST",
                }),
              )
            }
            className="flex h-7 w-7 items-center justify-center rounded-full text-ink-muted disabled:opacity-30"
          >
            ↑
          </button>
          <button
            type="button"
            disabled={last}
            aria-label={`Категорию «${category.name}» ниже`}
            onClick={() =>
              onRun(() =>
                adminMutate(
                  `/admin/categories/${category.id}/move?direction=down`,
                  { method: "POST" },
                ),
              )
            }
            className="flex h-7 w-7 items-center justify-center rounded-full text-ink-muted disabled:opacity-30"
          >
            ↓
          </button>
        </div>
      </div>

      <div className="mt-1 flex flex-wrap items-center gap-3 pl-6">
        <button
          type="button"
          onClick={() => setScheduling((v) => !v)}
          className="text-xs text-ink-muted underline"
        >
          {scheduled
            ? `Видна ${toInputTime(category.available_from) || "с начала дня"}–${
                toInputTime(category.available_to) || "до конца дня"
              }`
            : "Часы показа"}
        </button>
        <button
          type="button"
          onClick={() => setRenaming(true)}
          className="text-xs text-ink-muted underline"
        >
          Переименовать
        </button>
        <button
          type="button"
          onClick={() => {
            if (confirm(`Убрать категорию «${category.name}» с блюдами?`)) {
              onRun(() =>
                adminMutate(`/admin/categories/${category.id}`, {
                  method: "DELETE",
                }),
              );
            }
          }}
          className="text-xs text-ink-faint underline"
        >
          Убрать
        </button>
      </div>

      {scheduling && (
        <ScheduleForm
          category={category}
          onClose={() => setScheduling(false)}
          onRun={onRun}
        />
      )}
    </>
  );
}

/** Часы показа категории: бизнес-ланч с 12 до 16, завтраки до 11. */
function ScheduleForm({
  category,
  onClose,
  onRun,
}: {
  category: AdminCategory;
  onClose: () => void;
  onRun: Run;
}) {
  const [from, setFrom] = useState(toInputTime(category.available_from));
  const [to, setTo] = useState(toInputTime(category.available_to));

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onRun(() =>
          adminMutate(`/admin/categories/${category.id}`, {
            method: "PATCH",
            body: JSON.stringify({
              available_from: from || null,
              available_to: to || null,
              // оба поля пустые — это «показывать всегда», а не «не трогать»
              clear_schedule: from === "" && to === "",
            }),
          }),
        );
        onClose();
      }}
      className="mt-2 rounded-2xl border border-line bg-raised p-3"
    >
      <p className="text-xs text-ink-muted">
        Гость видит категорию только в эти часы по времени заведения. Оставьте
        пустыми, чтобы показывать всегда.
      </p>
      <div className="mt-2 flex items-center gap-2">
        <input
          type="time"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          aria-label="Показывать с"
          className="h-11 flex-1 rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
        />
        <span className="text-ink-faint">—</span>
        <input
          type="time"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          aria-label="Показывать до"
          className="h-11 flex-1 rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
        />
      </div>
      <div className="mt-2 flex gap-2">
        <button
          type="submit"
          className="h-11 flex-1 rounded-xl bg-accent font-semibold text-on-accent"
        >
          Сохранить
        </button>
        <button
          type="button"
          onClick={() => {
            setFrom("");
            setTo("");
          }}
          className="h-11 rounded-xl bg-muted px-4 text-ink-muted"
        >
          Всегда
        </button>
        <button
          type="button"
          onClick={onClose}
          className="h-11 rounded-xl bg-muted px-4 text-ink-muted"
        >
          Отмена
        </button>
      </div>
    </form>
  );
}

function DishCard({
  dish,
  categoryId,
  categories,
  first,
  last,
  onRun,
}: {
  dish: AdminDish;
  categoryId: number;
  categories: { id: number; name: string }[];
  first: boolean;
  last: boolean;
  onRun: Run;
}) {
  const [price, setPrice] = useState(String(dish.price));
  const [editing, setEditing] = useState(false);

  function savePrice() {
    const value = Number(price);
    if (!Number.isInteger(value) || value <= 0 || value === dish.price) {
      setPrice(String(dish.price));
      return;
    }
    onRun(() =>
      adminMutate(`/admin/dishes/${dish.id}`, {
        method: "PATCH",
        body: JSON.stringify({ price: value }),
      }),
    );
  }

  if (editing) {
    return (
      <li>
        <DishForm
          submitLabel="Сохранить"
          initial={dish}
          categories={categories}
          categoryId={categoryId}
          onCancel={() => setEditing(false)}
          onSubmit={async (values) => {
            await onRun(() =>
              adminMutate(`/admin/dishes/${dish.id}`, {
                method: "PATCH",
                body: JSON.stringify(values),
              }),
            );
            setEditing(false);
          }}
        />
      </li>
    );
  }

  const cost = foodCost(dish.price, dish.cost_price);

  return (
    <li
      className={`rounded-2xl bg-raised p-3 shadow-sm ${
        dish.is_active ? "" : "opacity-60"
      }`}
    >
      <div className="flex items-start gap-3">
        <PhotoSlot dish={dish} onRun={onRun} />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-ink">{dish.name}</p>
          {dish.description && (
            <p className="mt-0.5 line-clamp-2 text-xs text-ink-faint">
              {dish.description}
            </p>
          )}
          <div className="mt-1 flex flex-wrap gap-1">
            {TAGS.filter((tag) => dish[tag.key]).map((tag) => (
              <span
                key={tag.key}
                className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-ink-muted"
              >
                {tag.label}
              </span>
            ))}
            {dish.allergens && (
              <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-700 dark:text-amber-300">
                ⚠️ {dish.allergens}
              </span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <div className="flex items-center gap-1">
            <input
              value={price}
              onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))}
              onBlur={savePrice}
              inputMode="numeric"
              aria-label={`Цена «${dish.name}»`}
              className="h-9 w-20 rounded-xl border border-line bg-surface px-2 text-right text-[15px] tabular-nums text-ink focus:border-accent focus:outline-none"
            />
            <span className="text-sm text-ink-faint">₸</span>
          </div>
          {cost !== null && (
            <span
              className={`text-[11px] tabular-nums ${
                cost > 40 ? "text-danger" : "text-ink-faint"
              }`}
            >
              себест. {cost}%
            </span>
          )}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() =>
            onRun(() =>
              adminMutate(`/admin/dishes/${dish.id}`, {
                method: "PATCH",
                body: JSON.stringify({ is_active: !dish.is_active }),
              }),
            )
          }
          className={`h-9 rounded-full px-3 text-sm transition ${
            dish.is_active
              ? "bg-muted text-ink-muted"
              : "bg-danger text-white"
          }`}
        >
          {dish.is_active ? "В продаже" : "Нет в наличии"}
        </button>

        <div className="flex h-9 items-center gap-1 rounded-full border border-line px-1">
          <button
            type="button"
            disabled={first}
            aria-label="Выше"
            onClick={() =>
              onRun(() =>
                adminMutate(`/admin/dishes/${dish.id}/move?direction=up`, {
                  method: "POST",
                }),
              )
            }
            className="flex h-7 w-7 items-center justify-center rounded-full text-ink-muted disabled:opacity-30"
          >
            ↑
          </button>
          <button
            type="button"
            disabled={last}
            aria-label="Ниже"
            onClick={() =>
              onRun(() =>
                adminMutate(`/admin/dishes/${dish.id}/move?direction=down`, {
                  method: "POST",
                }),
              )
            }
            className="flex h-7 w-7 items-center justify-center rounded-full text-ink-muted disabled:opacity-30"
          >
            ↓
          </button>
        </div>

        <button
          type="button"
          onClick={() => setEditing(true)}
          className="h-9 rounded-full bg-muted px-3 text-sm text-ink"
        >
          Изменить
        </button>

        <button
          type="button"
          onClick={() => {
            if (confirm(`Удалить «${dish.name}» из меню?`)) {
              onRun(() =>
                adminMutate(`/admin/dishes/${dish.id}`, { method: "DELETE" }),
              );
            }
          }}
          className="ml-auto h-9 rounded-full px-3 text-sm text-ink-faint"
        >
          Удалить
        </button>
      </div>
    </li>
  );
}

/** Фото блюда: тап по квадрату открывает камеру или галерею телефона. */
function PhotoSlot({ dish, onRun }: { dish: AdminDish; onRun: Run }) {
  const [busy, setBusy] = useState(false);

  async function upload(file: File) {
    setBusy(true);
    const form = new FormData();
    form.append("file", file);
    // FormData сама проставит Content-Type с границей — вручную нельзя
    await onRun(() =>
      adminMutate(`/admin/dishes/${dish.id}/photo`, {
        method: "POST",
        body: form,
      }),
    );
    setBusy(false);
  }

  return (
    <div className="shrink-0">
      <label
        className="relative flex h-16 w-16 cursor-pointer items-center justify-center overflow-hidden rounded-xl bg-muted"
        aria-label={`Фото «${dish.name}»`}
      >
        {dish.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={dish.image_url}
            alt=""
            className="h-full w-full object-cover"
          />
        ) : (
          <span className="text-center text-[10px] leading-tight text-ink-faint">
            Добавить
            <br />
            фото
          </span>
        )}
        {busy && (
          <span className="absolute inset-0 grid place-items-center bg-surface/80 text-[10px] text-ink-muted">
            …
          </span>
        )}
        <input
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) upload(file);
            e.target.value = "";
          }}
        />
      </label>

      {dish.image_url && (
        <button
          type="button"
          onClick={() =>
            onRun(() =>
              adminMutate(`/admin/dishes/${dish.id}/photo`, {
                method: "DELETE",
              }),
            )
          }
          className="mt-1 w-16 text-center text-[11px] text-ink-faint underline"
        >
          Убрать фото
        </button>
      )}
    </div>
  );
}

/** Одна форма и для нового блюда, и для правки существующего — чтобы набор
 *  полей в этих двух местах не разъезжался. */
function DishForm({
  submitLabel,
  initial,
  categories,
  categoryId,
  onSubmit,
  onCancel,
}: {
  submitLabel: string;
  initial?: AdminDish;
  categories?: { id: number; name: string }[];
  categoryId?: number;
  onSubmit: (values: DishValues) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [nameKk, setNameKk] = useState(initial?.name_kk ?? "");
  const [descriptionKk, setDescriptionKk] = useState(
    initial?.description_kk ?? "",
  );
  const [price, setPrice] = useState(initial ? String(initial.price) : "");
  const [cost, setCost] = useState(
    initial?.cost_price != null ? String(initial.cost_price) : "",
  );
  const [description, setDescription] = useState(initial?.description ?? "");
  const [allergens, setAllergens] = useState(initial?.allergens ?? "");
  const [category, setCategory] = useState(String(categoryId ?? ""));
  const [tags, setTags] = useState({
    is_veg: initial?.is_veg ?? false,
    is_spicy: initial?.is_spicy ?? false,
    is_hit: initial?.is_hit ?? false,
    is_chef: initial?.is_chef ?? false,
  });

  const share = foodCost(Number(price), cost === "" ? null : Number(cost));

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({
          name: name.trim(),
          name_kk: nameKk.trim() || null,
          description_kk: descriptionKk.trim() || null,
          price: Number(price),
          cost_price: cost === "" ? null : Number(cost),
          description: description.trim() || null,
          allergens: allergens.trim() || null,
          ...tags,
          // категорию шлём только когда её реально можно было выбрать
          ...(categories ? { category_id: Number(category) } : {}),
        });
      }}
      className="mt-2 space-y-2 rounded-2xl border border-line bg-raised p-3"
    >
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Название"
        aria-label="Название блюда"
        required
        className="h-11 w-full rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
      />

      <div className="flex gap-2">
        <input
          value={price}
          onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))}
          placeholder="Цена, ₸"
          aria-label="Цена"
          inputMode="numeric"
          required
          className="h-11 flex-1 rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
        />
        <input
          value={cost}
          onChange={(e) => setCost(e.target.value.replace(/\D/g, ""))}
          placeholder="Себестоимость"
          aria-label="Себестоимость"
          inputMode="numeric"
          className="h-11 flex-1 rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
        />
      </div>
      {share !== null && (
        <p
          className={`text-xs ${share > 40 ? "text-danger" : "text-ink-faint"}`}
        >
          Себестоимость {share}% от цены
          {share > 40 && " — блюдо почти не зарабатывает"}
        </p>
      )}

      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value.slice(0, 500))}
        placeholder="Состав или пара слов о блюде"
        aria-label="Описание"
        rows={2}
        className="w-full resize-none rounded-xl border border-line bg-surface px-3 py-2 text-[15px] text-ink focus:border-accent focus:outline-none"
      />

      {/* Казахские версии необязательны: меню переводят постепенно, и блюдо
          без перевода остаётся видимым с русским названием */}
      <input
        value={nameKk}
        onChange={(e) => setNameKk(e.target.value)}
        placeholder="Атауы қазақша (необязательно)"
        aria-label="Название по-казахски"
        className="h-11 w-full rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
      />
      <textarea
        value={descriptionKk}
        onChange={(e) => setDescriptionKk(e.target.value.slice(0, 500))}
        placeholder="Сипаттамасы қазақша (необязательно)"
        aria-label="Описание по-казахски"
        rows={2}
        className="w-full resize-none rounded-xl border border-line bg-surface px-3 py-2 text-[15px] text-ink focus:border-accent focus:outline-none"
      />

      <input
        value={allergens}
        onChange={(e) => setAllergens(e.target.value.slice(0, 300))}
        placeholder="Аллергены: орехи, молоко, глютен"
        aria-label="Аллергены"
        className="h-11 w-full rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
      />

      <div className="flex flex-wrap gap-2">
        {TAGS.map((tag) => (
          <button
            key={tag.key}
            type="button"
            aria-pressed={tags[tag.key]}
            onClick={() => setTags((t) => ({ ...t, [tag.key]: !t[tag.key] }))}
            className={`h-9 rounded-full px-3 text-sm transition ${
              tags[tag.key]
                ? "bg-ink text-surface dark:bg-muted dark:text-ink"
                : "bg-muted text-ink-muted"
            }`}
          >
            {tag.label}
          </button>
        ))}
      </div>

      {categories && (
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          aria-label="Категория"
          className="h-11 w-full rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
        >
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      )}

      <div className="flex gap-2">
        <button
          type="submit"
          className="h-11 flex-1 rounded-xl bg-accent font-semibold text-on-accent"
        >
          {submitLabel}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="h-11 rounded-xl bg-muted px-4 text-ink-muted"
        >
          Отмена
        </button>
      </div>
    </form>
  );
}

function CategoryForm({
  onSubmit,
  onCancel,
}: {
  onSubmit: (name: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(name.trim());
      }}
      className="flex gap-2"
    >
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Название категории"
        required
        className="h-12 flex-1 rounded-2xl border border-line bg-raised px-4 text-[15px] text-ink focus:border-accent focus:outline-none"
      />
      <button
        type="submit"
        className="h-12 rounded-2xl bg-accent px-5 font-semibold text-on-accent"
      >
        Создать
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="h-12 rounded-2xl bg-muted px-4 text-ink-muted"
      >
        Отмена
      </button>
    </form>
  );
}
