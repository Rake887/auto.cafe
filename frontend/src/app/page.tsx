import Link from "next/link";
import { fetchDemoLink } from "@/lib/api";
import { CopyLink } from "@/components/CopyLink";

export const dynamic = "force-dynamic";

export default async function Home() {
  const demo = await fetchDemoLink();
  const token = demo?.token ?? process.env.NEXT_PUBLIC_DEMO_TOKEN ?? "demo";

  return (
    <main className="min-h-dvh bg-surface text-ink pb-16">
      {/* Header Bar */}
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5 border-b border-line/40">
        <div className="flex items-center gap-2.5">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-accent text-on-accent text-xl font-extrabold shadow-sm">
            ☕
          </span>
          <div>
            <span className="font-extrabold text-lg text-ink">auto.cafe</span>
            <span className="ml-2 rounded-md bg-accent/15 px-2 py-0.5 text-[10px] font-bold text-accent">MVP</span>
          </div>
        </div>

        <Link
          href="/admin/login"
          className="rounded-full border border-line-strong bg-raised px-4 py-2 text-xs font-semibold text-ink hover:bg-muted transition"
        >
          Кабинет заведения →
        </Link>
      </header>

      {/* Hero Section */}
      <section className="mx-auto max-w-4xl px-6 pt-12 text-center">
        <div className="inline-flex items-center gap-2 rounded-full bg-accent/10 px-4 py-1.5 text-xs font-bold text-accent">
          <span>✨</span>
          <span>Умное QR-меню для кафе и ресторанов Тараза</span>
        </div>

        <h1 className="mt-5 text-4xl sm:text-5xl font-extrabold leading-tight text-ink">
          Бесконтактный заказ <br className="hidden sm:inline" />
          <span className="text-accent">без скачивания приложений</span>
        </h1>

        <p className="mt-4 text-base sm:text-lg leading-relaxed text-ink-muted max-w-2xl mx-auto">
          Гость сканирует QR на столе, выбирает блюда в телефоне и оформляет заказ за 15 секунд. Заказ мгновенно прилетает поварам в Telegram-чат!
        </p>

        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href={`/m/${token}`}
            className="w-full sm:w-auto h-13 px-8 rounded-2xl bg-accent text-on-accent font-bold text-base flex items-center justify-center shadow-lg transition active:scale-95 hover:bg-accent-strong"
          >
            📱 Открыть меню гостя
          </Link>
          <a
            href="#demo-qr"
            className="w-full sm:w-auto h-13 px-8 rounded-2xl border border-line-strong bg-raised font-bold text-base text-ink flex items-center justify-center shadow-xs transition hover:bg-muted"
          >
            📷 Отсканировать QR-код
          </a>
        </div>
      </section>

      {/* Live QR Demo & Interactive Mockup */}
      <section id="demo-qr" className="mx-auto max-w-4xl px-6 pt-14">
        <div className="rounded-3xl bg-raised border border-line/60 p-6 sm:p-10 shadow-xl grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
          <div>
            <span className="text-xs font-bold tracking-wider text-accent uppercase">Демонстрация</span>
            <h2 className="mt-1 text-2xl font-extrabold text-ink">
              Протестируйте со своего смартфона
            </h2>
            <p className="mt-2 text-sm text-ink-muted leading-relaxed">
              Наведите камеру телефона на QR-код справа. Откроется меню стола
              {demo?.point_label ? ` (${demo.point_label})` : ""}.
            </p>

            {demo?.menu_url ? (
              <div className="mt-5">
                <CopyLink url={demo.menu_url} />
              </div>
            ) : (
              <div className="mt-4 rounded-2xl bg-amber-500/10 p-4 border border-amber-500/20 text-xs text-amber-900 dark:text-amber-300">
                <p className="font-bold">Публичный туннель не запущен</p>
                <p className="mt-1">Для открытия с мобильного интернета запустите Cloudflare туннель в docker.</p>
              </div>
            )}

            <div className="mt-6 flex flex-wrap gap-2 text-xs">
              <Link href="/m/invalid" className="text-ink-faint hover:text-ink underline">
                Экран ошибки QR
              </Link>
              <span>•</span>
              <Link href="/admin/qr" className="text-ink-faint hover:text-ink underline">
                Сетка наклеек для печати
              </Link>
            </div>
          </div>

          <div className="flex flex-col items-center justify-center">
            {demo?.menu_url ? (
              <div className="rounded-3xl bg-surface p-6 shadow-inner border border-line/60 flex flex-col items-center">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/api/demo/qr.svg"
                  alt="QR Code"
                  width={220}
                  height={220}
                  className="h-52 w-52 [image-rendering:pixelated]"
                />
                <span className="mt-3 text-xs font-semibold text-ink-muted">
                  Стол №1 (Демо)
                </span>
              </div>
            ) : (
              <div className="h-52 w-52 rounded-3xl bg-muted flex items-center justify-center text-4xl">
                📷
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Feature Cards Grid */}
      <section className="mx-auto max-w-5xl px-6 pt-16">
        <h2 className="text-center text-2xl font-extrabold text-ink">
          Всё необходимое для быстрой работы
        </h2>

        <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <FeatureCard
            icon="⚡"
            title="Быстрота"
            description="Открытие меню за 1 секунду по QR-коду без регистрации и ввода номеров."
          />
          <FeatureCard
            icon="💬"
            title="Telegram-бот"
            description="Заказы прилетают поварам и официантам в общий рабочий чат с кнопками статус-трекинга."
          />
          <FeatureCard
            icon="🔔"
            title="Вызов официанта"
            description="Гость может позвать официанта, попросить счёт или дополнительные приборы в 1 тап."
          />
          <FeatureCard
            icon="📊"
            title="Аналитика"
            description="Подробный дашборд выручки, популярных позиций и скорости работы персонала."
          />
        </div>
      </section>
    </main>
  );
}

function FeatureCard({ icon, title, description }: { icon: string; title: string; description: string }) {
  return (
    <div className="rounded-3xl bg-raised p-5 border border-line/60 shadow-xs">
      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-accent/15 text-xl">
        {icon}
      </div>
      <h3 className="mt-3 font-bold text-ink text-base">{title}</h3>
      <p className="mt-1 text-xs text-ink-muted leading-relaxed">{description}</p>
    </div>
  );
}

