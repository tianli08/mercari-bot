import { ClerkProvider } from "@clerk/nextjs";
import { clerkAppearance } from "@/lib/clerk-appearance";
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
      <body className="min-h-full flex flex-col">
        <ClerkProvider
          signInUrl="/login"
          signUpUrl="/signup"
          signInFallbackRedirectUrl="/dashboard"
          signUpFallbackRedirectUrl="/dashboard?welcome=1"
          appearance={clerkAppearance}
          localization={{
            signIn: { start: { title: "Log in to Static Archive" } },
            signUp: {
              start: { title: "Create your account" },
              emailCode: { title: "Check your inbox", subtitle: "Enter the verification code sent to your email." },
              emailLink: { title: "Check your inbox", subtitle: "Follow the verification link sent to your email." },
            },
          }}
        >
          {children}
        </ClerkProvider>
      </body>
    </html>
  );
}
