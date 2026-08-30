/** 活水墨背景(Living Ink Background)
    一幅永远「将干未干」的水墨画:
    - 第 2 层 · 远山墨意: 2 团大尺度淡墨晕染, 60~120s 浓度呼吸(0.04~0.08),
      形貌以 ≤3px/s 漂移, 极慢且不可逆——余光里的活气
    - 第 3 层 · 墨滴洇开: 事件触发(翻页落定/搜索提交/静置 45s)。
      3~5s 不规则洇开(噪声扰动半径+飞白断续+前快后慢), 峰值 opacity 0.12,
      20~30s 褪至 0.03「干透」并留存; 同屏最多 3 处, 第 4 滴落下时最旧的褪尽——
      页面因此有时间感, 每位用户看到的画都不同
    真假分水岭: 水线(最外圈略深的积墨细边) + 浓淡斑驳 + 只用淡墨/清墨两档。
    性能: 墨渍离屏预渲染, 每帧仅数个 drawImage; document.hidden 停帧;
    hardwareConcurrency ≤ 4 时远山静态化; reduced-motion 全静态。 */

// 墨分五色: 动态层只用淡墨与清墨, 焦墨重墨只属于文字
const INK_DAN = { r: 139, g: 139, b: 132 }; // 淡墨 #8B8B84
const INK_QING = { r: 216, g: 216, b: 208 }; // 清墨 #D8D8D0

const MAX_STAINS = 3;
const DROP_SPREAD_S = [3, 5] as const; // 洇开时长区间
const DROP_DRY_S = [20, 30] as const; // 褪淡至干透时长区间
const DROP_PEAK = 0.12;
const DROP_DRIED = 0.03;
const IDLE_DROP_MS = 45_000; // 久坐生墨

interface Wash {
  sprite: HTMLCanvasElement;
  anchorX: number; // 归一化锚点(视口比例)
  anchorY: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  scale: number;
  alpha: number;
  // 浓度呼吸: 两个不可约正弦 + 随机游走, 看不出周期
  p1: number; p2: number; f1: number; f2: number;
}

interface Drop {
  sprite: HTMLCanvasElement;
  x: number;
  y: number;
  bornAt: number;
  spreadS: number;
  dryS: number;
  maxR: number;
  evicting: boolean;
  evictAt: number;
}

let canvas: HTMLCanvasElement | null = null;
let ctx: CanvasRenderingContext2D | null = null;
let dpr = 1;
let vw = 0;
let vh = 0;
let washes: Wash[] = [];
let drops: Drop[] = [];
let raf = 0;
let running = false;
let lastFrame = 0;
let anchorEl: HTMLElement | null = null;
let lastActivity = 0;
let nextIdleDropAt = 0;
let reducedMotion = false;
let lowPower = false;

const rand = (a: number, b: number) => a + Math.random() * (b - a);

function rgba(c: typeof INK_DAN, a: number): string {
  return `rgba(${c.r},${c.g},${c.b},${a})`;
}

/* ---------------- 离屏预渲染: 形貌只生成一次 ---------------- */

