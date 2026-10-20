/*
 * SpaceT — Vietnamese UI layer for God's Eye View.
 *
 * The app builds its whole interface at runtime and has no i18n hooks, so this
 * script (injected by gateway.mjs ahead of the app) rewrites English UI text as
 * it appears in the DOM. It never touches app code or state: text nodes and a
 * few accessibility attributes are translated through a dictionary, and text
 * the dictionary does not know stays English (place names, callsigns, ...).
 *
 * Dictionary (window.__SPACET_DICT): { "English template": "Tiếng Việt" }
 *   - every number in a string is replaced by `#` before lookup and put back
 *     in order afterwards (`{1}`, `{2}` in the value reorder them);
 *   - lookup falls back to a case-insensitive match; an ALL-CAPS source gives
 *     an ALL-CAPS translation.
 * Disable with ?lang=en.
 */
(function () {
  'use strict';
  if (window.__spacetVi) return;
  try {
    if (/[?&]lang=en\b/.test(location.search)) return;
  } catch (e) {
    /* no location: carry on */
  }

  var DICT = window.__SPACET_DICT || {};
  var exact = new Map();
  var folded = new Map();
  Object.keys(DICT).forEach(function (key) {
    var value = DICT[key];
    if (typeof value !== 'string' || !value) return;
    exact.set(key, value);
    var lower = key.toLowerCase();
    if (!folded.has(lower)) folded.set(lower, value);
  });

  // The app often builds a message from a fixed fragment and a name or value
  // ('No camera matched "' + query + '"'). Fragments that end in a quote or colon,
  // verbs that take a name ("Select X"), and trailing fragments are matched at the
  // start / end of a string so the name in between is kept as is.
  var VERBS = ['Select', 'Focus', 'Track', 'Follow', 'Open', 'Show', 'Hide', 'Enable', 'Disable', 'Toggle', 'Close', 'Expand', 'Collapse', 'Pin', 'Unpin', 'Play', 'Pause', 'Stop', 'Flying to', 'Loading', 'Searching', 'Looking up'];
  var prefixKeys = [];
  var suffixKeys = [];
  var affixVi = new Map();
  exact.forEach(function (vi, key) {
    if (key.indexOf('#') !== -1 || key.length < 4) return;
    if (/["“:]$/.test(key) && key.length >= 8) {
      prefixKeys.push(key);
      affixVi.set(key, vi);
    }
    if ((/^["”—·]/.test(key) && key.length >= 6) || (/^[a-z]/.test(key) && key.length >= 10)) {
      suffixKeys.push(key);
      affixVi.set(key, vi);
    }
  });
  VERBS.forEach(function (verb) {
    var vi = exact.get(verb);
    if (vi === undefined) {
      vi = folded.get(verb.toLowerCase());
      if (vi !== undefined) vi = sentenceCase(vi);
    }
    if (vi !== undefined) {
      prefixKeys.push(verb);
      affixVi.set(verb, vi);
    }
  });
  function byLengthDesc(a, b) {
    return b.length - a.length;
  }
  prefixKeys.sort(byLengthDesc);
  suffixKeys.sort(byLengthDesc);

  function affixes(core) {
    if (core.length < 10 || core.indexOf(' ') === -1) return null;
    var pre = null;
    for (var i = 0; i < prefixKeys.length; i++) {
      var p = prefixKeys[i];
      if (core.length > p.length && core.lastIndexOf(p, 0) === 0 && (/[^A-Za-z]$/.test(p) || core.charAt(p.length) === ' ')) {
        pre = p;
        break;
      }
    }
    var rest = pre ? core.slice(pre.length) : core;
    var suf = null;
    for (var j = 0; j < suffixKeys.length; j++) {
      var q = suffixKeys[j];
      var at = rest.length - q.length;
      if (at > 0 && rest.indexOf(q, at) === at && (/^[^A-Za-z]/.test(q) || rest.charAt(at - 1) === ' ')) {
        suf = q;
        break;
      }
    }
    if (!pre && !suf) return null;
    var middle = suf ? rest.slice(0, rest.length - suf.length) : rest;
    return (pre ? affixVi.get(pre) : '') + middle + (suf ? affixVi.get(suf) : '');
  }

  var NUM = /\d[\d.,]*/g;
  var ATTRS = ['title', 'aria-label', 'placeholder', 'alt', 'aria-valuetext'];
  var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1, INPUT: 1, CODE: 1, PRE: 1, TITLE: 1 };
  // Icon ligatures, opt-outs, and the "GOD'S EYE VIEW" brand heading (its word "VIEW" is a name here).
  var SKIP_SELECTOR = '.material-symbols-outlined,.material-symbols-rounded,.notranslate,[translate="no"],[contenteditable="true"],h1:has(> .brand-logo)';
  var SEGMENT = /(\s[·|]\s|\s—\s|\s→\s)/;
  var CACHE_LIMIT = 6000;
  var cache = new Map();

  function fill(vi, nums) {
    if (/\{\d+\}/.test(vi)) {
      return vi.replace(/\{(\d+)\}/g, function (m, i) {
        return nums[i - 1] !== undefined ? nums[i - 1] : m;
      });
    }
    var next = 0;
    return vi.replace(/#/g, function (m) {
      return nums[next] !== undefined ? nums[next++] : m;
    });
  }

  function isAllCaps(s) {
    return s === s.toUpperCase() && /[A-Z]/.test(s);
  }

  /** "ĐANG TẢI" -> "Đang tải" (multi-word upper-case values only; "CCTV" stays). */
  function sentenceCase(vi) {
    if (/\s/.test(vi) && vi === vi.toLocaleUpperCase('vi-VN')) {
      return vi.charAt(0) + vi.slice(1).toLocaleLowerCase('vi-VN');
    }
    return vi;
  }

  /** Dictionary lookup for one phrase (numbers templated); null when unknown. */
  function lookup(core) {
    var nums = core.match(NUM) || [];
    var template = nums.length ? core.replace(NUM, '#') : core;
    var vi = exact.get(template);
    if (vi !== undefined) return fill(vi, nums);
    vi = folded.get(template.toLowerCase());
    if (vi !== undefined) {
      vi = fill(vi, nums);
      return isAllCaps(core) ? vi.toLocaleUpperCase('vi-VN') : sentenceCase(vi);
    }
    return null;
  }

  var AGO_UNITS = { s: 'giây', sec: 'giây', secs: 'giây', m: 'phút', min: 'phút', mins: 'phút', h: 'giờ', hr: 'giờ', hrs: 'giờ', d: 'ngày', day: 'ngày', days: 'ngày' };

  /** Hand-written rules for dynamic phrases the dictionary cannot template. */
  function rules(core) {
    var m;
    if ((m = /^(\d+)\s*(s|secs?|m|mins?|h|hrs?|d|days?)\s+ago$/i.exec(core))) {
      return m[1] + ' ' + AGO_UNITS[m[2].toLowerCase()] + ' trước';
    }
    if (/^just now$/i.test(core)) return 'vừa xong';
    return null;
  }

  function phrase(core) {
    return lookup(core) || rules(core);
  }

  function translateCore(core) {
    var out = phrase(core);
    if (out !== null) return out;

    // "A · B | C — D → E": translate each known segment, keep the rest.
    if (SEGMENT.test(core)) {
      var parts = core.split(SEGMENT);
      var changed = false;
      for (var i = 0; i < parts.length; i += 2) {
        var t = translateCore(parts[i]);
        if (t !== null) {
          parts[i] = t;
          changed = true;
        }
      }
      return changed ? parts.join('') : null;
    }

    // "Label: value" — translate the label, and the value when it is chrome too.
    var colon = /^([^:]{2,48}):\s+(.+)$/.exec(core);
    if (colon) {
      var label = phrase(colon[1] + ':') || phrase(colon[1]);
      if (label !== null) {
        var value = translateCore(colon[2]);
        return (/:$/.test(label) ? label : label + ':') + ' ' + (value !== null ? value : colon[2]);
      }
    }

    // "Label (12)" / "12 Label": keep the count, translate the label.
    var paren = /^(.+?)\s*(\(\d[\d.,]*\))$/.exec(core);
    if (paren) {
      var base = translateCore(paren[1]);
      if (base !== null) return base + ' ' + paren[2];
    }
    return affixes(core);
  }

  /** Translation of a raw string, or null when it should stay as is. */
  function tr(raw) {
    if (raw.length < 2 || raw.length > 400) return null;
    var hit = cache.get(raw);
    if (hit !== undefined) return hit;
    var lead = /^\s*/.exec(raw)[0];
    var trail = /\s*$/.exec(raw)[0];
    var core = raw.trim().replace(/\s+/g, ' ');
    var out = null;
    // Skip Material Symbols ligature names (view_in_ar, my_location) that lack the icon class.
    if (core && /[A-Za-z]{2}/.test(core) && !/^[a-z]+(_[a-z0-9]+)+$/.test(core)) {
      var t = translateCore(core);
      if (t !== null && t !== core) out = lead + t + trail;
    }
    if (cache.size > CACHE_LIMIT) cache.clear();
    cache.set(raw, out);
    return out;
  }

  var written = new WeakMap();

  function textNode(node) {
    var parent = node.parentElement;
    if (!parent || SKIP_TAGS[parent.tagName] || parent.closest(SKIP_SELECTOR)) return;
    var value = node.nodeValue;
    if (written.get(node) === value) return;
    var out = tr(value);
    if (out !== null) {
      written.set(node, out);
      node.nodeValue = out;
    }
  }

  function attributes(el) {
    for (var i = 0; i < ATTRS.length; i++) {
      var value = el.getAttribute(ATTRS[i]);
      if (!value) continue;
      var out = tr(value);
      if (out !== null) el.setAttribute(ATTRS[i], out);
    }
  }

  function walk(node) {
    if (node.nodeType === 3) return textNode(node);
    if (node.nodeType !== 1 || SKIP_TAGS[node.tagName]) return;
    if (node.matches(SKIP_SELECTOR)) return;
    attributes(node);
    for (var child = node.firstChild; child; child = child.nextSibling) walk(child);
  }

  function onMutations(records) {
    for (var i = 0; i < records.length; i++) {
      var r = records[i];
      if (r.type === 'characterData') {
        textNode(r.target);
      } else if (r.type === 'attributes') {
        if (r.target.nodeType === 1 && !r.target.matches(SKIP_SELECTOR)) attributes(r.target);
      } else {
        for (var j = 0; j < r.addedNodes.length; j++) walk(r.addedNodes[j]);
      }
    }
  }

  function start() {
    var root = document.documentElement;
    document.documentElement.lang = 'vi';
    walk(root);
    new MutationObserver(onMutations).observe(root, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ATTRS,
    });
  }

  window.__spacetVi = { tr: tr, size: exact.size };
  start();
  document.addEventListener('DOMContentLoaded', function () {
    walk(document.documentElement);
  });
})();
