// Thermal receipt print shader.
//
// Takes any image and renders it the way a cheap thermal printer would put it
// on receipt paper: 1-bit ink, noisy or ordered dither, soft bleed where the
// head overheats, dropout lines where it misses, and uneven density down the
// roll. Output is ink-on-transparent so it can sit over a paper texture with
// `mix-blend-mode: multiply`, or be flattened onto a paper colour.

export type DitherMode = "noise" | "bayer" | "mixed";

export interface ThermalPrintOptions {
  /** Size of one dither cell in CSS pixels. Bigger reads as a coarser printer. */
  grain: number;
  /** Contrast applied to the source luminance before thresholding. */
  contrast: number;
  /** Brightness offset in [-1, 1]. Negative prints darker. */
  brightness: number;
  /** Blur radius in source texels before thresholding. Softens edges like ink bleed. */
  bleed: number;
  /** Width of the threshold ramp. 0 is hard 1-bit; higher gives greyer, fuzzier ink. */
  softness: number;
  /** Fraction of rows that print faint or not at all, like a worn head. */
  dropout: number;
  /** Low-frequency density variation down the roll. */
  streak: number;
  /** Dither pattern. */
  mode: DitherMode;
  /** Seed for the noise so different frames get different grain. */
  seed: number;
  /** Ink colour as CSS hex. */
  ink: string;
  /** Invert the source before printing. */
  invert: boolean;
  /** Paper colour as CSS hex, or null to output ink on transparent. */
  paper: string | null;
}

export const DEFAULT_OPTIONS: ThermalPrintOptions = {
  grain: 1.6,
  contrast: 1.35,
  brightness: 0.02,
  bleed: 0.8,
  softness: 0.12,
  dropout: 0.12,
  streak: 0.18,
  mode: "noise",
  seed: 7,
  ink: "#1c1a17",
  invert: false,
  paper: null,
};

const VERTEX_SHADER = `#version 300 es
in vec2 aPos;
out vec2 vUv;
uniform vec2 uUvScale;
uniform vec2 uUvOffset;
void main() {
  vUv = (aPos * 0.5 + 0.5) * uUvScale + uUvOffset;
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

const FRAGMENT_SHADER = `#version 300 es
precision highp float;
in vec2 vUv;
out vec4 outColor;

uniform sampler2D uImage;
uniform float uGrain;
uniform float uContrast;
uniform float uBrightness;
uniform float uBleed;
uniform float uSoftness;
uniform float uDropout;
uniform float uStreak;
uniform float uMode;
uniform float uSeed;
uniform vec3 uInk;
uniform float uInvert;
uniform vec3 uPaper;
uniform float uHasPaper;

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float vnoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float bayer4(vec2 p) {
  ivec2 i = ivec2(mod(p, 4.0));
  int m[16] = int[](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5);
  return (float(m[i.y * 4 + i.x]) + 0.5) / 16.0;
}

float luma(vec3 c) {
  return dot(c, vec3(0.299, 0.587, 0.114));
}

float sampleLuma(vec2 uv) {
  vec4 c = texture(uImage, uv);
  // Treat transparent source pixels as paper (white), so cut-outs print clean.
  return mix(1.0, luma(c.rgb), c.a);
}

