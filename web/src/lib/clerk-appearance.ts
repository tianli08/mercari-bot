import type { ComponentProps } from "react";
import { ClerkProvider } from "@clerk/nextjs";

export const clerkAppearance: ComponentProps<typeof ClerkProvider>["appearance"] = {
  variables: {
    colorPrimary: "#2a2622",
    colorBackground: "#f4f3f0",
    colorForeground: "#1d1b17",
    colorMutedForeground: "#4a443d",
    colorDanger: "#b23a2c",
    fontFamily: 'var(--font-mono), "Courier New", monospace',
    borderRadius: "0",
  },
};

export const authCardAppearance = {
  elements: {
    rootBox: { width: "100%" },
    cardBox: { width: "100%", boxShadow: "none", border: "none" },
    card: { padding: 0, background: "transparent", boxShadow: "none" },
    footer: { background: "transparent" },
    headerTitle: { textTransform: "uppercase" as const, letterSpacing: "0.08em" },
  },
};
