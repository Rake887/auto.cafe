"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { LANGS, rememberLang, type Lang } from "@/lib/i18n";

/** Переключатель языка. Выбор живёт в адресе (чтобы SSR отдал нужную версию)
 *  и в cookie — чтобы следующий стол открылся сразу на выбранном языке. */
export function LangSwitch({ current }: { current: Lang }) {
  const router = useRouter();
  const params = useSearchParams();

  function choose(lang: Lang) {
    rememberLang(lang);
    const next = new URLSearchParams(params.toString());
    next.set("lang", lang);
    router.replace(`?${next.toString()}`);
    router.refresh();
  }

  return (
    <div className="inline-flex h-12 items-center rounded-full bg-muted p-0.5">
      {LANGS.map((lang) => (
        <button
          key={lang}
          type="button"
          onClick={() => choose(lang)}
          aria-pressed={lang === current}
          className={`h-11 rounded-full px-3.5 text-sm transition ${
            lang === current
              ? "bg-raised font-medium text-ink shadow-sm"
              : "text-ink-muted"
          }`}
        >
          {lang === "ru" ? "Рус" : "Қаз"}
        </button>
      ))}
    </div>
  );
}