void main() {
  vec2 px = gl_FragCoord.xy;
  vec2 texel = 1.0 / vec2(textureSize(uImage, 0));

  // Bleed: a small weighted blur before thresholding.
  float l = 0.0;
  float wsum = 0.0;
  for (int y = -1; y <= 1; y++) {
    for (int x = -1; x <= 1; x++) {
      float w = (x == 0 && y == 0) ? 2.0 : 1.0;
      l += sampleLuma(vUv + vec2(float(x), float(y)) * texel * uBleed) * w;
      wsum += w;
    }
  }
  l /= wsum;
  if (uInvert > 0.5) l = 1.0 - l;

  l = (l - 0.5) * uContrast + 0.5 + uBrightness;

  // Uneven density down the roll.
  l += (vnoise(vec2(px.y * 0.012, uSeed * 1.7)) - 0.5) * uStreak;

  // Dither threshold.
  vec2 cell = floor(px / uGrain);
  float nz = hash(cell + uSeed);
  float by = bayer4(cell);
  float n = uMode < 0.5 ? nz : (uMode < 1.5 ? by : mix(nz, by, 0.5));

  // Ink where the source is darker than the threshold, with a soft ramp.
  float ink = 1.0 - smoothstep(-uSoftness, uSoftness, l - n);

  // Dropout: whole rows print faint where the head missed.
  float rowHash = hash(vec2(floor(px.y), uSeed * 3.1));
  float missed = step(1.0 - uDropout * 0.18, rowHash);
  ink *= 1.0 - missed * 0.85;

  if (uHasPaper > 0.5) {
    outColor = vec4(mix(uPaper, uInk, ink), 1.0);
  } else {
    outColor = vec4(uInk, ink);
  }
}`;

export interface ThermalPrinter {
  /** Draw `image` through the shader, cover-fitted to the canvas. */
  render(
    image: TexImageSource & { width: number; height: number },
    options?: Partial<ThermalPrintOptions>,
  ): void;
  /** Release the GL context. */
  destroy(): void;
}

function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace("#", "");
  const full =
    clean.length === 3
      ? clean
          .split("")
          .map((c) => c + c)
          .join("")
      : clean;
  const n = parseInt(full, 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

function compile(gl: WebGL2RenderingContext, type: number, src: string) {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("Could not create shader");
  gl.shaderSource(shader, src);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    throw new Error(`Shader compile failed: ${log}`);
  }
  return shader;
}

/**
 * Create a thermal printer bound to a canvas. Reuse it across renders; each
 * `render` re-uploads the image and redraws with the given options.
 */
export function createThermalPrinter(canvas: HTMLCanvasElement): ThermalPrinter {
  const gl = canvas.getContext("webgl2", {
    premultipliedAlpha: false,
    alpha: true,
    antialias: false,
    preserveDrawingBuffer: true,
  });
  if (!gl) throw new Error("WebGL2 is not available");
  if (gl.isContextLost()) {
    gl.getExtension("WEBGL_lose_context")?.restoreContext();
  }

  const program = gl.createProgram();
  if (!program) throw new Error("Could not create program");
  gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, VERTEX_SHADER));
  gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(`Program link failed: ${gl.getProgramInfoLog(program)}`);
  }
  gl.useProgram(program);

  // Fullscreen triangle.
  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 3, -1, -1, 3]),
    gl.STATIC_DRAW,
  );
  const aPos = gl.getAttribLocation(program, "aPos");
  gl.enableVertexAttribArray(aPos);
  gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

  const texture = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

  const u = (name: string) => gl.getUniformLocation(program, name);
  const loc = {
    uvScale: u("uUvScale"),
    uvOffset: u("uUvOffset"),
    image: u("uImage"),
    grain: u("uGrain"),
    contrast: u("uContrast"),
    brightness: u("uBrightness"),
    bleed: u("uBleed"),
    softness: u("uSoftness"),
    dropout: u("uDropout"),
    streak: u("uStreak"),
    mode: u("uMode"),
    seed: u("uSeed"),
    ink: u("uInk"),
    invert: u("uInvert"),
    paper: u("uPaper"),
    hasPaper: u("uHasPaper"),
  };

  const modeIndex: Record<DitherMode, number> = { noise: 0, bayer: 1, mixed: 2 };

  return {
    render(image, overrides) {
      const o = { ...DEFAULT_OPTIONS, ...overrides };
      const dpr = canvas.width / Math.max(1, canvas.clientWidth || canvas.width);

      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.useProgram(program);
      gl.bindVertexArray(vao);

      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
      gl.uniform1i(loc.image, 0);

      // Cover-fit the image to the canvas.
      const canvasAspect = canvas.width / canvas.height;
      const imageAspect = image.width / image.height;
      let scaleX = 1;
      let scaleY = 1;
      if (imageAspect > canvasAspect) {
        scaleX = canvasAspect / imageAspect;
      } else {
        scaleY = imageAspect / canvasAspect;
      }
      gl.uniform2f(loc.uvScale, scaleX, scaleY);
      gl.uniform2f(loc.uvOffset, (1 - scaleX) / 2, (1 - scaleY) / 2);

      gl.uniform1f(loc.grain, Math.max(0.5, o.grain) * dpr);
      gl.uniform1f(loc.contrast, o.contrast);
      gl.uniform1f(loc.brightness, o.brightness);
      gl.uniform1f(loc.bleed, o.bleed);
      gl.uniform1f(loc.softness, Math.max(0.001, o.softness));
      gl.uniform1f(loc.dropout, o.dropout);
      gl.uniform1f(loc.streak, o.streak);
      gl.uniform1f(loc.mode, modeIndex[o.mode]);
      gl.uniform1f(loc.seed, o.seed);
      gl.uniform3f(loc.ink, ...hexToRgb(o.ink));
      gl.uniform1f(loc.invert, o.invert ? 1 : 0);
      const paper = o.paper ? hexToRgb(o.paper) : [1, 1, 1];
      gl.uniform3f(loc.paper, paper[0], paper[1], paper[2]);
      gl.uniform1f(loc.hasPaper, o.paper ? 1 : 0);

      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    },
    destroy() {
      gl.deleteTexture(texture);
      gl.deleteBuffer(buffer);
      gl.deleteVertexArray(vao);
      gl.deleteProgram(program);
      // Do not lose the context here: React re-runs effects in development,
      // and a canvas whose context was lost cannot hand out a new one.
    },
  };
}

/** Load an image URL as an element ready for the printer. */
export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Could not load image: ${src}`));
    img.src = src;
  });
}
