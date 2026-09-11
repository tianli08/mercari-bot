"use client";

import { useEffect } from "react";

const DURATION_MS = 360;

// Ease-out cubic: fast start, gentle landing.
const ease = (t: number) => 1 - Math.pow(1 - t, 3);

/**
 * Intercepts clicks on same-page `#hash` links and scrolls to the target with
 * a short eased animation. Honours the target's `scroll-margin-top` and falls
 * back to an instant jump under `prefers-reduced-motion`.
 */
export function SnappyAnchors() {
  useEffect(() => {
    let frame = 0;

    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

      const anchor = (event.target as Element | null)?.closest<HTMLAnchorElement>('a[href^="#"]');
      if (!anchor) return;
      const id = decodeURIComponent(anchor.getAttribute("href")!.slice(1));
      if (!id) return;
      const target = document.getElementById(id);
      if (!target) return;

      event.preventDefault();
      cancelAnimationFrame(frame);

      const margin = parseFloat(getComputedStyle(target).scrollMarginTop) || 0;
      const from = window.scrollY;
      const max = document.documentElement.scrollHeight - window.innerHeight;
      const to = Math.min(max, target.getBoundingClientRect().top + from - margin);

      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        window.scrollTo(0, to);
        history.pushState(null, "", `#${id}`);
        return;
      }

      const start = performance.now();
      const step = (now: number) => {
        const t = Math.min(1, (now - start) / DURATION_MS);
        window.scrollTo(0, from + (to - from) * ease(t));
        if (t < 1) {
          frame = requestAnimationFrame(step);
        } else {
          history.pushState(null, "", `#${id}`);
        }
      };
      frame = requestAnimationFrame(step);
    };

    document.addEventListener("click", onClick);
    return () => {
      document.removeEventListener("click", onClick);
      cancelAnimationFrame(frame);
    };
  }, []);

  return null;
}
