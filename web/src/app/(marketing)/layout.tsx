import type { ReactNode } from "react";

/**
 * Marketing pages only: loads DotGothic16 for the Japanese receipt text.
 * Its Japanese subset is served in unicode-range chunks by Google Fonts,
 * which next/font does not split, so it is linked directly. React hoists
 * these tags into <head>; `precedence` opts the stylesheet into hoisting
 * and dedupes it across marketing pages.
 */
export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      {/* eslint-disable-next-line @next/next/no-page-custom-font -- scoped to the (marketing) route group on purpose */}
      <link
        href="https://fonts.googleapis.com/css2?family=DotGothic16&display=swap"
        rel="stylesheet"
        precedence="default"
      />
      {children}
    </>
  );
}
