var i="https://spacet.sonxit.io.vn",e="route-spacet",s="spacet-route-style";var l=`
.${e} .workspace-container { padding: 72px 0 0; overflow: hidden; display: flex; }
.${e} .workspace-content { max-width: none; width: 100%; margin: 0; gap: 0; flex: 1; min-height: 0; }
.${e} .app-topnav { backdrop-filter: none; -webkit-backdrop-filter: none; }
.${e} *, .${e} *::before, .${e} *::after { animation: none !important; }
`,d={id:"spacet",name:"SpaceT",route:"/SpaceT",icon:"\u{1F310}",category:"Geospatial",description:"Qu\u1EA3 \u0111\u1ECBa c\u1EA7u 3D th\u1EDDi gian th\u1EF1c: m\xE1y bay, v\u1EC7 tinh, \u0111\u1ED9ng \u0111\u1EA5t, th\u1EDDi ti\u1EBFt (God's Eye View).",status:"active",_cleanup:null,render(t){if(this.unmount(),!document.getElementById(s)){let o=document.createElement("style");o.id=s,o.textContent=l,document.head.appendChild(o)}document.body.classList.add(e),t.innerHTML=`
      <div style="position:relative;flex:1;min-height:0;background:#05070d;">
        <iframe id="st-frame" src="${i}/" title="SpaceT \u2014 God's Eye View"
          allow="fullscreen; geolocation; clipboard-write" referrerpolicy="strict-origin-when-cross-origin"
          style="position:absolute;inset:0;width:100%;height:100%;border:0;"></iframe>
        <div id="st-status" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:1rem;color:#cbd5e1;background:#05070d;pointer-events:none;transition:opacity .25s;">
          \u0110ang t\u1EA3i qu\u1EA3 \u0111\u1ECBa c\u1EA7u\u2026
        </div>
      </div>`;let c=t.querySelector("#st-frame"),n=t.querySelector("#st-status"),r=()=>{clearTimeout(a),n.style.opacity="0",setTimeout(()=>{n.style.display="none"},300)},a=setTimeout(()=>{n.innerHTML=`\u0110ang t\u1EA3i l\xE2u h\u01A1n b\xECnh th\u01B0\u1EDDng\u2026<br><a href="${i}/" target="_blank" rel="noopener" style="pointer-events:auto;color:#7dd3fc;">M\u1EDF tr\u1EF1c ti\u1EBFp ${i.replace("https://","")}</a>`},3e4);c.addEventListener("load",r,{once:!0}),this._cleanup=()=>{clearTimeout(a),document.body.classList.remove(e)}},unmount(){this._cleanup&&(this._cleanup(),this._cleanup=null)}};export{d as spacetModule};
