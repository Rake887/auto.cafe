"use client";

import Link from "next/link";
import { useState } from "react";
import { adminMutate } from "@/lib/api";
import { useAdminAction } from "@/lib/use-admin-action";
import type { PointOut, Zone } from "@/lib/types";

type Run = (action: () => Promise<unknown>) => Promise<boolean>;

export function TablesManager({
  zones,
  points,
}: {
  zones: Zone[];
  points: PointOut[];
}) {
  const { error, busy, run } = useAdminAction();
  const [addingTo, setAddingTo] = useState<number | null>(null);
  const [label, setLabel] = useState("");
  const [newZone, setNewZone] = useState(false);
  const [zoneName, setZoneName] = useState("");

  async function createPoint(zoneId: number) {
    const value = label.trim();
    if (value === "") return;
    const ok = await run(() =>
      adminMutate("/admin/points", {
        method: "POST",
        body: JSON.stringify({ label: value, zone_id: zoneId }),
      }),
    );
    if (ok) {
      setLabel("");
      setAddingTo(null);
    }
  }

  async function createZone() {
    const value = zoneName.trim();
    if (value === "") return;
    const ok = await run(() =>
      adminMutate("/admin/zones", {
        method: "POST",
        body: JSON.stringify({ name: value }),
      }),
    );
    if (ok) {
      setZoneName("");
      setNewZone(false);
    }
  }

  return (
    <div className="mt-6 space-y-6">
      {error !== null && (
        <p className="rounded-xl bg-muted px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {zones.map((zone) => {
        const inZone = points.filter((p) => p.zone_id === zone.id);
        return (
          <section key={zone.id}>
            <ZoneHead
              zone={zone}
              count={inZone.length}
              canDelete={inZone.length === 0 && zones.length > 1}
              busy={busy}
              onRun={run}
            />

            <ul className="mt-2 space-y-2">
              {inZone.map((point) => (
                <TableCard
                  key={point.id}
                  point={point}
                  zones={zones}
                  busy={busy}
                  onRun={run}
                />
              ))}
            </ul>

            {addingTo === zone.id ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  createPoint(zone.id);
                }}
                className="mt-2 flex gap-2"
              >
                <input
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder="Например, «Стол 7»"
                  aria-label="Название стола"
                  required
                  autoFocus
                  className="h-11 flex-1 rounded-xl border border-line bg-raised px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={busy}
                  className="h-11 rounded-xl bg-accent px-4 font-semibold text-on-accent disabled:opacity-60"
                >
                  Создать
                </button>
                <button
                  type="button"
                  onClick={() => setAddingTo(null)}
                  className="h-11 rounded-xl bg-muted px-3 text-ink-muted"
                >
                  Отмена
                </button>
              </form>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setLabel("");
                  setAddingTo(zone.id);
                }}
                className="mt-2 flex h-11 w-full items-center justify-center rounded-2xl border border-dashed border-line text-sm text-ink-muted"
              >
                + Стол в «{zone.name}»
              </button>
            )}
          </section>
        );
      })}

      {newZone ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createZone();
          }}
          className="flex gap-2"
        >
          <input
            value={zoneName}
            onChange={(e) => setZoneName(e.target.value)}
            placeholder="Например, «Терраса» или «VIP»"
            aria-label="Название зоны"
            required
            autoFocus
            className="h-12 flex-1 rounded-2xl border border-line bg-raised px-4 text-[15px] text-ink focus:border-accent focus:outline-none"
          />
          <button
            type="submit"
            disabled={busy}
            className="h-12 rounded-2xl bg-accent px-5 font-semibold text-on-accent disabled:opacity-60"
          >
            Создать
          </button>
          <button
            type="button"
            onClick={() => setNewZone(false)}
            className="h-12 rounded-2xl bg-muted px-4 text-ink-muted"
          >
            Отмена
          </button>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => setNewZone(true)}
          className="flex h-12 w-full items-center justify-center rounded-2xl border border-line bg-raised font-medium text-ink"
        >
          Добавить зону
        </button>
      )}

      <Link
        href="/admin/qr"
        className="flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-accent font-semibold text-on-accent"
      >
        🖨️ Напечатать наклейки
      </Link>
    </div>
  );
}

