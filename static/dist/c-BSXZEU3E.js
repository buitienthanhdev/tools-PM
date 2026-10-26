import{a as d}from"./c-RIJMV2JA.js";import{b as c,c as l,e as b,f as u}from"./c-A7EUOZAY.js";async function m(e,t={}){try{let r=await fetch(e,t);if(!r.ok){let a=await r.json().catch(()=>({})),s=a.error||a.message||`HTTP Error ${r.status}`;throw c.emit("toast:show",{message:`\u274C ${s}`,type:"error"}),new Error(s)}return await r.json()}catch(r){throw r.name!=="AbortError"&&console.error(`[API Error] ${e}:`,r.message),r}}var h={async transcribeAudio(e,t,r,a){let s=new FormData;return s.append("audio",e),s.append("model",t),s.append("language",r),s.append("task",a),await m("/api/transcribe",{method:"POST",body:s})},createJobStream(e,t,r,a){let s=new EventSource(`/api/job/${e}/stream`);return s.onmessage=n=>{try{let i=JSON.parse(n.data);t&&t(i),i.status==="completed"?(s.close(),r&&r(i.result)):i.status==="failed"&&(s.close(),a&&a(new Error(i.message||"Job failed")))}catch(i){s.close(),a&&a(i)}},s.onerror=n=>{s.close(),a&&a(new Error("M\u1EA5t k\u1EBFt n\u1ED1i v\u1EDBi server"))},s},async exportResult(e,t){let r=await fetch(`/api/export/${e}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({result:t})});if(!r.ok)throw new Error("Export error");let a=await r.blob(),s=URL.createObjectURL(a),n=document.createElement("a");n.href=s,n.download=`transcription.${e}`,n.click(),URL.revokeObjectURL(s)}};var k={id:"whisper",name:"Whisper Speech AI",route:"/Whisper",icon:"\u{1F399}\uFE0F",category:"Speech AI",description:"B\xF3c b\u0103ng \xE2m thanh, d\u1ECBch thu\u1EADt v\xE0 xu\u1EA5t ph\u1EE5 \u0111\u1EC1 t\u1EF1 \u0111\u1ED9ng b\u1EB1ng m\xF4 h\xECnh OpenAI Whisper GPU.",status:"active",state:{selectedFile:null,resultData:null,isProcessing:!1,currentJobId:null,unsubscribe:null},render(e){this.state.selectedFile=null,e.innerHTML=`
      ${b(this,{title:'B\xF3c b\u0103ng <span class="thin">gi\u1ECDng n\xF3i</span> th\xE0nh v\u0103n b\u1EA3n',sub:"T\u1EA3i file \xE2m thanh ho\u1EB7c video, Whisper ch\u1EA1y tr\xEAn GPU s\u1EBD ch\xE9p l\u1EA1i t\u1EEBng c\xE2u k\xE8m m\u1ED1c th\u1EDDi gian, xu\u1EA5t \u0111\u01B0\u1EE3c TXT, SRT v\xE0 VTT.",word:"Whisper",meta:["GPU CUDA","MP3 \xB7 WAV \xB7 MP4","Xu\u1EA5t SRT / VTT"]})}

      <div class="mp-body">
        <div class="mp-grid">
          <div class="mp-panel">
            ${u("01","C\u1EA5u h\xECnh","b\xF3c b\u0103ng")}

            <div class="form-group">
              <label class="form-label">File \xE2m thanh / video</label>
              <div class="mp-drop" id="whisperDropzone">
                <div class="mp-drop-ic">${l("music",22)}</div>
                <div class="mp-drop-title" id="dropzoneTitle">K\xE9o th\u1EA3 file v\xE0o \u0111\xE2y ho\u1EB7c <u>ch\u1ECDn file</u></div>
                <div class="mp-drop-sub">MP3, WAV, M4A, FLAC, OGG, MP4, WebM</div>
                <input type="file" id="whisperFileInput" hidden accept=".mp3,.wav,.m4a,.flac,.ogg,.mp4,.webm" />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">M\xF4 h\xECnh AI</label>
              <select class="form-select" id="whisperModel">
                <option value="turbo" selected>Turbo \u2014 nhanh & ch\xEDnh x\xE1c nh\u1EA5t (khuy\xEAn d\xF9ng)</option>
                <option value="tiny">Tiny \u2014 r\u1EA5t nhanh, nh\u1EB9 nh\u1EA5t</option>
                <option value="base">Base \u2014 c\xE2n b\u1EB1ng cho b\xE0i test nhanh</option>
                <option value="small">Small \u2014 \u0111\u1ED9 ch\xEDnh x\xE1c t\u1ED1t</option>
                <option value="medium">Medium \u2014 ch\xEDnh x\xE1c cao, d\u1ECBch t\u1ED1t</option>
                <option value="large">Large \u2014 ch\xEDnh x\xE1c cao nh\u1EA5t</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Ng\xF4n ng\u1EEF</label>
              <select class="form-select" id="whisperLang">
                <option value="vi" selected>Ti\u1EBFng Vi\u1EC7t (khuy\xEAn d\xF9ng cho nh\u1EA1c Vi\u1EC7t)</option>
                <option value="auto">T\u1EF1 nh\u1EADn di\u1EC7n</option>
                <option value="en">Ti\u1EBFng Anh</option>
                <option value="zh">Ti\u1EBFng Trung</option>
                <option value="ja">Ti\u1EBFng Nh\u1EADt</option>
                <option value="ko">Ti\u1EBFng H\xE0n</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">T\xE1c v\u1EE5</label>
              <select class="form-select" id="whisperTask">
                <option value="transcribe" selected>Transcribe \u2014 ch\xE9p l\u1EA1i \u0111\xFAng ng\xF4n ng\u1EEF g\u1ED1c</option>
                <option value="translate">Translate \u2014 d\u1ECBch th\u1EB3ng sang ti\u1EBFng Anh</option>
              </select>
            </div>

            <button class="btn btn-primary btn-block btn-lg" id="btnStartTranscribe" disabled>
              ${l("spark",18,2)} B\u1EAFt \u0111\u1EA7u b\xF3c b\u0103ng
            </button>
          </div>

          <div class="mp-panel flex">
            ${u("02","K\u1EBFt qu\u1EA3","v\u0103n b\u1EA3n",`
              <span id="exportGroup" style="display:contents">
                <button class="btn btn-secondary btn-sm" id="btnCopyText">${l("copy",14,2)} Copy</button>
                <button class="btn btn-secondary btn-sm" id="btnExportTxt">${l("file",14,2)} TXT</button>
                <button class="btn btn-secondary btn-sm" id="btnExportSrt">${l("download",14,2)} SRT</button>
                <button class="btn btn-secondary btn-sm" id="btnExportVtt">${l("download",14,2)} VTT</button>
              </span>`)}

            <div class="mp-progress" id="progressArea" style="display:none;">
              <div class="mp-progress-msg" id="progressText">\u0110ang x\u1EED l\xFD...</div>
              <div class="progress-bar-bg"><div class="progress-bar-fill" id="progressBar"></div></div>
            </div>

            <audio id="whisperAudio" controls style="width:100%;display:none;"></audio>

            <div class="mp-output result-box" id="resultText" style="min-height:420px;max-height:640px;">
              <div class="mp-empty">
                <div class="mp-drop-ic">${l("text",22)}</div>
                Ch\u01B0a c\xF3 d\u1EEF li\u1EC7u. Ch\u1ECDn file v\xE0 b\u1EA5m \u201CB\u1EAFt \u0111\u1EA7u b\xF3c b\u0103ng\u201D.
              </div>
            </div>
          </div>
        </div>
      </div>
    `,this.bindEvents(e),this.restoreLatestJob(e)},restoreLatestJob(e){let t=d.getLatestJobForModule("whisper"),r=e.querySelector("#progressArea"),a=e.querySelector("#progressBar"),s=e.querySelector("#progressText"),n=e.querySelector("#resultText");(t==null?void 0:t.status)==="completed"&&t.result?(this.state.resultData=t.result,this.renderResult(t.result,n)):((t==null?void 0:t.status)==="queued"||(t==null?void 0:t.status)==="processing")&&(this.state.isProcessing=!0,r&&(r.style.display="block"),a&&(a.style.width=`${t.progress||10}%`),s&&(s.textContent=t.message||"\u0110ang b\xF3c b\u0103ng ng\u1EA7m...")),this.state.unsubscribe&&this.state.unsubscribe(),this.state.unsubscribe=d.subscribe(i=>{if((i==null?void 0:i.module)==="whisper"){if(i.status==="processing"||i.status==="queued")r&&(r.style.display="block"),a&&(a.style.width=`${i.progress||10}%`),s&&(s.textContent=i.message||"\u0110ang b\xF3c b\u0103ng...");else if(i.status==="completed"&&i.result){this.state.isProcessing=!1,r&&(r.style.display="none");let o=e.querySelector("#btnStartTranscribe");o&&(o.disabled=!1),this.state.resultData=i.result,this.renderResult(i.result,n)}else if(i.status==="failed"){this.state.isProcessing=!1,r&&(r.style.display="none");let o=e.querySelector("#btnStartTranscribe");o&&(o.disabled=!1),n&&(n.textContent=`\u274C L\u1ED7i: ${i.message}`)}}})},bindEvents(e){var n;let t=e.querySelector("#whisperDropzone"),r=e.querySelector("#whisperFileInput"),a=e.querySelector("#btnStartTranscribe"),s=e.querySelector("#dropzoneTitle");t&&r&&(t.addEventListener("click",()=>r.click()),t.addEventListener("dragover",i=>{i.preventDefault(),t.classList.add("drag-over")}),t.addEventListener("dragleave",()=>t.classList.remove("drag-over")),t.addEventListener("drop",i=>{i.preventDefault(),t.classList.remove("drag-over"),i.dataTransfer.files.length>0&&this.handleFile(i.dataTransfer.files[0],s,a)}),r.addEventListener("change",i=>{i.target.files[0]&&this.handleFile(i.target.files[0],s,a)})),a&&a.addEventListener("click",()=>this.startTranscribe(e)),(n=e.querySelector("#btnCopyText"))==null||n.addEventListener("click",()=>{var i;(i=this.state.resultData)!=null&&i.text&&(navigator.clipboard.writeText(this.state.resultData.text),c.emit("toast:show",{message:"\u0110\xE3 sao ch\xE9p v\u0103n b\u1EA3n v\xE0o b\u1ED9 nh\u1EDB t\u1EA1m!"}))}),["txt","srt","vtt"].forEach(i=>{var o;(o=e.querySelector(`#btnExport${i.charAt(0).toUpperCase()+i.slice(1)}`))==null||o.addEventListener("click",()=>{this.state.resultData&&h.exportResult(i,this.state.resultData).catch(p=>{c.emit("toast:show",{message:`L\u1ED7i xu\u1EA5t file: ${p.message}`,type:"error"})})})})},handleFile(e,t,r){this.state.selectedFile=e;let a=(e.size/(1024*1024)).toFixed(2);t&&(t.innerHTML=`<strong>${this.escapeHtml(e.name)}</strong> (${a} MB)`);let s=document.getElementById("whisperAudio");s&&(s.dataset.url&&URL.revokeObjectURL(s.dataset.url),s.dataset.url=URL.createObjectURL(e),s.src=s.dataset.url,s.style.display="block"),r&&(r.disabled=!1)},async startTranscribe(e){if(!this.state.selectedFile||this.state.isProcessing)return;let t=e.querySelector("#btnStartTranscribe"),r=e.querySelector("#progressArea"),a=e.querySelector("#progressBar"),s=e.querySelector("#progressText"),n=e.querySelector("#resultText");this.state.isProcessing=!0,t&&(t.disabled=!0),r&&(r.style.display="block"),a&&(a.style.width="10%"),s&&(s.textContent="\u0110ang t\u1EA3i file l\xEAn server..."),n&&(n.textContent="\u0110ang ti\u1EBFn h\xE0nh b\xF3c b\u0103ng \xE2m thanh...");let i=e.querySelector("#whisperModel").value,o=e.querySelector("#whisperLang").value,p=e.querySelector("#whisperTask").value;try{let v=(await h.transcribeAudio(this.state.selectedFile,i,o,p)).job_id;d.trackJob({id:v,module:"whisper",route:"/Whisper",title:`Whisper B\xF3c B\u0103ng (${this.state.selectedFile.name})`}),c.emit("toast:show",{message:"\u{1F680} T\xE1c v\u1EE5 \u0111\xE3 ch\u1EA1y ng\u1EA7m! B\u1EA1n c\xF3 th\u1EC3 chuy\u1EC3n trang tho\u1EA3i m\xE1i."})}catch(g){this.state.isProcessing=!1,t&&(t.disabled=!1),r&&(r.style.display="none"),n&&(n.textContent=`\u274C L\u1ED7i: ${g.message}`)}},renderResult(e,t){if(!e||!e.segments){t.textContent=(e==null?void 0:e.text)||"Kh\xF4ng ph\xE1t hi\u1EC7n th\u1EA5y gi\u1ECDng n\xF3i.";return}let r='<div class="mp-meta" style="margin:0 0 1rem;">';r+=`<span>Ng\xF4n ng\u1EEF: ${e.language.toUpperCase()}</span><span>Th\u1EDDi l\u01B0\u1EE3ng: ${e.duration}s</span><span>Model: ${e.model}</span>`,r+="</div>",e.segments.forEach(a=>{let s=this.formatTime(a.start),n=this.formatTime(a.end);r+=`
        <div class="segment-row" data-start="${a.start}" style="cursor:pointer;" title="B\u1EA5m \u0111\u1EC3 nghe \u0111o\u1EA1n n\xE0y">
          <div class="segment-time">${s} \u2192 ${n}</div>
          <div class="segment-text">${this.escapeHtml(a.text)}</div>
        </div>
      `}),t.innerHTML=r,t.querySelectorAll(".segment-row[data-start]").forEach(a=>{a.addEventListener("click",()=>{let s=document.getElementById("whisperAudio");s&&s.src&&(s.currentTime=parseFloat(a.dataset.start),s.play().catch(()=>{}))})})},formatTime(e){let t=Math.floor(e/60),r=Math.floor(e%60),a=Math.floor(e%1*10);return`${String(t).padStart(2,"0")}:${String(r).padStart(2,"0")}.${a}`},escapeHtml(e){return e.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")},unmount(e){this.state.unsubscribe&&(this.state.unsubscribe(),this.state.unsubscribe=null),e.innerHTML=""}};export{k as whisperModule};
