"use client";

import type { ButtonHTMLAttributes } from "react";

import { PRIMARY_BUTTON_CLASS_NAME } from "@/lib/ui-styles";

type SubmitButtonProps = {
  /** Whether a request is currently in flight. Disables the button and shows pending state. */
  pending?: boolean;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type" | "disabled">;

/**
 * A submit button that renders a pending state and disables itself while
 * in flight. Visual style matches the landing page's primary CTA.
 */
export function SubmitButton({ pending = false, children, className = "", ...rest }: SubmitButtonProps) {
  return (
    <button
      type="submit"
      disabled={pending}
      aria-busy={pending}
      className={[
        PRIMARY_BUTTON_CLASS_NAME,
        "w-full rounded-none uppercase",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      ].join(" ")}
      {...rest}
    >
      {pending ? <span role="status">Please wait…</span> : children}
    </button>
  );
}
