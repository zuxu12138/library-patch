/** 书的上下文: 章节注册表 + 翻页计数 + 翻页音效(默认关闭, 偏好持久化)。
    四个模块中「论文摘要」装订在知识地图一章内, 全书共三章。 */
import { ref } from "vue";

export interface Chapter {
  path: string;
  index: number;
  no: string;      // 眉线编号 "01"
  cn: string;      // 章节中文名
  en: string;      // 眉线英文小字
  numeral: string; // 页码罗马数字
}

export const CHAPTERS: Chapter[] = [
  { path: "/findbook", index: 0, no: "01", cn: "找书", en: "FIND A BOOK", numeral: "Ⅰ" },
  { path: "/knowledge", index: 1, no: "02", cn: "知识地图", en: "CITATION ATLAS", numeral: "Ⅱ" },
  { path: "/seat", index: 2, no: "03", cn: "座位预测", en: "SEAT FORECAST", numeral: "Ⅲ" },
];

export const TOTAL_NUMERAL = "Ⅲ";

export function chapterFor(path: string): Chapter | null {
  return CHAPTERS.find((c) => c.path === path) ?? null;
}

export function neighborOf(path: string, delta: 1 | -1): Chapter | null {
  const cur = chapterFor(path);
  if (!cur) return null;
  return CHAPTERS[cur.index + delta] ?? null;
}

/** 已完成的翻页次数: App 用它触发「可开启翻页音效」的一次性提示 */
export const flipCount = ref(0);

/** 翻页锁: 翻页进行的 700ms 内禁止再触发导航(头部 nav 也据此禁用) */
export const flipLock = ref(false);

export function noteFlip() {
  flipCount.value++;
  playFlipSound();
}

/* ---------- 翻页音效: WebAudio 合成纸张摩擦声, 音量 ≤ -20dB ---------- */

export type SoundPref = "on" | "off" | "unset";

const stored = typeof localStorage !== "undefined" ? localStorage.getItem("lp-flip-sound") : null;
export const soundPref = ref<SoundPref>(stored === "on" || stored === "off" ? stored : "unset");

export function setSoundPref(p: SoundPref) {
  soundPref.value = p;
  try {
    localStorage.setItem("lp-flip-sound", p);
  } catch {
    /* 隐私模式下静默 */
  }
}

let audioCtx: AudioContext | null = null;

export function playFlipSound() {
  if (soundPref.value !== "on") return;
  try {
    audioCtx ??= new AudioContext();
    const ctx = audioCtx;
    if (ctx.state === "suspended") void ctx.resume();
    const dur = 0.34;
    const buffer = ctx.createBuffer(1, Math.floor(ctx.sampleRate * dur), ctx.sampleRate);
    const data = buffer.getChannelData(0);
    // 衰减噪声: 前段密(纸离脊), 后段疏(纸落桌)
    for (let i = 0; i < data.length; i++) {
      const t = i / data.length;
      data[i] = (Math.random() * 2 - 1) * (1 - t) * (0.35 + 0.65 * Math.sin(t * Math.PI));
    }
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    const filter = ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.setValueAtTime(3200, ctx.currentTime);
    filter.frequency.exponentialRampToValueAtTime(1400, ctx.currentTime + dur);
    filter.Q.value = 0.9;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.055, ctx.currentTime + 0.05); // ≈ -25dB
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + dur);
    src.connect(filter);
    filter.connect(gain);
    gain.connect(ctx.destination);
    src.start();
  } catch {
    /* 无音频环境时静默 */
  }
}