/** 远山晕染: 极不规则的淡墨团(噪声扰动极坐标半径, 禁正圆) */
function makeWashSprite(): HTMLCanvasElement {
  const S = 520;
  const c = document.createElement("canvas");
  c.width = c.height = S;
  const g = c.getContext("2d")!;
  const cx = S / 2, cy = S / 2;
  const seed = Math.random() * 1000;
  const pts = 72;
  g.beginPath();
  for (let i = 0; i <= pts; i++) {
    const a = (i / pts) * Math.PI * 2;
    const n =
      Math.sin(a * 3 + seed) * 0.22 +
      Math.sin(a * 5 + seed * 1.7) * 0.12 +
      Math.sin(a * 9 + seed * 2.3) * 0.07;
    const r = S * 0.36 * (1 + n);
    const x = cx + Math.cos(a) * r;
    const y = cy + Math.sin(a) * r * 0.82; // 略扁, 像远山横卧
    if (i === 0) g.moveTo(x, y);
    else g.lineTo(x, y);
  }
  g.closePath();
  const grad = g.createRadialGradient(cx, cy, S * 0.04, cx, cy, S * 0.44);
  grad.addColorStop(0, rgba(INK_DAN, 1));
  grad.addColorStop(0.55, rgba(INK_DAN, 0.45));
  grad.addColorStop(1, rgba(INK_QING, 0));
  g.fillStyle = grad;
  g.fill();
  // 内部浓淡斑驳(10~15%)
  for (let i = 0; i < 9; i++) {
    const bx = cx + rand(-0.2, 0.2) * S;
    const by = cy + rand(-0.16, 0.16) * S;
    const br = rand(0.04, 0.1) * S;
    const bg = g.createRadialGradient(bx, by, 0, bx, by, br);
    const dark = Math.random() > 0.45;
    bg.addColorStop(0, rgba(dark ? INK_DAN : INK_QING, rand(0.15, 0.25)));
    bg.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = bg;
    g.fillRect(bx - br, by - br, br * 2, br * 2);
  }
  return c;
}

/** 墨滴: 不规则洇开体 + 水线积墨边 + 飞白断续 + 斑驳 */
function makeDropSprite(): HTMLCanvasElement {
  const S = 360;
  const c = document.createElement("canvas");
  c.width = c.height = S;
  const g = c.getContext("2d")!;
  const cx = S / 2, cy = S / 2;
  const seed = Math.random() * 1000;
  const pts = 96;
  // 主墨体: 各方向半径不等(噪声扰动), 前缘参差
  const path = new Path2D();
  for (let i = 0; i <= pts; i++) {
    const a = (i / pts) * Math.PI * 2;
    const n =
      Math.sin(a * 4 + seed) * 0.2 +
      Math.sin(a * 7 + seed * 1.3) * 0.13 +
      Math.sin(a * 13 + seed * 2.1) * 0.08 +
      Math.sin(a * 23 + seed * 3.7) * 0.04;
    const r = S * 0.34 * (1 + n);
    const x = cx + Math.cos(a) * r;
    const y = cy + Math.sin(a) * r;
    if (i === 0) path.moveTo(x, y);
    else path.lineTo(x, y);
  }
  path.closePath();
  const grad = g.createRadialGradient(cx, cy, S * 0.02, cx, cy, S * 0.42);
  grad.addColorStop(0, rgba(INK_DAN, 0.85));
  grad.addColorStop(0.6, rgba(INK_DAN, 0.5));
  grad.addColorStop(0.92, rgba(INK_DAN, 0.28));
  grad.addColorStop(1, rgba(INK_QING, 0.06));
  g.fillStyle = grad;
  g.fill(path);

  // 飞白: 沿边缘随机剜掉几个小缺口(纸纤维没吃到墨的地方)
  g.save();
  g.globalCompositeOperation = "destination-out";
  const gaps = 3 + Math.floor(Math.random() * 4);
  for (let i = 0; i < gaps; i++) {
    const a = rand(0, Math.PI * 2);
    const rr = S * 0.34 * rand(0.94, 1.06);
    const gx = cx + Math.cos(a) * rr;
    const gy = cy + Math.sin(a) * rr;
    const gr = rand(4, 14);
    g.beginPath();
    g.arc(gx, gy, gr, 0, Math.PI * 2);
    g.fillStyle = "rgba(0,0,0,0.75)";
    g.fill();
  }
  g.restore();

  // 水线: 最外圈一圈略深的细边(积墨线), 上屏后比中心高 0.01~0.02 —— 宣纸洇墨的标志
  g.save();
  g.globalAlpha = 0.95;
  g.strokeStyle = rgba(INK_DAN, 1);
  g.lineWidth = rand(1.4, 2.2);
  g.stroke(path);
  // 水线外侧一圈极淡的"水痕晕"
  g.globalAlpha = 0.12;
  g.lineWidth = rand(5, 9);
  g.stroke(path);
  g.restore();

  // 浓淡斑驳
  for (let i = 0; i < 11; i++) {
    const a = rand(0, Math.PI * 2);
    const rr = rand(0, 0.26) * S;
    const bx = cx + Math.cos(a) * rr;
    const by = cy + Math.sin(a) * rr;
    const br = rand(0.03, 0.08) * S;
    const bg = g.createRadialGradient(bx, by, 0, bx, by, br);
    bg.addColorStop(0, rgba(Math.random() > 0.4 ? INK_DAN : INK_QING, rand(0.15, 0.25)));
    bg.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = bg;
    g.fillRect(bx - br, by - br, br * 2, br * 2);
  }
  return c;
}

