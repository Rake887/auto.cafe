"use client";

import { useState } from "react";
import type { PointOut, Zone } from "@/lib/types";

type Format = "sticker" | "tent";

const FORMATS: { key: Format; label: string; hint: string }[] = [
  {
    key: "sticker",
    label: "Наклейки",
    hint: "Квадраты 65×65 мм. Режьте по пунктиру и ламинируйте: под плёнкой код переживает уборку, его труднее незаметно подменить чужим.",
  },
  {
    key: "tent",
    label: "Тейбл-тенты",
    hint: "Две палатки на лист. Согните по пунктиру — код будет виден с обеих сторон стола. Плотная бумага держит форму лучше офисной.",
  },
];

/** Печать QR: наклейка и подставка — разные физические вещи, поэтому и
 *  вёрстка у них разная, а не одна «сетка на глаз». */
export function QrSheet({
  zones,
  points,
  host,
}: {
  zones: Zone[];
  points: PointOut[];
  host: string | null;
}) {
  const [format, setFormat] = useState<Format>("sticker");
  const active = FORMATS.find((f) => f.key === format)!;
  const multiZone = zones.length > 1;

  return (
    <>
      <div className="mt-5 print:hidden">
        <div className="flex h-11 items-center rounded-xl border border-line bg-surface p-1">
          {FORMATS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFormat(f.key)}
              className={`h-9 flex-1 rounded-lg text-sm font-medium transition ${
                f.key === format
                  ? "bg-ink text-surface dark:bg-muted dark:text-ink"
                  : "text-ink-muted"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <p className="mt-2 text-sm text-ink-muted">{active.hint}</p>
      </div>

      {zones.map((zone) => {
        const inZone = points.filter((p) => p.zone_id === zone.id);
        if (inZone.length === 0) return null;
        return (
          <section
            key={zone.id}
            // каждая зона — своя пачка: их клеят в разных залах, и разбирать
            // общую стопку по столам никто не станет
            className="mt-8 break-after-page print:mt-0"
          >
            {multiZone && (
              <h2 className="mb-3 text-lg font-bold text-ink print:mb-2">
                {zone.name}
              </h2>
            )}

            {format === "sticker" ? (
              <div className="sticker-sheet grid grid-cols-2 gap-4 print:gap-0">
                {inZone.map((point) => (
                  <article
                    key={point.id}
                    className="sticker flex break-inside-avoid flex-col items-center justify-center rounded-3xl border border-line bg-raised p-5 text-center print:rounded-none print:bg-transparent"
                  >
                    <Face
                      label={point.label}
                      zone={multiZone ? zone.name : null}
                      token={point.token}
                      host={host}
                    />
                  </article>
                ))}
              </div>
            ) : (
              <div className="space-y-6 print:space-y-0">
                {inZone.map((point) => (
                  <article
                    key={point.id}
                    className="tent break-inside-avoid rounded-3xl border border-line bg-raised print:rounded-none print:border-0 print:bg-transparent"
                  >
                    {/* верхняя половина перевёрнута: после сгиба встаёт правильно */}
                    <div className="tent-face tent-face-flipped flex flex-col items-center justify-center p-5 text-center">
                      <Face
                        label={point.label}
                        zone={multiZone ? zone.name : null}
                        token={point.token}
                        host={host}
                      />
                    </div>
                    <div className="tent-fold border-t border-dashed border-line" />
                    <div className="tent-face flex flex-col items-center justify-center p-5 text-center">
                      <Face
                        label={point.label}
                        zone={multiZone ? zone.name : null}
                        token={point.token}
                        host={host}
                      />
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        );
      })}
    </>
  );
}

/** Одна сторона: подпись стола, код и домен под ним. */
function Face({
  label,
  zone,
  token,
  host,
}: {
  label: string;
  zone: string | null;
  token: string;
  host: string | null;
}) {
  return (
    <>
      <p className="text-lg font-bold text-ink print:text-black">{label}</p>
      {zone && <p className="text-xs text-ink-faint print:text-black">{zone}</p>}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`/api/admin/qr.svg?point=${encodeURIComponent(token)}`}
        alt={`QR-код: ${label}`}
        width={200}
        height={200}
        className="mt-2 h-40 w-40 [image-rendering:pixelated] print:h-[38mm] print:w-[38mm]"
      />
      <p className="mt-2 text-sm text-ink-muted print:text-black">
        Наведите камеру — откроется меню
      </p>
      <p className="mt-0.5 text-xs break-all text-ink-faint print:text-black">
        {host}
      </p>
    </>
  );
}
