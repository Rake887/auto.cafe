"use client";

import { useState } from "react";
import { adminMutate } from "@/lib/api";
import { useAdminAction } from "@/lib/use-admin-action";
import type { AdminStaff, StaffInvite, StaffRole } from "@/lib/types";

const ROLES: { key: StaffRole; label: string }[] = [
  { key: "cook", label: "Повар" },
  { key: "waiter", label: "Официант" },
];

function roleLabel(role: StaffRole): string {
  return ROLES.find((r) => r.key === role)?.label ?? role;
}

export function StaffManager({ staff }: { staff: AdminStaff[] }) {
  const { error, busy, run } = useAdminAction();
  const [adding, setAdding] = useState(false);
  /** Свежая ссылка приглашения: показываем её один раз крупно, чтобы владелец
   *  успел переслать её сотруднику, не выискивая в списке. */
  const [fresh, setFresh] = useState<StaffInvite | null>(null);

  const working = staff.filter((s) => s.is_active);
  const dismissed = staff.filter((s) => !s.is_active);

  async function invite(full_name: string, role: StaffRole) {
    const ok = await run(async () => {
      const created = await adminMutate<StaffInvite>("/admin/staff", {
        method: "POST",
        body: JSON.stringify({ full_name, role }),
      });
      setFresh(created);
    });
    if (ok) setAdding(false);
  }

  return (
    <div className="mt-6 space-y-4">
      {error !== null && (
        <p className="rounded-xl bg-muted px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {fresh !== null && (
        <InviteBanner invite={fresh} onClose={() => setFresh(null)} />
      )}

      {working.length === 0 && (
        <p className="rounded-2xl bg-muted px-4 py-3 text-sm text-ink-muted">
          Пока никого нет. Пригласите повара — без него никто не увидит заказы
          в чате.
        </p>
      )}

      <ul className="space-y-2">
        {working.map((person) => (
          <StaffCard key={person.id} person={person} busy={busy} onRun={run} />
        ))}
      </ul>

      {adding ? (
        <InviteForm onCancel={() => setAdding(false)} onSubmit={invite} />
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="flex h-12 w-full items-center justify-center rounded-2xl bg-accent font-semibold text-on-accent"
        >
          Пригласить сотрудника
        </button>
      )}

      {dismissed.length > 0 && (
        <section className="pt-2">
          <h2 className="text-sm font-bold text-ink-muted">Уволенные</h2>
          <p className="mt-1 text-xs text-ink-faint">
            Их имена остаются в статистике за прошлые смены, а кнопки в боте им
            больше не приходят.
          </p>
          <ul className="mt-2 space-y-2">
            {dismissed.map((person) => (
              <StaffCard
                key={person.id}
                person={person}
                busy={busy}
                onRun={run}
              />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/** Ссылка приглашения крупно и с копированием — её нужно переслать человеку. */
function InviteBanner({
  invite,
  onClose,
}: {
  invite: StaffInvite;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  if (invite.deep_link === null) {
    return (
      <div className="rounded-2xl border border-line bg-raised p-4">
        <p className="text-sm text-ink">
          Сотрудник заведён, но бот выключен — ссылку выдать не из чего. Задайте
          <code className="mx-1 text-xs">BOT_TOKEN</code>и нажмите «Новая
          ссылка».
        </p>
        <button
          type="button"
          onClick={onClose}
          className="mt-3 h-10 rounded-xl bg-muted px-4 text-sm text-ink-muted"
        >
          Понятно
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-accent/40 bg-accent/10 p-4">
      <p className="font-medium text-ink">Ссылка для сотрудника</p>
      <p className="mt-2 rounded-xl bg-surface px-3 py-2 text-xs break-all text-ink-muted">
        {invite.deep_link}
      </p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(invite.deep_link ?? "");
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            } catch {
              // буфер недоступен (не https) — ссылку видно и можно выделить
            }
          }}
          className="h-11 flex-1 rounded-xl bg-accent font-semibold text-on-accent"
        >
          {copied ? "Скопировано" : "Скопировать"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="h-11 rounded-xl bg-muted px-4 text-ink-muted"
        >
          Закрыть
        </button>
      </div>
    </div>
  );
}

function StaffCard({
  person,
  busy,
  onRun,
}: {
  person: AdminStaff;
  busy: boolean;
  onRun: (action: () => Promise<unknown>) => Promise<boolean>;
}) {
  const [name, setName] = useState(person.full_name);

  function saveName() {
    const value = name.trim();
    if (value === "" || value === person.full_name) {
      setName(person.full_name);
      return;
    }
    onRun(() =>
      adminMutate(`/admin/staff/${person.id}`, {
        method: "PATCH",
        body: JSON.stringify({ full_name: value }),
      }),
    );
  }

  return (
    <li
      className={`rounded-2xl bg-raised p-3 shadow-sm ${
        person.is_active ? "" : "opacity-60"
      }`}
    >
      <div className="flex items-center gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={saveName}
          aria-label={`Имя сотрудника ${person.full_name}`}
          className="h-10 min-w-0 flex-1 rounded-xl border border-transparent bg-transparent px-2 font-medium text-ink focus:border-line focus:bg-surface focus:outline-none"
        />
        <StatusBadge person={person} />
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <div className="flex h-9 items-center rounded-full border border-line p-1">
          {ROLES.map((role) => (
            <button
              key={role.key}
              type="button"
              disabled={busy || role.key === person.role}
              onClick={() =>
                onRun(() =>
                  adminMutate(`/admin/staff/${person.id}`, {
                    method: "PATCH",
                    body: JSON.stringify({ role: role.key }),
                  }),
                )
              }
              className={`h-7 rounded-full px-3 text-sm ${
                role.key === person.role
                  ? "bg-ink text-surface dark:bg-muted dark:text-ink"
                  : "text-ink-muted"
              }`}
            >
              {role.label}
            </button>
          ))}
        </div>

        <button
          type="button"
          disabled={busy}
          onClick={() => {
            if (
              !person.is_connected ||
              confirm(
                `Выдать ${person.full_name} новую ссылку? Прежняя привязка к Telegram сбросится.`,
              )
            ) {
              onRun(() =>
                adminMutate(`/admin/staff/${person.id}/reinvite`, {
                  method: "POST",
                }),
              );
            }
          }}
          className="h-9 rounded-full bg-muted px-3 text-sm text-ink"
        >
          Новая ссылка
        </button>

        {person.is_active ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              if (
                confirm(
                  `Уволить ${person.full_name}? Ссылка перестанет работать, но кнопки заказов приходят всем в чате заведения — удалите человека и из группы.`,
                )
              ) {
                onRun(() =>
                  adminMutate(`/admin/staff/${person.id}`, {
                    method: "DELETE",
                  }),
                );
              }
            }}
            className="ml-auto h-9 rounded-full px-3 text-sm text-ink-faint"
          >
            Уволить
          </button>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              onRun(() =>
                adminMutate(`/admin/staff/${person.id}`, {
                  method: "PATCH",
                  body: JSON.stringify({ is_active: true }),
                }),
              )
            }
            className="ml-auto h-9 rounded-full px-3 text-sm text-accent"
          >
            Вернуть
          </button>
        )}
      </div>

      {person.is_active && person.deep_link !== null && (
        <p className="mt-2 rounded-xl bg-muted px-3 py-2 text-[11px] break-all text-ink-faint">
          {person.deep_link}
        </p>
      )}
    </li>
  );
}

function StatusBadge({ person }: { person: AdminStaff }) {
  const [text, className] = !person.is_active
    ? ["уволен", "bg-muted text-ink-faint"]
    : person.is_connected
      ? ["в работе", "bg-accent/15 text-accent"]
      : ["ждёт активации", "bg-muted text-ink-muted"];

  return (
    <span
      className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${className}`}
    >
      {text} · {roleLabel(person.role)}
    </span>
  );
}

function InviteForm({
  onSubmit,
  onCancel,
}: {
  onSubmit: (fullName: string, role: StaffRole) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [role, setRole] = useState<StaffRole>("cook");

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(name.trim(), role);
      }}
      className="space-y-2 rounded-2xl border border-line bg-raised p-3"
    >
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Имя и фамилия"
        aria-label="Имя сотрудника"
        required
        className="h-11 w-full rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
      />
      <div className="flex h-11 items-center rounded-xl border border-line bg-surface p-1">
        {ROLES.map((r) => (
          <button
            key={r.key}
            type="button"
            onClick={() => setRole(r.key)}
            className={`h-9 flex-1 rounded-lg text-sm font-medium ${
              r.key === role
                ? "bg-ink text-surface dark:bg-muted dark:text-ink"
                : "text-ink-muted"
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>
      <div className="flex gap-2">
        <button
          type="submit"
          className="h-11 flex-1 rounded-xl bg-accent font-semibold text-on-accent"
        >
          Создать ссылку
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
