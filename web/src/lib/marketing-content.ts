// Canonical landing-page content

export const SIGNUP_HREF = "/signup" as const;
export const HOW_IT_WORKS_HREF = "#how-it-works" as const;
export const CATALOGS_HREF = "#catalogs" as const;

export const PRODUCT_NAME = "Static Archive";

export const HERO_COPY = {
  totalLabelJa: "合計金額",
  totalLabelEn: "TOTAL AMOUNT",
  totalValue: "¥0",
  plan: "FREE BETA",
  valueProposition:
    "REAL-TIME MERCARI JAPAN ALERTS FOR ARCHIVE FASHION, DELIVERED TO DISCORD.",
  thanksJa: ["ご案内", "ご利用ありがとうございました", "またのご来店をお待ちしております"],
  supportingLine: "EVERY NEW LISTING THAT MATCHES YOUR WATCHLIST PRINTS TO YOUR DISCORD.",
  primaryCta: "[ SIGN UP ]",
  secondaryCta: "[ HOW IT WORKS ]",
  footerLeft: "売場 SALES COUNTER",
  footerRight: "係員 CLERK",
  copyLine: "お客様控 CUSTOMER COPY",
  copyNumber: "87",
} as const;

export const HERO_LOOP_LABEL = "● LIVE · MERCARI JP → DISCORD";

