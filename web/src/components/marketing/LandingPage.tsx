import Link from "next/link";

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
          Static Archive
        </span>
        <Link
          href="/signup"
          className="bg-[#f0f0f0] px-4 py-2 text-xs font-medium uppercase tracking-[0.15em] text-[#0a0a0a] transition-colors hover:bg-[#c7c7c7]"
        >
          Sign up
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
          Real-time Mercari Japan alerts for archive and designer fashion,
          delivered to Discord.
        </h1>
        <div className="mt-12 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <Link
            href="/signup"
            className="inline-flex items-center justify-center bg-[#f0f0f0] px-8 py-3 text-xs font-medium uppercase tracking-[0.15em] text-[#0a0a0a] transition-colors hover:bg-[#c7c7c7]"
          >
            Sign up
          </Link>
          <a
            href="#what-it-does"
            className="inline-flex items-center justify-center border border-[#333333] px-8 py-3 text-xs font-medium uppercase tracking-[0.15em] text-[#f0f0f0] transition-colors hover:bg-[#1a1a1a]"
          >
            How it works
          </a>
        </div>
      </div>
    </section>
  );
}

function WhatItDoes() {
  const items = [
    {
      title: "Keyword watchlists",
      description:
        "Watch Mercari Japan with your own keywords. Add optional price and listing-status filters.",
    },
    {
      title: "Shared scraping, personal delivery",
      description:
        "Each unique keyword is scraped once. Matching listings fan out to every account watching it.",
    },
    {
      title: "Discord webhook alerts",
      description:
        "No bot to install. Paste a webhook URL. We run the scraper; you do not install a bot or host anything locally.",
    },
    {
      title: "Preset designer catalogs",
      description:
        "Start from curated designer presets instead of building every watchlist from scratch.",
    },
  ];

  return (
    <section
      id="what-it-does"
      className="scroll-mt-24 border-t border-[#222222] px-6 py-24"
    >
      <div className="mx-auto max-w-5xl">
        <h2 className="font-mono text-3xl font-light text-[#f0f0f0] md:text-4xl">
          What it does
        </h2>
        <div className="mt-16 grid grid-cols-1 gap-12 md:grid-cols-2">
          {items.map((item, index) => (
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
  const presets = [
    "Mihara Yasuhiro",
    "Carol Christian Poell",
    "TheSoloist",
    "14th Addiction",
    "Rick Owens",
    "Ann Demeulemeester",
    "Attachment",
    "Boris Bidjan Saberi",
    "Dior Homme",
    "Isamu Katayama Backlash",
    "Julius_7",
    "Kapital",
    "Lad Musician",
    "Maison Margiela",
    "Number (N)ine",
    "Saint Laurent Paris",
    "Tornado Mart",
    "Undercover",
    "A&G Rock n Roll Couture",
    "Raf Simons",
  ];

  return (
    <section
      id="presets"
      className="scroll-mt-24 border-t border-[#222222] px-6 py-24"
    >
      <div className="mx-auto max-w-6xl">
        <h2 className="font-mono text-3xl font-light text-[#f0f0f0] md:text-4xl">
          Curated designer presets, ready to watch.
        </h2>
        <p className="mt-4 text-sm text-[#737373]">
          Add any of these catalogs to a watchlist.
        </p>
        <div className="mt-16 grid grid-cols-1 gap-px border border-[#222222] bg-[#222222] sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {presets.map((name) => (
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
  const included = [
    "Hosted Mercari Japan monitoring",
    "Keyword watchlists with price and listing-status filters",
    "Discord webhook alerts (no bot to install)",
    "Curated designer presets",
    "Up to 100 keywords per account",
  ];

  return (
    <section
      id="pricing"
      className="scroll-mt-24 border-t border-[#222222] px-6 py-24"
    >
      <div className="mx-auto max-w-5xl">
        <h2 className="font-mono text-3xl font-light text-[#f0f0f0] md:text-4xl">
          Pricing
        </h2>
        <div className="mt-12 max-w-md border border-[#222222] p-8">
          <h3 className="text-sm font-medium uppercase tracking-[0.15em] text-[#f0f0f0]">
            Free beta
          </h3>
          <ul className="mt-8 space-y-4">
            {included.map((item) => (
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
            href="/signup"
            className="mt-10 inline-flex w-full items-center justify-center bg-[#f0f0f0] px-6 py-3 text-xs font-medium uppercase tracking-[0.15em] text-[#0a0a0a] transition-colors hover:bg-[#c7c7c7]"
          >
            Sign up
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
          Start watching Mercari Japan.
        </h2>
        <p className="mt-4 text-sm text-[#737373]">
          Create an account and send alerts to your Discord webhook.
        </p>
        <Link
          href="/signup"
          className="mt-10 inline-flex items-center justify-center bg-[#f0f0f0] px-8 py-3 text-xs font-medium uppercase tracking-[0.15em] text-[#0a0a0a] transition-colors hover:bg-[#c7c7c7]"
        >
          Sign up
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
          Static Archive
        </span>
        <Link
          href="/signup"
          className="text-xs uppercase tracking-[0.1em] text-[#a3a3a3] transition-colors hover:text-[#f0f0f0]"
        >
          Sign up
        </Link>
      </div>
    </footer>
  );
}
