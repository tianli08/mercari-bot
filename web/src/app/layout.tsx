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
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
