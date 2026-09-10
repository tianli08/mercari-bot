import Link from "next/link";

import {
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
} from "@/lib/marketing-content";

const LABEL =
  "font-mono text-[11px] uppercase tracking-[0.14em] text-muted";
const PRIMARY_BUTTON =
  "inline-flex items-center justify-center bg-foreground px-6 py-4 font-mono text-[11px] uppercase tracking-[0.14em] text-background transition-colors hover:bg-muted";
const SECONDARY_BUTTON =
  "inline-flex items-center justify-center border border-rule px-6 py-[15px] font-mono text-[11px] uppercase tracking-[0.14em] text-foreground transition-colors hover:border-muted";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-background font-sans text-foreground selection:bg-foreground selection:text-background">
      <Header />
      <main className="mx-auto max-w-[1440px] px-6 md:px-16">
        <Hero />
        <WhatItDoes />
        <Presets />
        <Pricing />
        <SignUpCTA />
        <Footer />
      </main>
    </div>
  );
}

function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-rule bg-background">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-6 md:px-16">
        <div className="flex items-center gap-8">
          <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-foreground">
            {PRODUCT_NAME}
          </span>
          <span className={`hidden items-center gap-2 sm:flex ${LABEL}`}>
            <span
              aria-hidden
              className="inline-block h-1.5 w-1.5 rounded-full bg-foreground"
            />
            {HERO_COPY.statusLine}
          </span>
        </div>
        <nav className="flex items-center gap-8">
          <a
            href={HOW_IT_WORKS_HREF}
            className={`hidden transition-colors hover:text-foreground md:inline ${LABEL}`}
          >
            {HERO_COPY.secondaryCta}
          </a>
          <a
            href="#pricing"
            className={`hidden transition-colors hover:text-foreground md:inline ${LABEL}`}
          >
            {PRICING_COPY.heading}
          </a>
          <Link
            href={SIGNUP_HREF}
            className="bg-foreground px-3.5 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-background transition-colors hover:bg-muted"
          >
            {HERO_COPY.primaryCta}
          </Link>
        </nav>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="grid grid-cols-1 items-start gap-12 py-16 md:py-24 lg:grid-cols-[560px_1fr] lg:gap-[72px]">
      <div className="flex flex-col gap-9">
        <h1 className="text-balance text-4xl font-normal leading-[1.02] tracking-[-0.03em] sm:text-5xl md:text-6xl lg:text-[64px]">
          {HERO_COPY.valueProposition}
        </h1>
        <div className="flex flex-wrap items-center gap-4 sm:gap-6">
          <Link href={SIGNUP_HREF} className={PRIMARY_BUTTON}>
            {HERO_COPY.primaryCta}
          </Link>
          <a href={HOW_IT_WORKS_HREF} className={SECONDARY_BUTTON}>
            {HERO_COPY.secondaryCta}
          </a>
        </div>
      </div>
      <Ledger />
    </section>
  );
}

