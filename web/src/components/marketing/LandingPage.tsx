import Link from "next/link";

import type { ReceiptFrame } from "@/lib/marketing-content";

import { ReceiptHero, ReceiptStrip } from "@/components/marketing/ReceiptFrames";
import { Barcode, Dashes, Line, Sheet } from "@/components/marketing/Sheet";
import {
  CATALOGS_HREF,
  FOOTER_COPY,
  HERO_COPY,
  HOW_IT_WORKS_HREF,
  PRESET_CATALOG,
  PRESETS_COPY,
  PRICING_COPY,
  PRODUCT_NAME,
  SAMPLE_FEED,
  SIGNUP_CTA_COPY,
  SIGNUP_HREF,
  WHAT_IT_DOES_COPY,
  loopLabel,
  stripLabel,
} from "@/lib/marketing-content";
import { getReceiptFrames } from "@/lib/receipt-frames";

const LABEL = "text-[11px] uppercase tracking-[0.16em]";
const BUTTON_PRIMARY =
  "inline-block border-2 border-ink bg-ink px-4 py-2 text-[17px] text-paper-white transition-opacity hover:opacity-80";
const BUTTON_SECONDARY =
  "inline-block border-2 border-ink px-4 py-2 text-[17px] text-ink transition-opacity hover:opacity-70";

export function LandingPage() {
  const frames = getReceiptFrames();
  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-ink selection:text-paper-white">
      <Header />
      <main className="mx-auto max-w-[1440px] px-5 pb-20 md:px-16">
        <Hero frames={frames} />
        <div className="mt-16 md:mt-[72px]">
          <ReceiptStrip frames={frames} stripLabel={stripLabel(frames.length)} />
        </div>
        <section
          id="how-it-works"
          className="mt-14 grid scroll-mt-24 grid-cols-1 gap-8 lg:grid-cols-[560px_minmax(0,1fr)] lg:gap-14"
        >
          <HowItWorksReceipt />
          <CatalogReceipt />
        </section>
        <Footer />
      </main>
    </div>
  );
}

function Header() {
  return (
    <header className="mx-auto flex max-w-[1440px] items-center justify-between px-5 pt-9 md:px-16">
      <span className={LABEL}>{PRODUCT_NAME}</span>
      <nav className={`flex gap-5 md:gap-7 ${LABEL}`}>
        <a href={HOW_IT_WORKS_HREF} className="hidden hover:opacity-70 sm:inline">
          How it works
        </a>
        <a href={CATALOGS_HREF} className="hidden hover:opacity-70 sm:inline">
          Catalogs
        </a>
        <Link href={SIGNUP_HREF} className="border-b border-ink hover:opacity-70">
          Sign up
        </Link>
      </nav>
    </header>
  );
}

function Hero({ frames }: { frames: ReceiptFrame[] }) {
  return (
    <section className="mt-12 grid grid-cols-1 items-start gap-10 lg:grid-cols-[680px_minmax(0,1fr)] lg:gap-14">
      <ReceiptHero frames={frames} loopLabel={loopLabel(frames.length)} />
      <div className="flex min-w-0 flex-col gap-6">
        <HeadlineReceipt />
        <FeedReceipt />
      </div>
    </section>
  );
}

function HeadlineReceipt() {
  return (
    <Sheet tint="pink" className="px-7 py-7 md:px-9">
      <div className="ink flex flex-col gap-2.5">
        <Line
          left={<span className="font-jp text-[22px]">{HERO_COPY.totalLabelJa}</span>}
          right={<span className="text-[22px]">{HERO_COPY.totalValue}</span>}
          className="items-end border-b-2 border-ink pb-1.5"
        />
        <Line
          left={HERO_COPY.totalLabelEn}
          right={HERO_COPY.plan}
          className="text-[13px] tracking-[0.1em]"
        />
        <h1 className="pb-5 pt-3 text-[24px] leading-[1.12] tracking-[0.02em] md:text-[30px]">
          <span className="tall text-balance">{HERO_COPY.valueProposition}</span>
        </h1>
        <div className="font-jp text-sm leading-relaxed">
          {HERO_COPY.thanksJa.map((line) => (
            <div key={line}>{line}</div>
          ))}
        </div>
        <p className="max-w-[420px] text-sm leading-normal">{HERO_COPY.supportingLine}</p>
        <div className="mt-2 flex flex-wrap gap-2.5">
          <Link href={SIGNUP_HREF} className={BUTTON_PRIMARY}>
            {HERO_COPY.primaryCta}
          </Link>
          <a href={HOW_IT_WORKS_HREF} className={BUTTON_SECONDARY}>
            {HERO_COPY.secondaryCta}
          </a>
        </div>
        <Line
          left={HERO_COPY.footerLeft}
          right={HERO_COPY.footerRight}
          className="mt-2.5 border-t border-ink pt-2 text-xs"
        />
        <Line
          left={<span className="font-jp">{HERO_COPY.copyLine}</span>}
          right={HERO_COPY.copyNumber}
          className="text-xs"
        />
      </div>
    </Sheet>
  );
}

