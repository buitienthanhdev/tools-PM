/**
 * Reviewing CV — chấm CV theo tin tuyển dụng bằng bộ quy tắc của
 * MadsLorentzen/ai-job-search (backend: modules/reviewingcv, API /api/cv/*).
 * Giao diện tự chứa: CSS gói trong lớp .rcv, chèn một lần vào <head>.
 */

import { eventBus } from '../../stores/eventBus.js';
import { pageHero } from '../../components/pageHero.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const toast = (message, type = 'info') => eventBus.emit('toast:show', { message, type });

// Icon nét mảnh (theo phong cách Lucide), dùng currentColor.
const ICON = {
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  spark: '<path d="M12 3l1.9 5.8L20 10.7l-6.1 1.9L12 18.5l-1.9-5.9L4 10.7l6.1-1.9z"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M8 16H3v5"/>',
  arrow: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  briefcase: '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
  plus: '<path d="M12 5v14"/><path d="M5 12h14"/>',
};
const ic = (name, size = 18) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON[name]}</svg>`;

const DIMS = [
  ['technical', 'Kỹ năng chuyên môn', 30],
  ['experience', 'Kinh nghiệm', 25],
  ['behavioral', 'Văn hóa & hành vi', 15],
  ['career', 'Định hướng nghề nghiệp', 30],
];
const GATE = {
  PASS: ['ok', 'Đạt'], FAIL: ['bad', 'Không đạt'], FLAG: ['warn', 'Cần lưu ý'],
  UNVERIFIED: ['warn', 'Chưa xác minh'], UNKNOWN: ['muted', 'Chưa rõ'],
};
const REASON = { keyword: 'Từ khóa', reframing: 'Diễn đạt lại', style: 'Văn phong', grounding: 'Sai dữ kiện', structure: 'Cấu trúc' };
const TONE_COLOR = { ok: '#34d399', good: '#4ade80', warn: '#fbbf24', bad: '#f87171' };
const tone = (n) => (n >= 75 ? 'ok' : n >= 60 ? 'good' : n >= 45 ? 'warn' : 'bad');
const LOADING_STEPS = ['Đọc CV', 'Đối chiếu yêu cầu', 'Chấm điểm', 'Viết đề xuất'];

const STYLE_ID = 'rcv-style';
const CSS = `
.rcv{--bg:#0f0f0f;--card:#161616;--card-2:#1c1c1c;--line:rgba(255,255,255,.09);--line-2:rgba(255,255,255,.16);
  --ink:#ffffff;--sub:rgba(255,255,255,.66);--mute:rgba(255,255,255,.4);--acc:#fd5b38;--acc-2:#ff7a5c;--acc-soft:rgba(253,91,56,.12);
  --ok:#34d399;--ok-bg:rgba(52,211,153,.1);--good:#4ade80;--warn:#fbbf24;--warn-bg:rgba(251,191,36,.1);--bad:#f87171;--bad-bg:rgba(248,113,113,.1);
  max-width:1240px;margin:0 auto;width:100%;color:var(--ink);font-family:"Plus Jakarta Sans",Inter,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
.rcv *{box-sizing:border-box}
.rcv [hidden]{display:none!important}
.rcv button{font-family:inherit}
.rcv a{color:var(--sub)}
.rcv-hero{position:relative;overflow:hidden;border:1px solid var(--line);border-radius:14px;padding:3.2rem 3rem 6.5rem;margin-bottom:1.5rem;
  background:radial-gradient(60% 90% at 85% 10%,rgba(91,33,182,.55),transparent 60%),radial-gradient(55% 80% at 55% 45%,rgba(159,18,57,.55),transparent 65%),radial-gradient(60% 90% at 5% 100%,rgba(133,77,14,.55),transparent 60%),#120d10}
.rcv-hero::after{content:"";position:absolute;inset:0;pointer-events:none;opacity:.18;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.6'/%3E%3C/svg%3E")}
.rcv-hero-in{position:relative;z-index:1;display:flex;justify-content:space-between;align-items:flex-end;gap:2rem;flex-wrap:wrap}
.rcv-eyebrow{display:block;font-size:.8rem;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--acc)}
.rcv-hero h1{font-size:clamp(2.2rem,4.6vw,3.9rem);line-height:1.12;font-weight:600;letter-spacing:-.02em;margin:.9rem 0 1.1rem;max-width:820px}
.rcv-hero h1 .thin{font-weight:200}
.rcv-hero p{color:var(--sub);font-size:1.02rem;max-width:560px;line-height:1.7;margin:0}
.rcv-outline{position:absolute;right:1.5rem;bottom:-2.6rem;font-size:clamp(5rem,15vw,12.5rem);font-weight:800;line-height:1;color:transparent;-webkit-text-stroke:1.5px rgba(255,255,255,.14);letter-spacing:-.03em;pointer-events:none;white-space:nowrap;user-select:none}
.rcv-trust{display:flex;flex-wrap:wrap;gap:.6rem 1.6rem;width:100%}
.rcv-trust span{display:inline-flex;align-items:center;gap:.55rem;font-size:.85rem;color:var(--sub)}
.rcv-trust svg{color:var(--acc)}
.rcv-card{background:var(--card);border:1px solid var(--line);border-radius:14px}
.rcv-grid{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}
@media (max-width:900px){.rcv-grid{grid-template-columns:1fr}.rcv-hero{padding:2.2rem 1.5rem 5rem}}
.rcv-pane{padding:2rem;display:flex;flex-direction:column;gap:1.1rem;min-width:0}
.rcv-pane-head{display:flex;align-items:baseline;gap:.9rem;padding-bottom:1.1rem;border-bottom:1px solid var(--line)}
.rcv-step{font-size:1.5rem;font-weight:600;color:var(--acc);font-variant-numeric:tabular-nums}
.rcv-pane-head h2{font-size:1.5rem;font-weight:600;margin:0;letter-spacing:-.01em}
.rcv-pane-head h2 .thin{font-weight:200}
.rcv-pane-head small{display:block;color:var(--mute);font-size:.82rem;font-weight:400;margin-top:.3rem}
.rcv-drop{border:1px dashed var(--line-2);background:rgba(255,255,255,.02);border-radius:10px;padding:1.9rem 1rem;text-align:center;cursor:pointer;transition:.2s}
.rcv-drop:hover,.rcv-drop.is-over{border-color:var(--acc);background:var(--acc-soft)}
.rcv-drop-icon{width:52px;height:52px;border-radius:50%;border:1px solid var(--line-2);display:grid;place-items:center;margin:0 auto .9rem;color:var(--acc)}
.rcv-drop b{font-weight:600}.rcv-drop u{color:var(--acc);text-decoration:none;font-weight:600}
.rcv-drop small{display:block;color:var(--mute);font-size:.78rem;margin-top:.45rem}
.rcv-filepill{display:flex;align-items:center;gap:.9rem;padding:.9rem 1rem;border:1px solid var(--line);border-radius:10px;background:var(--card-2)}
.rcv-filepill .ico{width:40px;height:40px;border-radius:50%;background:var(--acc-soft);color:var(--acc);display:grid;place-items:center;flex:none}
.rcv-filepill div{flex:1;min-width:0}.rcv-filepill b{display:block;font-size:.92rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rcv-filepill small{color:var(--mute);font-size:.78rem}
.rcv-iconbtn{border:1px solid var(--line);background:transparent;color:var(--sub);width:34px;height:34px;border-radius:50%;display:grid;place-items:center;cursor:pointer;transition:.2s}
.rcv-iconbtn:hover{border-color:var(--acc);color:var(--acc)}
.rcv-or{display:flex;align-items:center;gap:.9rem;color:var(--mute);font-size:.72rem;text-transform:uppercase;letter-spacing:2px;font-weight:600}
.rcv-or::before,.rcv-or::after{content:"";flex:1;height:1px;background:var(--line)}
.rcv-field{position:relative;display:flex;flex-direction:column;flex:1}
.rcv-field label{font-size:.78rem;font-weight:600;color:var(--sub);margin-bottom:.55rem;letter-spacing:1px;text-transform:uppercase}
.rcv-field label span{color:var(--mute);font-weight:400;text-transform:none;letter-spacing:0}
.rcv textarea{width:100%;flex:1;min-height:150px;resize:vertical;border:1px solid var(--line);border-radius:10px;padding:1rem 1.1rem 1.8rem;font:inherit;font-size:.92rem;line-height:1.65;color:var(--ink);background:#111;outline:none;transition:.2s}
.rcv textarea::placeholder{color:var(--mute)}
.rcv textarea:focus{border-color:var(--acc);box-shadow:0 0 0 3px rgba(253,91,56,.15)}
.rcv-count{position:absolute;right:.9rem;bottom:.6rem;font-size:.72rem;color:var(--mute);pointer-events:none}
.rcv-more{display:inline-flex;align-items:center;gap:.4rem;border:none;background:none;color:var(--acc);font-size:.88rem;font-weight:600;cursor:pointer;padding:0;align-self:flex-start}
.rcv-more:hover{color:var(--acc-2)}
.rcv-bar{margin-top:1.5rem;padding:1.1rem 1.4rem;display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap}
.rcv-seg{display:inline-flex;border:1px solid var(--line);border-radius:6px;padding:3px}
.rcv-seg button{border:none;background:none;padding:.45rem .9rem;border-radius:4px;font-size:.85rem;font-weight:500;color:var(--sub);cursor:pointer}
.rcv-seg button.on{background:#fff;color:#0f0f0f;font-weight:600}
.rcv-switch{display:inline-flex;align-items:center;gap:.65rem;font-size:.88rem;color:var(--sub);cursor:pointer;user-select:none}
.rcv-switch input{display:none}
.rcv-switch i{width:38px;height:21px;border-radius:999px;background:rgba(255,255,255,.14);position:relative;transition:.2s;flex:none}
.rcv-switch i::after{content:"";position:absolute;top:2.5px;left:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:.2s}
.rcv-switch input:checked+i{background:var(--acc)}.rcv-switch input:checked+i::after{left:19px}
.rcv-label{font-size:.72rem;color:var(--mute);font-weight:600;letter-spacing:2px;text-transform:uppercase}
.rcv-cta{margin-left:auto;display:inline-flex;align-items:center;gap:.6rem;border:1px solid transparent;cursor:pointer;background:var(--acc);color:#fff;font-weight:500;font-size:1rem;padding:.85rem 1.6rem;border-radius:5px;transition:.25s}
.rcv-cta:hover:not(:disabled){background:transparent;border-color:var(--acc);color:var(--acc)}
.rcv-cta:disabled{opacity:.55;cursor:not-allowed}
.rcv-btn{display:inline-flex;align-items:center;gap:.5rem;border:1px solid var(--line-2);background:transparent;color:var(--ink);font-weight:500;font-size:.86rem;padding:.6rem 1rem;border-radius:5px;cursor:pointer;transition:.2s}
.rcv-btn:hover{border-color:var(--acc);color:var(--acc)}
.rcv-btn.sm{padding:.35rem .7rem;font-size:.78rem}
.rcv-alert{display:flex;gap:.8rem;align-items:flex-start;padding:1rem 1.2rem;border-radius:10px;font-size:.9rem;margin-bottom:1.5rem;line-height:1.55}
.rcv-alert.warn{background:var(--warn-bg);color:#fde68a;border:1px solid rgba(251,191,36,.3)}
.rcv-alert.bad{background:var(--bad-bg);color:#fecaca;border:1px solid rgba(248,113,113,.3)}
.rcv-loading{margin-top:1.5rem;padding:2.75rem 2rem;text-align:center}
.rcv-spinner{width:46px;height:46px;border-radius:50%;border:2px solid var(--line);border-top-color:var(--acc);animation:rcv-spin .9s linear infinite;margin:0 auto 1.2rem}
@keyframes rcv-spin{to{transform:rotate(360deg)}}
.rcv-loading h3{font-size:1.35rem;font-weight:600;margin:0 0 .4rem}.rcv-loading p{color:var(--sub);font-size:.9rem;margin:0}
.rcv-steps{display:flex;justify-content:center;gap:.6rem;flex-wrap:wrap;margin-top:1.5rem}
.rcv-steps span{display:inline-flex;align-items:center;gap:.4rem;font-size:.8rem;padding:.4rem .85rem;border-radius:999px;color:var(--mute);border:1px solid var(--line)}
.rcv-steps span.done{color:var(--ok);border-color:rgba(52,211,153,.35)}
.rcv-steps span.now{color:var(--acc);border-color:rgba(253,91,56,.5);background:var(--acc-soft)}
.rcv-res{margin-top:2.25rem;display:flex;flex-direction:column;gap:1.5rem}
.rcv-summary{padding:2.2rem;display:grid;grid-template-columns:auto 1fr auto;gap:2.25rem;align-items:center;position:relative;overflow:hidden;
  background:radial-gradient(50% 120% at 0% 50%,rgba(253,91,56,.16),transparent 70%),var(--card)}
@media (max-width:900px){.rcv-summary{grid-template-columns:1fr;text-align:center;justify-items:center}}
.rcv-gauge{position:relative;width:148px;height:148px}
.rcv-gauge svg{transform:rotate(-90deg)}
.rcv-gauge div{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.rcv-gauge b{font-size:2.9rem;font-weight:700;letter-spacing:-.03em;line-height:1}.rcv-gauge small{font-size:.72rem;color:var(--mute);margin-top:.35rem;letter-spacing:2px;text-transform:uppercase}
.rcv-badge{display:inline-flex;align-items:center;gap:.35rem;font-size:.72rem;font-weight:600;padding:.3rem .7rem;border-radius:999px;letter-spacing:1px;text-transform:uppercase;border:1px solid}
.rcv-badge.ok{color:var(--ok);border-color:rgba(52,211,153,.35)}.rcv-badge.good{color:var(--good);border-color:rgba(74,222,128,.35)}
.rcv-badge.warn{color:var(--warn);border-color:rgba(251,191,36,.35)}.rcv-badge.bad{color:var(--bad);border-color:rgba(248,113,113,.35)}
.rcv-badge.muted{color:var(--sub);border-color:var(--line-2)}.rcv-badge.brand{color:var(--acc);border-color:rgba(253,91,56,.4)}
.rcv-summary h2{font-size:clamp(1.5rem,2.6vw,2.2rem);font-weight:600;letter-spacing:-.02em;margin:.8rem 0 .25rem;line-height:1.2}
.rcv-summary .role{color:var(--acc);font-size:.95rem;font-weight:500}
.rcv-summary p{color:var(--sub);line-height:1.7;margin:.9rem 0 0;font-size:.95rem;max-width:640px}
.rcv-actions{display:flex;flex-direction:column;gap:.55rem}
@media (max-width:900px){.rcv-actions{flex-direction:row;flex-wrap:wrap;justify-content:center}}
.rcv-gates{display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem}
@media (max-width:900px){.rcv-gates{grid-template-columns:1fr}}
.rcv-gate{padding:1.4rem 1.5rem}
.rcv-gate .top{display:flex;justify-content:space-between;align-items:center;gap:.5rem;margin-bottom:.7rem}
.rcv-gate .top span:first-child{font-size:.72rem;font-weight:600;color:var(--mute);text-transform:uppercase;letter-spacing:2px}
.rcv-gate p{font-size:.88rem;color:var(--sub);line-height:1.6;margin:0}
.rcv-section{padding:2rem}
.rcv-section h3{font-size:1.5rem;font-weight:600;margin:0 0 1.6rem;letter-spacing:-.01em}
.rcv-section h3 .thin{font-weight:200}
.rcv-dims{display:grid;grid-template-columns:1fr 1fr;gap:1.6rem 3rem}
@media (max-width:900px){.rcv-dims{grid-template-columns:1fr}}
.rcv-dim .row{display:flex;justify-content:space-between;align-items:baseline;font-size:.95rem;font-weight:600}
.rcv-dim .row small{color:var(--mute);font-weight:400;font-size:.75rem;margin-left:.5rem}
.rcv-dim .row>span:last-child{font-size:1.25rem}
.rcv-track{height:4px;background:rgba(255,255,255,.08);border-radius:999px;margin:.6rem 0 .7rem;overflow:hidden}
.rcv-track i{display:block;height:100%;border-radius:999px;transition:width .8s ease}
.rcv-dim p{font-size:.86rem;color:var(--sub);line-height:1.6;margin:0}
.rcv-tabs{display:flex;gap:.5rem;border-bottom:1px solid var(--line);padding:0 1.25rem;overflow-x:auto}
.rcv-tabs button{border:none;background:none;padding:1.15rem .9rem;font-size:.9rem;font-weight:500;color:var(--mute);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;white-space:nowrap;display:inline-flex;align-items:center;gap:.5rem;transition:.2s}
.rcv-tabs button:hover{color:var(--ink)}
.rcv-tabs button.on{color:var(--ink);border-bottom-color:var(--acc)}
.rcv-tabs button em{font-style:normal;font-size:.7rem;color:var(--acc);font-weight:600}
.rcv-tabbody{padding:2rem}
.rcv-cols{display:grid;grid-template-columns:1fr 1fr;gap:2rem 3rem}
@media (max-width:900px){.rcv-cols{grid-template-columns:1fr}}
.rcv-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:.75rem}
.rcv-list li{display:flex;gap:.7rem;font-size:.92rem;line-height:1.6;color:rgba(255,255,255,.82)}
.rcv-list li svg{flex:none;margin-top:.25rem}
.rcv-list.ok svg{color:var(--ok)}.rcv-list.warn svg{color:var(--warn)}.rcv-list.brand svg{color:var(--acc)}
.rcv-h4{font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:2px;color:var(--acc);margin:0 0 1rem}
.rcv-empty{color:var(--mute);font-size:.9rem;margin:0}
.rcv-kw-head{display:flex;align-items:center;gap:1.5rem;margin-bottom:2rem;flex-wrap:wrap}
.rcv-kw-head b{font-size:2.6rem;font-weight:700;letter-spacing:-.03em}
.rcv-kw-head .rcv-track{flex:1;min-width:180px;height:6px}
.rcv-chips{display:flex;flex-wrap:wrap;gap:.5rem}
.rcv-chip{display:inline-flex;align-items:center;gap:.35rem;font-size:.82rem;font-weight:500;padding:.38rem .8rem;border-radius:999px;border:1px solid}
.rcv-chip.ok{color:var(--ok);border-color:rgba(52,211,153,.3);background:var(--ok-bg)}
.rcv-chip.bad{color:var(--bad);border-color:rgba(248,113,113,.3);background:var(--bad-bg)}
.rcv-edit{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--card-2)}
.rcv-edit+.rcv-edit{margin-top:1rem}
.rcv-edit header{display:flex;align-items:center;gap:.7rem;padding:.85rem 1.1rem;border-bottom:1px solid var(--line)}
.rcv-edit header b{font-size:.92rem;font-weight:600;flex:1}
.rcv-diff{padding:1rem 1.1rem;display:grid;gap:.55rem}
.rcv-diff div{display:grid;grid-template-columns:22px 1fr;gap:.5rem;font-size:.9rem;line-height:1.6;padding:.6rem .8rem;border-radius:6px;white-space:pre-wrap;word-break:break-word}
.rcv-diff .del{background:var(--bad-bg);color:#fca5a5}.rcv-diff .del span{text-decoration:line-through;text-decoration-color:rgba(252,165,165,.5)}
.rcv-diff .add{background:var(--ok-bg);color:#a7f3d0}
.rcv-diff i{font-style:normal;font-weight:700;opacity:.7;text-align:center}
.rcv-warnline{display:flex;gap:.45rem;align-items:flex-start;margin-top:.55rem;padding:.5rem .7rem;border-radius:8px;background:var(--warn-bg);color:#fde68a;border:1px solid rgba(251,191,36,.3);font-size:.82rem;line-height:1.5}
.rcv-warnline svg{flex:none;margin-top:.15rem}
.rcv-edit footer{padding:0 1.1rem 1rem;font-size:.85rem;color:var(--sub);line-height:1.6}
.rcv-letter{white-space:pre-wrap;font-size:.98rem;line-height:1.85;color:rgba(255,255,255,.86);background:#111;border:1px solid var(--line);border-radius:10px;padding:2rem 2.25rem}
.rcv-foot{font-size:.78rem;color:var(--mute);text-align:center;padding:.5rem 0 1.5rem}
.route-reviewingcv .workspace-container{background:#0f0f0f}
`;

function toMarkdown(r) {
  const L = (a) => (a || []).map((x) => `- ${x}`).join('\n') || '- (không có)';
  return [
    `# Đánh giá CV: ${r.role_title}${r.company ? ' tại ' + r.company : ''}`,
    `**Điểm tổng: ${r.overall}/100 — ${r.verdict_vi} (${r.verdict})**`,
    `| Tiêu chí | Điểm | Ghi chú |\n|---|---|---|\n` + DIMS.map(([k, n]) => `| ${n} | ${r.scores[k].score}/100 | ${r.scores[k].note} |`).join('\n') +
      `\n| Địa điểm | ${r.location.verdict} | ${r.location.note} |`,
    `Điều kiện ứng tuyển: ${r.eligibility.verdict} — ${r.eligibility.note}\n\nNgôn ngữ: ${r.language_gate.verdict} — ${r.language_gate.note}`,
    `## Điểm mạnh\n${L(r.strengths)}`, `## Khoảng trống\n${L(r.gaps)}`, `## Khuyến nghị\n${r.recommendation}`,
    `## ATS\nĐã có: ${(r.ats.matched || []).join(', ')}\n\nCòn thiếu: ${(r.ats.missing || []).join(', ')}\n\n${L(r.ats.issues)}`,
    `## Đề xuất sửa CV\n` + (r.cv_edits || []).map((e, i) => `${i + 1}. **${e.section}** (${REASON[e.reason] || e.reason}): ${e.why}\n   - Cũ: ${e.old || '(thêm mới)'}\n   - Mới: ${e.new}`).join('\n'),
    `## Góp ý thêm\n### Yêu cầu bị bỏ sót\n${L(r.narrative.missed_keywords)}\n### Góc độ theo công ty\n${L(r.narrative.company_angles)}\n### Diễn đạt chủ động hơn\n${L(r.narrative.reframing)}\n### Giọng văn\n${L(r.narrative.tone)}`,
    `## Chỗ diễn đạt hơi quá\n${L(r.stretch_flags)}`, `## Câu hỏi phỏng vấn nên chuẩn bị\n${L(r.interview_questions)}`,
    r.cover_letter ? `## Thư xin việc\n\n${r.cover_letter}` : '',
  ].filter(Boolean).join('\n\n');
}

const list = (items, kind, icon, empty = 'Không có mục nào.') =>
  items?.length
    ? `<ul class="rcv-list ${kind}">${items.map((x) => `<li>${ic(icon, 16)}<span>${esc(x)}</span></li>`).join('')}</ul>`
    : `<p class="rcv-empty">${empty}</p>`;

const fmtSize = (n) => (n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB');

export const reviewingcvModule = {
  id: 'reviewingcv',
  name: 'Reviewing CV',
  route: '/reviewingCV',
  icon: '📄',
  category: 'Career AI',
  description: 'Chấm CV theo tin tuyển dụng: điểm phù hợp, ATS, đề xuất sửa từng dòng (bộ quy tắc ai-job-search).',
  status: 'active',

  _s: { busy: false, timer: null, result: null, file: null, lang: 'vi', tab: 'overview' },

  unmount() {
    clearTimeout(this._s.timer);
    this._s.timer = null;
    this._s.busy = false;
    document.body.classList.remove('route-reviewingcv');
  },

  render(el) {
    this.unmount();
    const s = this._s;
    if (!document.getElementById(STYLE_ID)) {
      const st = document.createElement('style');
      st.id = STYLE_ID;
      st.textContent = CSS;
      document.head.appendChild(st);
      const font = document.createElement('link');
      font.rel = 'stylesheet';
      font.href = 'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@200;300;400;500;600;700;800&display=swap';
      document.head.appendChild(font);
    }
    document.body.classList.add('route-reviewingcv');

    el.innerHTML = `
    ${pageHero(this, {
      title: 'Chấm CV <span class="thin">theo</span> tin tuyển dụng',
      sub: 'Tải CV và dán mô tả công việc. AI đối chiếu từng yêu cầu, chấm mức độ phù hợp, kiểm tra ATS và đề xuất sửa từng dòng mà không bịa thêm kinh nghiệm.',
      word: 'Review',
      meta: ['AI local · Ollama', 'Kiểm tra ATS', '1–2 phút mỗi lượt'],
    })}
    <div class="mp-body">
    <div class="rcv">

      <div id="rcv-warn"></div>

      <div class="rcv-grid">
        <section class="rcv-card rcv-pane">
          <div class="rcv-pane-head"><span class="rcv-step">01</span><div><h2>CV <span class="thin">của bạn</span></h2><small>PDF, DOCX, TXT, MD hoặc TEX</small></div></div>
          <div id="rcv-filebox"></div>
          <input type="file" id="rcv-file" accept=".pdf,.docx,.txt,.md,.tex" hidden />
          <div class="rcv-or">hoặc dán nội dung</div>
          <div class="rcv-field">
            <textarea id="rcv-cv" placeholder="Họ tên, tóm tắt, kinh nghiệm làm việc, học vấn, kỹ năng…"></textarea>
            <span class="rcv-count" id="rcv-cv-count">0 ký tự</span>
          </div>
        </section>

        <section class="rcv-card rcv-pane">
          <div class="rcv-pane-head"><span class="rcv-step">02</span><div><h2>Tin <span class="thin">tuyển dụng</span></h2><small>Dán toàn bộ mô tả công việc để kết quả chính xác nhất</small></div></div>
          <div class="rcv-field">
            <textarea id="rcv-job" style="min-height:236px" placeholder="Vị trí, công ty, trách nhiệm, yêu cầu bắt buộc, điểm cộng, địa điểm…"></textarea>
            <span class="rcv-count" id="rcv-job-count">0 ký tự</span>
          </div>
          <button class="rcv-more" id="rcv-more" type="button">${ic('plus', 15)} Thêm bối cảnh của bạn (không bắt buộc)</button>
          <div class="rcv-field" id="rcv-notes-box" hidden>
            <label for="rcv-notes">Bối cảnh <span>— mục tiêu nghề nghiệp, nơi ở, ngôn ngữ, giấy phép lao động</span></label>
            <textarea id="rcv-notes" style="min-height:90px" placeholder="VD: Sẵn sàng chuyển ra Hà Nội, muốn lên vị trí quản lý trong 2 năm tới."></textarea>
          </div>
        </section>
      </div>

      <div class="rcv-card rcv-bar">
        <span class="rcv-label">Ngôn ngữ nhận xét</span>
        <div class="rcv-seg" id="rcv-lang">
          <button type="button" data-lang="vi">Tiếng Việt</button><button type="button" data-lang="en">English</button>
        </div>
        <label class="rcv-switch"><input type="checkbox" id="rcv-cover" /><i></i> Viết kèm thư xin việc</label>
        <button class="rcv-cta" id="rcv-go" type="button">${ic('spark', 17)} <span>Phân tích CV</span></button>
      </div>

      <div id="rcv-out"></div>
    </div>
    </div>`;

    const $ = (id) => el.querySelector('#' + id);
    const out = $('rcv-out');

    // ── Trạng thái máy chủ ──
    const warn = (html) => { $('rcv-warn').innerHTML = `<div class="rcv-alert warn">${ic('alert', 18)}<div>${html}</div></div>`; };
    fetch('/api/cv/status').then((r) => r.json()).then((st) => {
      if (!st.llm) warn(`Chưa phân tích được CV: ${esc(st.error || 'AI local chưa sẵn sàng')}.`);
    }).catch(() => warn('Máy chủ chưa nạp API phân tích CV — cần khởi động lại Hub.'));

    // ── File CV ──
    const drawFile = () => {
      const f = s.file;
      $('rcv-filebox').innerHTML = f
        ? `<div class="rcv-filepill"><span class="ico">${ic('file', 18)}</span><div><b>${esc(f.name)}</b><small>${fmtSize(f.size)} · sẵn sàng phân tích</small></div>
             <button class="rcv-iconbtn" id="rcv-file-x" type="button" title="Bỏ file">${ic('x', 16)}</button></div>`
        : `<div class="rcv-drop" id="rcv-drop" role="button" tabindex="0">
             <div class="rcv-drop-icon">${ic('upload', 20)}</div>
             <b>Kéo thả CV vào đây</b> hoặc <u>chọn file</u>
             <small>Tối đa 10 MB · PDF phải có lớp chữ (không phải bản scan)</small>
           </div>`;
      if (f) {
        $('rcv-file-x').onclick = () => { s.file = null; $('rcv-file').value = ''; drawFile(); };
        return;
      }
      const drop = $('rcv-drop');
      drop.onclick = () => $('rcv-file').click();
      drop.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('rcv-file').click(); } };
      drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('is-over'); };
      drop.ondragleave = () => drop.classList.remove('is-over');
      drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove('is-over'); pick(e.dataTransfer.files[0]); };
    };
    const pick = (f) => {
      if (!f) return;
      if (!/\.(pdf|docx|txt|md|tex)$/i.test(f.name)) return toast('❌ Chỉ nhận PDF, DOCX, TXT, MD, TEX', 'error');
      if (f.size > 10 * 1048576) return toast('❌ File lớn hơn 10 MB', 'error');
      s.file = f;
      drawFile();
    };
    $('rcv-file').onchange = (e) => pick(e.target.files[0]);
    drawFile();

    // ── Ô nhập ──
    const counter = (ta, lbl) => { const n = $(ta).value.length; $(lbl).textContent = `${n.toLocaleString('vi-VN')} ký tự`; };
    $('rcv-cv').oninput = () => counter('rcv-cv', 'rcv-cv-count');
    $('rcv-job').oninput = () => counter('rcv-job', 'rcv-job-count');
    $('rcv-more').onclick = () => { $('rcv-notes-box').hidden = false; $('rcv-more').hidden = true; $('rcv-notes').focus(); };

    const drawLang = () => el.querySelectorAll('#rcv-lang button').forEach((b) => b.classList.toggle('on', b.dataset.lang === s.lang));
    el.querySelectorAll('#rcv-lang button').forEach((b) => { b.onclick = () => { s.lang = b.dataset.lang; drawLang(); }; });
    drawLang();

    const setBusy = (on) => {
      s.busy = on;
      $('rcv-go').disabled = on;
      $('rcv-go').querySelector('span').textContent = on ? 'Đang phân tích…' : 'Phân tích CV';
    };

    const drawLoading = (msg, secs) => {
      const idx = msg === 'Đang chờ lượt' ? -1 : Math.min(LOADING_STEPS.length - 1, Math.floor(secs / 15));
      out.innerHTML = `
        <div class="rcv-card rcv-loading">
          <div class="rcv-spinner"></div>
          <h3>${idx < 0 ? 'Đang chờ đến lượt…' : 'AI đang phân tích CV của bạn'}</h3>
          <p>${idx < 0 ? 'Có người đang dùng trước, lượt của bạn sẽ chạy ngay sau đó.' : 'Thường mất 1–2 phút. Bạn có thể để nguyên trang này.'} · ${secs}s</p>
          <div class="rcv-steps">${LOADING_STEPS.map((t, i) => `<span class="${i < idx ? 'done' : i === idx ? 'now' : ''}">${i < idx ? ic('check', 13) : ''}${t}</span>`).join('')}</div>
        </div>`;
    };

    // ── Kết quả ──
    const show = (r) => {
      s.result = r;
      const t = tone(r.overall);
      const color = TONE_COLOR[t];
      const C = 2 * Math.PI * 62;
      const failed = ['eligibility', 'language_gate', 'location'].some((k) => r[k].verdict === 'FAIL');
      const matched = r.ats.matched || [], missing = r.ats.missing || [];
      const rate = matched.length + missing.length ? Math.round((matched.length * 100) / (matched.length + missing.length)) : 0;
      const tabs = [
        ['overview', 'Tổng quan', null],
        ['keywords', 'Từ khóa ATS', missing.length],
        ['edits', 'Đề xuất sửa', (r.cv_edits || []).length],
        ['interview', 'Phỏng vấn', (r.interview_questions || []).length],
        ...(r.cover_letter ? [['letter', 'Thư xin việc', null]] : []),
      ];
      if (!tabs.some(([k]) => k === s.tab)) s.tab = 'overview';

      const gate = (title, g) => {
        const [k, label] = GATE[g.verdict] || ['muted', g.verdict];
        return `<div class="rcv-card rcv-gate"><div class="top"><span>${title}</span><span class="rcv-badge ${k}">${label}</span></div><p>${esc(g.note)}</p></div>`;
      };

      const body = {
        overview: () => `
          <div class="rcv-cols">
            <div><h4 class="rcv-h4">Điểm mạnh cho vị trí này</h4>${list(r.strengths, 'ok', 'check')}</div>
            <div><h4 class="rcv-h4">Khoảng trống cần xử lý</h4>${list(r.gaps, 'warn', 'alert')}</div>
            <div><h4 class="rcv-h4">Diễn đạt chủ động hơn</h4>${list(r.narrative.reframing, 'brand', 'arrow')}</div>
            <div><h4 class="rcv-h4">Góc độ theo công ty</h4>${list(r.narrative.company_angles, 'brand', 'briefcase')}</div>
            <div><h4 class="rcv-h4">Giọng văn</h4>${list(r.narrative.tone, 'brand', 'arrow')}</div>
            <div><h4 class="rcv-h4">Chỗ diễn đạt hơi quá</h4>${list(r.stretch_flags, 'warn', 'alert', 'Không thấy chỗ nào phóng đại.')}</div>
          </div>`,
        keywords: () => `
          <div class="rcv-kw-head"><b>${rate}%</b><div><div style="font-weight:600;font-size:.9rem">Mức khớp từ khóa</div><div style="color:var(--c-mute);font-size:.82rem">${matched.length} có trong CV · ${missing.length} còn thiếu</div></div>
            <div class="rcv-track"><i style="width:${rate}%;background:${TONE_COLOR[rate >= 60 ? 'ok' : rate >= 40 ? 'warn' : 'bad']}"></i></div></div>
          <div class="rcv-cols">
            <div><h4 class="rcv-h4">Còn thiếu trong CV</h4><div class="rcv-chips">${missing.map((x) => `<span class="rcv-chip bad">${ic('x', 12)}${esc(x)}</span>`).join('') || '<p class="rcv-empty">Không thiếu từ khóa nào.</p>'}</div>
              ${(r.narrative.missed_keywords || []).length ? `<h4 class="rcv-h4" style="margin-top:1.5rem">Yêu cầu bị bỏ sót</h4>${list(r.narrative.missed_keywords, 'warn', 'alert')}` : ''}</div>
            <div><h4 class="rcv-h4">Đã có trong CV</h4><div class="rcv-chips">${matched.map((x) => `<span class="rcv-chip ok">${ic('check', 12)}${esc(x)}</span>`).join('') || '<p class="rcv-empty">—</p>'}</div>
              ${(r.ats.issues || []).length ? `<h4 class="rcv-h4" style="margin-top:1.5rem">Vấn đề định dạng ATS</h4>${list(r.ats.issues, 'warn', 'alert')}` : ''}</div>
          </div>`,
        edits: () => (r.cv_edits || []).map((e, i) => `
          <article class="rcv-edit">
            <header><b>${esc(e.section)}</b><span class="rcv-badge brand">${esc(REASON[e.reason] || e.reason)}</span>
              <button class="rcv-btn sm" data-copy="${i}" type="button">${ic('copy', 13)} Sao chép</button></header>
            <div class="rcv-diff">
              ${e.old ? `<div class="del"><i>−</i><span>${esc(e.old)}</span></div>` : ''}
              <div class="add"><i>+</i><span>${esc(e.new)}</span></div>
            </div>
            <footer>${esc(e.why)}${(e.warnings || []).map((w) => `<div class="rcv-warnline">${ic('alert', 14)} ${esc(w)}</div>`).join('')}</footer>
          </article>`).join('') || '<p class="rcv-empty">Không có đề xuất sửa.</p>',
        interview: () => `<h4 class="rcv-h4">Câu hỏi nên chuẩn bị trước</h4>${list(r.interview_questions, 'brand', 'arrow')}`,
        letter: () => `<div style="display:flex;justify-content:flex-end;margin-bottom:.9rem"><button class="rcv-btn sm" id="rcv-copy-cl" type="button">${ic('copy', 13)} Sao chép thư</button></div><div class="rcv-letter">${esc(r.cover_letter)}</div>`,
      };

      out.innerHTML = `
      <div class="rcv-res">
        ${failed ? `<div class="rcv-alert bad">${ic('alert', 18)}<div><b>Có điều kiện bắt buộc không đạt.</b> Theo khung đánh giá, không nên nộp đơn trừ khi bạn chắc chắn về tình trạng của mình.</div></div>` : ''}
        <section class="rcv-card rcv-summary">
          <div class="rcv-gauge">
            <svg width="148" height="148"><circle cx="74" cy="74" r="62" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="8"/>
              <circle cx="74" cy="74" r="62" fill="none" stroke="${color}" stroke-width="8" stroke-linecap="round" stroke-dasharray="${(C * r.overall) / 100} ${C}"/></svg>
            <div><b>${r.overall}</b><small>/ 100</small></div>
          </div>
          <div>
            <span class="rcv-badge ${t}">${esc(r.verdict_vi)} · ${esc(r.verdict)}</span>
            <h2>${esc(r.role_title || 'Vị trí ứng tuyển')}</h2>
            <div class="role">${esc(r.company || '')}</div>
            <p>${esc(r.recommendation)}</p>
          </div>
          <div class="rcv-actions">
            <button class="rcv-btn" id="rcv-copy-md" type="button">${ic('copy', 15)} Sao chép báo cáo</button>
            <button class="rcv-btn" id="rcv-dl-md" type="button">${ic('download', 15)} Tải .md</button>
            <button class="rcv-btn" id="rcv-new" type="button">${ic('refresh', 15)} Phân tích CV khác</button>
          </div>
        </section>

        <div class="rcv-gates">${gate('Quyền ứng tuyển', r.eligibility)}${gate('Ngôn ngữ', r.language_gate)}${gate('Địa điểm', r.location)}</div>

        <section class="rcv-card rcv-section">
          <h3>Điểm <span class="thin">theo từng tiêu chí</span></h3>
          <div class="rcv-dims">${DIMS.map(([k, n, w]) => {
            const sc = r.scores[k];
            return `<div class="rcv-dim"><div class="row"><span>${n}<small>trọng số ${w}%</small></span><span>${sc.score}</span></div>
              <div class="rcv-track"><i style="width:${sc.score}%;background:${TONE_COLOR[tone(sc.score)]}"></i></div>
              <p>${esc(sc.note)}</p></div>`;
          }).join('')}</div>
        </section>

        <section class="rcv-card">
          <nav class="rcv-tabs">${tabs.map(([k, n, c]) => `<button type="button" data-tab="${k}" class="${k === s.tab ? 'on' : ''}">${n}${c ? `<em>${c}</em>` : ''}</button>`).join('')}</nav>
          <div class="rcv-tabbody" id="rcv-tabbody"></div>
        </section>

        <p class="rcv-foot">Mô hình ${esc(r.model)} · Khung đánh giá <a href="https://github.com/MadsLorentzen/ai-job-search" target="_blank" rel="noopener">ai-job-search</a> (MIT) · Kết quả mang tính tham khảo, hãy đọc lại trước khi sửa CV.</p>
      </div>`;

      const copy = (txt) => navigator.clipboard.writeText(txt).then(() => toast('📋 Đã sao chép', 'success'), () => toast('❌ Không sao chép được', 'error'));
      const drawTab = () => {
        const tb = out.querySelector('#rcv-tabbody');
        tb.innerHTML = body[s.tab]();
        tb.querySelectorAll('[data-copy]').forEach((b) => { b.onclick = () => copy(r.cv_edits[+b.dataset.copy].new); });
        tb.querySelector('#rcv-copy-cl')?.addEventListener('click', () => copy(r.cover_letter));
        out.querySelectorAll('[data-tab]').forEach((b) => b.classList.toggle('on', b.dataset.tab === s.tab));
      };
      out.querySelectorAll('[data-tab]').forEach((b) => { b.onclick = () => { s.tab = b.dataset.tab; drawTab(); }; });
      drawTab();

      out.querySelector('#rcv-copy-md').onclick = () => copy(toMarkdown(r));
      out.querySelector('#rcv-dl-md').onclick = () => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([toMarkdown(r)], { type: 'text/markdown' }));
        a.download = `cv-review-${(r.company || 'job').replace(/[^\w-]+/g, '_')}.md`;
        a.click();
        URL.revokeObjectURL(a.href);
      };
      out.querySelector('#rcv-new').onclick = () => {
        s.result = null;
        out.innerHTML = '';
        el.querySelector('.rcv').scrollIntoView({ behavior: 'smooth', block: 'start' });
      };
    };

    const poll = (jid, started) => {
      s.timer = setTimeout(async () => {
        try {
          const j = await (await fetch('/api/cv/jobs/' + jid)).json();
          if (!el.isConnected) return;
          if (j.status === 'running') {
            drawLoading(j.msg, Math.round((Date.now() - started) / 1000));
            return poll(jid, started);
          }
          setBusy(false);
          if (j.status === 'error') throw new Error(j.error);
          s.tab = 'overview';
          show(j.result);
          out.scrollIntoView({ behavior: 'smooth', block: 'start' });
          toast('✅ Đã phân tích xong CV', 'success');
        } catch (err) {
          setBusy(false);
          out.innerHTML = `<div class="rcv-alert bad" style="margin-top:1.25rem">${ic('alert', 18)}<div>${esc(err.message)}</div></div>`;
        }
      }, 2000);
    };

    $('rcv-go').addEventListener('click', async () => {
      if (s.busy) return;
      if (!s.file && $('rcv-cv').value.trim().length < 50) return toast('Hãy tải CV hoặc dán nội dung CV', 'error');
      if ($('rcv-job').value.trim().length < 50) return toast('Hãy dán nội dung tin tuyển dụng', 'error');
      const fd = new FormData();
      if (s.file) fd.append('cv_file', s.file);
      fd.append('cv_text', $('rcv-cv').value);
      fd.append('job_text', $('rcv-job').value);
      fd.append('notes', $('rcv-notes').value);
      fd.append('lang', s.lang);
      fd.append('cover', $('rcv-cover').checked ? '1' : '0');
      setBusy(true);
      drawLoading('Đang chờ lượt', 0);
      out.scrollIntoView({ behavior: 'smooth', block: 'center' });
      try {
        const res = await fetch('/api/cv/review', { method: 'POST', body: fd });
        const data = await res.json().catch(() => ({ error: `Máy chủ chưa có API phân tích CV (HTTP ${res.status}) — cần khởi động lại Hub` }));
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        poll(data.job, Date.now());
      } catch (err) {
        setBusy(false);
        out.innerHTML = `<div class="rcv-alert bad" style="margin-top:1.25rem">${ic('alert', 18)}<div>${esc(err.message)}</div></div>`;
      }
    });

    if (s.result) show(s.result);
  },
};
