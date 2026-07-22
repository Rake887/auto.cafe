import { MenuScreen } from "@/components/MenuScreen";
import { fetchMenu } from "@/lib/api";
import { ApiError } from "@/lib/api-error";
import { t } from "@/lib/i18n";
import { resolveLang } from "@/lib/lang-server";
import type { MenuResponse } from "@/lib/types";

// Меню рендерится на сервере: гость на мобильном интернете видит контент
// сразу, без ожидания клиентского запроса за данными.
export default async function MenuPage({
  params,
  searchParams,
}: {
  params: Promise<{ token: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { token } = await params;
  const lang = await resolveLang(await searchParams);

  let menu: MenuResponse | null = null;
  let failure: "not-found" | "unavailable" | null = null;
  try {
    menu = await fetchMenu(token, lang);
  } catch (e) {
    failure = e instanceof ApiError && e.status === 404 ? "not-found" : "unavailable";
  }

  if (menu === null) {
    return (
      <main className="flex min-h-dvh flex-col items-center justify-center bg-surface px-8 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted text-accent">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden className="h-8 w-8">
            <path
              d="M12 8v5m0 3.5h.01M12 3l9 16H3l9-16z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <h1 className="mt-5 text-xl font-bold text-ink">
          {t(lang, failure === "not-found" ? "menuNotFound" : "menuUnavailable")}
        </h1>
        <p className="mt-2 max-w-xs text-ink-muted">
          {t(
            lang,
            failure === "not-found" ? "menuNotFoundHint" : "menuUnavailableHint",
          )}
        </p>
        {failure === "unavailable" && (
          <a
            href={`/m/${token}`}
            className="mt-6 rounded-2xl bg-accent px-6 py-3 font-semibold text-on-accent"
          >
            {t(lang, "refresh")}
          </a>
        )}
      </main>
    );
  }

  return <MenuScreen menu={menu} token={token} lang={lang} />;
}
