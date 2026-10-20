/* ============================================================
   PM Tools Hub — phần đầu trang & tiêu đề khối dùng chung cho mọi module
   (phong cách Webfolio). CSS: static/styles/module.css
   ============================================================ */

import { moduleRegistry } from '../js/moduleRegistry.js';
import { svgIcon } from './icons.js';

/** Số thứ tự 01, 02… theo thứ tự đăng ký (bỏ trang chủ). */
export function moduleNumber(mod) {
  const list = moduleRegistry.getAllModules().filter((m) => m.id !== 'catalog' && !m.hidden);
  return String(list.findIndex((m) => m.id === mod.id) + 1).padStart(2, '0');
}

/**
 * @param {object} mod   module (id, name, category)
 * @param {object} opt   title (HTML, dùng <span class="thin">), sub, word (chữ viền lớn), meta (mảng chuỗi)
 */
export function pageHero(mod, { title, sub = '', word = '', meta = [] }) {
  return `
    <section class="mp-hero">
      <div class="mp-hero-in">
        <nav class="mp-crumb">
          <a href="/" data-link>Trang chủ</a><i>/</i><a href="/#wfl-tools" data-link="/">Công cụ</a><i>/</i><span>${mod.name}</span>
        </nav>
        <span class="mp-eyebrow">${mod.hidden ? '' : moduleNumber(mod) + ' · '}${mod.category}</span>
        <h1>${title}</h1>
        ${sub ? `<p>${sub}</p>` : ''}
        ${meta.length ? `<div class="mp-meta">${meta.map((m) => `<span>${m}</span>`).join('')}</div>` : ''}
      </div>
      ${word ? `<div class="mp-word" aria-hidden="true">${word}</div>` : ''}
    </section>`;
}

/** Tiêu đề khối: số cam + chữ đậm + chữ mảnh, tuỳ chọn nút bên phải. */
export function panelHead(num, bold, thin = '', actions = '') {
  return `
    <div class="mp-head">
      <span class="mp-num">${num}</span>
      <h3>${bold}${thin ? ` <span class="thin">${thin}</span>` : ''}</h3>
      ${actions ? `<div class="mp-actions">${actions}</div>` : ''}
    </div>`;
}

export { svgIcon };
