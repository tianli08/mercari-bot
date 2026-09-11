"use client";

import { useEffect, useRef } from "react";

import {
  createThermalPrinter,
  loadImage,
  type ThermalPrintOptions,
} from "@/lib/thermal-print/shader";

export interface ThermalPrintProps {
  /** Image URL, data URL, or object URL. Cross-origin URLs need CORS headers. */
  src: string;
  /** Render size in CSS pixels. The canvas is backed at device pixel ratio. */
  width: number;
  height: number;
  options?: Partial<ThermalPrintOptions>;
  className?: string;
  style?: React.CSSProperties;
  /** Called with the canvas once a frame has been drawn, for exporting. */
  onRender?: (canvas: HTMLCanvasElement) => void;
}

/**
 * Renders `src` through the thermal receipt shader. Ink is drawn on a
 * transparent canvas by default, so place it over receipt paper with
 * `mix-blend-mode: multiply`, or pass `options.paper` to flatten.
 */
export function ThermalPrint({
  src,
  width,
  height,
  options,
  className,
  style,
  onRender,
}: ThermalPrintProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const optionsKey = JSON.stringify(options ?? {});

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const dpr = typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);

    let cancelled = false;
    let printer: ReturnType<typeof createThermalPrinter> | null = null;
    try {
      printer = createThermalPrinter(canvas);
    } catch {
      return;
    }

    loadImage(src)
      .then((image) => {
        if (cancelled || !printer) return;
        printer.render(image, JSON.parse(optionsKey));
        onRender?.(canvas);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
      printer?.destroy();
    };
  }, [src, width, height, optionsKey, onRender]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{ width, height, display: "block", ...style }}
      aria-hidden
    />
  );
}
