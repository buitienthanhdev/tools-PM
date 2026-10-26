import{a as _}from"./c-RIJMV2JA.js";import{b as y,c as h,e as k,f}from"./c-A7EUOZAY.js";var M={id:"genreport",name:"B\xE1o C\xE1o Ti\u1EBFn \u0110\u1ED9 (GenReport)",route:"/genreport",icon:"\u{1F4C4}",category:"Automation AI",description:"T\u1EF1 \u0111\u1ED9ng sinh b\xE1o c\xE1o ti\u1EBFn \u0111\u1ED9 k\u1EF9 thu\u1EADt chuy\xEAn s\xE2u b\u1EB1ng AI local (Ollama) v\xE0 xu\u1EA5t file Word (.docx) chu\u1EA9n doanh nghi\u1EC7p.",status:"active",_state:{busy:!1,unsubscribe:null,dailyData:[]},render(t){this._state.busy=!1;let e=new Date,s=e.getDay(),n=s===0?-6:1-s,a=new Date(e);a.setDate(e.getDate()+n);let i=new Date(a);i.setDate(a.getDate()+5);let o=this._formatDate(a),r=this._formatDate(i),c=this._ddmmToISO(o),u=this._ddmmToISO(r);this._state.dailyData=[{day_idx:1,day_name:"Th\u1EE9 2",date_str:o,subtasks:[{content:"",progress:"100%"}]},{day_idx:2,day_name:"Th\u1EE9 3",date_str:this._addDaysStr(a,1),subtasks:[{content:"",progress:"100%"}]},{day_idx:3,day_name:"Th\u1EE9 4",date_str:this._addDaysStr(a,2),subtasks:[{content:"",progress:"100%"}]},{day_idx:4,day_name:"Th\u1EE9 5",date_str:this._addDaysStr(a,3),subtasks:[{content:"",progress:"100%"}]},{day_idx:5,day_name:"Th\u1EE9 6",date_str:this._addDaysStr(a,4),subtasks:[{content:"",progress:"100%"}]},{day_idx:6,day_name:"Th\u1EE9 7",date_str:r,subtasks:[{content:"",progress:"100%"}]}];let l=(d,p,D,S,v)=>`
      <div class="form-group">
        <label class="form-label">${v}</label>
        <div style="position:relative;display:flex;align-items:center;">
          <input type="text" class="form-input" id="${d}" value="${D}" placeholder="DD/MM/YYYY" style="padding-right:2.8rem;" />
          <input type="date" class="date-picker-overlay" id="${p}" value="${S}" style="position:absolute;right:0.5rem;opacity:0;width:2rem;height:2rem;cursor:pointer;z-index:2;" title="Ch\u1ECDn t\u1EEB l\u1ECBch" />
          <span style="position:absolute;right:0.85rem;pointer-events:none;color:var(--primary);display:flex;z-index:1;">${h("calendar",17,2)}</span>
        </div>
      </div>`;t.innerHTML=`
    ${k(this,{title:'B\xE1o c\xE1o ti\u1EBFn \u0111\u1ED9 <span class="thin">t\u1EF1 vi\u1EBFt</span> b\u1EB1ng AI',sub:"\u0110i\u1EC1n th\xF4ng tin v\xE0 ghi v\u1EAFn t\u1EAFt vi\u1EC7c t\u1EEBng ng\xE0y. AI local s\u1EBD l\xE0m r\xF5 thu\u1EADt ng\u1EEF, vi\u1EBFt \u0111\u1EE7 4 ph\u1EA7n b\xE1o c\xE1o v\xE0 xu\u1EA5t file Word chu\u1EA9n doanh nghi\u1EC7p.",word:"Report",meta:["Ollama \xB7 Qwen","Xu\u1EA5t .docx","4 ph\u1EA7n b\xE1o c\xE1o"]})}

    <div class="mp-body">

      <div class="mp-panel">
        ${f("01","Th\xF4ng tin","h\xE0nh ch\xEDnh")}
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(260px, 1fr));column-gap:18px;">
          <div class="form-group">
            <label class="form-label">T\xEAn c\xF4ng ty</label>
            <input type="text" class="form-input" id="rep-company" value="C\xD4NG TY C\u1ED4 PH\u1EA6N PAINT & MORE" />
          </div>
          <div class="form-group">
            <label class="form-label">Ph\xF2ng ban</label>
            <input type="text" class="form-input" id="rep-dept" value="Ph\xF2ng IT-AI" />
          </div>
          <div class="form-group">
            <label class="form-label">H\u1ECD v\xE0 t\xEAn</label>
            <input type="text" class="form-input" id="rep-name" value="B\xD9I TI\u1EBEN TH\xC0NH" />
          </div>
          <div class="form-group">
            <label class="form-label">Ch\u1EE9c v\u1EE5</label>
            <input type="text" class="form-input" id="rep-pos" value="Nh\xE2n vi\xEAn AI-IT" />
          </div>
          ${l("rep-start-date","picker-start-date",o,c,"T\u1EEB ng\xE0y (th\u1EE9 2)")}
          ${l("rep-end-date","picker-end-date",r,u,"\u0110\u1EBFn ng\xE0y (th\u1EE9 7)")}
          ${l("rep-date","picker-rep-date",r,u,"Ng\xE0y vi\u1EBFt b\xE1o c\xE1o")}
        </div>
      </div>

      <div class="mp-panel">
        ${f("02","C\xF4ng vi\u1EC7c","trong tu\u1EA7n",`
          <button class="btn btn-secondary btn-sm" id="btnEmptySheet">${h("trash",14,2)} Xo\xE1 tr\u1ED1ng</button>
          <button class="btn btn-secondary btn-sm" id="btnFillSampleSheet">${h("bulb",14,2)} N\u1EA1p m\u1EABu</button>`)}

        <div class="mp-hint" style="margin:-8px 0 22px;">${h("bulb",15,2)}<span>Ng\xE0y th\xE1ng \u0111\xE3 kho\xE1 theo tu\u1EA7n \u0111ang ch\u1ECDn. B\u1EA5m \u201CTh\xEAm vi\u1EC7c\u201D \u0111\u1EC3 ghi nhi\u1EC1u \u0111\u1EA7u vi\u1EC7c trong m\u1ED9t ng\xE0y.</span></div>

        <div id="sheetGridContainer" class="gr-days">
          ${this._renderSheetGridHTML()}
        </div>

        <button class="btn btn-primary btn-block btn-lg" id="btnGenerateReport" style="margin-top:28px;">
          ${h("spark",18,2)} AI vi\u1EBFt b\xE1o c\xE1o & xu\u1EA5t Word (.docx)
        </button>

        <div class="mp-progress" id="gen-progress-wrap" style="display:none;margin-top:18px;">
          <div class="mp-progress-msg" id="gen-progress-msg">\u0110ang kh\u1EDFi t\u1EA1o...</div>
          <div class="progress-bar-bg"><div class="progress-bar-fill" id="gen-progress-bar" style="width:10%"></div></div>
        </div>
      </div>

      <div id="gen-output-result"></div>

    </div>`,this._bind(t),this._restoreLatestJob(t)},_renderSheetGridHTML(){return Array.isArray(this._state.dailyData)?this._state.dailyData.map((t,e)=>{let s=t.day_idx||e+1,n=t.day_name||`Th\u1EE9 ${s+1}`,a=t.date_str||"",i=Array.isArray(t.subtasks)&&t.subtasks.length>0?t.subtasks:[{content:"",progress:"100%"}],o=i.map((r,c)=>`
        <div class="sheet-subtask-row gr-row" data-day-idx="${s}" data-sub-idx="${c}">
          <span class="gr-bullet">${String(c+1).padStart(2,"0")}</span>
          <textarea class="form-textarea st-content" rows="2" placeholder="Ghi v\u1EAFn t\u1EAFt c\xF4ng vi\u1EC7c...">${r.content||""}</textarea>
          <div class="gr-pct">
            <input type="text" class="form-input st-progress" value="${r.progress||"100%"}" title="Ti\u1EBFn \u0111\u1ED9" />
          </div>
          ${i.length>1?`
            <button type="button" class="btn-del-sheet-subtask gr-del" data-day-idx="${s}" data-sub-idx="${c}" title="Xo\xE1 d\xF2ng n\xE0y">${h("trash",16,2)}</button>
          `:'<div class="gr-del-ph"></div>'}
        </div>
      `).join("");return`
        <div class="sheet-day-card gr-day" data-day-idx="${s}">
          <div class="gr-day-head">
            <div><b>${n}</b><span>${a}</span></div>
            <button type="button" class="btn btn-secondary btn-sm btn-add-sheet-subtask" data-day-idx="${s}" title="Th\xEAm vi\u1EC7c cho ng\xE0y n\xE0y">${h("plus",14,2)} Th\xEAm vi\u1EC7c</button>
          </div>
          <div class="sheet-subtasks-list">
            ${o}
          </div>
        </div>
      `}).join(""):""},_updateSheetGridDOM(t){let e=t.querySelector("#sheetGridContainer");e&&(e.innerHTML=this._renderSheetGridHTML(),this._bindSheetGridEvents(t))},_syncStateFromDOM(t){let e={};t.querySelectorAll(".sheet-day-card").forEach(s=>{let n=parseInt(s.getAttribute("data-day-idx"),10);isNaN(n)&&(n=1);let a=[];s.querySelectorAll(".sheet-subtask-row").forEach(i=>{var c,u;let o=((c=i.querySelector(".st-content"))==null?void 0:c.value.trim())||"",r=((u=i.querySelector(".st-progress"))==null?void 0:u.value.trim())||"100%";a.push({content:o,progress:r})}),e[n]=a}),this._state.dailyData.forEach(s=>{e[s.day_idx]&&(s.subtasks=e[s.day_idx])})},_bindSheetGridEvents(t){t.querySelectorAll(".btn-add-sheet-subtask").forEach(e=>{e.addEventListener("click",()=>{let s=parseInt(e.getAttribute("data-day-idx"),10);if(isNaN(s))return;this._syncStateFromDOM(t);let n=this._state.dailyData.find(a=>a.day_idx===s);n&&(n.subtasks.push({content:"",progress:"100%"}),this._updateSheetGridDOM(t),y.emit("toast:show",{message:`\u0110\xE3 th\xEAm d\xF2ng c\xF4ng vi\u1EC7c m\u1EDBi cho ${n.day_name}!`}))})}),t.querySelectorAll(".btn-del-sheet-subtask").forEach(e=>{e.addEventListener("click",()=>{let s=parseInt(e.getAttribute("data-day-idx"),10),n=parseInt(e.getAttribute("data-sub-idx"),10);if(isNaN(s)||isNaN(n))return;this._syncStateFromDOM(t);let a=this._state.dailyData.find(i=>i.day_idx===s);a&&a.subtasks.length>1&&(a.subtasks.splice(n,1),this._updateSheetGridDOM(t))})})},_updateWeeklyDatesFromStart(t,e){let s=this._parseDDMMYYYY(e);if(!s)return;let n=new Date(s);n.setDate(s.getDate()+5);let a=this._formatDate(n),i=t.querySelector("#rep-end-date"),o=t.querySelector("#rep-date"),r=t.querySelector("#picker-start-date"),c=t.querySelector("#picker-end-date"),u=t.querySelector("#picker-rep-date");i&&(i.value=a),o&&(o.value=a),r&&(r.value=this._ddmmToISO(e)),c&&(c.value=this._ddmmToISO(a)),u&&(u.value=this._ddmmToISO(a)),this._syncStateFromDOM(t),this._state.dailyData.forEach((l,d)=>{if(d<6){let p=new Date(s);p.setDate(s.getDate()+d),l.date_str=this._formatDate(p)}}),this._updateSheetGridDOM(t)},_updateWeeklyDatesFromEnd(t,e){let s=this._parseDDMMYYYY(e);if(!s)return;let n=new Date(s);n.setDate(s.getDate()-5);let a=this._formatDate(n),i=t.querySelector("#rep-start-date"),o=t.querySelector("#rep-date"),r=t.querySelector("#picker-start-date"),c=t.querySelector("#picker-end-date"),u=t.querySelector("#picker-rep-date");i&&(i.value=a),o&&(o.value=e),r&&(r.value=this._ddmmToISO(a)),c&&(c.value=this._ddmmToISO(e)),u&&(u.value=this._ddmmToISO(e)),this._syncStateFromDOM(t),this._state.dailyData.forEach((l,d)=>{if(d<6){let p=new Date(n);p.setDate(n.getDate()+d),l.date_str=this._formatDate(p)}}),this._updateSheetGridDOM(t)},_bind(t){var r,c,u;let e=t.querySelector("#rep-start-date"),s=t.querySelector("#rep-end-date"),n=t.querySelector("#rep-date"),a=t.querySelector("#picker-start-date"),i=t.querySelector("#picker-end-date"),o=t.querySelector("#picker-rep-date");e==null||e.addEventListener("input",l=>{this._updateWeeklyDatesFromStart(t,l.target.value)}),s==null||s.addEventListener("input",l=>{this._updateWeeklyDatesFromEnd(t,l.target.value)}),a==null||a.addEventListener("change",l=>{let d=this._isoToDDMMYYYY(l.target.value);e&&(e.value=d),this._updateWeeklyDatesFromStart(t,d)}),i==null||i.addEventListener("change",l=>{let d=this._isoToDDMMYYYY(l.target.value);s&&(s.value=d),this._updateWeeklyDatesFromEnd(t,d)}),o==null||o.addEventListener("change",l=>{let d=this._isoToDDMMYYYY(l.target.value);n&&(n.value=d)}),(r=t.querySelector("#btnEmptySheet"))==null||r.addEventListener("click",()=>{this._state.dailyData.forEach(l=>{l.subtasks=[{content:"",progress:"100%"}]}),this._updateSheetGridDOM(t),y.emit("toast:show",{message:"\u0110\xE3 x\xF3a t\u1EA5t c\u1EA3 \xF4 nh\u1EADp v\u1EC1 khung tr\u1ED1ng!"})}),(c=t.querySelector("#btnFillSampleSheet"))==null||c.addEventListener("click",()=>{let l=e?e.value:"03/08/2026",d=this._parseDDMMYYYY(l)||new Date;this._state.dailyData=[{day_idx:1,day_name:"Th\u1EE9 2",date_str:this._formatDate(d),subtasks:[{content:"ph\u1EE5 l\u1EAFp m\xE1y t\xEDnh, l\xE0m AFP",progress:"100%"},{content:"s\u1EEDa logic t\xEDnh di\u1EC7n t\xEDch object, nh\u1EEFng \u0111\u1ED1i t\u01B0\u1EE3ng kh\xF4ng c\xF3 h\u1EA1ng m\u1EE5c category AI n\u1ED9i suy n\xEAn kh\xF4ng ch\u1EAFc \u0111\xFAng 100%",progress:"80%"}]},{day_idx:2,day_name:"Th\u1EE9 3",date_str:this._addDaysStr(d,1),subtasks:[{content:"H\u1ECDp, \u0111i kh\u1EA3o s\xE1t Ba Son",progress:"100%"},{content:"Chi\u1EC1u g\u1EB7p ch\u1ECB KTS Ph\u1EE5ng",progress:"100%"}]},{day_idx:3,day_name:"Th\u1EE9 4",date_str:this._addDaysStr(d,2),subtasks:[{content:"study nh\u1EEFng vi\u1EC7c m\xE0 l\xE2u n\xE0y h\u1ECDc v\u1EC1 AI, c\xE1c Model t\xECm hi\u1EC3u m\xE0 ch\xFAng ta n\xEAn quan t\xE2m, c\xE1ch t\u1EA1o Database, t\u1EA7m quan tr\u1ECDng c\u1EE7a Object Model, Rule Engine & Knowledge Graph c\xF3 li\xEAn quan \u0111\u1EBFn AFP",progress:"100%"}]},{day_idx:4,day_name:"Th\u1EE9 5",date_str:this._addDaysStr(d,3),subtasks:[{content:"AFP, n\xE2ng c\u1EA5p m\xF4 h\xECnh RAG, d\xF9ng AI local Qwen 3.6 c\u1EE7a ollama l\xE0m AI ch\xEDnh \u0111\u1EC3 th\u1EED nghi\u1EC7m, cho h\u1ECDc data s\u01A1n l\u01B0u d\u1EA1ng json, k\u1EBFt h\u1EE3p v\u1EDBi rule engine, knowledge graph v\xE0 thu\u1EADt to\xE1n BM25(vector search+ranking) \u0111\u1EC3 xem \u0111\u1ED9 th\xF4ng minh khi tr\u1EA3 v\u1EC1 s\u01A1n g\u1EE3i \xFD",progress:"40%"},{content:"C\u1EA7n th\xEAm nhi\u1EC1u r\xE0ng bu\u1ED9c n\u1EEFa n\u1EBFu mu\u1ED1n tinh vi h\u01A1n",progress:"50%"}]},{day_idx:5,day_name:"Th\u1EE9 6",date_str:this._addDaysStr(d,4),subtasks:[{content:"l\xE0m flowchart \u1EA3nh h\u01B0\u1EDFng c\u1EE7a ch\xEDnh ph\u1EE7/h\u1ECDc thu\u1EADt/c\xF4ng ngh\u1EC7/ th\u1EDDi ti\u1EBFt \u0111\u1EBFn d\u1EF1 \xE1n AFP",progress:"100%"}]},{day_idx:6,day_name:"Th\u1EE9 7",date_str:this._addDaysStr(d,5),subtasks:[{content:"h\u1ECDp anh T\xFA, v\u1EBD r\xF5 h\u01A1n v\u1EC1 b\u1EE9c tranh h\u1EC7 th\u1ED1ng \u0111\u1EC3 kh\u1EA3 thi cho x\xE2y d\u1EF1ng d\u1EF1 \xE1n AFP",progress:"100%"},{content:"h\u1ECDp v\u1EC1 chi\u1EBFn d\u1ECBch m\u1EDBi c\u1EE7a Marketing",progress:"100%"}]}],this._updateSheetGridDOM(t),y.emit("toast:show",{message:"\u0110\xE3 n\u1EA1p m\u1EABu c\xF4ng vi\u1EC7c m\u1EB7c \u0111\u1ECBnh v\xE0o b\u1EA3ng Sheet!"})}),this._bindSheetGridEvents(t),(u=t.querySelector("#btnGenerateReport"))==null||u.addEventListener("click",()=>this._generate(t))},_formatDate(t){(!t||isNaN(t.getTime()))&&(t=new Date);let e=String(t.getDate()).padStart(2,"0"),s=String(t.getMonth()+1).padStart(2,"0"),n=t.getFullYear();return`${e}/${s}/${n}`},_addDaysStr(t,e){(!t||isNaN(t.getTime()))&&(t=new Date);let s=new Date(t);return s.setDate(s.getDate()+e),this._formatDate(s)},_parseDDMMYYYY(t){if(!t)return null;let e=t.trim().split(/[\/\.\-]/);if(e.length>=2){let s=parseInt(e[0],10),n=parseInt(e[1],10)-1,a=e.length>=3?parseInt(e[2],10):new Date().getFullYear();if(!isNaN(s)&&!isNaN(n)&&!isNaN(a)){let i=new Date(a,n,s);if(i.getDate()===s&&i.getMonth()===n)return i}}return null},_isoToDDMMYYYY(t){if(!t)return"";let e=t.split("-");return e.length===3?`${e[2]}/${e[1]}/${e[0]}`:t},_ddmmToISO(t){let e=this._parseDDMMYYYY(t);if(!e)return"";let s=e.getFullYear(),n=String(e.getMonth()+1).padStart(2,"0"),a=String(e.getDate()).padStart(2,"0");return`${s}-${n}-${a}`},async _generate(t){if(this._state.busy)return;this._syncStateFromDOM(t);let e=t.querySelector("#rep-company").value.trim(),s=t.querySelector("#rep-dept").value.trim(),n=t.querySelector("#rep-name").value.trim(),a=t.querySelector("#rep-pos").value.trim(),i=t.querySelector("#rep-start-date").value.trim(),o=t.querySelector("#rep-end-date").value.trim(),r=t.querySelector("#rep-date").value.trim(),c=[],u=0;this._state.dailyData.forEach(g=>{let m=`${g.day_name} (${g.date_str}):`;c.push(m),Array.isArray(g.subtasks)&&g.subtasks.forEach(b=>{b.content&&b.content.trim()&&(u++,c.push(`  - ${b.content.trim()}                                       (%): ${b.progress||"100%"}`))})});let l=c.join(`
`);if(u===0){y.emit("toast:show",{message:"Vui l\xF2ng nh\u1EADp \xEDt nh\u1EA5t 1 n\u1ED9i dung c\xF4ng vi\u1EC7c trong b\u1EA3ng Sheet!",type:"error"});return}let d=t.querySelector("#btnGenerateReport"),p=t.querySelector("#gen-progress-wrap"),D=t.querySelector("#gen-progress-bar"),S=t.querySelector("#gen-progress-msg"),v=t.querySelector("#gen-output-result");this._state.busy=!0,d.disabled=!0,p.style.display="block",D.style.width="10%",S.textContent="\u0110ang n\u1EA1p d\u1EEF li\u1EC7u & kh\u1EDFi t\u1EA1o AI local (Ollama)...",v.innerHTML="";try{let m=await fetch("/api/genreport/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({company:e,department:s,full_name:n,position:a,start_date:i,end_date:o,report_date:r,raw_text:l})});if(!m.ok){let $=await m.json().catch(()=>({}));throw new Error($.error||`HTTP ${m.status}`)}let{job_id:b}=await m.json();_.trackJob({id:b,module:"genreport",route:"/genreport",title:`B\xE1o C\xE1o Ti\u1EBFn \u0110\u1ED9 (${n})`}),y.emit("toast:show",{message:"\u{1F680} T\xE1c v\u1EE5 \u0111ang ch\u1EA1y ng\u1EA7m b\u1EB1ng AI local! B\u1EA1n c\xF3 th\u1EC3 chuy\u1EC3n trang."})}catch(g){this._state.busy=!1,d.disabled=!1,p.style.display="none",v.innerHTML=`<div class="mp-error">${h("alert",18,2)} L\u1ED7i: ${g.message}</div>`,y.emit("toast:show",{message:`\u274C ${g.message}`,type:"error"})}},_restoreLatestJob(t){let e=_.getLatestJobForModule("genreport"),s=t.querySelector("#gen-progress-wrap"),n=t.querySelector("#gen-progress-bar"),a=t.querySelector("#gen-progress-msg"),i=t.querySelector("#gen-output-result"),o=t.querySelector("#btnGenerateReport");(e==null?void 0:e.status)==="completed"&&e.result?this._renderReportResult(e.result,i):((e==null?void 0:e.status)==="queued"||(e==null?void 0:e.status)==="processing")&&(this._state.busy=!0,o&&(o.disabled=!0),s&&(s.style.display="block"),n&&(n.style.width=`${e.progress||15}%`),a&&(a.textContent=e.message||"\u0110ang sinh b\xE1o c\xE1o ng\u1EA7m...")),this._state.unsubscribe&&this._state.unsubscribe(),this._state.unsubscribe=_.subscribe(r=>{(r==null?void 0:r.module)==="genreport"&&(r.status==="processing"||r.status==="queued"?(this._state.busy=!0,o&&(o.disabled=!0),s&&(s.style.display="block"),n&&(n.style.width=`${r.progress||15}%`),a&&(a.textContent=r.message||"\u0110ang suy lu\u1EADn Ollama AI...")):r.status==="completed"&&r.result?(this._state.busy=!1,o&&(o.disabled=!1),s&&(s.style.display="none"),this._renderReportResult(r.result,i)):r.status==="failed"&&(this._state.busy=!1,o&&(o.disabled=!1),s&&(s.style.display="none"),i.innerHTML=`<div class="mp-error">${h("alert",18,2)} L\u1ED7i: ${r.message}</div>`))})},_renderReportResult(t,e){if(!e||!t)return;let s="";Array.isArray(t.daily_tasks)&&t.daily_tasks.forEach((a,i)=>{let o=a.subtasks&&a.subtasks.length>0?a.subtasks:[a];o.forEach((r,c)=>{s+=`
            <tr>
              ${c===0?`<td rowspan="${o.length}" style="font-weight:600;white-space:nowrap;">${a.day||`Th\u1EE9 ${i+2}`}</td>`:""}
              <td>${r.content||""}</td>
              <td style="color:var(--secondary);">${r.result||""}</td>
              <td style="text-align:center;font-weight:600;color:var(--primary);">${r.progress||"100%"}</td>
              <td>${r.note||"Ho\xE0n th\xE0nh"}</td>
            </tr>
          `})});let n=(a,i,o,r)=>`
      <div class="mp-panel">
        ${f(a,i,o)}
        ${r}
      </div>`;e.innerHTML=`
      <div style="display:flex;flex-direction:column;gap:30px;">
        <div class="mp-success">
          <div>
            <span class="mp-eyebrow">\u0110\xE3 t\u1EA1o xong</span>
            <h4>B\xE1o c\xE1o ti\u1EBFn \u0111\u1ED9 Word \u0111\xE3 s\u1EB5n s\xE0ng</h4>
            <p>H\u1ECD v\xE0 t\xEAn: <b>${t.full_name||""}</b> \xB7 Ng\xE0y vi\u1EBFt: <b>${t.report_date||""}</b></p>
          </div>
          <a href="${t.download_url}" download="${t.filename}" class="btn btn-primary btn-lg">${h("download",18,2)} T\u1EA3i file .docx</a>
        </div>

        ${n("I","T\xECnh h\xECnh","chung",`<div class="mp-output">${t.general_summary||"Ch\u01B0a c\xF3 th\xF4ng tin."}</div>`)}

        ${n("II","C\xF4ng vi\u1EC7c","h\u1EB1ng ng\xE0y",`
          <div style="overflow-x:auto;">
            <table class="mp-table data-table">
              <thead>
                <tr>
                  <th style="width:120px;">Th\u1EE9 / Ng\xE0y</th>
                  <th>N\u1ED9i dung c\xF4ng vi\u1EC7c</th>
                  <th>K\u1EBFt qu\u1EA3 th\u1EF1c hi\u1EC7n</th>
                  <th style="width:90px;text-align:center;">Ti\u1EBFn \u0111\u1ED9</th>
                  <th style="width:120px;">Ghi ch\xFA</th>
                </tr>
              </thead>
              <tbody>${s}</tbody>
            </table>
          </div>`)}

        ${n("III","\u0110\xE1nh gi\xE1","ng\u1EAFn",`<div class="mp-output" style="white-space:pre-line;">${t.eval_short||"Ch\u01B0a c\xF3 \u0111\xE1nh gi\xE1."}</div>`)}

        ${n("IV","K\u1EBF ho\u1EA1ch","tu\u1EA7n ti\u1EBFp theo",`<div class="mp-output">${t.next_plan_ideas||"Ch\u01B0a c\xF3 k\u1EBF ho\u1EA1ch."}</div>`)}
      </div>
    `},unmount(t){this._state.unsubscribe&&(this._state.unsubscribe(),this._state.unsubscribe=null),t.innerHTML=""}};export{M as genreportModule};
