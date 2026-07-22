import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export const SESSION_COOKIE = "qrmenu_admin";

/** Токен сессии владельца из cookie. В этой версии Next `cookies()` асинхронна. */
export async function getSession(): Promise<string | null> {
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value ?? null;
}

/** То же, но без сессии сразу уводит на страницу входа. */
export async function requireSession(): Promise<string> {
  const session = await getSession();
  if (session === null) redirect("/admin/login");
  return session;
}
