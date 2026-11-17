/* 免费午餐 · 纯前端单页。无依赖、无后端，只读 ./data.json。 */
(() => {
  'use strict';

  const state = { q: '', group: 'all', onlyCompat: false, onlyZero: false, sort: 'default' };

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));

  const GROUPS = [
    { key: 'all', label: '全部' },
    { key: 'direct', label: '🟢 国内直连' },
    { key: 'partial', label: '🟡 部分可用' },
    { key: 'blocked', label: '🔴 需代理' },
    { key: 'unknown', label: '⚪ 待实测' },
    { key: 'archived', label: '已归档' },
  ];

  const FRESH = {
    verified: '已核验', stale: '待复核', unverified: '待核验', archived: '已归档',
  };

  let data = null;

  /* ---------------- data ---------------- */

  async function load() {
    const res = await fetch('./data.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(`data.json ${res.status}`);
    return res.json();
  }

  function matches(r) {
    // 归档条目只在「已归档」视图里出现，不混进「全部」
    if (state.group === 'archived') {
      if (!r.archived) return false;
    } else {
      if (r.archived) return false;
      if (state.group !== 'all' && r.cn_access !== state.group) return false;
    }
    if (state.onlyCompat && !r.openai_compatible) return false;
    if (state.onlyZero && r.tier === 'kyc') return false;
    if (!state.q) return true;
    const hay = [
      r.name, r.provider, r.id, r.notes,
      ...(r.models || []), ...(r.tags || []), ...(r.limits_text || []),
    ].join(' ').toLowerCase();
    return state.q.toLowerCase().split(/\s+/).filter(Boolean).every((t) => hay.includes(t));
  }

  function sortRows(rows) {
    const copy = rows.slice();
    if (state.sort === 'recent') {
      copy.sort((a, b) => (b.verification?.checked_at || '').localeCompare(a.verification?.checked_at || ''));
    } else if (state.sort === 'name') {
      copy.sort((a, b) => a.name.localeCompare(b.name, 'zh-Hans-CN'));
    }
    return copy;
  }

  /* ---------------- render ---------------- */

  function renderStats(s) {
    $('stats').innerHTML = [
      `<li>在用 <b>${s.active}</b> 条</li>`,
      `<li>零门槛 <b>${s.zero ?? 0}</b></li>`,
      `<li>需实名/手机 <b>${s.kyc ?? 0}</b></li>`,
      `<li>国内直连 <b>${s.direct}</b></li>`,
      `<li>OpenAI 兼容 <b>${s.openai}</b></li>`,
      `<li>已核验 <b>${s.verified}</b></li>`,
      s.unverified ? `<li>待核验 <b>${s.unverified}</b></li>` : '',
      s.archived ? `<li>已归档 <b>${s.archived}</b></li>` : '',
    ].join('');
  }

  function renderChips(rows) {
    const box = $('groups');
    box.innerHTML = GROUPS.map((g) => {
      let n;
      if (g.key === 'all') n = rows.filter((r) => !r.archived).length;
      else if (g.key === 'archived') n = rows.filter((r) => r.archived).length;
      else n = rows.filter((r) => !r.archived && r.cn_access === g.key).length;
      if (n === 0) return '';
      return `<button class="chip" role="tab" data-group="${g.key}"
        aria-selected="${state.group === g.key}">${g.label} <span style="opacity:.6">${n}</span></button>`;
    }).join('');
    box.querySelectorAll('.chip').forEach((el) => {
      el.addEventListener('click', () => {
        state.group = el.dataset.group;
        renderChips(rows);
        renderCards(rows);
      });
    });
  }

  function hue(str) {
    let h = 0;
    for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) % 360;
    return h;
  }

  function renderCards(rows) {
    const list = sortRows(rows.filter(matches));
    $('empty').hidden = list.length > 0;
    $('cards').innerHTML = list.map(card).join('');
    $('cards').querySelectorAll('[data-copy]').forEach((el) => {
      el.addEventListener('click', () => copy(el.dataset.copy));
    });
  }

  function card(r) {
    const h = hue(r.provider || r.id);
    const avatar = `<div class="avatar" style="background:hsl(${h} 55% 42%)">${esc((r.provider || r.name)[0])}</div>`;

    const limits = (r.limits_text || []).slice(0, 4)
      .map((t) => `<div>${esc(t)}</div>`).join('') || '<div class="limit-note">额度见备注</div>';

    const models = (r.models || []).length
      ? `<div class="models">${r.models.slice(0, 4).map((m) => `<code>${esc(m)}</code>`).join('')}</div>`
      : '';

    const base = r.base_url
      ? `<div class="baseurl"><code title="${esc(r.base_url)}">${esc(r.base_url)}</code>
           <button type="button" data-copy="${esc(r.base_url)}">复制</button></div>`
      : '';

    const verified = r.verification?.checked_at
      ? `${esc(r.verification.checked_at)} · ${esc(r.verification.method_label)}`
      : '尚未核验';

    const tags = (r.tags || []).length
      ? `<div class="tags">${r.tags.map((t) => `<span>#${esc(t)}</span>`).join('')}</div>`
      : '';

    return `<article class="card ${r.archived ? 'is-archived' : ''}">
      <div class="card-head">
        ${avatar}
        <div class="card-title">
          <h3><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.name)}</a></h3>
          <div class="provider">${esc(r.provider)}${r.openai_compatible ? ' · OpenAI 兼容' : ''}</div>
        </div>
        ${r.tier === 'kyc' ? `<span class="badge kyc" title="${esc(r.tier_label || '需实名/手机')}">📇 ${esc(r.threshold_text || '需实名/手机')}</span>` : ''}
        <span class="badge ${esc(r.cn_access)}" title="${esc(r.cn_label)}">${esc(r.cn_label)}</span>
      </div>
      <div class="limits">${limits}</div>
      ${models}
      ${base}
      ${r.notes ? `<p class="notes">${esc(r.notes)}</p>` : ''}
      <div class="card-foot">
        <span class="dot ${esc(r.freshness)}"></span>
        <span>${esc(FRESH[r.freshness] || r.freshness)} · ${verified}</span>
        ${tags}
      </div>
    </article>`;
  }

  /* ---------------- actions ---------------- */

  function toast(msg) {
    let el = document.querySelector('.toast');
    if (!el) {
      el = document.createElement('div');
      el.className = 'toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('show'), 1600);
  }

  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast('已复制 base_url');
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
      toast('已复制 base_url');
    }
  }

  /* ---------------- init ---------------- */

  async function init() {
    try {
      data = await load();
    } catch (err) {
      $('cards').innerHTML = `<p class="empty">数据加载失败：${esc(err.message)}。
        本地预览请先运行 <code>python scripts/build.py</code>，再用
        <code>python -m http.server -d dist</code> 打开。</p>`;
      return;
    }

    const rows = data.resources || [];
    renderStats(data.stats || {});
    renderChips(rows);
    renderCards(rows);

    $('built').textContent = data.generated_at || '未知';
    if (data.repo) $('repo-link').href = data.repo;

    $('q').addEventListener('input', (e) => {
      state.q = e.target.value.trim();
      renderCards(rows);
    });
    $('only-compat').addEventListener('change', (e) => {
      state.onlyCompat = e.target.checked;
      renderCards(rows);
    });
    $('only-zero').addEventListener('change', (e) => {
      state.onlyZero = e.target.checked;
      renderCards(rows);
    });
    $('sort').addEventListener('change', (e) => {
      state.sort = e.target.value;
      renderCards(rows);
    });
    $('reset').addEventListener('click', (e) => {
      e.preventDefault();
      state.q = ''; state.group = 'all'; state.onlyCompat = false; state.onlyZero = false;
      $('q').value = ''; $('only-compat').checked = false; $('only-zero').checked = false;
      renderChips(rows);
      renderCards(rows);
    });
  }

  init();
})();
