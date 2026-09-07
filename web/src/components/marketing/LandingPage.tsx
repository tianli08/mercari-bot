import Link from "next/link";

import {
  HERO_COPY,
  HOW_IT_WORKS_HREF,
  PRESET_DESIGNER_NAMES,
  PRESETS_COPY,
  PRICING_COPY,
  PRODUCT_NAME,
  SIGNUP_CTA_COPY,
  SIGNUP_HREF,
  WHAT_IT_DOES_COPY,
} from "@/lib/marketing-content";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] font-mono text-[#f0f0f0] selection:bg-[#f0f0f0] selection:text-[#0a0a0a]">
      <Header />
      <main>
        <Hero />
        <WhatItDoes />
        <Presets />
        <Pricing />
        <SignUpCTA />
      </main>
      <Footer />
    </div>
  );
}

function Header() {
  return (
    <header className="fixed left-0 right-0 top-0 z-50 border-b border-[#222222] bg-[#0a0a0a]">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <span className="text-xs font-medium uppercase tracking-[0.2em] text-[#f0f0f0]">
          {PRODUCT_NAME}
        </span>
        <Link
          href={SIGNUP_HREF}
          className="bg-[#f0f0f0] px-4 py-2 text-xs font-medium uppercase tracking-[0.15em] text-[#0a0a0a] transition-colors hover:bg-[#c7c7c7]"
        >
          {HERO_COPY.primaryCta}
        </Link>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="flex min-h-screen flex-col items-center justify-center px-6 pb-16 pt-20">
      <div className="max-w-4xl text-center">
        <h1 className="font-mono text-4xl font-light leading-[1.15] text-[#f0f0f0] md:text-6xl lg:text-7xl">
          {HERO_COPY.valueProposition}
        </h1>
        <div className="mt-12 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <Link
            href={SIGNUP_HREF}
            className="inline-flex items-center justify-center bg-[#f0f0f0] px-8 py-3 text-xs font-medium uppercase tracking-[0.15em] text-[#0a0a0a] transition-colors hover:bg-[#c7c7c7]"
          >
            {HERO_COPY.primaryCta}
          </Link>
          <a
            href={HOW_IT_WORKS_HREF}
            className="inline-flex items-center justify-center border border-[#333333] px-8 py-3 text-xs font-medium uppercase tracking-[0.15em] text-[#f0f0f0] transition-colors hover:bg-[#1a1a1a]"
          >
            {HERO_COPY.secondaryCta}
          </a>
        </div>
      </div>
    </section>
  );
}

function WhatItDoes() {
  return (
    <section
      id="what-it-does"
      className="scroll-mt-24 border-t border-[#222222] px-6 py-24"
    >
      <div className="mx-auto max-w-5xl">
        <h2 className="font-mono text-3xl font-light text-[#f0f0f0] md:text-4xl">
          {WHAT_IT_DOES_COPY.heading}
        </h2>
        <div className="mt-16 grid grid-cols-1 gap-12 md:grid-cols-2">
          {WHAT_IT_DOES_COPY.features.map((item, index) => (
            <div key={item.title} className="flex gap-6">
              <span className="text-sm text-[#737373]">0{index + 1}</span>
              <div>
                <h3 className="text-sm font-medium uppercase tracking-[0.1em] text-[#f0f0f0]">
                  {item.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-[#a3a3a3]">
                  {item.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Presets() {
  return (
    <section
      id="presets"
      className="scroll-mt-24 border-t border-[#222222] px-6 py-24"
    >
      <div className="mx-auto max-w-6xl">
        <h2 className="font-mono text-3xl font-light text-[#f0f0f0] md:text-4xl">
          {PRESETS_COPY.heading}
        </h2>
        <p className="mt-4 text-sm text-[#737373]">
          {PRESETS_COPY.supportingLine}
        </p>
        <div className="mt-16 grid grid-cols-1 gap-px border border-[#222222] bg-[#222222] sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {PRESET_DESIGNER_NAMES.map((name) => (
            <div
              key={name}
              className="break-words bg-[#0a0a0a] px-6 py-5 text-sm text-[#a3a3a3] transition-colors hover:bg-[#141414] hover:text-[#f0f0f0]"
            >
              {name}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Pricing() {
  return (
    <section
      id="pricing"
      className="scroll-mt-24 border-t border-[#222222] px-6 py-24"
    >
      <div className="mx-auto max-w-5xl">
        <h2 className="font-mono text-3xl font-light text-[#f0f0f0] md:text-4xl">
          {PRICING_COPY.heading}
        </h2>
        <div className="mt-12 max-w-md border border-[#222222] p-8">
          <h3 className="text-sm font-medium uppercase tracking-[0.15em] text-[#f0f0f0]">
            {PRICING_COPY.tierName}
          </h3>
          <ul className="mt-8 space-y-4">
            {PRICING_COPY.included.map((item) => (
              <li
                key={item}
                className="flex items-start gap-3 text-sm text-[#a3a3a3]"
              >
                <span className="mt-1.5 h-1 w-1 shrink-0 bg-[#f0f0f0]" />
                {item}
              </li>
            ))}
          </ul>
          <Link
            href={SIGNUP_HREF}
            className="mt-10 inline-flex w-full items-center justify-center bg-[#f0f0f0] px-6 py-3 text-xs font-medium uppercase tracking-[0.15em] text-[#0a0a0a] transition-colors hover:bg-[#c7c7c7]"
          >
            {PRICING_COPY.cta}
          </Link>
        </div>
      </div>
    </section>
  );
}

function SignUpCTA() {
  return (
    <section
      id="signup-cta"
      className="scroll-mt-24 border-t border-[#222222] px-6 py-24"
    >
      <div className="mx-auto max-w-3xl text-center">
        <h2 className="font-mono text-3xl font-light text-[#f0f0f0] md:text-4xl">
          {SIGNUP_CTA_COPY.heading}
        </h2>
        <p className="mt-4 text-sm text-[#737373]">
          {SIGNUP_CTA_COPY.supportingLine}
        </p>
        <Link
          href={SIGNUP_HREF}
          className="mt-10 inline-flex items-center justify-center bg-[#f0f0f0] px-8 py-3 text-xs font-medium uppercase tracking-[0.15em] text-[#0a0a0a] transition-colors hover:bg-[#c7c7c7]"
        >
          {SIGNUP_CTA_COPY.cta}
        </Link>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-[#222222] px-6 py-8">
      <div className="mx-auto flex max-w-6xl items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-[0.2em] text-[#f0f0f0]">
          {PRODUCT_NAME}
        </span>
        <Link
          href={SIGNUP_HREF}
          className="text-xs uppercase tracking-[0.1em] text-[#a3a3a3] transition-colors hover:text-[#f0f0f0]"
        >
          {SIGNUP_CTA_COPY.cta}
        </Link>
      </div>
    </footer>
  );
}
