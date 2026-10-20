/**
 * MonaliMeow — GenReport AI Module
 * Structured Sheet Form UI for Daily Work Notes & AI local Word (.docx) Generator
 */

import { jobTracker } from '../../services/jobTracker.js';
import { eventBus } from '../../stores/eventBus.js';
import { pageHero, panelHead, svgIcon } from '../../components/pageHero.js';

export const genreportModule = {
  id: 'genreport',
  name: 'Báo Cáo Tiến Độ (GenReport)',
  route: '/genreport',
  icon: '📄',
  category: 'Automation AI',
  description: 'Tự động sinh báo cáo tiến độ kỹ thuật chuyên sâu bằng AI local (Ollama) và xuất file Word (.docx) chuẩn doanh nghiệp.',
  status: 'active',

  _state: { busy: false, unsubscribe: null, dailyData: [] },

  render(el) {
    this._state.busy = false;

    // Helper date calculations
    const today = new Date();
    const dayOfWeek = today.getDay(); // 0 is Sun, 1 is Mon
    const distanceToMon = (dayOfWeek === 0 ? -6 : 1 - dayOfWeek);
    const monDate = new Date(today);
    monDate.setDate(today.getDate() + distanceToMon);
    const satDate = new Date(monDate);
    satDate.setDate(monDate.getDate() + 5);

    const startStr = this._formatDate(monDate);
    const endStr   = this._formatDate(satDate);

    const isoStartStr = this._ddmmToISO(startStr);
    const isoEndStr   = this._ddmmToISO(endStr);

    // Initial 6-day Sheet Grid starts completely EMPTY by default as requested by user
    this._state.dailyData = [
      { day_idx: 1, day_name: 'Thứ 2', date_str: startStr, subtasks: [{ content: '', progress: '100%' }] },
      { day_idx: 2, day_name: 'Thứ 3', date_str: this._addDaysStr(monDate, 1), subtasks: [{ content: '', progress: '100%' }] },
      { day_idx: 3, day_name: 'Thứ 4', date_str: this._addDaysStr(monDate, 2), subtasks: [{ content: '', progress: '100%' }] },
      { day_idx: 4, day_name: 'Thứ 5', date_str: this._addDaysStr(monDate, 3), subtasks: [{ content: '', progress: '100%' }] },
      { day_idx: 5, day_name: 'Thứ 6', date_str: this._addDaysStr(monDate, 4), subtasks: [{ content: '', progress: '100%' }] },
      { day_idx: 6, day_name: 'Thứ 7', date_str: endStr, subtasks: [{ content: '', progress: '100%' }] }
    ];

    const dateField = (id, pickerId, value, iso, label) => `
      <div class="form-group">
        <label class="form-label">${label}</label>
        <div style="position:relative;display:flex;align-items:center;">
          <input type="text" class="form-input" id="${id}" value="${value}" placeholder="DD/MM/YYYY" style="padding-right:2.8rem;" />
          <input type="date" class="date-picker-overlay" id="${pickerId}" value="${iso}" style="position:absolute;right:0.5rem;opacity:0;width:2rem;height:2rem;cursor:pointer;z-index:2;" title="Chọn từ lịch" />
          <span style="position:absolute;right:0.85rem;pointer-events:none;color:var(--primary);display:flex;z-index:1;">${svgIcon('calendar', 17, 2)}</span>
        </div>
      </div>`;

    el.innerHTML = `
    ${pageHero(this, {
      title: 'Báo cáo tiến độ <span class="thin">tự viết</span> bằng AI',
      sub: 'Điền thông tin và ghi vắn tắt việc từng ngày. AI local sẽ làm rõ thuật ngữ, viết đủ 4 phần báo cáo và xuất file Word chuẩn doanh nghiệp.',
      word: 'Report',
      meta: ['Ollama · Qwen', 'Xuất .docx', '4 phần báo cáo'],
    })}

    <div class="mp-body">

      <div class="mp-panel">
        ${panelHead('01', 'Thông tin', 'hành chính')}
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(260px, 1fr));column-gap:18px;">
          <div class="form-group">
            <label class="form-label">Tên công ty</label>
            <input type="text" class="form-input" id="rep-company" value="CÔNG TY CỔ PHẦN PAINT & MORE" />
          </div>
          <div class="form-group">
            <label class="form-label">Phòng ban</label>
            <input type="text" class="form-input" id="rep-dept" value="Phòng IT-AI" />
          </div>
          <div class="form-group">
            <label class="form-label">Họ và tên</label>
            <input type="text" class="form-input" id="rep-name" value="BÙI TIẾN THÀNH" />
          </div>
          <div class="form-group">
            <label class="form-label">Chức vụ</label>
            <input type="text" class="form-input" id="rep-pos" value="Nhân viên AI-IT" />
          </div>
          ${dateField('rep-start-date', 'picker-start-date', startStr, isoStartStr, 'Từ ngày (thứ 2)')}
          ${dateField('rep-end-date', 'picker-end-date', endStr, isoEndStr, 'Đến ngày (thứ 7)')}
          ${dateField('rep-date', 'picker-rep-date', endStr, isoEndStr, 'Ngày viết báo cáo')}
        </div>
      </div>

      <div class="mp-panel">
        ${panelHead('02', 'Công việc', 'trong tuần', `
          <button class="btn btn-secondary btn-sm" id="btnEmptySheet">${svgIcon('trash', 14, 2)} Xoá trống</button>
          <button class="btn btn-secondary btn-sm" id="btnFillSampleSheet">${svgIcon('bulb', 14, 2)} Nạp mẫu</button>`)}

        <div class="mp-hint" style="margin:-8px 0 22px;">${svgIcon('bulb', 15, 2)}<span>Ngày tháng đã khoá theo tuần đang chọn. Bấm “Thêm việc” để ghi nhiều đầu việc trong một ngày.</span></div>

        <div id="sheetGridContainer" class="gr-days">
          ${this._renderSheetGridHTML()}
        </div>

        <button class="btn btn-primary btn-block btn-lg" id="btnGenerateReport" style="margin-top:28px;">
          ${svgIcon('spark', 18, 2)} AI viết báo cáo & xuất Word (.docx)
        </button>

        <div class="mp-progress" id="gen-progress-wrap" style="display:none;margin-top:18px;">
          <div class="mp-progress-msg" id="gen-progress-msg">Đang khởi tạo...</div>
          <div class="progress-bar-bg"><div class="progress-bar-fill" id="gen-progress-bar" style="width:10%"></div></div>
        </div>
      </div>

      <div id="gen-output-result"></div>

    </div>`;

    this._bind(el);
    this._restoreLatestJob(el);
  },

  _renderSheetGridHTML() {
    if (!Array.isArray(this._state.dailyData)) return '';

    return this._state.dailyData.map((dayItem, dIdx) => {
      const dayNum = dayItem.day_idx || (dIdx + 1);
      const dayName = dayItem.day_name || `Thứ ${dayNum + 1}`;
      const dateStr = dayItem.date_str || '';

      const subtasks = (Array.isArray(dayItem.subtasks) && dayItem.subtasks.length > 0)
        ? dayItem.subtasks
        : [{ content: '', progress: '100%' }];

      const subtaskRowsHTML = subtasks.map((st, stIdx) => `
        <div class="sheet-subtask-row gr-row" data-day-idx="${dayNum}" data-sub-idx="${stIdx}">
          <span class="gr-bullet">${String(stIdx + 1).padStart(2, '0')}</span>
          <textarea class="form-textarea st-content" rows="2" placeholder="Ghi vắn tắt công việc...">${st.content || ''}</textarea>
          <div class="gr-pct">
            <input type="text" class="form-input st-progress" value="${st.progress || '100%'}" title="Tiến độ" />
          </div>
          ${subtasks.length > 1 ? `
            <button type="button" class="btn-del-sheet-subtask gr-del" data-day-idx="${dayNum}" data-sub-idx="${stIdx}" title="Xoá dòng này">${svgIcon('trash', 16, 2)}</button>
          ` : '<div class="gr-del-ph"></div>'}
        </div>
      `).join('');

      return `
        <div class="sheet-day-card gr-day" data-day-idx="${dayNum}">
          <div class="gr-day-head">
            <div><b>${dayName}</b><span>${dateStr}</span></div>
            <button type="button" class="btn btn-secondary btn-sm btn-add-sheet-subtask" data-day-idx="${dayNum}" title="Thêm việc cho ngày này">${svgIcon('plus', 14, 2)} Thêm việc</button>
          </div>
          <div class="sheet-subtasks-list">
            ${subtaskRowsHTML}
          </div>
        </div>
      `;
    }).join('');
  },

  _updateSheetGridDOM(el) {
    const container = el.querySelector('#sheetGridContainer');
    if (container) {
      container.innerHTML = this._renderSheetGridHTML();
      this._bindSheetGridEvents(el);
    }
  },

  _syncStateFromDOM(el) {
    const dayMap = {};
    el.querySelectorAll('.sheet-day-card').forEach(card => {
      let dayNum = parseInt(card.getAttribute('data-day-idx'), 10);
      if (isNaN(dayNum)) dayNum = 1;

      const subtasks = [];
      card.querySelectorAll('.sheet-subtask-row').forEach(row => {
        const content  = row.querySelector('.st-content')?.value.trim() || '';
        const progress = row.querySelector('.st-progress')?.value.trim() || '100%';
        subtasks.push({ content, progress });
      });

      dayMap[dayNum] = subtasks;
    });

    this._state.dailyData.forEach(d => {
      if (dayMap[d.day_idx]) {
        d.subtasks = dayMap[d.day_idx];
      }
    });
  },

  _bindSheetGridEvents(el) {
    // Add subtask (+)
    el.querySelectorAll('.btn-add-sheet-subtask').forEach(btn => {
      btn.addEventListener('click', () => {
        const dayNum = parseInt(btn.getAttribute('data-day-idx'), 10);
        if (isNaN(dayNum)) return;
        this._syncStateFromDOM(el);
        const dayItem = this._state.dailyData.find(d => d.day_idx === dayNum);
        if (dayItem) {
          dayItem.subtasks.push({ content: '', progress: '100%' });
          this._updateSheetGridDOM(el);
          eventBus.emit('toast:show', { message: `Đã thêm dòng công việc mới cho ${dayItem.day_name}!` });
        }
      });
    });

    // Delete subtask (🗑️)
    el.querySelectorAll('.btn-del-sheet-subtask').forEach(btn => {
      btn.addEventListener('click', () => {
        const dayNum = parseInt(btn.getAttribute('data-day-idx'), 10);
        const subIdx = parseInt(btn.getAttribute('data-sub-idx'), 10);
        if (isNaN(dayNum) || isNaN(subIdx)) return;
        this._syncStateFromDOM(el);
        const dayItem = this._state.dailyData.find(d => d.day_idx === dayNum);
        if (dayItem && dayItem.subtasks.length > 1) {
          dayItem.subtasks.splice(subIdx, 1);
          this._updateSheetGridDOM(el);
        }
      });
    });
  },

  _updateWeeklyDatesFromStart(el, startDateStr) {
    const monDate = this._parseDDMMYYYY(startDateStr);
    if (!monDate) return;

    const satDate = new Date(monDate);
    satDate.setDate(monDate.getDate() + 5);

    const satStr = this._formatDate(satDate);
    const endDateInput  = el.querySelector('#rep-end-date');
    const repDateInput  = el.querySelector('#rep-date');
    const pickerStart   = el.querySelector('#picker-start-date');
    const pickerEnd     = el.querySelector('#picker-end-date');
    const pickerRep     = el.querySelector('#picker-rep-date');

    if (endDateInput) endDateInput.value = satStr;
    if (repDateInput) repDateInput.value = satStr;
    if (pickerStart)  pickerStart.value  = this._ddmmToISO(startDateStr);
    if (pickerEnd)    pickerEnd.value    = this._ddmmToISO(satStr);
    if (pickerRep)    pickerRep.value    = this._ddmmToISO(satStr);

    this._syncStateFromDOM(el);
    this._state.dailyData.forEach((dayItem, idx) => {
      if (idx < 6) {
        const curDate = new Date(monDate);
        curDate.setDate(monDate.getDate() + idx);
        dayItem.date_str = this._formatDate(curDate);
      }
    });
    this._updateSheetGridDOM(el);
  },

  _updateWeeklyDatesFromEnd(el, endDateStr) {
    const satDate = this._parseDDMMYYYY(endDateStr);
    if (!satDate) return;

    const monDate = new Date(satDate);
    monDate.setDate(satDate.getDate() - 5);

    const monStr = this._formatDate(monDate);
    const startDateInput = el.querySelector('#rep-start-date');
    const repDateInput   = el.querySelector('#rep-date');
    const pickerStart    = el.querySelector('#picker-start-date');
    const pickerEnd      = el.querySelector('#picker-end-date');
    const pickerRep      = el.querySelector('#picker-rep-date');

    if (startDateInput) startDateInput.value = monStr;
    if (repDateInput)   repDateInput.value   = endDateStr;
    if (pickerStart)    pickerStart.value    = this._ddmmToISO(monStr);
    if (pickerEnd)      pickerEnd.value      = this._ddmmToISO(endDateStr);
    if (pickerRep)      pickerRep.value      = this._ddmmToISO(endDateStr);

    this._syncStateFromDOM(el);
    this._state.dailyData.forEach((dayItem, idx) => {
      if (idx < 6) {
        const curDate = new Date(monDate);
        curDate.setDate(monDate.getDate() + idx);
        dayItem.date_str = this._formatDate(curDate);
      }
    });
    this._updateSheetGridDOM(el);
  },

  _bind(el) {
    const startDateInput = el.querySelector('#rep-start-date');
    const endDateInput   = el.querySelector('#rep-end-date');
    const repDateInput   = el.querySelector('#rep-date');

    const pickerStart    = el.querySelector('#picker-start-date');
    const pickerEnd      = el.querySelector('#picker-end-date');
    const pickerRep      = el.querySelector('#picker-rep-date');

    // Text inputs
    startDateInput?.addEventListener('input', e => {
      this._updateWeeklyDatesFromStart(el, e.target.value);
    });

    endDateInput?.addEventListener('input', e => {
      this._updateWeeklyDatesFromEnd(el, e.target.value);
    });

    // Calendar Pickers 📅
    pickerStart?.addEventListener('change', e => {
      const formatted = this._isoToDDMMYYYY(e.target.value);
      if (startDateInput) startDateInput.value = formatted;
      this._updateWeeklyDatesFromStart(el, formatted);
    });

    pickerEnd?.addEventListener('change', e => {
      const formatted = this._isoToDDMMYYYY(e.target.value);
      if (endDateInput) endDateInput.value = formatted;
      this._updateWeeklyDatesFromEnd(el, formatted);
    });

    pickerRep?.addEventListener('change', e => {
      const formatted = this._isoToDDMMYYYY(e.target.value);
      if (repDateInput) repDateInput.value = formatted;
    });

    // Empty Sheet button
    el.querySelector('#btnEmptySheet')?.addEventListener('click', () => {
      this._state.dailyData.forEach(d => {
        d.subtasks = [{ content: '', progress: '100%' }];
      });
      this._updateSheetGridDOM(el);
      eventBus.emit('toast:show', { message: 'Đã xóa tất cả ô nhập về khung trống!' });
    });

    // Sample Sheet data button
    el.querySelector('#btnFillSampleSheet')?.addEventListener('click', () => {
      const startDateVal = startDateInput ? startDateInput.value : '03/08/2026';
      const monDate = this._parseDDMMYYYY(startDateVal) || new Date();

      this._state.dailyData = [
        {
          day_idx: 1, day_name: 'Thứ 2', date_str: this._formatDate(monDate),
          subtasks: [
            { content: 'phụ lắp máy tính, làm AFP', progress: '100%' },
            { content: 'sửa logic tính diện tích object, những đối tượng không có hạng mục category AI nội suy nên không chắc đúng 100%', progress: '80%' }
          ]
        },
        {
          day_idx: 2, day_name: 'Thứ 3', date_str: this._addDaysStr(monDate, 1),
          subtasks: [
            { content: 'Họp, đi khảo sát Ba Son', progress: '100%' },
            { content: 'Chiều gặp chị KTS Phụng', progress: '100%' }
          ]
        },
        {
          day_idx: 3, day_name: 'Thứ 4', date_str: this._addDaysStr(monDate, 2),
          subtasks: [
            { content: 'study những việc mà lâu này học về AI, các Model tìm hiểu mà chúng ta nên quan tâm, cách tạo Database, tầm quan trọng của Object Model, Rule Engine & Knowledge Graph có liên quan đến AFP', progress: '100%' }
          ]
        },
        {
          day_idx: 4, day_name: 'Thứ 5', date_str: this._addDaysStr(monDate, 3),
          subtasks: [
            { content: 'AFP, nâng cấp mô hình RAG, dùng AI local Qwen 3.6 của ollama làm AI chính để thử nghiệm, cho học data sơn lưu dạng json, kết hợp với rule engine, knowledge graph và thuật toán BM25(vector search+ranking) để xem độ thông minh khi trả về sơn gợi ý', progress: '40%' },
            { content: 'Cần thêm nhiều ràng buộc nữa nếu muốn tinh vi hơn', progress: '50%' }
          ]
        },
        {
          day_idx: 5, day_name: 'Thứ 6', date_str: this._addDaysStr(monDate, 4),
          subtasks: [
            { content: 'làm flowchart ảnh hưởng của chính phủ/học thuật/công nghệ/ thời tiết đến dự án AFP', progress: '100%' }
          ]
        },
        {
          day_idx: 6, day_name: 'Thứ 7', date_str: this._addDaysStr(monDate, 5),
          subtasks: [
            { content: 'họp anh Tú, vẽ rõ hơn về bức tranh hệ thống để khả thi cho xây dựng dự án AFP', progress: '100%' },
            { content: 'họp về chiến dịch mới của Marketing', progress: '100%' }
          ]
        }
      ];

      this._updateSheetGridDOM(el);
      eventBus.emit('toast:show', { message: 'Đã nạp mẫu công việc mặc định vào bảng Sheet!' });
    });

    // Bind Sheet Grid Event Delegation
    this._bindSheetGridEvents(el);

    // Generate Report Button
    el.querySelector('#btnGenerateReport')?.addEventListener('click', () => this._generate(el));
  },

  _formatDate(dateObj) {
    if (!dateObj || isNaN(dateObj.getTime())) dateObj = new Date();
    const dd = String(dateObj.getDate()).padStart(2, '0');
    const mm = String(dateObj.getMonth() + 1).padStart(2, '0');
    const yyyy = dateObj.getFullYear();
    return `${dd}/${mm}/${yyyy}`;
  },

  _addDaysStr(dateObj, days) {
    if (!dateObj || isNaN(dateObj.getTime())) dateObj = new Date();
    const d = new Date(dateObj);
    d.setDate(d.getDate() + days);
    return this._formatDate(d);
  },

  _parseDDMMYYYY(str) {
    if (!str) return null;
    const parts = str.trim().split(/[\/\.\-]/);
    if (parts.length >= 2) {
      const day   = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10) - 1;
      const year  = parts.length >= 3 ? parseInt(parts[2], 10) : new Date().getFullYear();
      if (!isNaN(day) && !isNaN(month) && !isNaN(year)) {
        const d = new Date(year, month, day);
        if (d.getDate() === day && d.getMonth() === month) {
          return d;
        }
      }
    }
    return null;
  },

  _isoToDDMMYYYY(isoStr) {
    if (!isoStr) return '';
    const parts = isoStr.split('-');
    if (parts.length === 3) {
      return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }
    return isoStr;
  },

  _ddmmToISO(ddmmStr) {
    const d = this._parseDDMMYYYY(ddmmStr);
    if (!d) return '';
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  },

  async _generate(el) {
    if (this._state.busy) return;

    this._syncStateFromDOM(el);

    const company     = el.querySelector('#rep-company').value.trim();
    const department  = el.querySelector('#rep-dept').value.trim();
    const full_name   = el.querySelector('#rep-name').value.trim();
    const position    = el.querySelector('#rep-pos').value.trim();
    const start_date  = el.querySelector('#rep-start-date').value.trim();
    const end_date    = el.querySelector('#rep-end-date').value.trim();
    const report_date = el.querySelector('#rep-date').value.trim();

    // Convert dailyData sheet entries into raw_text format for AI processing
    let rawTextLines = [];
    let totalSubtasks = 0;

    this._state.dailyData.forEach(d => {
      const dayTitle = `${d.day_name} (${d.date_str}):`;
      rawTextLines.push(dayTitle);
      if (Array.isArray(d.subtasks)) {
        d.subtasks.forEach(st => {
          if (st.content && st.content.trim()) {
            totalSubtasks++;
            rawTextLines.push(`  - ${st.content.trim()}                                       (%): ${st.progress || '100%'}`);
          }
        });
      }
    });

    const raw_text = rawTextLines.join('\n');

    if (totalSubtasks === 0) {
      eventBus.emit('toast:show', { message: 'Vui lòng nhập ít nhất 1 nội dung công việc trong bảng Sheet!', type: 'error' });
      return;
    }

    const btn      = el.querySelector('#btnGenerateReport');
    const progWrap = el.querySelector('#gen-progress-wrap');
    const progBar  = el.querySelector('#gen-progress-bar');
    const progMsg  = el.querySelector('#gen-progress-msg');
    const output   = el.querySelector('#gen-output-result');

    this._state.busy = true;
    btn.disabled     = true;
    progWrap.style.display = 'block';
    progBar.style.width    = '10%';
    progMsg.textContent    = 'Đang nạp dữ liệu & khởi tạo AI local (Ollama)...';
    output.innerHTML       = '';

    try {
      const payload = {
        company, department, full_name, position,
        start_date, end_date, report_date,
        raw_text
      };

      const res = await fetch('/api/genreport/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${res.status}`);
      }

      const { job_id } = await res.json();

      // Track job in background
      jobTracker.trackJob({
        id: job_id,
        module: 'genreport',
        route: '/genreport',
        title: `Báo Cáo Tiến Độ (${full_name})`
      });

      eventBus.emit('toast:show', { message: '🚀 Tác vụ đang chạy ngầm bằng AI local! Bạn có thể chuyển trang.' });

    } catch (err) {
      this._state.busy = false;
      btn.disabled     = false;
      progWrap.style.display = 'none';
      output.innerHTML = `<div class="mp-error">${svgIcon('alert', 18, 2)} Lỗi: ${err.message}</div>`;
      eventBus.emit('toast:show', { message: `❌ ${err.message}`, type: 'error' });
    }
  },

  _restoreLatestJob(el) {
    const latest = jobTracker.getLatestJobForModule('genreport');
    if (!latest) return;

    const progWrap = el.querySelector('#gen-progress-wrap');
    const progBar  = el.querySelector('#gen-progress-bar');
    const progMsg  = el.querySelector('#gen-progress-msg');
    const output   = el.querySelector('#gen-output-result');
    const btn      = el.querySelector('#btnGenerateReport');

    if (latest.status === 'completed' && latest.result) {
      this._renderReportResult(latest.result, output);
    } else if (latest.status === 'queued' || latest.status === 'processing') {
      this._state.busy = true;
      if (btn) btn.disabled = true;
      if (progWrap) progWrap.style.display = 'block';
      if (progBar)  progBar.style.width    = `${latest.progress || 15}%`;
      if (progMsg)  progMsg.textContent    = latest.message || 'Đang sinh báo cáo ngầm...';
    }

    this._state.unsubscribe = jobTracker.subscribe(job => {
      if (job.module !== 'genreport') return;

      if (job.status === 'processing' || job.status === 'queued') {
        this._state.busy = true;
        if (btn) btn.disabled = true;
        if (progWrap) progWrap.style.display = 'block';
        if (progBar)  progBar.style.width    = `${job.progress || 15}%`;
        if (progMsg)  progMsg.textContent    = job.message || 'Đang suy luận Ollama AI...';
      } else if (job.status === 'completed' && job.result) {
        this._state.busy = false;
        if (btn) btn.disabled = false;
        if (progWrap) progWrap.style.display = 'none';
        this._renderReportResult(job.result, output);
      } else if (job.status === 'failed') {
        this._state.busy = false;
        if (btn) btn.disabled = false;
        if (progWrap) progWrap.style.display = 'none';
        output.innerHTML = `<div class="mp-error">${svgIcon('alert', 18, 2)} Lỗi: ${job.message}</div>`;
      }
    });
  },

  _renderReportResult(r, outputEl) {
    if (!outputEl || !r) return;

    let dailyRowsHTML = '';
    if (Array.isArray(r.daily_tasks)) {
      r.daily_tasks.forEach((dt, idx) => {
        const subtasks = dt.subtasks && dt.subtasks.length > 0 ? dt.subtasks : [dt];
        subtasks.forEach((st, stIdx) => {
          dailyRowsHTML += `
            <tr>
              ${stIdx === 0 ? `<td rowspan="${subtasks.length}" style="font-weight:600;white-space:nowrap;">${dt.day || `Thứ ${idx + 2}`}</td>` : ''}
              <td>${st.content || ''}</td>
              <td style="color:var(--secondary);">${st.result || ''}</td>
              <td style="text-align:center;font-weight:600;color:var(--primary);">${st.progress || '100%'}</td>
              <td>${st.note || 'Hoàn thành'}</td>
            </tr>
          `;
        });
      });
    }

    const section = (num, bold, thin, body) => `
      <div class="mp-panel">
        ${panelHead(num, bold, thin)}
        ${body}
      </div>`;

    outputEl.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:30px;">
        <div class="mp-success">
          <div>
            <span class="mp-eyebrow">Đã tạo xong</span>
            <h4>Báo cáo tiến độ Word đã sẵn sàng</h4>
            <p>Họ và tên: <b>${r.full_name || ''}</b> · Ngày viết: <b>${r.report_date || ''}</b></p>
          </div>
          <a href="${r.download_url}" download="${r.filename}" class="btn btn-primary btn-lg">${svgIcon('download', 18, 2)} Tải file .docx</a>
        </div>

        ${section('I', 'Tình hình', 'chung', `<div class="mp-output">${r.general_summary || 'Chưa có thông tin.'}</div>`)}

        ${section('II', 'Công việc', 'hằng ngày', `
          <div style="overflow-x:auto;">
            <table class="mp-table data-table">
              <thead>
                <tr>
                  <th style="width:120px;">Thứ / Ngày</th>
                  <th>Nội dung công việc</th>
                  <th>Kết quả thực hiện</th>
                  <th style="width:90px;text-align:center;">Tiến độ</th>
                  <th style="width:120px;">Ghi chú</th>
                </tr>
              </thead>
              <tbody>${dailyRowsHTML}</tbody>
            </table>
          </div>`)}

        ${section('III', 'Đánh giá', 'ngắn', `<div class="mp-output" style="white-space:pre-line;">${r.eval_short || 'Chưa có đánh giá.'}</div>`)}

        ${section('IV', 'Kế hoạch', 'tuần tiếp theo', `<div class="mp-output">${r.next_plan_ideas || 'Chưa có kế hoạch.'}</div>`)}
      </div>
    `;
  },

  unmount(el) {
    if (this._state.unsubscribe) {
      this._state.unsubscribe();
      this._state.unsubscribe = null;
    }
    el.innerHTML = '';
  }
};