/** Заголовок зоны: переименование и удаление пустой зоны. */
function ZoneHead({
  zone,
  count,
  canDelete,
  busy,
  onRun,
}: {
  zone: Zone;
  count: number;
  canDelete: boolean;
  busy: boolean;
  onRun: Run;
}) {
  const [name, setName] = useState(zone.name);

  function saveName() {
    const value = name.trim();
    if (value === "" || value === zone.name) {
      setName(zone.name);
      return;
    }
    onRun(() =>
      adminMutate(`/admin/zones/${zone.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name: value }),
      }),
    );
  }

  return (
    <div className="flex items-center gap-2">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        onBlur={saveName}
        aria-label={`Название зоны ${zone.name}`}
        className="h-10 min-w-0 flex-1 rounded-xl border border-transparent bg-transparent px-2 text-lg font-bold text-ink focus:border-line focus:bg-surface focus:outline-none"
      />
      <span className="shrink-0 text-sm text-ink-faint tabular-nums">
        {count}
      </span>
      {canDelete && (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            if (confirm(`Убрать зону «${zone.name}»?`)) {
              onRun(() =>
                adminMutate(`/admin/zones/${zone.id}`, { method: "DELETE" }),
              );
            }
          }}
          className="shrink-0 text-xs text-ink-faint underline"
        >
          Убрать зону
        </button>
      )}
    </div>
  );
}

function TableCard({
  point,
  zones,
  busy,
  onRun,
}: {
  point: PointOut;
  zones: Zone[];
  busy: boolean;
  onRun: Run;
}) {
  const [label, setLabel] = useState(point.label);

  function saveLabel() {
    const value = label.trim();
    if (value === "" || value === point.label) {
      setLabel(point.label);
      return;
    }
    onRun(() =>
      adminMutate(`/admin/points/${point.id}`, {
        method: "PATCH",
        body: JSON.stringify({ label: value }),
      }),
    );
  }

  return (
    <li className="rounded-2xl bg-raised p-3 shadow-sm">
      <input
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        onBlur={saveLabel}
        aria-label={`Название стола ${point.label}`}
        className="h-10 w-full rounded-xl border border-transparent bg-transparent px-2 font-medium text-ink focus:border-line focus:bg-surface focus:outline-none"
      />

      {point.menu_url !== null ? (
        <p className="mt-1 px-2 text-[11px] break-all text-ink-faint">
          {point.menu_url}
        </p>
      ) : (
        <p className="mt-1 px-2 text-[11px] text-ink-faint">
          Публичный адрес не поднят — ссылку показать не из чего.
        </p>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        {zones.length > 1 && (
          <select
            value={point.zone_id}
            disabled={busy}
            aria-label={`Зона стола ${point.label}`}
            onChange={(e) =>
              onRun(() =>
                adminMutate(`/admin/points/${point.id}`, {
                  method: "PATCH",
                  body: JSON.stringify({ zone_id: Number(e.target.value) }),
                }),
              )
            }
            className="h-9 rounded-full border border-line bg-surface px-3 text-sm text-ink"
          >
            {zones.map((z) => (
              <option key={z.id} value={z.id}>
                {z.name}
              </option>
            ))}
          </select>
        )}

        <button
          type="button"
          disabled={busy}
          onClick={() => {
            if (
              confirm(
                `Перевыпустить QR для «${point.label}»? Старая наклейка перестанет работать — её придётся перепечатать.`,
              )
            ) {
              onRun(() =>
                adminMutate(`/admin/points/${point.id}/rotate`, {
                  method: "POST",
                }),
              );
            }
          }}
          className="h-9 rounded-full bg-muted px-3 text-sm text-ink"
        >
          Перевыпустить QR
        </button>

        <button
          type="button"
          disabled={busy}
          onClick={() => {
            if (
              confirm(
                `Убрать «${point.label}»? Гости по его QR больше не попадут в меню, а прошлые заказы останутся в статистике.`,
              )
            ) {
              onRun(() =>
                adminMutate(`/admin/points/${point.id}`, { method: "DELETE" }),
              );
            }
          }}
          className="ml-auto h-9 rounded-full px-3 text-sm text-ink-faint"
        >
          Убрать стол
        </button>
      </div>
    </li>
  );
}
