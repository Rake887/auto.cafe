"use client";

import { useState } from "react";

/** Ссылка на демо-меню с копированием в один тап — чтобы кинуть в мессенджер. */
export function CopyLink({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // буфер недоступен (не https / нет прав) — ссылку видно и можно выделить
    }
  }

  return (
    <div className="mt-4 w-full">
      <p className="rounded-xl bg-muted px-3 py-2 text-xs break-all text-ink-muted">
        {url}
      </p>
      <button
        type="button"
        onClick={copy}
        className="mt-2 h-11 w-full rounded-2xl border border-line bg-raised font-medium text-ink transition active:bg-muted"
      >
        {copied ? "Скопировано" : "Скопировать ссылку"}
      </button>
    </div>
  );
}
