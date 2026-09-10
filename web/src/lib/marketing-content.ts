// Canonical landing-page content

export const SIGNUP_HREF = "/signup" as const;
export const HOW_IT_WORKS_HREF = "#what-it-does" as const;

export const PRODUCT_NAME = "Static Archive";

export const HERO_COPY = {
  valueProposition:
    "Real-time Mercari Japan alerts for archive fashion, delivered to Discord.",
  primaryCta: "Sign up",
  secondaryCta: "How it works",
  statusLine: "Monitoring Mercari JP",
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
        "No bot to install. Paste a webhook URL. We run the scraper; you host nothing.",
    },
    {
      title: "Preset designer catalogs",
      description:
        "Start from curated designer presets instead of building every watchlist from scratch.",
    },
  ],
} as const;

// Seeded catalog, in catalog order. `keyword` is the Japanese search term
// from backend/config/config.json (or the romaji fallback when none exists).
export const PRESET_CATALOG = [
  { name: "Mihara Yasuhiro", keyword: "ミハラヤスヒロ" },
  { name: "Carol Christian Poell", keyword: "キャロルクリスチャンポエル" },
  { name: "TheSoloist", keyword: "タカヒロミヤシタザソロイスト" },
  { name: "14th Addiction", keyword: "フォーティーンスアディクション" },
  { name: "Rick Owens", keyword: "リックオウエンス" },
  { name: "Ann Demeulemeester", keyword: "アン ドゥムルメステール" },
  { name: "Attachment", keyword: "kazuyuki kumagai" },
  { name: "Boris Bidjan Saberi", keyword: "ボリスビジャンサベリ" },
  { name: "Dior Homme", keyword: "ディオールオム" },
  { name: "Isamu Katayama Backlash", keyword: "イサムカタヤマバックラッシュ" },
  { name: "Julius_7", keyword: "ユリウス" },
  { name: "Kapital", keyword: "キャピタル" },
  { name: "Lad Musician", keyword: "ラッドミュージシャン" },
  { name: "Maison Margiela", keyword: "メゾンマルジェラ" },
  { name: "Number (N)ine", keyword: "ナンバーナイン" },
  { name: "Saint Laurent Paris", keyword: "サンローランパリ" },
  { name: "Tornado Mart", keyword: "トルネードマート" },
  { name: "Undercover", keyword: "アンダーカバー" },
  { name: "A&G Rock n Roll Couture", keyword: "エーアンドジー" },
  { name: "Raf Simons", keyword: "ラフシモンズ" },
] as const;

export const PRESET_DESIGNER_NAMES = PRESET_CATALOG.map(
  (preset) => preset.name,
);

export type PresetDesignerName = (typeof PRESET_CATALOG)[number]["name"];

export const PRESETS_COPY = {
  heading: "Curated designer presets, ready to watch.",
  countLabel: `${PRESET_CATALOG.length} catalogs`,
} as const;

// Illustrative rows for the hero ledger. Not live data.
export const SAMPLE_FEED = {
  columns: ["Time", "Catalog", "Listing", "Price", "Status"],
  footnote: "Sample feed",
  rows: [
    { time: "14:02:11", catalog: "Carol Christian Poell", listing: "CCP drip sneakers, size 42, black kangaroo", price: "¥186,000", status: "Active" },
    { time: "14:01:47", catalog: "Boris Bidjan Saberi", listing: "BBS P13 pants, horse leather, M", price: "¥98,000", status: "Active" },
    { time: "13:58:20", catalog: "Maison Margiela", listing: "Margiela AW98 flat garment jacket", price: "¥64,500", status: "Active" },
    { time: "13:55:03", catalog: "Number (N)ine", listing: "Number (N)ine 2006 Noir hooded knit", price: "¥42,000", status: "Sold" },
    { time: "13:51:39", catalog: "Rick Owens", listing: "Rick Owens Geobasket, 2012, milk", price: "¥71,000", status: "Active" },
    { time: "13:49:12", catalog: "Undercover", listing: "Undercover SS03 Scab denim jacket", price: "¥128,000", status: "Active" },
    { time: "13:44:58", catalog: "Julius_7", listing: "Julius_7 coated denim, size 1", price: "¥23,800", status: "Active" },
    { time: "13:40:31", catalog: "Raf Simons", listing: "Raf Simons AW05 History of my World bomber", price: "¥340,000", status: "Sold" },
  ],
} as const;

export type SampleFeedRow = (typeof SAMPLE_FEED.rows)[number];

export const PRICING_COPY = {
  heading: "Pricing",
  tierName: "Free beta",
  priceLine: "¥0 · while in beta",
  included: [
    "Hosted Mercari Japan monitoring",
    "Keyword watchlists with price and listing-status filters",
    "Discord webhook alerts, no bot to install",
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

export const FOOTER_COPY = {
  tagline: "Mercari JP · Discord webhooks",
} as const;
