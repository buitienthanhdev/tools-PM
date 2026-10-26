import{b as q,e as A}from"./c-A7EUOZAY.js";var c=e=>String(e!=null?e:"").replace(/[&<>"']/g,t=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[t]),g=(e,t="info")=>q.emit("toast:show",{message:e,type:t}),B={upload:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',file:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/>',x:'<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',spark:'<path d="M12 3l1.9 5.8L20 10.7l-6.1 1.9L12 18.5l-1.9-5.9L4 10.7l6.1-1.9z"/>',check:'<path d="M20 6 9 17l-5-5"/>',alert:'<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',clock:'<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',target:'<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',copy:'<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',refresh:'<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M8 16H3v5"/>',arrow:'<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',briefcase:'<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',plus:'<path d="M12 5v14"/><path d="M5 12h14"/>'},l=(e,t=18)=>`<svg width="${t}" height="${t}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${B[e]}</svg>`,P=[["technical","K\u1EF9 n\u0103ng chuy\xEAn m\xF4n",30],["experience","Kinh nghi\u1EC7m",25],["behavioral","V\u0103n h\xF3a & h\xE0nh vi",15],["career","\u0110\u1ECBnh h\u01B0\u1EDBng ngh\u1EC1 nghi\u1EC7p",30]],F={PASS:["ok","\u0110\u1EA1t"],FAIL:["bad","Kh\xF4ng \u0111\u1EA1t"],FLAG:["warn","C\u1EA7n l\u01B0u \xFD"],UNVERIFIED:["warn","Ch\u01B0a x\xE1c minh"],UNKNOWN:["muted","Ch\u01B0a r\xF5"]},N={keyword:"T\u1EEB kh\xF3a",reframing:"Di\u1EC5n \u0111\u1EA1t l\u1EA1i",style:"V\u0103n phong",grounding:"Sai d\u1EEF ki\u1EC7n",structure:"C\u1EA5u tr\xFAc"},C={ok:"#34d399",good:"#4ade80",warn:"#fbbf24",bad:"#f87171"},H=e=>e>=75?"ok":e>=60?"good":e>=45?"warn":"bad",I=["\u0110\u1ECDc CV","\u0110\u1ED1i chi\u1EBFu y\xEAu c\u1EA7u","Ch\u1EA5m \u0111i\u1EC3m","Vi\u1EBFt \u0111\u1EC1 xu\u1EA5t"],D="rcv-style",G=`
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
`;function K(e){let t=a=>(a||[]).map(s=>`- ${s}`).join(`
`)||"- (kh\xF4ng c\xF3)";return[`# \u0110\xE1nh gi\xE1 CV: ${e.role_title}${e.company?" t\u1EA1i "+e.company:""}`,`**\u0110i\u1EC3m t\u1ED5ng: ${e.overall}/100 \u2014 ${e.verdict_vi} (${e.verdict})**`,`| Ti\xEAu ch\xED | \u0110i\u1EC3m | Ghi ch\xFA |
|---|---|---|
`+P.map(([a,s])=>`| ${s} | ${e.scores[a].score}/100 | ${e.scores[a].note} |`).join(`
`)+`
| \u0110\u1ECBa \u0111i\u1EC3m | ${e.location.verdict} | ${e.location.note} |`,`\u0110i\u1EC1u ki\u1EC7n \u1EE9ng tuy\u1EC3n: ${e.eligibility.verdict} \u2014 ${e.eligibility.note}

Ng\xF4n ng\u1EEF: ${e.language_gate.verdict} \u2014 ${e.language_gate.note}`,`## \u0110i\u1EC3m m\u1EA1nh
${t(e.strengths)}`,`## Kho\u1EA3ng tr\u1ED1ng
${t(e.gaps)}`,`## Khuy\u1EBFn ngh\u1ECB
${e.recommendation}`,`## ATS
\u0110\xE3 c\xF3: ${(e.ats.matched||[]).join(", ")}

C\xF2n thi\u1EBFu: ${(e.ats.missing||[]).join(", ")}

${t(e.ats.issues)}`,`## \u0110\u1EC1 xu\u1EA5t s\u1EEDa CV
`+(e.cv_edits||[]).map((a,s)=>`${s+1}. **${a.section}** (${N[a.reason]||a.reason}): ${a.why}
   - C\u0169: ${a.old||"(th\xEAm m\u1EDBi)"}
   - M\u1EDBi: ${a.new}`).join(`
`),`## G\xF3p \xFD th\xEAm
### Y\xEAu c\u1EA7u b\u1ECB b\u1ECF s\xF3t
${t(e.narrative.missed_keywords)}
### G\xF3c \u0111\u1ED9 theo c\xF4ng ty
${t(e.narrative.company_angles)}
### Di\u1EC5n \u0111\u1EA1t ch\u1EE7 \u0111\u1ED9ng h\u01A1n
${t(e.narrative.reframing)}
### Gi\u1ECDng v\u0103n
${t(e.narrative.tone)}`,`## Ch\u1ED7 di\u1EC5n \u0111\u1EA1t h\u01A1i qu\xE1
${t(e.stretch_flags)}`,`## C\xE2u h\u1ECFi ph\u1ECFng v\u1EA5n n\xEAn chu\u1EA9n b\u1ECB
${t(e.interview_questions)}`,e.cover_letter?`## Th\u01B0 xin vi\u1EC7c

${e.cover_letter}`:""].filter(Boolean).join(`

`)}var p=(e,t,a,s="Kh\xF4ng c\xF3 m\u1EE5c n\xE0o.")=>e!=null&&e.length?`<ul class="rcv-list ${t}">${e.map(f=>`<li>${l(a,16)}<span>${c(f)}</span></li>`).join("")}</ul>`:`<p class="rcv-empty">${s}</p>`,R=e=>e>1048576?(e/1048576).toFixed(1)+" MB":Math.max(1,Math.round(e/1024))+" KB",Y={id:"reviewingcv",name:"Reviewing CV",route:"/reviewingCV",icon:"\u{1F4C4}",category:"Career AI",description:"Ch\u1EA5m CV theo tin tuy\u1EC3n d\u1EE5ng: \u0111i\u1EC3m ph\xF9 h\u1EE3p, ATS, \u0111\u1EC1 xu\u1EA5t s\u1EEDa t\u1EEBng d\xF2ng (b\u1ED9 quy t\u1EAFc ai-job-search).",status:"active",_s:{busy:!1,timer:null,result:null,file:null,lang:"vi",tab:"overview"},unmount(){clearTimeout(this._s.timer),this._s.timer=null,this._s.busy=!1,document.body.classList.remove("route-reviewingcv")},render(e){this.unmount();let t=this._s;if(!document.getElementById(D)){let r=document.createElement("style");r.id=D,r.textContent=G,document.head.appendChild(r)}document.body.classList.add("route-reviewingcv"),e.innerHTML=`
    ${A(this,{title:'Ch\u1EA5m CV <span class="thin">theo</span> tin tuy\u1EC3n d\u1EE5ng',sub:"T\u1EA3i CV v\xE0 d\xE1n m\xF4 t\u1EA3 c\xF4ng vi\u1EC7c. AI \u0111\u1ED1i chi\u1EBFu t\u1EEBng y\xEAu c\u1EA7u, ch\u1EA5m m\u1EE9c \u0111\u1ED9 ph\xF9 h\u1EE3p, ki\u1EC3m tra ATS v\xE0 \u0111\u1EC1 xu\u1EA5t s\u1EEDa t\u1EEBng d\xF2ng m\xE0 kh\xF4ng b\u1ECBa th\xEAm kinh nghi\u1EC7m.",word:"Review",meta:["AI local \xB7 Ollama","Ki\u1EC3m tra ATS","1\u20132 ph\xFAt m\u1ED7i l\u01B0\u1EE3t"]})}
    <div class="mp-body">
    <div class="rcv">

      <div id="rcv-warn"></div>

      <div class="rcv-grid">
        <section class="rcv-card rcv-pane">
          <div class="rcv-pane-head"><span class="rcv-step">01</span><div><h2>CV <span class="thin">c\u1EE7a b\u1EA1n</span></h2><small>PDF, DOCX, TXT, MD ho\u1EB7c TEX</small></div></div>
          <div id="rcv-filebox"></div>
          <input type="file" id="rcv-file" accept=".pdf,.docx,.txt,.md,.tex" hidden />
          <div class="rcv-or">ho\u1EB7c d\xE1n n\u1ED9i dung</div>
          <div class="rcv-field">
            <textarea id="rcv-cv" placeholder="H\u1ECD t\xEAn, t\xF3m t\u1EAFt, kinh nghi\u1EC7m l\xE0m vi\u1EC7c, h\u1ECDc v\u1EA5n, k\u1EF9 n\u0103ng\u2026"></textarea>
            <span class="rcv-count" id="rcv-cv-count">0 k\xFD t\u1EF1</span>
          </div>
        </section>

        <section class="rcv-card rcv-pane">
          <div class="rcv-pane-head"><span class="rcv-step">02</span><div><h2>Tin <span class="thin">tuy\u1EC3n d\u1EE5ng</span></h2><small>D\xE1n to\xE0n b\u1ED9 m\xF4 t\u1EA3 c\xF4ng vi\u1EC7c \u0111\u1EC3 k\u1EBFt qu\u1EA3 ch\xEDnh x\xE1c nh\u1EA5t</small></div></div>
          <div class="rcv-field">
            <textarea id="rcv-job" style="min-height:236px" placeholder="V\u1ECB tr\xED, c\xF4ng ty, tr\xE1ch nhi\u1EC7m, y\xEAu c\u1EA7u b\u1EAFt bu\u1ED9c, \u0111i\u1EC3m c\u1ED9ng, \u0111\u1ECBa \u0111i\u1EC3m\u2026"></textarea>
            <span class="rcv-count" id="rcv-job-count">0 k\xFD t\u1EF1</span>
          </div>
          <button class="rcv-more" id="rcv-more" type="button">${l("plus",15)} Th\xEAm b\u1ED1i c\u1EA3nh c\u1EE7a b\u1EA1n (kh\xF4ng b\u1EAFt bu\u1ED9c)</button>
          <div class="rcv-field" id="rcv-notes-box" hidden>
            <label for="rcv-notes">B\u1ED1i c\u1EA3nh <span>\u2014 m\u1EE5c ti\xEAu ngh\u1EC1 nghi\u1EC7p, n\u01A1i \u1EDF, ng\xF4n ng\u1EEF, gi\u1EA5y ph\xE9p lao \u0111\u1ED9ng</span></label>
            <textarea id="rcv-notes" style="min-height:90px" placeholder="VD: S\u1EB5n s\xE0ng chuy\u1EC3n ra H\xE0 N\u1ED9i, mu\u1ED1n l\xEAn v\u1ECB tr\xED qu\u1EA3n l\xFD trong 2 n\u0103m t\u1EDBi."></textarea>
          </div>
        </section>
      </div>

      <div class="rcv-card rcv-bar">
        <span class="rcv-label">Ng\xF4n ng\u1EEF nh\u1EADn x\xE9t</span>
        <div class="rcv-seg" id="rcv-lang">
          <button type="button" data-lang="vi">Ti\u1EBFng Vi\u1EC7t</button><button type="button" data-lang="en">English</button>
        </div>
        <label class="rcv-switch"><input type="checkbox" id="rcv-cover" /><i></i> Vi\u1EBFt k\xE8m th\u01B0 xin vi\u1EC7c</label>
        <button class="rcv-cta" id="rcv-go" type="button">${l("spark",17)} <span>Ph\xE2n t\xEDch CV</span></button>
      </div>

      <div id="rcv-out"></div>
    </div>
    </div>`;let a=r=>e.querySelector("#"+r),s=a("rcv-out"),f=r=>{a("rcv-warn").innerHTML=`<div class="rcv-alert warn">${l("alert",18)}<div>${r}</div></div>`};fetch("/api/cv/status").then(r=>r.json()).then(r=>{r.llm||f(`Ch\u01B0a ph\xE2n t\xEDch \u0111\u01B0\u1EE3c CV: ${c(r.error||"AI local ch\u01B0a s\u1EB5n s\xE0ng")}.`)}).catch(()=>f("M\xE1y ch\u1EE7 ch\u01B0a n\u1EA1p API ph\xE2n t\xEDch CV \u2014 c\u1EA7n kh\u1EDFi \u0111\u1ED9ng l\u1EA1i Hub."));let k=()=>{let r=t.file;if(a("rcv-filebox").innerHTML=r?`<div class="rcv-filepill"><span class="ico">${l("file",18)}</span><div><b>${c(r.name)}</b><small>${R(r.size)} \xB7 s\u1EB5n s\xE0ng ph\xE2n t\xEDch</small></div>
             <button class="rcv-iconbtn" id="rcv-file-x" type="button" title="B\u1ECF file">${l("x",16)}</button></div>`:`<div class="rcv-drop" id="rcv-drop" role="button" tabindex="0">
             <div class="rcv-drop-icon">${l("upload",20)}</div>
             <b>K\xE9o th\u1EA3 CV v\xE0o \u0111\xE2y</b> ho\u1EB7c <u>ch\u1ECDn file</u>
             <small>T\u1ED1i \u0111a 10 MB \xB7 PDF ph\u1EA3i c\xF3 l\u1EDBp ch\u1EEF (kh\xF4ng ph\u1EA3i b\u1EA3n scan)</small>
           </div>`,r){a("rcv-file-x").onclick=()=>{t.file=null,a("rcv-file").value="",k()};return}let o=a("rcv-drop");o.onclick=()=>a("rcv-file").click(),o.onkeydown=i=>{(i.key==="Enter"||i.key===" ")&&(i.preventDefault(),a("rcv-file").click())},o.ondragover=i=>{i.preventDefault(),o.classList.add("is-over")},o.ondragleave=()=>o.classList.remove("is-over"),o.ondrop=i=>{i.preventDefault(),o.classList.remove("is-over"),M(i.dataTransfer.files[0])}},M=r=>{if(r){if(!/\.(pdf|docx|txt|md|tex)$/i.test(r.name))return g("\u274C Ch\u1EC9 nh\u1EADn PDF, DOCX, TXT, MD, TEX","error");if(r.size>10*1048576)return g("\u274C File l\u1EDBn h\u01A1n 10 MB","error");t.file=r,k()}};a("rcv-file").onchange=r=>M(r.target.files[0]),k();let T=(r,o)=>{let i=a(r).value.length;a(o).textContent=`${i.toLocaleString("vi-VN")} k\xFD t\u1EF1`};a("rcv-cv").oninput=()=>T("rcv-cv","rcv-cv-count"),a("rcv-job").oninput=()=>T("rcv-job","rcv-job-count"),a("rcv-more").onclick=()=>{a("rcv-notes-box").hidden=!1,a("rcv-more").hidden=!0,a("rcv-notes").focus()};let V=()=>e.querySelectorAll("#rcv-lang button").forEach(r=>r.classList.toggle("on",r.dataset.lang===t.lang));e.querySelectorAll("#rcv-lang button").forEach(r=>{r.onclick=()=>{t.lang=r.dataset.lang,V()}}),V();let x=r=>{t.busy=r,a("rcv-go").disabled=r,a("rcv-go").querySelector("span").textContent=r?"\u0110ang ph\xE2n t\xEDch\u2026":"Ph\xE2n t\xEDch CV"},j=(r,o)=>{let i=r==="\u0110ang ch\u1EDD l\u01B0\u1EE3t"?-1:Math.min(I.length-1,Math.floor(o/15));s.innerHTML=`
        <div class="rcv-card rcv-loading">
          <div class="rcv-spinner"></div>
          <h3>${i<0?"\u0110ang ch\u1EDD \u0111\u1EBFn l\u01B0\u1EE3t\u2026":"AI \u0111ang ph\xE2n t\xEDch CV c\u1EE7a b\u1EA1n"}</h3>
          <p>${i<0?"C\xF3 ng\u01B0\u1EDDi \u0111ang d\xF9ng tr\u01B0\u1EDBc, l\u01B0\u1EE3t c\u1EE7a b\u1EA1n s\u1EBD ch\u1EA1y ngay sau \u0111\xF3.":"Th\u01B0\u1EDDng m\u1EA5t 1\u20132 ph\xFAt. B\u1EA1n c\xF3 th\u1EC3 \u0111\u1EC3 nguy\xEAn trang n\xE0y."} \xB7 ${o}s</p>
          <div class="rcv-steps">${I.map((w,m)=>`<span class="${m<i?"done":m===i?"now":""}">${m<i?l("check",13):""}${w}</span>`).join("")}</div>
        </div>`},_=r=>{t.result=r;let o=H(r.overall),i=C[o],w=2*Math.PI*62,m=["eligibility","language_gate","location"].some(n=>r[n].verdict==="FAIL"),b=r.ats.matched||[],u=r.ats.missing||[],y=b.length+u.length?Math.round(b.length*100/(b.length+u.length)):0,S=[["overview","T\u1ED5ng quan",null],["keywords","T\u1EEB kh\xF3a ATS",u.length],["edits","\u0110\u1EC1 xu\u1EA5t s\u1EEDa",(r.cv_edits||[]).length],["interview","Ph\u1ECFng v\u1EA5n",(r.interview_questions||[]).length],...r.cover_letter?[["letter","Th\u01B0 xin vi\u1EC7c",null]]:[]];S.some(([n])=>n===t.tab)||(t.tab="overview");let $=(n,v)=>{let[d,h]=F[v.verdict]||["muted",v.verdict];return`<div class="rcv-card rcv-gate"><div class="top"><span>${n}</span><span class="rcv-badge ${d}">${h}</span></div><p>${c(v.note)}</p></div>`},O={overview:()=>`
          <div class="rcv-cols">
            <div><h4 class="rcv-h4">\u0110i\u1EC3m m\u1EA1nh cho v\u1ECB tr\xED n\xE0y</h4>${p(r.strengths,"ok","check")}</div>
            <div><h4 class="rcv-h4">Kho\u1EA3ng tr\u1ED1ng c\u1EA7n x\u1EED l\xFD</h4>${p(r.gaps,"warn","alert")}</div>
            <div><h4 class="rcv-h4">Di\u1EC5n \u0111\u1EA1t ch\u1EE7 \u0111\u1ED9ng h\u01A1n</h4>${p(r.narrative.reframing,"brand","arrow")}</div>
            <div><h4 class="rcv-h4">G\xF3c \u0111\u1ED9 theo c\xF4ng ty</h4>${p(r.narrative.company_angles,"brand","briefcase")}</div>
            <div><h4 class="rcv-h4">Gi\u1ECDng v\u0103n</h4>${p(r.narrative.tone,"brand","arrow")}</div>
            <div><h4 class="rcv-h4">Ch\u1ED7 di\u1EC5n \u0111\u1EA1t h\u01A1i qu\xE1</h4>${p(r.stretch_flags,"warn","alert","Kh\xF4ng th\u1EA5y ch\u1ED7 n\xE0o ph\xF3ng \u0111\u1EA1i.")}</div>
          </div>`,keywords:()=>`
          <div class="rcv-kw-head"><b>${y}%</b><div><div style="font-weight:600;font-size:.9rem">M\u1EE9c kh\u1EDBp t\u1EEB kh\xF3a</div><div style="color:var(--c-mute);font-size:.82rem">${b.length} c\xF3 trong CV \xB7 ${u.length} c\xF2n thi\u1EBFu</div></div>
            <div class="rcv-track"><i style="width:${y}%;background:${C[y>=60?"ok":y>=40?"warn":"bad"]}"></i></div></div>
          <div class="rcv-cols">
            <div><h4 class="rcv-h4">C\xF2n thi\u1EBFu trong CV</h4><div class="rcv-chips">${u.map(n=>`<span class="rcv-chip bad">${l("x",12)}${c(n)}</span>`).join("")||'<p class="rcv-empty">Kh\xF4ng thi\u1EBFu t\u1EEB kh\xF3a n\xE0o.</p>'}</div>
              ${(r.narrative.missed_keywords||[]).length?`<h4 class="rcv-h4" style="margin-top:1.5rem">Y\xEAu c\u1EA7u b\u1ECB b\u1ECF s\xF3t</h4>${p(r.narrative.missed_keywords,"warn","alert")}`:""}</div>
            <div><h4 class="rcv-h4">\u0110\xE3 c\xF3 trong CV</h4><div class="rcv-chips">${b.map(n=>`<span class="rcv-chip ok">${l("check",12)}${c(n)}</span>`).join("")||'<p class="rcv-empty">\u2014</p>'}</div>
              ${(r.ats.issues||[]).length?`<h4 class="rcv-h4" style="margin-top:1.5rem">V\u1EA5n \u0111\u1EC1 \u0111\u1ECBnh d\u1EA1ng ATS</h4>${p(r.ats.issues,"warn","alert")}`:""}</div>
          </div>`,edits:()=>(r.cv_edits||[]).map((n,v)=>`
          <article class="rcv-edit">
            <header><b>${c(n.section)}</b><span class="rcv-badge brand">${c(N[n.reason]||n.reason)}</span>
              <button class="rcv-btn sm" data-copy="${v}" type="button">${l("copy",13)} Sao ch\xE9p</button></header>
            <div class="rcv-diff">
              ${n.old?`<div class="del"><i>\u2212</i><span>${c(n.old)}</span></div>`:""}
              <div class="add"><i>+</i><span>${c(n.new)}</span></div>
            </div>
            <footer>${c(n.why)}${(n.warnings||[]).map(d=>`<div class="rcv-warnline">${l("alert",14)} ${c(d)}</div>`).join("")}</footer>
          </article>`).join("")||'<p class="rcv-empty">Kh\xF4ng c\xF3 \u0111\u1EC1 xu\u1EA5t s\u1EEDa.</p>',interview:()=>`<h4 class="rcv-h4">C\xE2u h\u1ECFi n\xEAn chu\u1EA9n b\u1ECB tr\u01B0\u1EDBc</h4>${p(r.interview_questions,"brand","arrow")}`,letter:()=>`<div style="display:flex;justify-content:flex-end;margin-bottom:.9rem"><button class="rcv-btn sm" id="rcv-copy-cl" type="button">${l("copy",13)} Sao ch\xE9p th\u01B0</button></div><div class="rcv-letter">${c(r.cover_letter)}</div>`};s.innerHTML=`
      <div class="rcv-res">
        ${m?`<div class="rcv-alert bad">${l("alert",18)}<div><b>C\xF3 \u0111i\u1EC1u ki\u1EC7n b\u1EAFt bu\u1ED9c kh\xF4ng \u0111\u1EA1t.</b> Theo khung \u0111\xE1nh gi\xE1, kh\xF4ng n\xEAn n\u1ED9p \u0111\u01A1n tr\u1EEB khi b\u1EA1n ch\u1EAFc ch\u1EAFn v\u1EC1 t\xECnh tr\u1EA1ng c\u1EE7a m\xECnh.</div></div>`:""}
        <section class="rcv-card rcv-summary">
          <div class="rcv-gauge">
            <svg width="148" height="148"><circle cx="74" cy="74" r="62" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="8"/>
              <circle cx="74" cy="74" r="62" fill="none" stroke="${i}" stroke-width="8" stroke-linecap="round" stroke-dasharray="${w*r.overall/100} ${w}"/></svg>
            <div><b>${r.overall}</b><small>/ 100</small></div>
          </div>
          <div>
            <span class="rcv-badge ${o}">${c(r.verdict_vi)} \xB7 ${c(r.verdict)}</span>
            <h2>${c(r.role_title||"V\u1ECB tr\xED \u1EE9ng tuy\u1EC3n")}</h2>
            <div class="role">${c(r.company||"")}</div>
            <p>${c(r.recommendation)}</p>
          </div>
          <div class="rcv-actions">
            <button class="rcv-btn" id="rcv-copy-md" type="button">${l("copy",15)} Sao ch\xE9p b\xE1o c\xE1o</button>
            <button class="rcv-btn" id="rcv-dl-md" type="button">${l("download",15)} T\u1EA3i .md</button>
            <button class="rcv-btn" id="rcv-new" type="button">${l("refresh",15)} Ph\xE2n t\xEDch CV kh\xE1c</button>
          </div>
        </section>

        <div class="rcv-gates">${$("Quy\u1EC1n \u1EE9ng tuy\u1EC3n",r.eligibility)}${$("Ng\xF4n ng\u1EEF",r.language_gate)}${$("\u0110\u1ECBa \u0111i\u1EC3m",r.location)}</div>

        <section class="rcv-card rcv-section">
          <h3>\u0110i\u1EC3m <span class="thin">theo t\u1EEBng ti\xEAu ch\xED</span></h3>
          <div class="rcv-dims">${P.map(([n,v,d])=>{let h=r.scores[n];return`<div class="rcv-dim"><div class="row"><span>${v}<small>tr\u1ECDng s\u1ED1 ${d}%</small></span><span>${h.score}</span></div>
              <div class="rcv-track"><i style="width:${h.score}%;background:${C[H(h.score)]}"></i></div>
              <p>${c(h.note)}</p></div>`}).join("")}</div>
        </section>

        <section class="rcv-card">
          <nav class="rcv-tabs">${S.map(([n,v,d])=>`<button type="button" data-tab="${n}" class="${n===t.tab?"on":""}">${v}${d?`<em>${d}</em>`:""}</button>`).join("")}</nav>
          <div class="rcv-tabbody" id="rcv-tabbody"></div>
        </section>

        <p class="rcv-foot">M\xF4 h\xECnh ${c(r.model)} \xB7 Khung \u0111\xE1nh gi\xE1 <a href="https://github.com/MadsLorentzen/ai-job-search" target="_blank" rel="noopener">ai-job-search</a> (MIT) \xB7 K\u1EBFt qu\u1EA3 mang t\xEDnh tham kh\u1EA3o, h\xE3y \u0111\u1ECDc l\u1EA1i tr\u01B0\u1EDBc khi s\u1EEDa CV.</p>
      </div>`;let z=n=>navigator.clipboard.writeText(n).then(()=>g("\u{1F4CB} \u0110\xE3 sao ch\xE9p","success"),()=>g("\u274C Kh\xF4ng sao ch\xE9p \u0111\u01B0\u1EE3c","error")),E=()=>{var v;let n=s.querySelector("#rcv-tabbody");n.innerHTML=O[t.tab](),n.querySelectorAll("[data-copy]").forEach(d=>{d.onclick=()=>z(r.cv_edits[+d.dataset.copy].new)}),(v=n.querySelector("#rcv-copy-cl"))==null||v.addEventListener("click",()=>z(r.cover_letter)),s.querySelectorAll("[data-tab]").forEach(d=>d.classList.toggle("on",d.dataset.tab===t.tab))};s.querySelectorAll("[data-tab]").forEach(n=>{n.onclick=()=>{t.tab=n.dataset.tab,E()}}),E(),s.querySelector("#rcv-copy-md").onclick=()=>z(K(r)),s.querySelector("#rcv-dl-md").onclick=()=>{let n=document.createElement("a");n.href=URL.createObjectURL(new Blob([K(r)],{type:"text/markdown"})),n.download=`cv-review-${(r.company||"job").replace(/[^\w-]+/g,"_")}.md`,n.click(),URL.revokeObjectURL(n.href)},s.querySelector("#rcv-new").onclick=()=>{t.result=null,s.innerHTML="",e.querySelector(".rcv").scrollIntoView({behavior:"smooth",block:"start"})}},L=(r,o)=>{t.timer=setTimeout(async()=>{try{let i=await(await fetch("/api/cv/jobs/"+r)).json();if(!e.isConnected)return;if(i.status==="running")return j(i.msg,Math.round((Date.now()-o)/1e3)),L(r,o);if(x(!1),i.status==="error")throw new Error(i.error);t.tab="overview",_(i.result),s.scrollIntoView({behavior:"smooth",block:"start"}),g("\u2705 \u0110\xE3 ph\xE2n t\xEDch xong CV","success")}catch(i){x(!1),s.innerHTML=`<div class="rcv-alert bad" style="margin-top:1.25rem">${l("alert",18)}<div>${c(i.message)}</div></div>`}},2e3)};a("rcv-go").addEventListener("click",async()=>{if(t.busy)return;if(!t.file&&a("rcv-cv").value.trim().length<50)return g("H\xE3y t\u1EA3i CV ho\u1EB7c d\xE1n n\u1ED9i dung CV","error");if(a("rcv-job").value.trim().length<50)return g("H\xE3y d\xE1n n\u1ED9i dung tin tuy\u1EC3n d\u1EE5ng","error");let r=new FormData;t.file&&r.append("cv_file",t.file),r.append("cv_text",a("rcv-cv").value),r.append("job_text",a("rcv-job").value),r.append("notes",a("rcv-notes").value),r.append("lang",t.lang),r.append("cover",a("rcv-cover").checked?"1":"0"),x(!0),j("\u0110ang ch\u1EDD l\u01B0\u1EE3t",0),s.scrollIntoView({behavior:"smooth",block:"center"});try{let o=await fetch("/api/cv/review",{method:"POST",body:r}),i=await o.json().catch(()=>({error:`M\xE1y ch\u1EE7 ch\u01B0a c\xF3 API ph\xE2n t\xEDch CV (HTTP ${o.status}) \u2014 c\u1EA7n kh\u1EDFi \u0111\u1ED9ng l\u1EA1i Hub`}));if(!o.ok)throw new Error(i.error||`HTTP ${o.status}`);L(i.job,Date.now())}catch(o){x(!1),s.innerHTML=`<div class="rcv-alert bad" style="margin-top:1.25rem">${l("alert",18)}<div>${c(o.message)}</div></div>`}}),t.result&&_(t.result)}};export{Y as reviewingcvModule};
