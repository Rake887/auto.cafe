"use client";

import { useState } from "react";

interface ImportRow {
  line: number;
  category: string;
  name: string;
  price: number;
  action: string;
}

interface ImportReport {
  applied: boolean;
  to_create: number;
  to_update: number;
  new_categories: string[];
  errors: string[];
  preview: ImportRow[];
}

/** Заливка меню таблицей: сначала разбор с отчётом, потом применение.
 *  Без предпросмотра одна кривая колонка молча переписала бы всё меню. */
export function MenuImport({ onDone }: { onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(dryRun: boolean) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`/api/admin/menu/import?dry_run=${dryRun}`, {
        method: "POST",
        body: form,
      });
      const body = await res.json();
      if (!res.ok) {
        setError(body.detail ?? "Не удалось разобрать файл");
        setReport(null);
      } else {
        setReport(body);
        if (!dryRun) {
          await fetch("/revalidate", { method: "POST" }).catch(() => {});
          onDone();
        }
      }
    } catch {
      setError("Нет связи с сервером");
    }
    setBusy(false);
  }

  return (
    <section className="rounded-2xl border border-line bg-raised p-4">
      <h2 className="font-bold text-ink">Загрузить меню таблицей</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Файл CSV с колонками: категория, название, цена, описание. Подойдёт
        выгрузка из Excel — точку с запятой и кодировку разберём сами.
      </p>
      <a
        href="/api/admin/menu/import/template"
        className="mt-2 inline-block text-sm text-accent underline"
      >
        Скачать шаблон
      </a>

      <input
        type="file"
        accept=".csv,text/csv"
        onChange={(e) => {
          setFile(e.target.files?.[0] ?? null);
          setReport(null);
        }}
        className="mt-3 block w-full text-sm text-ink-muted file:mr-3 file:rounded-full file:border-0 file:bg-muted file:px-4 file:py-2 file:text-sm file:text-ink"
      />

      {error !== null && (
        <p className="mt-3 rounded-xl bg-muted px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {file && report === null && (
        <button
          type="button"
          onClick={() => send(true)}
          disabled={busy}
          className="mt-3 h-11 w-full rounded-2xl bg-muted font-medium text-ink disabled:opacity-60"
        >
          {busy ? "Разбираем…" : "Проверить файл"}
        </button>
      )}

      {report !== null && (
        <div className="mt-3 space-y-2">
          <p className="text-sm text-ink">
            {report.applied ? "Загружено: " : "Будет добавлено: "}
            <b>{report.to_create}</b>, обновлено <b>{report.to_update}</b>
            {report.new_categories.length > 0 && (
              <>
                {" "}
                · новые категории: {report.new_categories.join(", ")}
              </>
            )}
          </p>

          {report.errors.length > 0 && (
            <div className="rounded-xl bg-muted px-3 py-2 text-sm text-danger">
              <p className="font-medium">Строки с ошибками пропущены:</p>
              <ul className="mt-1 list-disc pl-4">
                {report.errors.slice(0, 5).map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            </div>
          )}

          {!report.applied && report.preview.length > 0 && (
            <>
              <ul className="max-h-48 overflow-y-auto rounded-xl bg-surface p-3 text-sm">
                {report.preview.map((row) => (
                  <li key={row.line} className="flex justify-between gap-3 py-0.5">
                    <span className="min-w-0 truncate text-ink">
                      {row.category} · {row.name}
                    </span>
                    <span className="shrink-0 text-ink-faint tabular-nums">
                      {row.price} ·{" "}
                      {row.action === "create" ? "новое" : "обновится"}
                    </span>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                onClick={() => send(false)}
                disabled={busy}
                className="h-11 w-full rounded-2xl bg-accent font-semibold text-on-accent disabled:opacity-60"
              >
                {busy ? "Загружаем…" : "Загрузить в меню"}
              </button>
            </>
          )}
        </div>
      )}
    </section>
  );
}
