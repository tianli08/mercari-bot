// Canonical landing-page content

export const SIGNUP_HREF = "/signup" as const;
export const HOW_IT_WORKS_HREF = "#what-it-does" as const;

export const PRODUCT_NAME = "Static Archive";

export const HERO_COPY = {
  valueProposition:
    "Real-time Mercari Japan alerts for archive and designer fashion, delivered to Discord.",
  primaryCta: "Sign up",
  secondaryCta: "How it works",
} as const;

export const WHAT_IT_DOES_COPY = {
  heading: "What it does",
  features: [
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
  ],
} as const;

type TwentyNames = readonly [
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
];

// Seeded catalog names, catalog order.
export const PRESET_DESIGNER_NAMES = [
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
] as const satisfies TwentyNames;

export type PresetDesignerName = (typeof PRESET_DESIGNER_NAMES)[number];

export const PRESETS_COPY = {
  heading: "Curated designer presets, ready to watch.",
  supportingLine: "Add any of these catalogs to a watchlist.",
} as const;

export const PRICING_COPY = {
  heading: "Pricing",
  tierName: "Free beta",
  included: [
    "Hosted Mercari Japan monitoring",
    "Keyword watchlists with price and listing-status filters",
    "Discord webhook alerts (no bot to install)",
    "Curated designer presets",
    "Up to 100 keywords per account",
  ],
  cta: "Sign up",
} as const;

export const SIGNUP_CTA_COPY = {
  heading: "Start watching Mercari Japan.",
  supportingLine: "Create an account and send alerts to your Discord webhook.",
  cta: "Sign up",
} as const;
