import type { Metadata } from "next";
import { Libre_Barcode_128, Share_Tech_Mono } from "next/font/google";
import "./globals.css";

const shareTechMono = Share_Tech_Mono({
  variable: "--font-mono",
  weight: "400",
  subsets: ["latin"],
});

const libreBarcode = Libre_Barcode_128({
  variable: "--font-barcode",
  weight: "400",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Static Archive — Real-time Mercari Japan alerts",
  description:
    "Real-time Mercari Japan alerts for archive fashion, delivered to Discord.",
  openGraph: {
    title: "Static Archive",
    description:
      "Real-time Mercari Japan alerts for archive fashion, delivered to Discord.",
    type: "website",
  },
  twitter: {
    card: "summary",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${shareTechMono.variable} ${libreBarcode.variable} h-full antialiased`}
    >
      <head>
        {/* DotGothic16 covers the Japanese receipt text; its Japanese subset is
            served in unicode-range chunks by Google Fonts, which next/font
            does not split, so it is linked directly. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font -- app-router root layout applies to every page */}
        <link
          href="https://fonts.googleapis.com/css2?family=DotGothic16&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
