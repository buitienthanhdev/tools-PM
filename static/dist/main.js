import{a as V}from"./c-JBZBYPLK.js";import{a as u}from"./c-2MTW4ZAX.js";import{a as p,b as m,c as v,d as S,e as T,f as I}from"./c-A7EUOZAY.js";var E=class{constructor(){this.state={theme:"dark",activeRoute:"catalog",systemHealth:{status:"connecting",device:"CPU",torchVersion:"2.13.0",cudaAvailable:!1},user:{name:"AI Master",role:"Administrator",avatar:"AI"},sidebarCollapsed:localStorage.getItem("pm_sidebar_collapsed")==="true"},document.documentElement.setAttribute("data-theme",this.state.theme)}getState(){return this.state}setTheme(e){this.state.theme=e,localStorage.setItem("pm_theme_v2",e),document.documentElement.setAttribute("data-theme",e),m.emit("theme:changed",e)}toggleTheme(){let e=this.state.theme==="dark"?"light":"dark";this.setTheme(e)}toggleSidebar(){this.state.sidebarCollapsed=!this.state.sidebarCollapsed,localStorage.setItem("pm_sidebar_collapsed",this.state.sidebarCollapsed),m.emit("sidebar:toggle",this.state.sidebarCollapsed)}setSystemHealth(e){this.state.systemHealth={...this.state.systemHealth,...e},m.emit("health:updated",this.state.systemHealth)}setActiveRoute(e){this.state.activeRoute=e,m.emit("route:changed",e)}},w=new E;var x=(t,e)=>{try{let n=JSON.stringify({vid:M,sid:$,...e});if(navigator.sendBeacon&&navigator.sendBeacon(`/api/track/${t}`,n))return;fetch(`/api/track/${t}`,{method:"POST",body:n,keepalive:!0,credentials:"same-origin"}).catch(()=>{})}catch{}},A=()=>crypto.randomUUID?crypto.randomUUID():`${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`,M;try{M=localStorage.getItem("pm_vid")||A(),localStorage.setItem("pm_vid",M)}catch{M=A()}var $;try{$=sessionStorage.getItem("pm_sid")||A(),sessionStorage.setItem("pm_sid",$)}catch{$=A()}var g=null,q=()=>document.visibilityState==="visible";function B(){if(!g)return;let t=g.visibleMs+(g.lastShown?Date.now()-g.lastShown:0);x("leave",{path:g.path,dur:Math.round(t/100)/10})}var P={page(t){g&&g.path===t||(B(),g={path:t,visibleMs:0,lastShown:q()?Date.now():0},x("pv",{path:t,title:document.title,ref:document.referrer||"",screen:`${screen.width}x${screen.height}`}))}};document.addEventListener("visibilitychange",()=>{g&&(q()?g.lastShown=Date.now():(g.lastShown&&(g.visibleMs+=Date.now()-g.lastShown),g.lastShown=0,B(),g.visibleMs=0))});window.addEventListener("pagehide",B);setInterval(()=>{q()&&g&&x("ping",{path:g.path})},6e4);var Q=0,C=(t,e,n,i)=>{++Q>20||x("err",{kind:t,msg:String(e||"").slice(0,500),src:String(n||"").slice(0,300),stack:String(i||"").slice(0,3e3),path:location.pathname})};window.addEventListener("error",t=>{var e,n,i;t.target&&t.target!==window&&(t.target.src||t.target.href)?C("ResourceError",`Kh\xF4ng t\u1EA3i \u0111\u01B0\u1EE3c ${(e=t.target.tagName)==null?void 0:e.toLowerCase()}`,t.target.src||t.target.href):/^ResizeObserver loop/.test(t.message||"")||C(((n=t.error)==null?void 0:n.name)||"Error",t.message,`${t.filename}:${t.lineno}:${t.colno}`,(i=t.error)==null?void 0:i.stack)},!0);window.addEventListener("unhandledrejection",t=>{let e=t.reason;C((e==null?void 0:e.name)||"UnhandledRejection",(e==null?void 0:e.message)||String(e),"",e==null?void 0:e.stack)});var H=class{constructor(){this.currentModule=null,this.workspaceEl=null,window.addEventListener("popstate",()=>{this.handleRouteResolution(window.location.pathname)})}init(e){this.workspaceEl=e,this.handleRouteResolution(window.location.pathname)}getCurrentRoute(){return window.location.pathname}navigate(e,n=!0){e||(e="/"),n&&window.location.pathname!==e&&history.pushState({route:e},"",e),this.handleRouteResolution(e)}handleRouteResolution(e){let n=p.getModuleByRoute(e);if(n||(console.warn(`[Router] No module found for route '${e}'. Defaulting to Catalog.`),n=p.getModuleById("catalog")||p.getAllModules()[0]),!n){console.error("[Router] Critical: No modules registered in registry."),this.workspaceEl&&(this.workspaceEl.innerHTML=`
          <div class="panel-card" style="padding:3rem; text-align:center;">
            <h2>\u26A0\uFE0F H\u1EC7 th\u1ED1ng \u0111ang kh\u1EDFi t\u1EA1o</h2>
            <p style="color:var(--text-dim); margin-top:0.5rem;">Ch\u01B0a t\xECm th\u1EA5y module. Vui l\xF2ng t\u1EA3i l\u1EA1i trang.</p>
          </div>
        `);return}if(!["catalog","login"].includes(n.id)&&u.loaded&&(n.id==="admin"?!u.isAdmin():!u.can(n.id))&&(u.user?m.emit("toast:show",{message:u.isActive()?"B\u1EA1n ch\u01B0a \u0111\u01B0\u1EE3c c\u1EA5p quy\u1EC1n d\xF9ng c\xF4ng c\u1EE5 n\xE0y":"T\xE0i kho\u1EA3n \u0111ang ch\u1EDD admin duy\u1EC7t",type:"error"}):sessionStorage.setItem("pm_next",e),window.location.pathname!=="/login"&&history.replaceState({route:"/login"},"","/login"),n=p.getModuleById("login")),this.currentModule&&this.currentModule.unmount&&this.workspaceEl)try{this.currentModule.unmount(this.workspaceEl)}catch(a){console.error(`[Router] Error unmounting module '${this.currentModule.name}':`,a)}if(this.currentModule=n,w.setActiveRoute(n.route),P.page(window.location.pathname),this.workspaceEl){this.workspaceEl.scrollTop=0;let a=o=>{this.currentModule===n&&(console.error(`[Router] Error rendering module '${n.name}':`,o),this.workspaceEl.innerHTML=`
          <div class="panel-card" style="text-align:center; padding:3rem;">
            <h2>\u274C L\u1ED7i T\u1EA3i Module</h2>
            <p style="color:var(--rose); margin-top:0.5rem;">${o.message}</p>
            <button class="btn btn-primary" style="margin-top:1.5rem;" onclick="window.router.navigate('/')">V\u1EC1 Trang Ch\u1EE7</button>
          </div>
        `)};try{Promise.resolve(n.render(this.workspaceEl)).catch(a)}catch(o){a(o)}}}},h=new H;window.router=h;var L=class{constructor(){this.container=document.createElement("div"),this.container.className="toast-container",document.body.appendChild(this.container),m.on("toast:show",e=>this.show(e))}show({message:e,type:n="info",duration:i=4e3,onClick:a=null}){let o=document.createElement("div");o.className=`toast ${n==="error"?"toast-error":""}`,a&&(o.style.cursor="pointer"),o.innerHTML=`<span>${e}</span>`,a&&o.addEventListener("click",()=>{try{a()}catch{}o.remove()}),this.container.appendChild(o),setTimeout(()=>{o.parentNode&&(o.style.opacity="0",o.style.transform="translateY(10px)",o.style.transition="all 0.3s ease",setTimeout(()=>o.remove(),300))},i)}};function j(t){let e=null,n=()=>{let i=w.getState().systemHealth||{status:"ok",device:"CUDA"},a=i.status==="ok";if(e&&(e.status==="processing"||e.status==="queued")){let o=e.progress||10,c=e.message||"\u0110ang x\u1EED l\xFD...",l=e.module==="whisper"?"\u{1F399}\uFE0F":"\u{1F50A}";t.innerHTML=`
        <div class="status-pill status-pill-running" id="liveJobPill" style="cursor:pointer;" title="B\u1EA5m \u0111\u1EC3 m\u1EDF giao di\u1EC7n t\xE1c v\u1EE5 \u0111ang ch\u1EA1y">
          <span class="status-dot status-dot-active"></span>
          <div style="display:flex; flex-direction:column; line-height:1.2; text-align:left;">
            <div style="font-size:0.75rem; font-weight:800; color:var(--primary); display:flex; align-items:center; gap:0.35rem;">
              <span>${l} ${e.title}</span>
              <span class="pct-badge">${o}%</span>
            </div>
            <div style="font-size:0.68rem; color:var(--text-main); font-weight:500; text-overflow:ellipsis; overflow:hidden; max-width:260px; white-space:nowrap;">
              ${c}
            </div>
          </div>
        </div>
      `;let d=t.querySelector("#liveJobPill");d&&(d.onclick=()=>{window.router&&window.router.navigate(e.route)})}else{let o=a?`System Ready \xB7 ${i.device.toUpperCase()} GPU`:"Connecting to AI Engine...";t.innerHTML=`
        <div class="status-pill">
          <span class="status-dot" style="${a?"":"background-color: var(--amber); box-shadow: 0 0 8px var(--amber);"}"></span>
          <span style="font-size:0.78rem; font-weight:600;">${o}</span>
        </div>
      `}};m.on("health:updated",n),V.subscribe(i=>{i.status==="processing"||i.status==="queued"?e=i:e&&e.id===i.id&&(e=null),n()}),n()}function N(t){let e=p.getAllModules().filter(r=>r.id!=="catalog"&&!r.hidden);t.innerHTML=`
    <header class="hn" id="hn">
      <a class="hn-logo" href="/" data-link>
        <img src="/assets/logo-sm.webp" alt="" />
        <b>PM Tools <span>Hub</span></b>
      </a>
      <nav class="hn-links">
        <a href="/" data-link data-nav="/">Trang ch\u1EE7</a>
        <div class="hn-drop" id="hnDrop">
          <button type="button" aria-haspopup="true">C\xF4ng c\u1EE5 ${v("chevron",14,2.2)}</button>
          <div class="hn-menu" role="menu">
            ${e.map(r=>`
              <a href="${r.route}" data-link data-nav="${r.route}" role="menuitem">
                <span class="ic">${S(r,18)}</span>
                <span><b>${r.name}</b><small>${r.category}</small></span>
              </a>`).join("")}
          </div>
        </div>
        <a href="/SpaceT" data-link data-nav="/SpaceT" class="hide-sm">SpaceT</a>
        <a href="/admin" data-link data-nav="/admin" id="hnAdmin" class="hide-sm" style="display:none">Qu\u1EA3n tr\u1ECB</a>
      </nav>
      <div class="hn-right">
        <div id="statusBadgeMount"></div>
        <a class="hn-user" id="hnUser" href="/login" data-link>\u0110\u0103ng nh\u1EADp</a>
        <a class="hn-cta" href="/" data-link>${v("grid",16,2)}<span>T\u1EA5t c\u1EA3 c\xF4ng c\u1EE5</span></a>
        <a class="gh-ava" href="https://github.com/buitienthanhdev" target="_blank" rel="noopener" title="GitHub \xB7 buitienthanhdev"><span class="gh-ring"></span><img src="https://github.com/buitienthanhdev.png?size=96" alt="buitienthanhdev" loading="lazy" decoding="async" width="40" height="40" /></a>
      </div>
    </header>
  `;let n=t.querySelector("#hn"),i=t.querySelector("#hnDrop");j(t.querySelector("#statusBadgeMount"));let a=t.querySelector("#hnUser"),o=t.querySelector("#hnAdmin"),c=r=>{a.textContent=r?r.status==="active"?r.name||r.email:"Ch\u1EDD duy\u1EC7t":"\u0110\u0103ng nh\u1EADp",a.classList.toggle("on",!!r),o.style.display=u.isAdmin()?"":"none"};m.on("auth:changed",c),c(u.user);let l=0,d=()=>{i.classList.contains("open")||(l=Date.now()),i.classList.add("open")};i.querySelector("button").addEventListener("click",r=>{r.stopPropagation(),i.classList.contains("open")&&Date.now()-l>400?i.classList.remove("open"):d()}),i.addEventListener("mouseenter",d),i.addEventListener("mouseleave",()=>i.classList.remove("open")),document.addEventListener("click",()=>i.classList.remove("open"));let s=r=>{t.querySelectorAll("[data-nav]").forEach(f=>{f.classList.toggle("on",f.dataset.nav.toLowerCase()===String(r||"/").toLowerCase())})};m.on("route:changed",r=>{s(r),i.classList.remove("open"),n.classList.remove("is-solid")}),s(h.getCurrentRoute()),requestAnimationFrame(()=>{let r=document.getElementById("mainWorkspaceViewport");r&&r.addEventListener("scroll",()=>{n.classList.toggle("is-solid",r.scrollTop>40)},{passive:!0})})}document.addEventListener("click",t=>{let e=t.target.closest("a[data-link]");!e||t.ctrlKey||t.metaKey||t.shiftKey||t.button!==0||(t.preventDefault(),h.navigate(e.dataset.link||e.getAttribute("href")))});function U(t){let e=p.getAllModules(),n={};e.forEach(l=>{let d=l.category||"General";n[d]||(n[d]=[]),n[d].push(l)});let i="";for(let[l,d]of Object.entries(n))i+=`
      <div class="nav-section">
        <div class="nav-section-label">${l}</div>
        <ul class="nav-list">
    `,d.forEach(s=>{i+=`
        <li>
          <button class="nav-item-btn" data-route="${s.route}" id="nav-btn-${s.id}">
            <span class="nav-icon">${S(s,18)}</span>
            <span class="nav-text">${s.name}</span>
          </button>
        </li>
      `}),i+=`
        </ul>
      </div>
    `;t.innerHTML=`
    <aside class="app-sidebar" id="appSidebar">
      <div class="sidebar-header">
        <a href="/" class="brand-logo" onclick="event.preventDefault(); window.router.navigate('/');">
          <div class="brand-logo-wrapper">
            <img src="/assets/logo-sm.webp" alt="PM Tools" class="brand-img-logo" />
            <div class="brand-logo-glow"></div>
          </div>
          <div class="brand-name">
            <span class="brand-name-main">PM Tools <span class="brand-accent">Hub</span></span>
            <span class="brand-tagline">AI Workspace Platform</span>
          </div>
        </a>
        <button class="sidebar-toggle-btn" id="sidebarCollapseBtn" title="Toggle Sidebar">
          <span>\u25C0</span>
        </button>
      </div>

      <nav class="sidebar-nav">
        ${i}
      </nav>

      <div class="sidebar-footer">
        <div class="sidebar-footer-card">
          <span>PM Tools Hub v3.0</span><b>CUDA GPU</b>
        </div>
      </div>
    </aside>
  `,t.querySelectorAll(".nav-item-btn").forEach(l=>{l.addEventListener("click",()=>{let d=l.getAttribute("data-route");d&&h.navigate(d)})});let a=t.querySelector("#sidebarCollapseBtn"),o=t.querySelector("#appSidebar");a&&o&&a.addEventListener("click",()=>{w.toggleSidebar()});let c=l=>{t.querySelectorAll(".nav-item-btn").forEach(d=>{let s=d.getAttribute("data-route");s===l||l==="/"&&s==="/"?d.classList.add("active"):d.classList.remove("active")})};m.on("route:changed",l=>c(l)),c(h.getCurrentRoute())}function W(t){t.innerHTML=`
    <main class="workspace-container" id="mainWorkspaceViewport">
      <div class="workspace-content" id="workspaceContent">
        <!-- Dynamic Module Page Mounted Here -->
      </div>
    </main>
  `}var y=t=>String(t!=null?t:"").replace(/[&<>"']/g,e=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[e]),k=t=>`/assets/previews/${t}.webp`,z=document.documentElement.classList.contains("lite"),J=t=>String(t+1).padStart(2,"0"),O=["Ch\u1EA1y tr\xEAn GPU ri\xEAng","Kh\xF4ng c\u1EA7n c\xE0i \u0111\u1EB7t","T\u1EF1 gi\xE1m s\xE1t 24/7","H\u1ED7 tr\u1EE3 ti\u1EBFng Vi\u1EC7t"],G={id:"catalog",name:"Trang ch\u1EE7 Hub",route:"/",icon:"\u{1F3E0}",category:"Platform",description:"Trung t\xE2m t\u1ED5ng h\u1EE3p & \u0111i\u1EC1u ph\u1ED1i c\xE1c c\xF4ng c\u1EE5 AI",status:"active",_cleanup:null,render(t){this.unmount(t),document.body.classList.add("route-home");let e=p.getAllModules().filter(s=>s.id!=="catalog"&&!s.hidden),n=e.map(s=>s.id),i=[...O,...O].map(s=>`<span>${y(s)}</span>`).join("");t.innerHTML=`
    <div class="wfl">
      <nav class="wfl-nav" id="wfl-nav">
        <div class="wfl-container wfl-nav-in">
          <div class="wfl-nav-links">
            <a href="#wfl-tools" data-jump="wfl-tools">C\xF4ng c\u1EE5</a>
            <a href="#wfl-features" data-jump="wfl-features">T\xEDnh n\u0103ng</a>
            <a href="#wfl-devices" data-jump="wfl-devices">Thi\u1EBFt b\u1ECB</a>
            <a href="/login" id="wfl-login" data-route="/login">${u.user?y(u.user.name||u.user.email):"\u0110\u0103ng nh\u1EADp"}</a>
          </div>
          <div class="wfl-nav-cta">
            <button class="wfl-btn" type="button" data-jump="wfl-tools">${v("arrow",18,2)} B\u1EAFt \u0111\u1EA7u ngay</button>
            <a class="gh-ava" href="https://github.com/buitienthanhdev" target="_blank" rel="noopener" title="GitHub \xB7 buitienthanhdev"><span class="gh-ring"></span><img src="https://github.com/buitienthanhdev.png?size=96" alt="buitienthanhdev" loading="lazy" decoding="async" width="40" height="40" /></a>
          </div>
        </div>
      </nav>

      <header class="wfl-hero wfl-noise">
        <div class="wfl-iso" aria-hidden="true">
          ${(z?[]:["voxcpm","spacet","whisper","reviewingcv","genreport","image"]).filter(s=>n.includes(s)).map(s=>`<img src="${k(s)}" alt="" loading="eager" />`).join("")}
        </div>
        <div class="wfl-container wfl-hero-c">
          <h1>B\u1ED9 c\xF4ng c\u1EE5 <span class="thin">AI Workspace</span> m\u1EA1nh m\u1EBD nh\u1EA5t \u0111\xE3 s\u1EB5n s\xE0ng</h1>
          <div class="wfl-hero-word" aria-hidden="true">PM Tools</div>
        </div>
      </header>

      <section class="wfl-demos" id="wfl-tools">
        <div class="wfl-demos-box">
          <h2 class="wfl-demos-title wfl-reveal">B\u1ED9 <b>${e.length}</b> c\xF4ng c\u1EE5 AI</h2>
          <div class="wfl-grid">
            ${e.map((s,r)=>`
              <button class="wfl-card wfl-reveal" type="button" data-route="${y(s.route)}" title="${y(s.description)}">
                <div class="wfl-card-img">
                  <img src="${k(s.id)}" alt="${y(s.name)}" loading="lazy" onerror="this.parentNode.style.background='#161616'" />
                  <span class="wfl-card-no">${J(r)}</span>
                  ${u.can(s.id)?"":`<span class="wfl-lock">${v("lock",12,2)} ${u.user?"Ch\u01B0a c\u1EA5p quy\u1EC1n":"\u0110\u0103ng nh\u1EADp"}</span>`}
                  <span class="wfl-card-go">M\u1EDF</span>
                </div>
                <div class="wfl-card-cap"><h3>${y(s.name)}</h3><small>${y(s.category)}</small></div>
              </button>`).join("")}
          </div>
        </div>
      </section>

      <section class="wfl-pages" id="wfl-features">
        <div class="wfl-container wfl-reveal">
          <span class="wfl-eyebrow">T\xEDnh n\u0103ng n\u1ED5i b\u1EADt</span>
          <h2>M\u1ECDi c\xF4ng c\u1EE5 ch\u1EA1y ngay trong tr\xECnh duy\u1EC7t, kh\xF4ng c\u1EA7n c\xE0i \u0111\u1EB7t</h2>
        </div>
        <div class="wfl-collage" aria-hidden="true">
          <div class="wfl-collage-in">
            ${[...n,"mobile",...n].slice(0,12).map(s=>`<img src="${k(s)}" alt="" loading="lazy" />`).join("")}
          </div>
        </div>
        <div class="wfl-container wfl-counters">
          <div class="wfl-counter"><b>${e.length}+</b><small>C\xF4ng c\u1EE5 AI</small></div>
          <div class="wfl-counter"><b>24/7</b><small>T\u1EF1 gi\xE1m s\xE1t</small></div>
        </div>
      </section>

      <section class="wfl-resp" id="wfl-devices">
        <div class="wfl-container wfl-resp-in">
          <div class="wfl-devices wfl-reveal" aria-hidden="true">
            <div class="wfl-tablet"><img src="${k(n.includes("reviewingcv")?"reviewingcv":n[0])}" alt="" loading="lazy" /></div>
            <div class="wfl-phone"><img src="${k("mobile")}" alt="" loading="lazy" /></div>
          </div>
          <div class="wfl-resp-text wfl-reveal">
            <span class="wfl-eyebrow">Tr\xEAn m\u1ECDi thi\u1EBFt b\u1ECB</span>
            <h2>D\xF9ng m\u01B0\u1EE3t <span class="thin">tr\xEAn m\u1ECDi</span> thi\u1EBFt b\u1ECB</h2>
            <p>Giao di\u1EC7n t\u1EF1 nh\u1EADn k\xEDch th\u01B0\u1EDBc m\xE0n h\xECnh v\xE0 co gi\xE3n n\u1ED9i dung, d\xF9ng t\u1ED1t tr\xEAn m\xE1y t\xEDnh, m\xE1y t\xEDnh b\u1EA3ng l\u1EABn \u0111i\u1EC7n tho\u1EA1i.</p>
            <button class="wfl-more" type="button" data-jump="wfl-tools">Kh\xE1m ph\xE1 ngay <span>${v("arrow",16,2)}</span></button>
          </div>
        </div>
      </section>

      <section class="wfl-band" aria-hidden="true">
        <div class="wfl-band-track">${i}${i}</div>
      </section>

      <section class="wfl-cta wfl-noise">
        ${(z?[]:["image","voxcpm","whisper","genreport","reviewingcv","legal"]).filter(s=>n.includes(s)).map((s,r)=>`<img class="wfl-float f${r+1}" src="${k(s)}" alt="" loading="lazy" />`).join("")}
        <div class="wfl-cta-in wfl-reveal">
          <span class="wfl-tag">S\u1EB5n s\xE0ng cho b\u1EA1n!</span>
          <h2 class="wfl-glass">B\u1EAFt \u0111\u1EA7u l\xE0m vi\u1EC7c c\xF9ng<br>AI ngay h\xF4m nay!</h2>
          <p>Kh\xF4ng c\u1EA7n t\xE0i kho\u1EA3n, kh\xF4ng c\u1EA7n c\xE0i \u0111\u1EB7t<br>Ch\u1ECDn m\u1ED9t c\xF4ng c\u1EE5 v\xE0 b\u1EAFt \u0111\u1EA7u trong v\xE0i gi\xE2y!</p>
          <button class="wfl-btn pill" type="button" data-jump="wfl-tools">Ch\u1ECDn c\xF4ng c\u1EE5</button>
        </div>
      </section>

      <button class="wfl-top" id="wfl-top" type="button" title="L\xEAn \u0111\u1EA7u trang">${v("down",18,2).replace("<svg",'<svg style="transform:rotate(180deg)"')}</button>
    </div>`;let a=document.getElementById("mainWorkspaceViewport")||t,o=t.querySelector("#wfl-nav"),c=t.querySelector("#wfl-top");t.querySelectorAll("[data-route]").forEach(s=>{s.addEventListener("click",()=>h.navigate(s.getAttribute("data-route")))}),t.querySelectorAll("[data-jump]").forEach(s=>{s.addEventListener("click",r=>{var f;r.preventDefault(),(f=t.querySelector("#"+s.dataset.jump))==null||f.scrollIntoView({behavior:"smooth",block:"start"})})}),c.addEventListener("click",()=>a.scrollTo({top:0,behavior:"smooth"}));let l=()=>{let s=a.scrollTop;o.classList.toggle("is-solid",s>40),c.classList.toggle("show",s>600)};a.addEventListener("scroll",l,{passive:!0}),a.scrollTop=0,l();let d=new IntersectionObserver(s=>{s.forEach(r=>{r.isIntersecting&&(r.target.classList.add("in"),d.unobserve(r.target))})},{root:a,threshold:.12});t.querySelectorAll(".wfl-reveal").forEach(s=>d.observe(s)),this._cleanup=()=>{a.removeEventListener("scroll",l),d.disconnect()}},unmount(t){this._cleanup&&this._cleanup(),this._cleanup=null,document.body.classList.remove("route-home"),t&&(t.innerHTML="")}};var R=t=>String(t!=null?t:"").replace(/[&<>"']/g,e=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[e]),D=(t,e="info")=>m.emit("toast:show",{message:t,type:e}),F={whisper:"Whisper Speech AI",voxcpm:"VoxCPM Voice AI",image:"N\xE9t \u1EA2nh AI",genreport:"B\xE1o c\xE1o ti\u1EBFn \u0111\u1ED9",legal:"AI T\u01B0 v\u1EA5n ph\xE1p lu\u1EADt",spacet:"SpaceT",reviewingcv:"Reviewing CV",accounting:"K\u1EBF to\xE1n AI",video:"Video Workspace"},K={id:"login",name:"T\xE0i kho\u1EA3n",route:"/login",icon:"\u{1F464}",category:"Platform",description:"\u0110\u0103ng nh\u1EADp v\xE0 qu\u1EA3n l\xFD t\xE0i kho\u1EA3n",status:"active",hidden:!0,_tab:"login",async render(t){await u.refresh();let e=u.user;if(e)return this._account(t,e);t.innerHTML=`
      ${T(this,{title:'\u0110\u0103ng nh\u1EADp <span class="thin">\u0111\u1EC3 d\xF9ng</span> c\xF4ng c\u1EE5 AI',sub:"T\xE0i kho\u1EA3n m\u1EDBi c\u1EA7n \u0111\u01B0\u1EE3c qu\u1EA3n tr\u1ECB vi\xEAn duy\u1EC7t v\xE0 c\u1EA5p quy\u1EC1n t\u1EEBng c\xF4ng c\u1EE5 tr\u01B0\u1EDBc khi s\u1EED d\u1EE5ng.",word:"Login",meta:["B\u1EA3o m\u1EADt","Admin c\u1EA5p quy\u1EC1n","D\u1EEF li\u1EC7u ri\xEAng t\u01B0"]})}
      <div class="mp-body" style="max-width:560px;">
        <div class="mp-panel">
          <div class="au-tabs">
            <button type="button" data-tab="login" class="${this._tab==="login"?"on":""}">\u0110\u0103ng nh\u1EADp</button>
            <button type="button" data-tab="register" class="${this._tab==="register"?"on":""}">\u0110\u0103ng k\xFD</button>
          </div>
          <form id="au-form" autocomplete="on"></form>
        </div>
      </div>`;let n=t.querySelector("#au-form"),i=()=>{let a=this._tab==="register";n.innerHTML=`
        ${a?'<div class="form-group"><label class="form-label">H\u1ECD t\xEAn</label><input class="form-input" name="name" autocomplete="name" placeholder="Nguy\u1EC5n V\u0103n A" /></div>':""}
        <div class="form-group"><label class="form-label">${a?"Email":"Email / T\xEAn \u0111\u0103ng nh\u1EADp"}</label><input class="form-input" type="${a?"email":"text"}" name="email" autocomplete="${a?"email":"username"}" required placeholder="${a?"ban@example.com":"Email ho\u1EB7c t\xEAn \u0111\u0103ng nh\u1EADp"}" /></div>
        <div class="form-group"><label class="form-label">M\u1EADt kh\u1EA9u</label><input class="form-input" type="password" name="password" required minlength="${a?8:1}" autocomplete="${a?"new-password":"current-password"}" placeholder="${a?"T\u1ED1i thi\u1EC3u 8 k\xFD t\u1EF1":""}" /></div>
        ${a&&u.needsAdminSetup?'<div class="form-group"><label class="form-label">M\xE3 c\xE0i \u0111\u1EB7t admin <span style="text-transform:none;letter-spacing:0;color:var(--text-dim)">(ch\u1EC9 d\xF9ng cho email qu\u1EA3n tr\u1ECB l\u1EA7n \u0111\u1EA7u)</span></label><input class="form-input" name="setup_code" autocomplete="off" /></div>':""}
        <div id="au-err" class="mp-error" style="display:none;margin-bottom:16px;"></div>
        <button class="btn btn-primary btn-block btn-lg" type="submit">${a?"T\u1EA1o t\xE0i kho\u1EA3n":"\u0110\u0103ng nh\u1EADp"}</button>
        ${a?'<div class="mp-hint" style="margin-top:14px;">'+v("bulb",15,2)+"<span>Sau khi \u0111\u0103ng k\xFD, qu\u1EA3n tr\u1ECB vi\xEAn s\u1EBD duy\u1EC7t v\xE0 c\u1EA5p quy\u1EC1n cho b\u1EA1n.</span></div>":""}`};i(),t.querySelectorAll("[data-tab]").forEach(a=>{a.onclick=()=>{this._tab=a.dataset.tab,t.querySelectorAll("[data-tab]").forEach(o=>o.classList.toggle("on",o===a)),i()}}),n.onsubmit=async a=>{a.preventDefault();let o=Object.fromEntries(new FormData(n)),c=n.querySelector("#au-err"),l=n.querySelector("button[type=submit]");c.style.display="none",l.disabled=!0;try{this._tab==="register"?await u.register(o):await u.login(o.email,o.password);let d=sessionStorage.getItem("pm_next");sessionStorage.removeItem("pm_next"),D("\u0110\u0103ng nh\u1EADp th\xE0nh c\xF4ng","success"),h.navigate(u.isActive()?d||"/":"/login")}catch(d){c.textContent=d.message,c.style.display="flex",l.disabled=!1}}},_account(t,e){var i;let n=e.status!=="active";t.innerHTML=`
      ${T(this,{title:n?'T\xE0i kho\u1EA3n <span class="thin">\u0111ang ch\u1EDD</span> duy\u1EC7t':`Xin ch\xE0o, <span class="thin">${R(e.name||e.email)}</span>`,sub:n?"Qu\u1EA3n tr\u1ECB vi\xEAn s\u1EBD duy\u1EC7t t\xE0i kho\u1EA3n v\xE0 c\u1EA5p quy\u1EC1n c\xF4ng c\u1EE5 cho b\u1EA1n. B\u1EA1n c\xF3 th\u1EC3 quay l\u1EA1i trang n\xE0y sau.":"\u0110\xE2y l\xE0 c\xE1c c\xF4ng c\u1EE5 b\u1EA1n \u0111\u01B0\u1EE3c ph\xE9p s\u1EED d\u1EE5ng.",word:"Account",meta:[e.role==="admin"?"Qu\u1EA3n tr\u1ECB vi\xEAn":"Th\xE0nh vi\xEAn",R(e.email)]})}
      <div class="mp-body" style="max-width:900px;">
        <div class="mp-panel">
          ${I("01","Quy\u1EC1n","truy c\u1EADp")}
          ${n?`<div class="mp-empty"><div class="mp-drop-ic">${v("lock",22)}</div>Ch\u01B0a c\xF3 quy\u1EC1n n\xE0o. Vui l\xF2ng ch\u1EDD qu\u1EA3n tr\u1ECB vi\xEAn duy\u1EC7t.</div>`:`<div class="au-mods">${e.modules.map(a=>`<a class="au-mod" href="#" data-go="${a}">${R(F[a]||a)}</a>`).join("")||'<span style="color:var(--text-dim)">Ch\u01B0a \u0111\u01B0\u1EE3c c\u1EA5p c\xF4ng c\u1EE5 n\xE0o.</span>'}</div>`}
          ${e.role==="admin"?`<div style="margin-top:22px;"><button class="btn btn-primary" id="au-admin">${v("grid",16,2)} M\u1EDF trang qu\u1EA3n tr\u1ECB</button></div>`:""}
        </div>
        <div class="mp-panel">
          ${I("02","\u0110\u1ED5i","m\u1EADt kh\u1EA9u")}
          <form id="au-pw" style="max-width:420px;">
            <div class="form-group"><label class="form-label">M\u1EADt kh\u1EA9u c\u0169</label><input class="form-input" type="password" name="old" required autocomplete="current-password" /></div>
            <div class="form-group"><label class="form-label">M\u1EADt kh\u1EA9u m\u1EDBi</label><input class="form-input" type="password" name="new" required minlength="8" autocomplete="new-password" /></div>
            <button class="btn btn-secondary" type="submit">C\u1EADp nh\u1EADt m\u1EADt kh\u1EA9u</button>
          </form>
        </div>
        <div><button class="btn btn-secondary" id="au-out">\u0110\u0103ng xu\u1EA5t</button></div>
      </div>`,t.querySelectorAll("[data-go]").forEach(a=>{a.onclick=o=>{var l;o.preventDefault();let c=(l=window.moduleRegistry)==null?void 0:l.getModuleById(a.dataset.go);h.navigate(c?c.route:"/")}}),(i=t.querySelector("#au-admin"))==null||i.addEventListener("click",()=>h.navigate("/admin")),t.querySelector("#au-out").onclick=async()=>{await u.logout(),h.navigate("/")},t.querySelector("#au-pw").onsubmit=async a=>{a.preventDefault();let o=a.target;try{await u.changePassword(o.old.value,o.new.value),o.reset(),D("\u0110\xE3 \u0111\u1ED5i m\u1EADt kh\u1EA9u","success")}catch(c){D(c.message,"error")}}},unmount(){}};function b(t,e){let n=null,i=null,a={...t,async render(o){if(!n){o.innerHTML='<div class="lazy-loading"><span class="spinner"></span></div>';try{n=await(i||(i=e()))}catch(c){throw i=null,c}if(h.currentModule!==a)return}return n.render(o)},unmount(o){var c;(c=n==null?void 0:n.unmount)==null||c.call(n,o)},preload(){return!n&&!i&&(i=e().then(o=>n=o,o=>{throw i=null,o})),i}};return a}var X=b({id:"whisper",name:"Whisper Speech AI",route:"/Whisper",icon:"\u{1F399}\uFE0F",category:"Speech AI",status:"active",description:"B\xF3c b\u0103ng \xE2m thanh, d\u1ECBch thu\u1EADt v\xE0 xu\u1EA5t ph\u1EE5 \u0111\u1EC1 t\u1EF1 \u0111\u1ED9ng b\u1EB1ng m\xF4 h\xECnh OpenAI Whisper GPU."},()=>import("./c-4SWYQHPX.js").then(t=>t.whisperModule)),Y=b({id:"voxcpm",name:"VoxCPM Voice AI",route:"/VoxCPM",icon:"\u{1F50A}",category:"Speech AI",status:"active",description:"VoxCPM2 (2B) \u2014 30 ng\xF4n ng\u1EEF, Voice Design & Cloning, 48kHz WAV. Ch\u1EA1y tr\u1EF1c ti\u1EBFp trong trang."},()=>import("./c-P4KCV6DH.js").then(t=>t.voxcpmModule)),Z=b({id:"image",name:"Image Workspace",route:"/Image",icon:"\u{1F5BC}\uFE0F",category:"Vision AI",status:"active",description:"Ch\u1EC9nh s\u1EEDa v\xE0 n\xE2ng c\u1EA5p \u1EA3nh b\u1EB1ng AI theo d\u1EF1 \xE1n: \u1EA3nh ngu\u1ED3n b\xEAn tr\xE1i, k\u1EBFt qu\u1EA3 b\xEAn ph\u1EA3i."},()=>import("./c-6R2RRB4N.js").then(t=>t.imageModule)),tt=b({id:"genreport",name:"B\xE1o C\xE1o Ti\u1EBFn \u0110\u1ED9 (GenReport)",route:"/genreport",icon:"\u{1F4C4}",category:"Automation AI",status:"active",description:"T\u1EF1 \u0111\u1ED9ng sinh b\xE1o c\xE1o ti\u1EBFn \u0111\u1ED9 k\u1EF9 thu\u1EADt chuy\xEAn s\xE2u b\u1EB1ng AI local (Ollama) v\xE0 xu\u1EA5t file Word (.docx) chu\u1EA9n doanh nghi\u1EC7p."},()=>import("./c-CKVIHI5D.js").then(t=>t.genreportModule)),et=b({id:"legal",name:"AI T\u01B0 v\u1EA5n ph\xE1p lu\u1EADt",route:"/legal",icon:"\u2696\uFE0F",category:"Legal AI",status:"active",description:"H\u1ECFi \u0111\xE1p ph\xE1p lu\u1EADt b\u1EB1ng AI \u2014 tr\u1EA3 l\u1EDDi c\xF3 c\u0103n c\u1EE9 \u0111i\u1EC1u lu\u1EADt, th\xE2n thi\u1EC7n v\xE0 \u0111\u1EA7y \u0111\u1EE7."},()=>import("./c-3MMWW5L7.js").then(t=>t.legalModule)),nt=b({id:"spacet",name:"SpaceT",route:"/SpaceT",icon:"\u{1F310}",category:"Geospatial",status:"active",description:"Qu\u1EA3 \u0111\u1ECBa c\u1EA7u 3D th\u1EDDi gian th\u1EF1c: m\xE1y bay, v\u1EC7 tinh, \u0111\u1ED9ng \u0111\u1EA5t, th\u1EDDi ti\u1EBFt (God's Eye View)."},()=>import("./c-5PLFVP3D.js").then(t=>t.spacetModule)),at=b({id:"reviewingcv",name:"Reviewing CV",route:"/reviewingCV",icon:"\u{1F4C4}",category:"Career AI",status:"active",description:"Ch\u1EA5m CV theo tin tuy\u1EC3n d\u1EE5ng: \u0111i\u1EC3m ph\xF9 h\u1EE3p, ATS, \u0111\u1EC1 xu\u1EA5t s\u1EEDa t\u1EEBng d\xF2ng (b\u1ED9 quy t\u1EAFc ai-job-search)."},()=>import("./c-FAI6UBEG.js").then(t=>t.reviewingcvModule)),ot=b({id:"accounting",name:"K\u1EBF to\xE1n AI",route:"/accounting",icon:"\u{1F9FE}",category:"Finance AI",status:"active",description:"K\xE9o th\u1EA3 ch\u1EE9ng t\u1EEB, ra l\u1EC7nh b\u1EB1ng ti\u1EBFng Vi\u1EC7t: AI \u0111\u1ECDc ho\xE1 \u0111\u01A1n, sao k\xEA, Excel, \u0111\u1ED1i so\xE1t, \u0111\u1ECBnh kho\u1EA3n \u0111\u1EC1 xu\u1EA5t v\xE0 xu\u1EA5t b\xE1o c\xE1o c\xF3 ki\u1EC3m ch\u1EE9ng."},()=>import("./c-O72JSPQZ.js").then(t=>t.accountingModule)),st=b({id:"video",name:"Video Workspace",route:"/video",icon:"\u{1F3AC}",category:"Video AI",status:"active",description:"T\u0103ng \u0111\u1ED9 ph\xE2n gi\u1EA3i, kh\u1EED nhi\u1EC5u, ph\u1EE5c h\u1ED3i video n\xE9n v\xE0 n\u1ED9i suy fps b\u1EB1ng REAL-Video-Enhancer tr\xEAn GPU ri\xEAng; c\xF3 x\u1EED l\xFD th\u1EED v\xE0 so s\xE1nh tr\u01B0\u1EDBc/sau."},()=>import("./c-56EK4ZOD.js").then(t=>t.videoModule)),it=b({id:"admin",name:"Qu\u1EA3n tr\u1ECB",route:"/admin",icon:"\u{1F6E1}\uFE0F",category:"Platform",status:"active",hidden:!0,description:"Dashboard theo d\xF5i, qu\u1EA3n l\xFD t\xE0i kho\u1EA3n v\xE0 quy\u1EC1n truy c\u1EADp"},()=>import("./c-5RWMDCSX.js").then(t=>t.adminModule));async function rt(){console.log("[PM Tools Hub] Booting platform..."),new L,p.register(G),p.register(X),p.register(Y),p.register(Z),p.register(tt),p.register(et),p.register(nt),p.register(at),p.register(K),p.register(it),window.moduleRegistry=p,await u.refresh(),u.features.accounting&&p.register(ot),u.features.video&&p.register(st);let t=document.getElementById("sidebarMount"),e=document.getElementById("topNavMount"),n=document.getElementById("workspaceMount");t&&U(t),e&&N(e),n&&W(n);let i=document.getElementById("workspaceContent");i&&h.init(i),window.addEventListener("monali:job_completed",c=>{let l=c.detail;m.emit("toast:show",{message:`\u{1F389} ${l.title} \u0111\xE3 ho\xE0n th\xE0nh! Click \u0111\u1EC3 xem k\u1EBFt qu\u1EA3.`,type:"success",duration:1e4,onClick:()=>h.navigate(l.route)})}),"serviceWorker"in navigator&&location.protocol==="https:"&&addEventListener("load",()=>navigator.serviceWorker.register("/sw.js").catch(()=>{}));async function a(){try{let c=await fetch("/api/health");c.ok&&w.setSystemHealth(await c.json())}catch{w.setSystemHealth({status:"connecting",device:"CPU"})}}a(),setInterval(()=>{document.hidden||a()},3e4),document.addEventListener("visibilitychange",()=>{document.hidden||a()});let o=c=>{var s,r,f,_;let l=(r=(s=c.target).closest)==null?void 0:r.call(s,"a[href], [data-route]"),d=l&&(l.getAttribute("data-route")||l.getAttribute("href"));d&&d.startsWith("/")&&((_=(f=p.getModuleByRoute(d))==null?void 0:f.preload)==null||_.call(f).catch(()=>{}))};document.addEventListener("pointerover",o,{passive:!0}),document.addEventListener("touchstart",o,{passive:!0}),console.log("[PM Tools Hub] Platform ready!")}document.addEventListener("DOMContentLoaded",rt);