/* ---------------- 世界构建 ---------------- */

function makeWashes(): Wash[] {
  // 两团远山: 左上外缘 / 右下外缘, 活动范围约束在视口边缘(正文底层墨色 ≤0.04 不被突破)
  const defs = [
    { anchorX: 0.06, anchorY: 0.1, scale: rand(0.9, 1.2) },
    { anchorX: 0.94, anchorY: 0.9, scale: rand(1.0, 1.35) },
  ];
  return defs.map((d) => ({
    sprite: makeWashSprite(),
    anchorX: d.anchorX,
    anchorY: d.anchorY,
    x: 0,
    y: 0,
    vx: rand(-1.2, 1.2), // ≤3px/s 的漂移速度
    vy: rand(-0.9, 0.9),
    scale: d.scale,
    alpha: 0.05,
    p1: rand(0, Math.PI * 2),
    p2: rand(0, Math.PI * 2),
    f1: (Math.PI * 2) / rand(60, 120), // 60~120s 周期
    f2: (Math.PI * 2) / rand(37, 83), // 不可约的第二频率
  }));
}

function resize() {
  if (!canvas) return;
  dpr = Math.min(window.devicePixelRatio || 1, 2);
  vw = window.innerWidth;
  vh = window.innerHeight;
  canvas.width = Math.floor(vw * dpr);
  canvas.height = Math.floor(vh * dpr);
  canvas.style.width = `${vw}px`;
  canvas.style.height = `${vh}px`;
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
  // 远山初始位置落在锚点附近
  for (const w of washes) {
    if (!w.x && !w.y) {
      w.x = w.anchorX * vw;
      w.y = w.anchorY * vh;
    }
  }
}

/* ---------------- 墨滴 ---------------- */

/** 落点: 避开内容区(书本 rect 外扩), 偏向书页边缘的留白带 */
function pickDropPoint(maxR: number): { x: number; y: number } {
  let excl: DOMRect | null = null;
  if (anchorEl) {
    const r = anchorEl.getBoundingClientRect();
    // 墨滴中心至少离书本边缘 maxR*0.35, 保证墨体不压正文
    const m = maxR * 0.35;
    excl = new DOMRect(r.left - m, r.top - m, r.width + m * 2, r.height + m * 2);
  }
  const inExcl = (x: number, y: number) =>
    excl && x > excl.left && x < excl.right && y > excl.top && y < excl.bottom;

  // 60% 落在书页四周的页缘带(向外 20~150px), 40% 落在视口边缘
  for (let tries = 0; tries < 50; tries++) {
    let x = 0, y = 0;
    if (anchorEl && Math.random() < 0.6) {
      const r = anchorEl.getBoundingClientRect();
      const side = Math.floor(rand(0, 4));
      const off = rand(30, 110);
      if (side === 0) { x = rand(r.left, r.right); y = r.top - off; }
      else if (side === 1) { x = rand(r.left, r.right); y = r.bottom + off; }
      else if (side === 2) { x = r.left - off; y = rand(r.top, r.bottom); }
      else { x = r.right + off; y = rand(r.top, r.bottom); }
    } else {
      const edge = Math.floor(rand(0, 4));
      const off = rand(24, Math.min(vw, vh) * 0.16);
      if (edge === 0) { x = rand(0, vw); y = off; }
      else if (edge === 1) { x = rand(0, vw); y = vh - off; }
      else if (edge === 2) { x = off; y = rand(0, vh); }
      else { x = vw - off; y = rand(0, vh); }
    }
    if (x < 40 || x > vw - 40 || y < 76 || y > vh - 40) continue; // y≥76: 避开固定头部遮挡
    if (!inExcl(x, y)) return { x, y };
  }
  // 兜底: 四个角挑一个不在排除区的
  const corners = [
    { x: 70, y: 110 },
    { x: vw - 70, y: 110 },
    { x: 70, y: vh - 90 },
    { x: vw - 70, y: vh - 90 },
  ];
  return corners.find((c) => !inExcl(c.x, c.y)) ?? corners[0];
}