export const WHAT_IT_DOES_COPY = {
  heading: "HOW IT WORKS",
  features: [
    { label: "01 KEYWORD WATCHLISTS", value: "PRICE + STATUS FILTERS" },
    { label: "02 SHARED SCRAPING", value: "ONE SCRAPE / KEYWORD" },
    { label: "03 DISCORD WEBHOOK", value: "PASTE URL. DONE." },
    { label: "04 PRESET CATALOGS", value: "20 DESIGNERS" },
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
  heading: `CATALOG LIST · ${PRESET_CATALOG.length} PRESETS`,
  supportingLine: "COPY ANY CATALOG INTO A WATCHLIST",
  barcode: "CATALOG20",
} as const;

// Illustrative rows for the alert feed receipt. Not live data.
export const SAMPLE_FEED = {
  heading: "LATEST ALERTS",
  footnote: "SAMPLE FEED",
  rows: [
    { time: "14:02", listing: "CCP DRIP SNEAKER 42 BLACK", price: "¥186,000", sold: false },
    { time: "14:01", listing: "BBS P13 PANTS HORSE LEATHER M", price: "¥98,000", sold: false },
    { time: "13:58", listing: "MARGIELA AW98 FLAT GARMENT JKT", price: "¥64,500", sold: false },
    { time: "13:55", listing: "N(N)INE NOIR KNIT 2006", price: "¥42,000", sold: true },
    { time: "13:51", listing: "RICK OWENS GEOBASKET 2012 MILK", price: "¥71,000", sold: false },
  ],
  soldStamp: "済 SOLD",
} as const;

export const PRICING_COPY = {
  included: [
    { label: "HOSTED MONITORING", value: "¥0" },
    { label: "WATCHLISTS + FILTERS", value: "¥0" },
    { label: "DISCORD WEBHOOK ALERTS", value: "¥0" },
    { label: "100 KEYWORDS / ACCOUNT", value: "¥0" },
  ],
  subtotal: { label: "SUBTOTAL", value: "¥0" },
  tax: { label: "TAX (10%)", value: "¥0" },
  total: { label: "TOTAL", value: "¥0" },
  plan: { label: "PLAN", value: "FREE BETA" },
} as const;

export const SIGNUP_CTA_COPY = {
  heading: ["START WATCHING", "MERCARI JAPAN."],
  cta: "[ SIGN UP ]",
  barcode: "STATICARCHIVE0917",
  thanksJa: "ご利用ありがとうございました",
} as const;

export const FOOTER_COPY = {
  tagline: "MERCARI JP · DISCORD WEBHOOKS",
} as const;

// Recycled receipts the hero loop prints on. Shops are fictional. Frame images
// come from whatever is in public/frames (see lib/receipt-frames.ts); each
// image is paired with the next template here, cycling as needed.
export type PaperTint = "white" | "grey" | "pink";

export interface ReceiptFrame {
  image: string;
  tint: PaperTint;
  shop: string;
  address: string;
  datetime: string;
  register: string;
  items: ReadonlyArray<readonly [string, string]>;
  total: string;
  tax: string;
  member: string;
  approval: string;
  slip: string;
  /** Vertical offset of the receipt inside the square, in px at 680. */
  offset: number;
}

export type ReceiptTemplate = Omit<ReceiptFrame, "image">;

export const RECEIPT_TEMPLATES: readonly ReceiptTemplate[] = [
  { tint: "white", shop: "サイゼリヤ 渋谷店", address: "東京都渋谷区道玄坂2-6-17", datetime: "2026年08月14日(木) 21:07", register: "レジ#2 No.1749", items: [["ミラノ風ドリア", "¥300"], ["ドリンクバー", "¥200"], ["小エビのサラダ", "¥350"]], total: "¥850", tax: "¥68", member: "************1749", approval: "449318", slip: "250-626-278-1810", offset: -40 },
  { tint: "pink", shop: "STATIC STORE 下北沢", address: "世田谷区北沢2-25-8", datetime: "2026年08月15日(金) 13:42", register: "レジ#1 No.1762", items: [["古着 ジャケット", "¥6,800"], ["ハンガー", "¥110"]], total: "¥6,910", tax: "¥552", member: "************1750", approval: "449325", slip: "250-626-279-1810", offset: -3 },
  { tint: "grey", shop: "ローソン 新宿三丁目", address: "新宿区新宿3-17-5", datetime: "2026年08月15日(金) 18:20", register: "レジ#2 No.1775", items: [["からあげクン", "¥238"], ["緑茶 525ml", "¥140"], ["レジ袋", "¥5"]], total: "¥383", tax: "¥30", member: "************1751", approval: "449332", slip: "250-626-280-1810", offset: 34 },
  { tint: "white", shop: "古着屋 セカンド 高円寺", address: "杉並区高円寺南4-27", datetime: "2026年08月16日(土) 15:03", register: "レジ#1 No.1788", items: [["デニム 中古", "¥12,000"], ["ベルト", "¥1,500"]], total: "¥13,500", tax: "¥1,080", member: "************1752", approval: "449339", slip: "250-626-281-1810", offset: -19 },
  { tint: "white", shop: "ユニクロ 原宿店", address: "渋谷区神宮前6-1-9", datetime: "2026年08月16日(土) 19:51", register: "レジ#2 No.1801", items: [["ヒートテック", "¥990"], ["ソックス", "¥390"]], total: "¥1,380", tax: "¥110", member: "************1753", approval: "449346", slip: "250-626-282-1810", offset: 18 },
  { tint: "grey", shop: "ブックオフ 中野店", address: "中野区中野5-52", datetime: "2026年08月17日(日) 11:30", register: "レジ#2 No.1814", items: [["雑誌 バックナンバー", "¥420"], ["写真集", "¥1,980"]], total: "¥2,400", tax: "¥192", member: "************1754", approval: "449353", slip: "250-626-283-1810", offset: -30 },
  { tint: "pink", shop: "STATIC STORE 代官山", address: "渋谷区代官山町17-6", datetime: "2026年08月17日(日) 16:12", register: "レジ#1 No.1827", items: [["スニーカー 中古", "¥28,000"]], total: "¥28,000", tax: "¥2,240", member: "************1755", approval: "449360", slip: "250-626-284-1810", offset: 7 },
  { tint: "white", shop: "セブン-イレブン 池袋東口", address: "豊島区南池袋1-28", datetime: "2026年08月18日(月) 07:55", register: "レジ#2 No.1840", items: [["おにぎり 梅", "¥140"], ["水 500ml", "¥110"], ["ガム", "¥130"]], total: "¥380", tax: "¥30", member: "************1756", approval: "449367", slip: "250-626-285-1810", offset: 44 },
];