function Ledger() {
  const [timeHeader, catalogHeader, listingHeader, priceHeader, statusHeader] =
    SAMPLE_FEED.columns;
  return (
    <div
      aria-label="Sample alert feed"
      className="overflow-x-auto border border-rule px-5 pb-2"
    >
      <table className="w-full min-w-[640px] border-collapse font-mono text-xs">
        <thead>
          <tr className="text-left">
            <th className={`py-3.5 pr-5 font-normal ${LABEL}`}>{timeHeader}</th>
            <th className={`py-3.5 pr-5 font-normal ${LABEL}`}>{catalogHeader}</th>
            <th className={`py-3.5 pr-5 font-normal ${LABEL}`}>{listingHeader}</th>
            <th className={`py-3.5 pr-5 text-right font-normal ${LABEL}`}>
              {priceHeader}
            </th>
            <th className={`py-3.5 font-normal ${LABEL}`}>{statusHeader}</th>
          </tr>
        </thead>
        <tbody>
          {SAMPLE_FEED.rows.map((row) => (
            <tr key={row.time} className="border-t border-rule-faint">
              <td className="whitespace-nowrap py-3 pr-5 text-muted">
                {row.time}
              </td>
              <td className="whitespace-nowrap py-3 pr-5">{row.catalog}</td>
              <td className="max-w-[280px] truncate py-3 pr-5">{row.listing}</td>
              <td className="whitespace-nowrap py-3 pr-5 text-right">
                {row.price}
              </td>
              <td
                className={`whitespace-nowrap py-3 ${
                  row.status === "Sold" ? "text-dim" : "text-muted"
                }`}
              >
                {row.status}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className={`pb-1 pt-3.5 ${LABEL}`}>{SAMPLE_FEED.footnote}</p>
    </div>
  );
}

function WhatItDoes() {
  return (
    <section
      id="what-it-does"
      className="scroll-mt-20 border-t border-rule py-10 md:py-16"
    >
      <h2 className="sr-only">{WHAT_IT_DOES_COPY.heading}</h2>
      <div className="grid grid-cols-1 gap-10 sm:grid-cols-2 lg:grid-cols-4">
        {WHAT_IT_DOES_COPY.features.map((item, index) => (
          <div key={item.title} className="flex flex-col gap-3.5">
            <span className={LABEL}>0{index + 1}</span>
            <h3 className="text-xl font-medium tracking-[-0.01em]">
              {item.title}
            </h3>
            <p className="text-[15px] leading-relaxed text-muted">
              {item.description}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Presets() {
  return (
    <section
      id="presets"
      className="scroll-mt-20 border-t border-rule py-10 md:py-16"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-baseline sm:justify-between">
        <h2 className="text-2xl font-normal tracking-[-0.02em] md:text-[32px]">
          {PRESETS_COPY.heading}
        </h2>
        <span className={LABEL}>{PRESETS_COPY.countLabel}</span>
      </div>
      <ul className="mt-8 grid grid-cols-2 border-l border-t border-rule md:grid-cols-3 lg:grid-cols-5">
        {PRESET_CATALOG.map((preset, index) => (
          <li
            key={preset.name}
            className="flex min-h-24 flex-col gap-2.5 border-b border-r border-rule px-5 pb-[22px] pt-5 transition-colors hover:bg-rule-faint"
          >
            <span className={LABEL}>
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="text-[17px] leading-snug">{preset.name}</span>
            <span className="font-mono text-[11px] text-muted">
              {preset.keyword}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Pricing() {
  return (
    <section
      id="pricing"
      className="scroll-mt-20 grid grid-cols-1 gap-10 border-t border-rule py-10 md:py-16 lg:grid-cols-[560px_1fr] lg:gap-[72px]"
    >
      <div className="flex flex-col gap-5">
        <span className={LABEL}>{PRICING_COPY.heading}</span>
        <h2 className="text-5xl font-light leading-none tracking-[-0.03em]">
          {PRICING_COPY.tierName}
        </h2>
        <span className={LABEL}>{PRICING_COPY.priceLine}</span>
      </div>
      <div className="flex flex-col">
        <ul>
          {PRICING_COPY.included.map((item) => (
            <li
              key={item}
              className="border-t border-rule py-3.5 text-[17px] last:border-b"
            >
              {item}
            </li>
          ))}
        </ul>
        <Link href={SIGNUP_HREF} className={`mt-7 self-start ${PRIMARY_BUTTON}`}>
          {PRICING_COPY.cta}
        </Link>
      </div>
    </section>
  );
}

function SignUpCTA() {
  return (
    <section
      id="signup-cta"
      className="scroll-mt-20 flex flex-col gap-8 border-t border-rule py-16 md:flex-row md:items-end md:justify-between md:py-24"
    >
      <div className="flex flex-col gap-4">
        <h2 className="text-balance text-4xl font-normal leading-[1.02] tracking-[-0.03em] md:text-5xl">
          {SIGNUP_CTA_COPY.heading}
        </h2>
        <p className="text-[17px] text-muted">
          {SIGNUP_CTA_COPY.supportingLine}
        </p>
      </div>
      <Link href={SIGNUP_HREF} className={`self-start ${PRIMARY_BUTTON}`}>
        {SIGNUP_CTA_COPY.cta}
      </Link>
    </section>
  );
}

function Footer() {
  return (
    <footer className="flex items-center justify-between border-t border-rule pb-12 pt-5">
      <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-foreground">
        {PRODUCT_NAME}
      </span>
      <span className={LABEL}>{FOOTER_COPY.tagline}</span>
    </footer>
  );
}