/** 在宣纸边缘落一滴墨(翻页落定 / 搜索提交 / 久坐生墨时调用) */
export function inkDrop() {
  if (!ctx) return;
  const maxR = rand(85, 155);
  const p = pickDropPoint(maxR);
  const now = performance.now();
  drops.push({
    sprite: makeDropSprite(),
    x: p.x,
    y: p.y,
    bornAt: now,
    spreadS: rand(DROP_SPREAD_S[0], DROP_SPREAD_S[1]),
    dryS: rand(DROP_DRY_S[0], DROP_DRY_S[1]),
    maxR,
    evicting: false,
    evictAt: 0,
  });
  // 同屏最多 3 处墨渍, 第 4 滴落下时最旧的继续褪至消失
  const alive = drops.filter((d) => !d.evicting);
  if (alive.length > MAX_STAINS) {
    const oldest = alive[0];
    oldest.evicting = true;
    oldest.evictAt = now;
  }
  start();
}

/* ---------------- 帧循环 ---------------- */

function dropAlpha(d: Drop, now: number): number {
  const age = (now - d.bornAt) / 1000;
  if (d.evicting) {
    // 褪尽: 8s 从当前浓度降到 0
    const t = Math.min(1, (now - d.evictAt) / 8000);
    return Math.max(0, DROP_DRIED * (1 - t));
  }
  if (age < d.spreadS) {
    // 洇开期: 浓度随半径一起到达峰值
    const t = age / d.spreadS;
    return DROP_PEAK * Math.min(1, t * 1.5);
  }
  const dt = age - d.spreadS;
  if (dt < d.dryS) {
    // 褪淡期: 20~30s 缓降至「干透」
    return DROP_PEAK + (DROP_DRIED - DROP_PEAK) * (dt / d.dryS);
  }
  return DROP_DRIED; // 干透留存
}

