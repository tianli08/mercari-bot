"use client";

import { useEffect, useRef, useState } from "react";

import { tintClass } from "@/components/marketing/Sheet";
import type { ReceiptFrame } from "@/lib/marketing-content";
import {
  createThermalPrinter,
  loadImage,
  type ThermalPrintOptions,
} from "@/lib/thermal-print/shader";

const HERO_SIZE = 680;
const STRIP_SIZE = 160;
const FRAME_MS = 300;

const PRINT_OPTIONS: Partial<ThermalPrintOptions> = {
  grain: 1.6,
  contrast: 1.35,
  brightness: 0.02,
  bleed: 0.8,
  softness: 0.12,
  dropout: 0.12,
  streak: 0.18,
  mode: "noise",
  ink: "#1c1a17",
};

/**
 * Print every frame once through the shader on one hidden WebGL canvas and
 * hand back data URLs, so the page never holds more than one GL context.
 */
function useThermalPrints(frames: readonly ReceiptFrame[], size: number) {
  const [prints, setPrints] = useState<string[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    const canvas = document.createElement("canvas");
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(size * dpr);
    canvas.height = Math.round(size * dpr);
    // The shader scales grain by canvas.width / clientWidth; give it a CSS size.
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;

    let printer: ReturnType<typeof createThermalPrinter>;
    try {
      printer = createThermalPrinter(canvas);
    } catch {
      return;
    }

    (async () => {
      const out: string[] = [];
      for (let i = 0; i < frames.length; i++) {
        try {
          const image = await loadImage(frames[i].image);
          if (cancelled) return;
          printer.render(image, { ...PRINT_OPTIONS, seed: 7 + i * 11 });
          out.push(canvas.toDataURL("image/png"));
        } catch {
          out.push("");
        }
      }
      if (!cancelled) setPrints(out);
    })();

    return () => {
      cancelled = true;
      printer.destroy();
    };
  }, [frames, size]);

  return prints;
}

function ReceiptUnderPrint({ frame, scale }: { frame: ReceiptFrame; scale: number }) {
  const fs = 18 * scale;
  return (
    <div
      className="ink font-jp absolute"
      style={{
        left: `${9}%`,
        right: `${9}%`,
        top: frame.offset * scale,
        fontSize: fs,
        lineHeight: 1.35,
      }}
    >
      <div className="text-center" style={{ fontSize: fs * 1.35, letterSpacing: "0.06em" }}>
        <span className="tall" style={{ transformOrigin: "top center" }}>{frame.shop}</span>
      </div>
      <div className="text-center text-ink-dim" style={{ fontSize: fs * 0.8, lineHeight: 1.4 }}>
        {frame.address}
        <br />
        TEL 03-0000-0000
        <br />
        {frame.datetime} {frame.register}
      </div>
      <div className="dashes" style={{ fontSize: fs * 0.9, height: fs }}>
        {"-".repeat(60)}
      </div>
      {frame.items.map(([name, price]) => (
        <div key={name} className="flex justify-between gap-3">
          <span>{name}</span>
          <span>{price}</span>
        </div>
      ))}
      <div className="dashes" style={{ fontSize: fs * 0.9, height: fs }}>
        {"-".repeat(60)}
      </div>
      <div className="flex justify-between gap-3">
        <span>小　計（税抜 8%）</span>
        <span>{frame.total}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>消費税等（ 8%）</span>
        <span>{frame.tax}</span>
      </div>
      <div className="flex justify-between gap-3" style={{ fontSize: fs * 1.45, margin: "2px 0" }}>
        <span className="tall">合　計</span>
        <span className="tall">{frame.total}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>（内消費税等 8%）</span>
        <span>—</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>クレジット支払</span>
        <span>{frame.total}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>お買上明細</span>
        <span />
      </div>
      <div className="text-ink-dim" style={{ fontSize: fs * 0.8, marginTop: 6 * scale }}>
        [*]マークは軽減税率対象商品です。
      </div>
      <div className="dashes" style={{ fontSize: fs * 0.9, height: fs }}>
        {"-".repeat(60)}
      </div>
      <div className="flex justify-between gap-3">
        <span>ご利用日</span>
        <span>{frame.datetime.slice(0, 11)}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>会員番号</span>
        <span>{frame.member}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>支払方法　1回CL</span>
        <span>承認番号 {frame.approval}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>金額</span>
        <span>{frame.total}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span>伝票番号</span>
        <span>{frame.slip}</span>
      </div>
      <div
        className="font-barcode text-center leading-none"
        style={{ fontSize: fs * 3.6, marginTop: 8 * scale }}
        aria-hidden
      >
        {`SA${frame.slip.replace(/-/g, "").slice(0, 8)}`}
      </div>
      <div className="text-center text-ink-dim" style={{ fontSize: fs * 0.8, marginTop: 8 * scale }}>
        またのご来店をお待ちしております
      </div>
    </div>
  );
}

function ScannedFrame({
  frame,
  print,
  size,
  index,
}: {
  frame: ReceiptFrame;
  print: string | null;
  size: number;
  index: number;
}) {
  const scale = size / HERO_SIZE;
  return (
    <div
      className={`sheet relative overflow-hidden ${tintClass(frame.tint)}`}
      style={{ width: size, height: size }}
    >
      <ReceiptUnderPrint frame={frame} scale={scale} />
      {print ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={print}
          alt=""
          width={size}
          height={size}
          className="absolute inset-0 block"
          style={{ width: size, height: size, mixBlendMode: "multiply" }}
          draggable={false}
        />
      ) : null}
      <span className="sr-only">Frame {index + 1}</span>
    </div>
  );
}

export function ReceiptHero({
  frames,
  loopLabel,
}: {
  frames: readonly ReceiptFrame[];
  loopLabel: string;
}) {
  const prints = useThermalPrints(frames, HERO_SIZE);
  const [current, setCurrent] = useState(0);
  const heroRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const el = heroRef.current;
    if (!el) return;
    const update = () => setScale(Math.min(1, el.clientWidth / HERO_SIZE));
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!prints) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(
      () => setCurrent((c) => (c + 1) % frames.length),
      FRAME_MS,
    );
    return () => window.clearInterval(id);
  }, [prints, frames.length]);

  if (frames.length === 0) return null;

  return (
    <div ref={heroRef} className="relative w-full max-w-[680px]">
      <div className="aspect-square w-full overflow-hidden">
        <div
          className="origin-top-left"
          style={{ width: HERO_SIZE, height: HERO_SIZE, transform: `scale(${scale})` }}
        >
          <ScannedFrame
            frame={frames[current % frames.length]}
            print={prints ? prints[current % frames.length] : null}
            size={HERO_SIZE}
            index={current % frames.length}
          />
        </div>
      </div>
      <div className="mt-3 text-[11px] uppercase tracking-[0.16em] text-ink-dim">{loopLabel}</div>
    </div>
  );
}

export function ReceiptStrip({ frames }: { frames: readonly ReceiptFrame[] }) {
  const prints = useThermalPrints(frames, STRIP_SIZE);
  if (frames.length === 0) return null;
  return (
    <section aria-label="All frames">
      <div className="flex gap-5 overflow-x-auto pb-2 pt-1">
        {frames.map((frame, i) => (
          <div
            key={frame.image}
            className="shrink-0"
            style={{ transform: `rotate(${[-1.5, 1, -0.5, 1.5, -1, 0.5, -1.5, 1][i % 8]}deg)` }}
          >
            <ScannedFrame
              frame={frame}
              print={prints ? prints[i] : null}
              size={STRIP_SIZE}
              index={i}
            />
          </div>
        ))}
      </div>
    </section>
  );
}
