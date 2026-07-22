"use client";

import { useState } from "react";
import { adminMutate } from "@/lib/api";
import { useAdminAction } from "@/lib/use-admin-action";
import type { AdminBranch } from "@/lib/types";

/** Что заведение сообщает гостю: имя в шапке меню, предупреждение об
 *  аллергенах и куда звать за публичным отзывом. */
/** «10:00:00» → «10:00»: input[type=time] длиннее не принимает. */
function toInputTime(value: string | null): string {
  return value === null ? "" : value.slice(0, 5);
}

export function BranchForm({ branch }: { branch: AdminBranch }) {
  const { error, busy, run } = useAdminAction();
  const [name, setName] = useState(branch.name);
  const [disclaimer, setDisclaimer] = useState(branch.menu_disclaimer ?? "");
  const [reviewUrl, setReviewUrl] = useState(branch.review_url ?? "");
  const [opensAt, setOpensAt] = useState(toInputTime(branch.opens_at));
  const [closesAt, setClosesAt] = useState(toInputTime(branch.closes_at));
  const [lat, setLat] = useState(branch.lat === null ? "" : String(branch.lat));
  const [lon, setLon] = useState(branch.lon === null ? "" : String(branch.lon));
  const [radius, setRadius] = useState(
    branch.geo_radius_m === null ? "" : String(branch.geo_radius_m),
  );
  const [trustedIp, setTrustedIp] = useState(branch.trusted_ip ?? "");
  const [saved, setSaved] = useState(false);

  const [ipHint, setIpHint] = useState<string | null>(null);
  const [placeLink, setPlaceLink] = useState("");
  const [geoHint, setGeoHint] = useState<
    { text: string; verify: string | null } | null
  >(null);

  /** Координаты заведения из ссылки на 2ГИС, Яндекс или Google.
   *
   *  Ссылка указывает на само заведение, а не на устройство, с которого
   *  открыт кабинет, — поэтому настраивать можно откуда угодно.
   */
  async function fillFromLink() {
    setGeoHint(null);
    const res = await fetch("/api/admin/branch/place-link", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: placeLink }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      setGeoHint({ text: body.detail ?? "Не удалось разобрать ссылку", verify: null });
      return;
    }
    setLat(String(body.lat));
    setLon(String(body.lon));
    if (radius === "") setRadius("150");
    setGeoHint({
      text: `Определено по ссылке ${body.source}. Проверьте точку на карте — если она не там, порядок чисел в ссылке необычный, впишите координаты руками.`,
      verify: body.verify_url,
    });
  }

  /** Подставить IP, с которого открыт кабинет. Работает только из браузера:
   *  со стороны сервера это был бы адрес контейнера. */
  async function fillCurrentIp() {
    setIpHint(null);
    const res = await fetch("/api/admin/my-ip", { cache: "no-store" });
    if (!res.ok) return;
    const body = await res.json();
    if (body.usable) {
      setTrustedIp(body.ip);
      return;
    }
    // адрес технический — сохранять его нельзя, иначе доверенными станут все
    setIpHint(
      `Определился адрес ${body.ip ?? "неизвестно"} — он внутренний. Так бывает, ` +
        "когда кабинет открыт через туннель или напрямую по localhost. " +
        "Откройте кабинет по настоящему домену заведения и нажмите ещё раз.",
    );
  }

  /** Подставить координаты заведения из браузера — владелец обычно
   *  открывает кабинет, стоя в своём зале. */
  function fillFromBrowser() {
    navigator.geolocation?.getCurrentPosition((p) => {
      setLat(p.coords.latitude.toFixed(6));
      setLon(p.coords.longitude.toFixed(6));
      if (radius === "") setRadius("150");
    });
  }

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setSaved(false);
        const geoFilled = lat !== "" && lon !== "" && radius !== "";
        const ok = await run(() =>
          adminMutate("/admin/branch", {
            method: "PATCH",
            body: JSON.stringify({
              name: name.trim(),
              menu_disclaimer: disclaimer,
              review_url: reviewUrl,
              opens_at: opensAt || null,
              closes_at: closesAt || null,
              // оба пустые — это «круглосуточно», а не «не трогать»
              clear_hours: opensAt === "" && closesAt === "",
              lat: geoFilled ? Number(lat) : null,
              lon: geoFilled ? Number(lon) : null,
              geo_radius_m: geoFilled ? Number(radius) : null,
              clear_geo: !geoFilled,
              trusted_ip: trustedIp.trim(),
            }),
          }),
        );
        setSaved(ok);
      }}
      className="space-y-2 rounded-2xl border border-line bg-raised p-4"
    >
      <h2 className="font-bold text-ink">Заведение</h2>

      <label className="block">
        <span className="text-sm text-ink-muted">Название в шапке меню</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="mt-1 h-11 w-full rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
        />
      </label>

      <label className="block">
        <span className="text-sm text-ink-muted">
          Предупреждение об аллергенах
        </span>
        <textarea
          value={disclaimer}
          onChange={(e) => setDisclaimer(e.target.value.slice(0, 1000))}
          rows={3}
          placeholder="Блюда готовятся на одной кухне: следы орехов, глютена и молока возможны в любой позиции."
          className="mt-1 w-full resize-none rounded-xl border border-line bg-surface px-3 py-2 text-[15px] text-ink focus:border-accent focus:outline-none"
        />
        <span className="text-xs text-ink-faint">
          Выводится внизу меню обычным текстом. Пусто — блок не показывается.
        </span>
      </label>

      <fieldset className="rounded-xl border border-line p-3">
        <legend className="px-1 text-sm text-ink-muted">Часы приёма заказов</legend>
        <div className="flex items-center gap-2">
          <input
            type="time"
            value={opensAt}
            onChange={(e) => setOpensAt(e.target.value)}
            aria-label="Открытие"
            className="h-11 flex-1 rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
          />
          <span className="text-ink-faint">—</span>
          <input
            type="time"
            value={closesAt}
            onChange={(e) => setClosesAt(e.target.value)}
            aria-label="Закрытие"
            className="h-11 flex-1 rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
          />
        </div>
        <p className="mt-2 text-xs text-ink-faint">
          Вне этих часов гость видит «закрыто» и не может оформить заказ. Пусто —
          принимаем круглосуточно. Окно через полночь (22:00—02:00) работает.
        </p>
      </fieldset>

      <fieldset className="rounded-xl border border-line p-3">
        <legend className="px-1 text-sm text-ink-muted">Wi-Fi заведения</legend>
        <div className="flex gap-2">
          <input
            value={trustedIp}
            onChange={(e) => setTrustedIp(e.target.value)}
            placeholder="Публичный IP"
            aria-label="Публичный IP заведения"
            className="h-11 min-w-0 flex-1 rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
          />
          <button
            type="button"
            onClick={fillCurrentIp}
            className="h-11 shrink-0 rounded-xl bg-muted px-4 text-sm text-ink"
          >
            Мой IP
          </button>
        </div>
        {ipHint !== null && (
          <p className="mt-2 rounded-xl bg-muted px-3 py-2 text-xs text-danger">
            {ipHint}
          </p>
        )}
        <p className="mt-2 text-xs text-ink-faint">
          Заказ с этого адреса считается сделанным из зала — гость сидит на
          вашем Wi-Fi. Нажимайте «Мой IP», <b>находясь в заведении и подключившись
          к его сети</b>, иначе запишется адрес вашего дома. Пусто — признак не
          используется.
        </p>
      </fieldset>

      <fieldset className="rounded-xl border border-line p-3">
        <legend className="px-1 text-sm text-ink-muted">Где находится зал</legend>
        <div className="flex gap-2">
          <input
            value={placeLink}
            onChange={(e) => setPlaceLink(e.target.value)}
            placeholder="Ссылка на заведение в 2ГИС"
            aria-label="Ссылка на карточку заведения"
            className="h-11 min-w-0 flex-1 rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
          />
          <button
            type="button"
            onClick={fillFromLink}
            disabled={placeLink.trim() === ""}
            className="h-11 shrink-0 rounded-xl bg-accent px-4 text-sm font-semibold text-on-accent disabled:opacity-50"
          >
            Определить
          </button>
        </div>

        {geoHint !== null && (
          <p className="mt-2 rounded-xl bg-muted px-3 py-2 text-xs text-ink-muted">
            {geoHint.text}
            {geoHint.verify !== null && (
              <>
                {" "}
                <a
                  href={geoHint.verify}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent underline"
                >
                  Открыть на карте
                </a>
              </>
            )}
          </p>
        )}

        <div className="mt-2 flex gap-2">
          <input
            value={lat}
            onChange={(e) => setLat(e.target.value)}
            placeholder="Широта"
            aria-label="Широта"
            inputMode="decimal"
            className="h-11 min-w-0 flex-1 rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
          />
          <input
            value={lon}
            onChange={(e) => setLon(e.target.value)}
            placeholder="Долгота"
            aria-label="Долгота"
            inputMode="decimal"
            className="h-11 min-w-0 flex-1 rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
          />
          <input
            value={radius}
            onChange={(e) => setRadius(e.target.value.replace(/\D/g, ""))}
            placeholder="м"
            aria-label="Радиус в метрах"
            inputMode="numeric"
            className="h-11 w-20 rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
          />
        </div>
        <button
          type="button"
          onClick={fillFromBrowser}
          className="mt-2 h-10 rounded-xl bg-muted px-4 text-sm text-ink"
        >
          Взять с этого устройства
        </button>
        <p className="mt-1 text-xs text-ink-faint">
          Годится, только если вы <b>сейчас в зале и с телефона</b>: у компьютера
          нет GPS, он определяет место по сети и может промахнуться на километры.
          Из дома так настраивать нельзя — сохранятся координаты квартиры.
        </p>
        <p className="mt-2 text-xs text-ink-faint">
          Гость внутри радиуса считается сидящим в зале. Заказ снаружи всё равно
          примем, но пометим «вне зала». Блокировать нельзя: в помещении GPS
          врёт на сотни метров, а часть гостей вообще откажет в доступе — тогда
          за стол ручается официант кнопкой в чате. Пусто — проверка выключена.
        </p>
      </fieldset>

      <label className="block">
        <span className="text-sm text-ink-muted">Ссылка на отзывы</span>
        <input
          value={reviewUrl}
          onChange={(e) => setReviewUrl(e.target.value)}
          type="url"
          placeholder="https://2gis.kz/taraz/firm/..."
          className="mt-1 h-11 w-full rounded-xl border border-line bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none"
        />
        <span className="text-xs text-ink-faint">
          Сюда отправим гостя, который поставил 4–5 звёзд. 2GIS, Google Maps или
          Яндекс Карты.
        </span>
      </label>

      {error !== null && (
        <p className="rounded-xl bg-muted px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      {saved && (
        <p className="rounded-xl bg-muted px-3 py-2 text-sm text-ink-muted">
          Сохранено. Гости увидят изменения сразу.
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="h-11 w-full rounded-xl bg-accent font-semibold text-on-accent disabled:opacity-60"
      >
        {busy ? "Сохраняем…" : "Сохранить"}
      </button>
    </form>
  );
}