function draw(now: number) {
  if (!ctx) return;
  const dt = Math.min(0.1, (now - lastFrame) / 1000);
  lastFrame = now;
  ctx.clearRect(0, 0, vw, vh);

  // 第 2 层 · 远山墨意
  for (const w of washes) {
    if (!lowPower && !reducedMotion) {
      // ≤3px/s 漂移, 锚点附近 6vw 内折返
      w.x += w.vx * dt;
      w.y += w.vy * dt;
      const ax = w.anchorX * vw, ay = w.anchorY * vh;
      const range = vw * 0.06;
      if (Math.abs(w.x - ax) > range) w.vx *= -1;
      if (Math.abs(w.y - ay) > range * 0.7) w.vy *= -1;
      w.vx += rand(-0.06, 0.06); // 随机扰动, 不可逆不循环
      w.vy += rand(-0.05, 0.05);
      w.vx = Math.max(-2.6, Math.min(2.6, w.vx));
      w.vy = Math.max(-2.2, Math.min(2.2, w.vy));
      // 浓度呼吸: 双正弦不可约叠加 + 随机游走, 0.04~0.08
      const t = now / 1000;
      const wave = Math.sin(t * w.f1 + w.p1) * 0.6 + Math.sin(t * w.f2 + w.p2) * 0.4;
      w.alpha = 0.06 + wave * 0.02;
    }
    const size = Math.min(vw, vh) * 0.85 * w.scale;
    ctx.globalAlpha = Math.max(0.04, Math.min(0.08, w.alpha));
    ctx.drawImage(w.sprite, w.x - size / 2, w.y - size / 2, size, size);
  }

  // 第 3 层 · 墨滴洇开
  for (const d of drops) {
    const age = (now - d.bornAt) / 1000;
    const alpha = dropAlpha(d, now);
    // 扩散半径: ease-out 前快后慢; reduced-motion 瞬间到位
    const t = reducedMotion ? 1 : Math.min(1, age / d.spreadS);
    const eased = 1 - Math.pow(1 - t, 3);
    const r = d.maxR * (0.25 + 0.75 * eased);
    ctx.globalAlpha = alpha;
    ctx.drawImage(d.sprite, d.x - r, d.y - r, r * 2, r * 2);
  }
  // 褪尽的墨渍移除
  drops = drops.filter((d) => !(d.evicting && dropAlpha(d, now) <= 0.001));

  ctx.globalAlpha = 1;

  // 久坐生墨: 静置 45s 自动洇一滴, 之后每 45s+随机再续
  if (now > nextIdleDropAt && !document.hidden) {
    nextIdleDropAt = now + IDLE_DROP_MS + rand(0, 15_000);
    inkDrop();
  }

  // 全部静止时收帧节能: 没有动的东西就停
  const dropsActive = drops.some((d) => !d.evicting && (now - d.bornAt) / 1000 < d.spreadS + d.dryS);
  const washesActive = !lowPower && !reducedMotion;
  if (washesActive || dropsActive || drops.length) {
    raf = requestAnimationFrame(draw);
  } else {
    running = false;
  }
}

function start() {
  if (!running && !document.hidden) {
    running = true;
    lastFrame = performance.now();
    raf = requestAnimationFrame(draw);
  }
}

function onVisibility() {
  if (document.hidden) {
    cancelAnimationFrame(raf);
    running = false;
  } else {
    start();
  }
}

function onActivity() {
  lastActivity = performance.now();
  nextIdleDropAt = lastActivity + IDLE_DROP_MS + rand(0, 15_000);
}

/** 书本元素: 落点算法读取它的 bounding box 避开内容区 */
export function setInkAnchor(el: HTMLElement | null) {
  anchorEl = el;
}

/** 初始化活水墨背景。幂等。 */
export function initInkBackground(el: HTMLCanvasElement) {
  if (canvas) return;
  canvas = el;
  ctx = canvas.getContext("2d");
  if (!ctx) return;
  reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  lowPower = (navigator.hardwareConcurrency ?? 8) <= 4;
  washes = makeWashes();
  resize();
  window.addEventListener("resize", resize);
  document.addEventListener("visibilitychange", onVisibility);
  for (const ev of ["pointermove", "keydown", "scroll", "pointerdown"] as const) {
    window.addEventListener(ev, onActivity, { passive: true });
  }
  onActivity();
  start();
  // 开卷落墨: 首屏 splash 落幕后连续洇开两滴, 让"这页纸是活的"立刻可感
  window.setTimeout(() => inkDrop(), 1400);
  window.setTimeout(() => inkDrop(), 3400);
  // 调试探针(只读): 验收时检查墨渍生命周期
  (window as unknown as { __ink: unknown }).__ink = {
    stats: () => ({
      drops: drops.map((d) => ({
        x: Math.round(d.x),
        y: Math.round(d.y),
        ageS: Math.round((performance.now() - d.bornAt) / 100) / 10,
        alpha: Math.round(dropAlpha(d, performance.now()) * 1000) / 1000,
        evicting: d.evicting,
      })),
      washes: washes.map((w) => ({ x: Math.round(w.x), y: Math.round(w.y), a: Math.round(w.alpha * 1000) / 1000 })),
      running,
      lowPower,
      reducedMotion,
    }),
  };
}
