import{a as d}from"./c-JBZBYPLK.js";import{b as u,c as a,e as m,f as g}from"./c-A7EUOZAY.js";var S={id:"voxcpm",name:"VoxCPM Voice AI",route:"/VoxCPM",icon:"\u{1F50A}",category:"Speech AI",description:"VoxCPM2 (2B) \u2014 30 ng\xF4n ng\u1EEF, Voice Design & Cloning, 48kHz WAV. Ch\u1EA1y tr\u1EF1c ti\u1EBFp trong trang.",status:"active",_state:{refFile:null,busy:!1,unsubscribe:null},render(e){this._state.refFile=null,this._state.busy=!1,e.innerHTML=`
    ${m(this,{title:'Thi\u1EBFt k\u1EBF <span class="thin">& nh\xE2n b\u1EA3n</span> gi\u1ECDng n\xF3i AI',sub:"T\u1EA1o gi\u1ECDng n\xF3i 48kHz cho 30 ng\xF4n ng\u1EEF. M\xF4 t\u1EA3 gi\u1ECDng b\u1EA1n mu\u1ED1n, ho\u1EB7c \u0111\u01B0a m\u1ED9t \u0111o\u1EA1n audio ng\u1EAFn \u0111\u1EC3 AI nh\xE2n b\u1EA3n \u0111\xFAng ch\u1EA5t gi\u1ECDng \u0111\xF3.",word:"Voice",meta:["VoxCPM2 \xB7 2B","30 ng\xF4n ng\u1EEF","WAV 48kHz"]})}

    <div class="mp-body">
      <div class="mp-grid">

        <div class="mp-panel">
          ${g("01","C\xE0i \u0111\u1EB7t","gi\u1ECDng n\xF3i")}

          <div class="form-group">
            <label class="form-label">Ch\u1EBF \u0111\u1ED9</label>
            <select class="form-select" id="vox-mode">
              <option value="design" selected>Voice Design \u2014 t\u1EA1o gi\u1ECDng t\u1EEB m\xF4 t\u1EA3</option>
              <option value="cloning">Voice Cloning \u2014 nh\xE2n b\u1EA3n t\u1EEB audio</option>
              <option value="ultimate">Ultimate Clone \u2014 k\u1EBF th\u1EEBa ho\xE0n to\xE0n</option>
            </select>
          </div>

          <div class="form-group" id="vox-group-prompt">
            <label class="form-label">M\xF4 t\u1EA3 gi\u1ECDng n\xF3i</label>
            <textarea class="form-textarea" id="vox-prompt" rows="3"
              placeholder="V\xED d\u1EE5: Gi\u1ECDng nam tr\u1EBB, truy\u1EC1n c\u1EA3m, nh\u1ECBp nh\xE0ng, n\u0103ng l\u01B0\u1EE3ng t\xEDch c\u1EF1c..."></textarea>
          </div>

          <div class="form-group" id="vox-group-ref-text" style="display:none">
            <label class="form-label">L\u1EDDi tho\u1EA1i trong audio tham chi\u1EBFu</label>
            <textarea class="form-textarea" id="vox-ref-text" rows="2"
              placeholder="Nh\u1EADp \u0111\xFAng l\u1EDDi n\xF3i trong file tham chi\u1EBFu (\u0111\u1EC3 tr\u1ED1ng \u0111\u1EC3 AI t\u1EF1 nh\u1EADn di\u1EC7n)..."></textarea>
          </div>

          <div class="form-group">
            <label class="form-label">Audio tham chi\u1EBFu (cho nh\xE2n b\u1EA3n gi\u1ECDng)</label>
            <input type="file" class="form-input" id="vox-ref-audio" accept=".mp3,.wav,.m4a,.flac,.ogg,.webm" />
            <div id="vox-ref-name" style="font-size:12.5px;color:var(--primary);margin-top:8px;"></div>
            <div class="mp-hint">${a("bulb",15,2)}<span><b>M\u1EB9o:</b> ch\u1ECDn \u0111o\u1EA1n 5\u201315 gi\xE2y <em>ch\u1EC9 c\xF3 ti\u1EBFng ng\u01B0\u1EDDi n\xF3i</em>, tr\xE1nh b\xE0i h\xE1t d\xE0i ho\u1EB7c c\xF3 nh\u1EA1c n\u1EC1n.</span></div>
          </div>

          <div style="display:grid;grid-template-columns:1fr 1.4fr;gap:14px;">
            <div class="form-group">
              <label class="form-label">CFG Scale</label>
              <input type="number" class="form-input" id="vox-cfg" value="2.0" step="0.5" min="1.0" max="5.0" />
            </div>
            <div class="form-group">
              <label class="form-label">M\xF4 h\xECnh</label>
              <select class="form-select" id="vox-model">
                <option value="voxcpm2-2b" selected>VoxCPM2 \xB7 2B \xB7 48kHz</option>
                <option value="voxcpm1.5">VoxCPM1.5 \xB7 Expressive</option>
              </select>
            </div>
          </div>
        </div>

        <div class="mp-panel flex">
          ${g("02","V\u0103n b\u1EA3n","c\u1EA7n \u0111\u1ECDc",`<button class="btn btn-secondary btn-sm" id="btnInsertSampleText">${a("bulb",14,2)} V\u0103n b\u1EA3n m\u1EABu</button>`)}

          <textarea class="form-textarea" id="vox-text" rows="8"
            placeholder="Nh\u1EADp \u0111o\u1EA1n v\u0103n b\u1EA3n b\u1EA1n mu\u1ED1n AI \u0111\u1ECDc (Ti\u1EBFng Vi\u1EC7t, Anh, Trung, Nh\u1EADt, H\xE0n...)"></textarea>

          <button class="btn btn-primary btn-block btn-lg" id="vox-btn">${a("spark",18,2)} T\u1ED5ng h\u1EE3p gi\u1ECDng n\xF3i</button>

          <div class="mp-progress" id="vox-progress-wrap" style="display:none;">
            <div class="mp-progress-msg" id="vox-progress-msg">\u0110ang x\u1EED l\xFD...</div>
            <div class="progress-bar-bg"><div class="progress-bar-fill" id="vox-progress-bar" style="width:5%"></div></div>
          </div>

          <div>
            <div class="mp-label">K\u1EBFt qu\u1EA3 \xE2m thanh</div>
            <div class="mp-output" id="vox-output">
              <div class="mp-empty" style="min-height:150px;">
                <div class="mp-drop-ic">${a("voxcpm",22)}</div>
                Ch\u01B0a c\xF3 \xE2m thanh. Nh\u1EADp v\u0103n b\u1EA3n v\xE0 b\u1EA5m \u201CT\u1ED5ng h\u1EE3p gi\u1ECDng n\xF3i\u201D.
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>`,this._bind(e),this._restoreLatestJob(e)},_restoreLatestJob(e){let t=d.getLatestJobForModule("voxcpm"),s=e.querySelector("#vox-progress-wrap"),n=e.querySelector("#vox-progress-bar"),l=e.querySelector("#vox-progress-msg"),c=e.querySelector("#vox-output"),i=e.querySelector("#vox-btn");(t==null?void 0:t.status)==="completed"&&t.result?this._renderAudioResult(t.result,c):((t==null?void 0:t.status)==="queued"||(t==null?void 0:t.status)==="processing")&&(this._state.busy=!0,i&&(i.disabled=!0),s&&(s.style.display="block"),n&&(n.style.width=`${t.progress||10}%`),l&&(l.textContent=t.message||"\u0110ang sinh gi\u1ECDng ng\u1EA7m...")),this._state.unsubscribe&&this._state.unsubscribe(),this._state.unsubscribe=d.subscribe(o=>{(o==null?void 0:o.module)==="voxcpm"&&(o.status==="processing"||o.status==="queued"?(this._state.busy=!0,i&&(i.disabled=!0),s&&(s.style.display="block"),n&&(n.style.width=`${o.progress||10}%`),l&&(l.textContent=o.message||"\u0110ang sinh gi\u1ECDng n\xF3i...")):o.status==="completed"&&o.result?(this._state.busy=!1,i&&(i.disabled=!1),s&&(s.style.display="none"),this._renderAudioResult(o.result,c)):o.status==="failed"&&(this._state.busy=!1,i&&(i.disabled=!1),s&&(s.style.display="none"),c.innerHTML=`<div class="mp-error">${a("alert",18,2)} L\u1ED7i: ${o.message}</div>`))})},_bind(e){var t;(t=e.querySelector("#btnInsertSampleText"))==null||t.addEventListener("click",()=>{let s="Th\u1EB1ng em t\u1EA1o c\xF3 l\u1ED7i, nh\u01B0ng \u1EDF \u0111\xE2y c\xF3 th\u1EB1ng n\xE0o kh\xF4ng c\xF3 l\u1ED7i kh\xF4ng? Ngay c\u1EA3 tao v\u1EDBi m\xE0y c\u0169ng c\xF3 l\u1ED7i!";e.querySelector("#vox-text").value=s,u.emit("toast:show",{message:"\u0110\xE3 \u0111i\u1EC1n v\u0103n b\u1EA3n m\u1EABu!"})}),e.querySelector("#vox-mode").addEventListener("change",s=>{let n=s.target.value;e.querySelector("#vox-group-prompt").style.display=n==="ultimate"?"none":"block",e.querySelector("#vox-group-ref-text").style.display=n==="ultimate"?"block":"none"}),e.querySelector("#vox-ref-audio").addEventListener("change",s=>{let n=s.target.files[0];n&&(this._state.refFile=n,e.querySelector("#vox-ref-name").textContent=`\u{1F3B5} ${n.name} (${(n.size/1048576).toFixed(2)} MB)`)}),e.querySelector("#vox-btn").addEventListener("click",()=>this._synthesize(e))},async _synthesize(e){if(this._state.busy)return;let t=e.querySelector("#vox-text").value.trim();if(!t){u.emit("toast:show",{message:"Vui l\xF2ng nh\u1EADp v\u0103n b\u1EA3n b\u1EA1n mu\u1ED1n AI \u0111\u1ECDc!",type:"error"}),e.querySelector("#vox-text").focus();return}let s=e.querySelector("#vox-prompt").value.trim(),n=e.querySelector("#vox-ref-text").value.trim(),l=parseFloat(e.querySelector("#vox-cfg").value)||2,c=e.querySelector("#vox-mode").value,i=e.querySelector("#vox-btn"),o=e.querySelector("#vox-progress-wrap"),v=e.querySelector("#vox-progress-bar"),b=e.querySelector("#vox-progress-msg"),h=e.querySelector("#vox-output");this._state.busy=!0,i.disabled=!0,o.style.display="block",v.style.width="5%",b.textContent="\u0110ang g\u1EEDi y\xEAu c\u1EA7u t\u1EDBi VoxCPM2 GPU Engine...";try{let r=new FormData;r.append("text",t),r.append("control",c==="ultimate"?"":s),r.append("prompt_text",c==="ultimate"?n:""),r.append("cfg",l),this._state.refFile&&r.append("ref_audio",this._state.refFile);let p=await fetch("/api/voxcpm/generate",{method:"POST",body:r});if(!p.ok){let f=await p.json().catch(()=>({}));throw new Error(f.error||`HTTP ${p.status}`)}let{job_id:x}=await p.json();d.trackJob({id:x,module:"voxcpm",route:"/VoxCPM",title:`VoxCPM Gi\u1ECDng N\xF3i AI ("${t.slice(0,20)}...")`}),u.emit("toast:show",{message:"\u{1F680} T\xE1c v\u1EE5 sinh gi\u1ECDng \u0111ang ch\u1EA1y ng\u1EA7m! B\u1EA1n c\xF3 th\u1EC3 chuy\u1EC3n trang."})}catch(r){this._state.busy=!1,i.disabled=!1,o.style.display="none",h.innerHTML=`<div class="mp-error">${a("alert",18,2)} L\u1ED7i: ${r.message}</div>`,u.emit("toast:show",{message:`\u274C ${r.message}`,type:"error"})}},_renderAudioResult(e,t){if(!t||!e)return;let s=e.duration?`${e.duration}s`:"Ho\xE0n t\u1EA5t!";t.innerHTML=`
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px;">
        <div class="mp-meta" style="margin:0;"><span>Ho\xE0n t\u1EA5t</span><span>${s}</span><span>${e.sample_rate||48e3}Hz</span></div>
        <a href="${e.audio_url}" download="voxcpm_output.wav" class="btn btn-primary btn-sm">${a("download",14,2)} T\u1EA3i WAV 48kHz</a>
      </div>
      <audio controls autoplay src="${e.audio_url}" style="width:100%;outline:none;"></audio>`},unmount(e){this._state.unsubscribe&&(this._state.unsubscribe(),this._state.unsubscribe=null),e.innerHTML=""}};export{S as voxcpmModule};
