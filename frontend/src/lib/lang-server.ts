import { cookies } from "next/headers";
import { DEFAULT_LANG, LANG_COOKIE, isLang, type Lang } from "./i18n";

/** Язык страницы: сначала из адреса, затем из cookie, иначе русский.
 *
 * Параметр в адресе важен для SSR-кэша: у разных языков разные ключи, и
 * казахская версия не подменит русскую в кэше.
 */
export async function resolveLang(
  searchParams: { [key: string]: string | string[] | undefined },
): Promise<Lang> {
  const fromUrl = searchParams.lang;
  if (isLang(fromUrl)) return fromUrl;

  const store = await cookies();
  const fromCookie = store.get(LANG_COOKIE)?.value;
  return isLang(fromCookie) ? fromCookie : DEFAULT_LANG;
}
