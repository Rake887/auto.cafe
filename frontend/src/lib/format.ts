/** Цена в карточке меню: 2500 -> «2 500», без символа валюты.
 *
 *  Меню без явной отсылки к деньгам даёт больший средний чек (Cornell, 2007:
 *  +8,15 % на человека). Чтобы цифры не были двусмысленными, валюта названа
 *  один раз в шапке меню. В корзине и на экране заказа символ остаётся: там
 *  гость уже принял решение и сумма должна читаться однозначно.
 */
export function formatMenuPrice(value: number): string {
  return value.toLocaleString("ru-RU");
}

/** Цена в тенге: 2500 -> «2 500 ₸» */
export function formatPrice(value: number): string {
  return `${value.toLocaleString("ru-RU")} ₸`;
}

/** Русская плюрализация: plural(2, "блюдо", "блюда", "блюд") -> «блюда» */
export function plural(n: number, one: string, few: string, many: string): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return many;
  const mod10 = n % 10;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return few;
  return many;
}

/** «только что», «3 мин», «1 ч 20 мин» — сколько прошло с момента заказа */
export function formatElapsed(fromIso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.floor((now - Date.parse(fromIso)) / 1000));
  if (seconds < 60) return "только что";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} ${plural(minutes, "минута", "минуты", "минут")}`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} ч` : `${hours} ч ${rest} мин`;
}
