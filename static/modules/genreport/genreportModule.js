/**
 * MonaliMeow — GenReport AI Module
 * Structured Sheet Form UI for Daily Work Notes & Ollama Qwen 3.6 Word (.docx) Generator
 */

import { jobTracker } from '../../services/jobTracker.js';
import { eventBus } from '../../stores/eventBus.js';

export const genreportModule = {
  id: 'genreport',
  name: 'Báo Cáo Tiến Độ (GenReport)',
  route: '/genreport',
  icon: '📄',
  category: 'Automation AI',
  description: 'Tự động sinh báo cáo tiến độ kỹ thuật chuyên sâu bằng Local AI (Ollama Qwen 3.6) và xuất file Word (.docx) chuẩn doanh nghiệp.',
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

    el.innerHTML = `
    <div class="workspace-page-header">
      <div class="page-title-group">
        <h1>📄 GenReport — Tự Động Sinh Báo Cáo Tiến Độ &amp; Xuất Word</h1>
        <p>Nhập thông tin hành chính &amp; điền công việc theo dạng Bảng Sheet từng ngày bên dưới. Ollama AI (Qwen 3.6 35B) sẽ tự động làm rõ thuật ngữ, tổng hợp 4 phần báo cáo &amp; xuất file Word (.docx).</p>
      </div>
    </div>

    <div style="display:flex;flex-direction:column;gap:1.5rem;max-width:1200px;">

      <!-- SECTION 1: Administrative Info -->
      <div class="panel-card">
        <h3 class="panel-title">📋 1. Thông Tin Hành Chính (Mặc định điền sẵn)</h3>
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:1rem;">
          <div class="form-group">
            <label class="form-label">Tên Công Ty</label>
            <input type="text" class="form-input" id="rep-company" value="CÔNG TY CỔ PHẦN PAINT & MORE" />
          </div>
          <div class="form-group">
            <label class="form-label">Phòng Ban</label>
            <input type="text" class="form-input" id="rep-dept" value="Phòng IT-AI" />
          </div>
          <div class="form-group">
            <label class="form-label">Họ và Tên</label>
            <input type="text" class="form-input" id="rep-name" value="BÙI TIẾN THÀNH" />
          </div>
          <div class="form-group">
            <label class="form-label">Chức Vụ</label>
            <input type="text" class="form-input" id="rep-pos" value="Nhân viên AI-IT" />
          </div>
          <div class="form-group">
            <label class="form-label">Từ Ngày (Bắt đầu tuần - Thứ 2)</label>
            <div style="position:relative;display:flex;align-items:center;">
              <input type="text" class="form-input" id="rep-start-date" value="${startStr}" placeholder="DD/MM/YYYY" style="padding-right:2.5rem;" />
              <input type="date" class="date-picker-overlay" id="picker-start-date" value="${isoStartStr}" style="position:absolute;right:0.4rem;opacity:0;width:2rem;height:2rem;cursor:pointer;z-index:2;" title="Chọn từ lịch" />
              <span style="position:absolute;right:0.6rem;pointer-events:none;font-size:1.1rem;z-index:1;user-select:none;">📅</span>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Đến Ngày (Kết thúc tuần - Thứ 7)</label>
            <div style="position:relative;display:flex;align-items:center;">
              <input type="text" class="form-input" id="rep-end-date" value="${endStr}" placeholder="DD/MM/YYYY" style="padding-right:2.5rem;" />
              <input type="date" class="date-picker-overlay" id="picker-end-date" value="${isoEndStr}" style="position:absolute;right:0.4rem;opacity:0;width:2rem;height:2rem;cursor:pointer;z-index:2;" title="Chọn từ lịch" />
              <span style="position:absolute;right:0.6rem;pointer-events:none;font-size:1.1rem;z-index:1;user-select:none;">📅</span>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Ngày Viết Báo Cáo</label>
            <div style="position:relative;display:flex;align-items:center;">
              <input type="text" class="form-input" id="rep-date" value="${endStr}" placeholder="DD/MM/YYYY" style="padding-right:2.5rem;" />
              <input type="date" class="date-picker-overlay" id="picker-rep-date" value="${isoEndStr}" style="position:absolute;right:0.4rem;opacity:0;width:2rem;height:2rem;cursor:pointer;z-index:2;" title="Chọn từ lịch" />
              <span style="position:absolute;right:0.6rem;pointer-events:none;font-size:1.1rem;z-index:1;user-select:none;">📅</span>
            </div>
          </div>
        </div>
      </div>

      <!-- SECTION 2: Structured Sheet Form Grid for Work Notes -->
      <div class="panel-card" style="border:1px solid var(--primary-glow);background:var(--bg-card-hover);">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;flex-wrap:wrap;gap:0.5rem;">
          <h3 class="panel-title" style="color:var(--primary);margin-bottom:0;">
            📊 2. Bảng Sheet Nhập Công Việc Sơ Phác (Khóa cứng Ngày/Tháng/Năm — Tự do (+) việc con)
          </h3>
          <div style="display:flex;gap:0.4rem;">
            <button class="btn btn-secondary" id="btnEmptySheet" style="font-size:0.78rem;padding:0.3rem 0.6rem;">
              🧹 Xóa Khung Trống
            </button>
            <button class="btn btn-secondary" id="btnFillSampleSheet" style="font-size:0.78rem;padding:0.3rem 0.6rem;">
              💡 Nạp Mẫu Mặc Định
            </button>
          </div>
        </div>

        <div id="sheetGridContainer" style="display:flex;flex-direction:column;gap:1.25rem;">
          ${this._renderSheetGridHTML()}
        </div>

        <button class="btn btn-primary" id="btnGenerateReport" style="width:100%;font-size:1.05rem;padding:0.9rem;margin-top:1.5rem;display:flex;align-items:center;justify-content:center;gap:0.5rem;">
          🚀 AI Phân Tích, Tự Động Sinh Toàn Bộ Báo Cáo &amp; Xuất Word (.docx)
        </button>

        <!-- Progress Bar -->
        <div id="gen-progress-wrap" style="display:none;margin-top:1rem;">
          <div id="gen-progress-msg" style="font-size:0.88rem;font-weight:600;color:var(--primary);margin-bottom:0.5rem;">
            Đang khởi tạo...
          </div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" id="gen-progress-bar" style="width:10%"></div>
          </div>
        </div>
      </div>

      <!-- Download & AI Preview Result Container -->
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
      const headerTitle = `${dayName} (${dateStr})`;

      const subtasks = (Array.isArray(dayItem.subtasks) && dayItem.subtasks.length > 0)
        ? dayItem.subtasks
        : [{ content: '', progress: '100%' }];

      const subtaskRowsHTML = subtasks.map((st, stIdx) => `
        <div class="sheet-subtask-row" data-day-idx="${dayNum}" data-sub-idx="${stIdx}" style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem;">
          <span style="font-weight:700;color:var(--primary);font-size:0.9rem;user-select:none;width:24px;text-align:center;">+</span>
          <textarea class="form-textarea st-content" rows="2" placeholder="Nhập nội dung công việc sơ phác..." style="flex:1;font-size:0.85rem;padding:0.4rem;">${st.content || ''}</textarea>
          <div style="display:flex;align-items:center;gap:0.3rem;width:110px;">
            <span style="font-size:0.78rem;color:var(--text-dim);">%:</span>
            <input type="text" class="form-input st-progress" value="${st.progress || '100%'}" style="font-size:0.85rem;padding:0.35rem;text-align:center;" />
          </div>
          ${subtasks.length > 1 ? `
            <button type="button" class="btn-del-sheet-subtask" data-day-idx="${dayNum}" data-sub-idx="${stIdx}"
                    style="background:none;border:none;color:var(--rose);cursor:pointer;font-size:1.1rem;padding:0 0.3rem;" title="Xóa dòng công việc này">
              🗑️
            </button>
          ` : '<div style="width:24px;"></div>'}
        </div>
      `).join('');

      return `
        <div class="sheet-day-card" data-day-idx="${dayNum}" style="background:var(--bg-input);border:1px solid var(--border-color);border-radius:var(--radius-md);padding:1rem;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem;padding-bottom:0.5rem;border-bottom:1px dashed var(--border-color);">
            <div style="display:flex;align-items:center;gap:0.5rem;">
              <span style="font-size:1.1rem;">📅</span>
              <span style="font-weight:700;color:var(--text-main);font-size:0.95rem;">
                ${headerTitle}
              </span>
            </div>
            <button type="button" class="btn btn-secondary btn-add-sheet-subtask" data-day-idx="${dayNum}" style="font-size:0.75rem;padding:0.25rem 0.6rem;display:flex;align-items:center;gap:0.2rem;" title="Thêm dòng công việc con cho ngày này">
              ➕ Thêm việc
            </button>
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
    progMsg.textContent    = 'Đang nạp dữ liệu & khởi tạo Ollama Qwen 3.6 AI Engine...';
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

      eventBus.emit('toast:show', { message: '🚀 Tác vụ đang chạy ngầm bằng Ollama Qwen 3.6 AI! Bạn có thể chuyển trang.' });

    } catch (err) {
      this._state.busy = false;
      btn.disabled     = false;
      progWrap.style.display = 'none';
      output.innerHTML = `<div style="color:var(--rose);font-weight:600;padding:1rem;background:var(--bg-input);border-radius:var(--radius-md);">❌ Lỗi: ${err.message}</div>`;
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
        output.innerHTML = `<div style="color:var(--rose);font-weight:600;padding:1rem;background:var(--bg-input);border-radius:var(--radius-md);">❌ Lỗi: ${job.message}</div>`;
      }
    });
  },

  _renderReportResult(r, outputEl) {
    if (!outputEl || !r) return;

    // Render Preview Cards for AI Generated Sections
    let dailyRowsHTML = '';
    if (Array.isArray(r.daily_tasks)) {
      r.daily_tasks.forEach((dt, idx) => {
        const subtasks = dt.subtasks && dt.subtasks.length > 0 ? dt.subtasks : [dt];
        subtasks.forEach((st, stIdx) => {
          dailyRowsHTML += `
            <tr style="border-bottom:1px solid var(--border-color);">
              ${stIdx === 0 ? `<td rowspan="${subtasks.length}" style="padding:0.5rem;font-weight:600;vertical-align:top;background:var(--bg-card);">${dt.day || `Thứ ${idx+2}`}</td>` : ''}
              <td style="padding:0.5rem;">${st.content || ''}</td>
              <td style="padding:0.5rem;color:var(--primary);">${st.result || ''}</td>
              <td style="padding:0.5rem;text-align:center;font-weight:600;">${st.progress || '100%'}</td>
              <td style="padding:0.5rem;">${st.note || 'Hoàn thành'}</td>
            </tr>
          `;
        });
      });
    }

    outputEl.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:1.5rem;margin-top:1.5rem;">
        
        <!-- DOWNLOAD BUTTON CARD -->
        <div style="background:var(--bg-input);border:1px solid var(--primary);border-radius:var(--radius-md);padding:1.5rem;text-align:center;">
          <div style="color:var(--primary);font-size:1.15rem;font-weight:700;margin-bottom:0.4rem;">
            🎉 Báo Cáo Tiến Độ Word (.docx) Đã Được Ollama AI Tạo Thành Công!
          </div>
          <div style="font-size:0.85rem;color:var(--text-dim);margin-bottom:1rem;">
            Họ và tên: <strong>${r.full_name || 'BÙI TIẾN THÀNH'}</strong> &nbsp;·&nbsp; Ngày viết: <strong>${r.report_date || ''}</strong>
          </div>
          <a href="${r.download_url}" download="${r.filename}"
             class="btn btn-primary" style="text-decoration:none;display:inline-flex;align-items:center;gap:0.5rem;font-size:1rem;padding:0.75rem 1.75rem;">
            📥 Tải File Báo Cáo Word (.docx) Về Máy
          </a>
        </div>

        <!-- AI PREVIEW 1: GENERAL SUMMARY -->
        <div class="panel-card">
          <h3 class="panel-title" style="color:var(--primary);">📌 I. Tình Hình Chung (Do Ollama AI Tự Động Tổng Hợp)</h3>
          <div style="background:var(--bg-input);padding:1rem;border-radius:var(--radius-sm);font-size:0.9rem;line-height:1.6;">
            ${r.general_summary || 'Chưa có thông tin.'}
          </div>
        </div>

        <!-- AI PREVIEW 2: DAILY TASKS TABLE -->
        <div class="panel-card">
          <h3 class="panel-title" style="color:var(--primary);">📊 II. Bảng Công Việc Hàng Ngày (AI Đã Phân Tách Dòng Con &amp; Làm Rõ Thuật Ngữ)</h3>
          <div style="overflow-x:auto;">
            <table class="data-table" style="width:100%;border-collapse:collapse;font-size:0.82rem;">
              <thead>
                <tr style="background:var(--bg-input);text-align:left;border-bottom:1px solid var(--border-color);">
                  <th style="padding:0.5rem;width:120px;">Thứ / Ngày</th>
                  <th style="padding:0.5rem;">Nội Dung Công Việc</th>
                  <th style="padding:0.5rem;">Kết Quả Thực Hiện (Đã làm rõ thuật ngữ)</th>
                  <th style="padding:0.5rem;width:80px;text-align:center;">Tiến Độ</th>
                  <th style="padding:0.5rem;width:100px;">Ghi Chú</th>
                </tr>
              </thead>
              <tbody>
                ${dailyRowsHTML}
              </tbody>
            </table>
          </div>
        </div>

        <!-- AI PREVIEW 3: SHORT EVALUATION -->
        <div class="panel-card">
          <h3 class="panel-title" style="color:var(--primary);">📌 III. Đánh Giá Ngắn (Do Ollama AI Tự Động Sinh)</h3>
          <div style="background:var(--bg-input);padding:1rem;border-radius:var(--radius-sm);font-size:0.9rem;line-height:1.6;white-space:pre-line;">
            ${r.eval_short || 'Chưa có đánh giá.'}
          </div>
        </div>

        <!-- AI PREVIEW 4: NEXT WEEK PLAN -->
        <div class="panel-card">
          <h3 class="panel-title" style="color:var(--primary);">🤖 IV. Kế Hoạch Tuần Tiếp Theo (Do Ollama AI Tự Động Định Hướng)</h3>
          <div style="background:var(--bg-input);padding:1rem;border-radius:var(--radius-sm);font-size:0.9rem;line-height:1.6;">
            ${r.next_plan_ideas || 'Chưa có kế hoạch.'}
          </div>
        </div>

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