function FeedReceipt() {
  return (
    <Sheet className="px-6 pb-5 pt-5 md:px-8">
      <div className="ink flex flex-col gap-1.5 text-[15px]">
        <Line
          left={SAMPLE_FEED.heading}
          right={SAMPLE_FEED.footnote}
          className="text-xs tracking-[0.14em] text-ink-faded"
        />
        {SAMPLE_FEED.rows.map((row) => (
          <Line
            key={row.time}
            left={
              <>
                {row.time} {row.listing}{" "}
                {row.sold && <span className="stamp font-jp text-[13px]">{SAMPLE_FEED.soldStamp}</span>}
              </>
            }
            right={<span className={row.sold ? "line-through" : ""}>{row.price}</span>}
            className={row.sold ? "text-ink-faded" : ""}
          />
        ))}
      </div>
    </Sheet>
  );
}

function HowItWorksReceipt() {
  return (
    <Sheet className="px-7 pb-6 pt-6 md:px-9">
      <div className="ink flex flex-col gap-2 text-[15px]">
        <h2 className="text-[20px] tracking-[0.06em]">
          <span className="tall">{WHAT_IT_DOES_COPY.heading}</span>
        </h2>
        <Dashes />
        {WHAT_IT_DOES_COPY.features.map((f) => (
          <Line key={f.label} left={f.label} right={f.value} />
        ))}
        <Dashes />
        {PRICING_COPY.included.map((f) => (
          <Line key={f.label} left={f.label} right={f.value} />
        ))}
        <Dashes />
        <Line left={PRICING_COPY.subtotal.label} right={PRICING_COPY.subtotal.value} />
        <Line left={PRICING_COPY.tax.label} right={PRICING_COPY.tax.value} />
        <Line
          left={<span className="tall">{PRICING_COPY.total.label}</span>}
          right={<span className="tall">{PRICING_COPY.total.value}</span>}
          className="py-1.5 text-[30px]"
        />
        <Line left={PRICING_COPY.plan.label} right={PRICING_COPY.plan.value} />
        <Dashes double />
        <div id="signup-cta" className="flex flex-col items-center gap-2.5 pt-1 text-center">
          <div className="text-[22px] leading-[1.15]">
            <span className="tall" style={{ transformOrigin: "top center" }}>
              {SIGNUP_CTA_COPY.heading[0]}
              <br />
              {SIGNUP_CTA_COPY.heading[1]}
            </span>
          </div>
          <Link
            href={SIGNUP_HREF}
            className="mt-2 block w-full bg-ink px-5 py-3 text-center text-[18px] text-paper-white transition-opacity hover:opacity-80"
          >
            {SIGNUP_CTA_COPY.cta}
          </Link>
          <Barcode value={SIGNUP_CTA_COPY.barcode} className="mt-2 text-[52px] md:text-[70px]" />
          <div className="font-jp text-xs">{SIGNUP_CTA_COPY.thanksJa}</div>
        </div>
      </div>
    </Sheet>
  );
}

function CatalogReceipt() {
  return (
    <Sheet className="min-w-0 px-6 pb-5 pt-6 md:px-8 lg:mt-8">
      <div id="catalogs" className="ink flex scroll-mt-24 flex-col gap-1">
        <h2 className="text-center text-[20px] tracking-[0.06em]">
          <span className="tall" style={{ transformOrigin: "top center" }}>
            {PRESETS_COPY.heading}
          </span>
        </h2>
        <div className="text-center text-xs text-ink-faded">{PRESETS_COPY.supportingLine}</div>
        <Dashes />
        <ul className="flex flex-col gap-0.5 text-[13px]">
          {PRESET_CATALOG.map((preset, i) => (
            <li key={preset.name} className="flex min-w-0 justify-between gap-3">
              <span className="shrink-0">
                {String(i + 1).padStart(2, "0")} {preset.name.toUpperCase()}
              </span>
              <span className="font-jp min-w-0 truncate text-right text-ink-faded">{preset.keyword}</span>
            </li>
          ))}
        </ul>
        <Dashes />
        <Barcode value={PRESETS_COPY.barcode} className="text-[54px]" />
      </div>
    </Sheet>
  );
}

function Footer() {
  return (
    <footer className={`mt-16 flex items-center justify-between border-t border-ink-dim/30 pt-5 ${LABEL} text-ink-dim`}>
      <span>{PRODUCT_NAME}</span>
      <span>{FOOTER_COPY.tagline}</span>
    </footer>
  );
}
