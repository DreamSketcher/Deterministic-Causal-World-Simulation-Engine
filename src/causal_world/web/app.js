/* v0.8 client: the living CELL map, the problem feed, the analytical mode.
 *
 * Three rules the client obeys:
 *   1. it never invents a fact — every number it shows came from the
 *      server (a frame's world section, or an analysis of the archive);
 *   2. it never calls itself — the URL is derived from the page, so the
 *      client works on any host without a hard-coded address;
 *   3. it never explains — it shows the world's own words (the situation
 *      feed) and the transition ids behind them.
 */
"use strict";

const $ = (id) => document.getElementById(id);
const SVG = "http://www.w3.org/2000/svg";

const state = {
  ws: null,
  session: null,
  seq: 0,
  tick: 0,
  world: null,
  selected: null,
  actionCard: {},
  decreeCard: {},
  lastDirective: {kind: 0, target: "", param: 0.25},
  autoplay: true,
  timer: null,
};

function wsUrl() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws`;
}

function setStatus(text) { $("status").textContent = text; }

// --------------------------------------------------------------- transport

function connect() {
  setStatus("подключение…");
  const ws = new WebSocket(wsUrl());
  ws.onopen = () => {
    setStatus("соединено");
    const seed = parseInt($("seed").value, 10) || 7;
    const ruleset = $("ruleset").value || "player_spatial";
    const regions = parseInt($("regions").value, 10) || 2;
    const agents = parseInt($("agents").value, 10) || 54;
    ws.send(JSON.stringify({
      type: "hello", seed, ruleset, regions, agents,
    }));
  };
  ws.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }
    handle(msg);
  };
  ws.onclose = () => {
    setStatus("соединение закрыто");
    if (state.timer) { clearInterval(state.timer); state.timer = null; }
  };
  ws.onerror = () => setStatus("ошибка соединения");
  state.ws = ws;
}

function send(obj) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(obj));
    return true;
  }
  return false;
}

function handle(msg) {
  if (msg.type === "welcome") {
    state.session = msg.session_id;
    state.actionCard = msg.action_card || {};
    state.decreeCard = msg.decree_card || {};
    state.seq = msg.last_seq || 0;
    state.world = msg.world || null;
    renderCards();
    renderDecrees();
    renderSituations();
    renderGoals();
    setStatus(`сессия ${msg.session_id} · тик ${msg.tick}`);
    if (state.autoplay) scheduleStep();
  } else if (msg.type === "frame") {
    state.seq = msg.seq;
    state.tick = msg.tick;
    state.world = msg.world;
    state.orders = msg.orders || state.orders;
    // What happened to the order sent with this message: accepted,
    // queued (a free tick will come) or rejected. Never silent.
    if (msg.decree) fadeOrder(msg.decree);
    setStatus(`тик ${msg.tick} · живых ${msg.world ? msg.world.alive_agents : "?"} ` +
              `· ${msg.journal.committed} переходов`);
    renderMap();
    renderSituations();
    renderGoals();
    if (msg.finished) {
      setStatus(`жизнь окончена: ${msg.finished.reason}`);
      if (state.timer) { clearInterval(state.timer); state.timer = null; }
    }
    if (state.autoplay) scheduleStep();
  } else if (msg.type === "error") {
    setStatus(`ошибка: ${msg.code} — ${msg.msg}`);
    // A refused message never consumed its decision slot (the server
    // validates BEFORE it applies), so re-align the counter with the
    // server: the next message must use the same seq.
    if (msg.resync && typeof msg.resync.last_seq === "number") {
      state.seq = msg.resync.last_seq;
    } else if (typeof msg.seq === "number") {
      state.seq = msg.seq - 1;
    }
  } else if (msg.type === "analysis") {
    renderAnalysis(msg);
  }
}

// The order banner: the last answer of the civic layer, in plain words.
function fadeOrder(result) {
  const box = $("order-status");
  if (!box) return;
  const cls = result.status === "accepted" ? "confirmed" :
              (result.status === "queued" ? "hypothesis" : "refuted");
  const label = result.status === "accepted" ? "принят" :
                (result.status === "queued" ? "в очереди" : "отклонён");
  box.innerHTML = `<span class="badge ${cls}">приказ ${label}</span> ` +
    `${result.name} → ${result.target} ` +
    (result.tick ? `· в силе с тика ${result.tick} ` : "") +
    `<span class="hint">${result.message}</span>`;
}

function scheduleStep() {
  if (state.timer) clearInterval(state.timer);
  state.timer = setTimeout(() => {
    state.seq += 1;
    send({type: "decide", seq: state.seq, action: 6});
  }, 120);
}

// ------------------------------------------------------------------ cards

function renderCards() {
  const row = $("card-row");
  row.innerHTML = "";
  for (const [idx, name] of Object.entries(state.actionCard)) {
    const b = document.createElement("button");
    b.innerHTML = `<b>${idx}</b>${name}`;
    b.onclick = () => {
      state.seq += 1;
      send({type: "decide", seq: state.seq, action: parseInt(idx, 10)});
    };
    row.appendChild(b);
  }
}

// The decree targets: the CELLS of a spatial world, the REGIONS of the
// old one. The server refuses a target that does not exist.
function decreeTargets() {
  const cells = (state.world && state.world.cells) || [];
  if (cells.length) return cells.map(c => c.id);
  return ((state.world && state.world.regions) || []).map(r => r.id);
}

function renderDecrees() {
  const box = $("decrees");
  if (!Object.keys(state.decreeCard).length) {
    box.innerHTML = "<h3>Устав</h3><p class='hint'>В этом мире нет civic-слоя: " +
      "правила выбраны при создании, приказы недоступны.</p>";
    return;
  }
  const kinds = Object.entries(state.decreeCard);
  const targets = decreeTargets();
  box.innerHTML = "<h3>Устав — приказы правителю</h3>" +
    "<p>Приказ вступает в силу со следующего тика и пишется в журнал " +
    "как обычный переход: его можно найти в бюджете причин. " +
    "Для <b>claim</b> и <b>terrace</b> сила не нужна: цену платит мир " +
    "(еда и почва), а ответ записывается в состояние клетки.</p>";
  const mk = (label, options, current) => {
    const sel = document.createElement("select");
    for (const [v, t] of options) {
      const o = document.createElement("option");
      o.value = v; o.textContent = t;
      if (String(v) === String(current)) o.selected = true;
      sel.appendChild(o);
    }
    return sel;
  };
  const kindSel = mk("", kinds.map(([k, n]) => [k, n]), state.lastDirective.kind);
  const targetSel = mk("", targets.map(t => [t, t]),
                       state.lastDirective.target || targets[0]);
  const paramInput = document.createElement("input");
  paramInput.type = "number"; paramInput.step = "0.05";
  paramInput.value = state.lastDirective.param; paramInput.style.width = "80px";
  const apply = document.createElement("button");
  apply.textContent = "Отдать приказ";
  apply.onclick = () => {
    state.lastDirective = {
      kind: parseInt(kindSel.value, 10),
      target: targetSel.value,
      param: parseFloat(paramInput.value),
    };
    state.seq += 1;
    send({
      type: "decide", seq: state.seq, action: 6,
      decree: {
        kind: state.lastDirective.kind,
        target: state.lastDirective.target,
        region: state.lastDirective.target,
        param: state.lastDirective.param,
      },
    });
  };
  const row = document.createElement("div");
  row.className = "row";
  row.append(kindSel, targetSel, paramInput, apply);
  box.appendChild(row);
  const status = document.createElement("div");
  status.id = "order-status";
  status.className = "order-status";
  box.appendChild(status);
  const pending = (state.orders && state.orders.pending) || [];
  if (pending.length) {
    const q = document.createElement("div");
    q.className = "hint";
    q.textContent = "В очереди: " + pending.map(p =>
      `${p.name} → ${p.target} (просили тик ${p.requested_tick})`).join("; ");
    box.appendChild(q);
  }
  if (state.world) {
    const law = document.createElement("div");
    law.className = "row";
    const scopes = (state.world.cells && state.world.cells.length)
      ? state.world.cells : (state.world.regions || []);
    law.innerHTML = scopes.map(s =>
      `<span class="badge hypothesis">${s.id}: ` +
      (s.land_active === 0 ? "целина (можно заявить) · " : "") +
      (s.land_active !== 0 && s.capacity
        ? `предел ${Math.round(s.capacity)}${s.limit && s.limit !== "none"
            ? " · лимит: " + (LIMIT_WORDS[s.limit] || s.limit) : ""}, ` : "") +
      (s.law ? `отвод ${(s.law.labor_diversion).toFixed(2)}, ` +
               `полив ${(s.law.water_aid).toFixed(2)}` +
               (s.law.nursery ? `, ясли ${(s.law.nursery).toFixed(2)}` : "") +
               (s.law.resting ? ", залежь" : "") : "базовый закон")
      + `</span>`).join(" ");
    box.appendChild(law);
  }
}

// -------------------------------------------------------------- situations

// The world's own words about itself: the situation feed is computed by
// the server from the state, and every alert cites the transitions it
// rests on.
function renderSituations() {
  const box = $("problems");
  if (!box) return;
  const list = (state.world && state.world.situations) || [];
  if (!list.length) {
    box.innerHTML = "<h3>Проблемы мира</h3>" +
      "<p class='hint'>Мир не просит о помощи: признаков бедствия нет.</p>";
    return;
  }
  box.innerHTML = "<h3>Проблемы мира <span class='hint'>(вычислены из состояния)</span></h3>";
  for (const a of list.slice(0, 12)) {
    const e = document.createElement("div");
    e.className = "problem sev-" + (a.severity > 0.75 ? "high" :
                                    (a.severity > 0.4 ? "mid" : "low"));
    const ev = (a.evidence || []).slice(0, 3)
      .map(x => `<span class="tid">T${x.tid}</span>`).join(" ");
    e.innerHTML = `<span class="badge ${a.severity > 0.75 ? "refuted" :
                     (a.severity > 0.4 ? "confirmed" : "hypothesis")}">` +
      `${a.kind}</span> ${a.message} <span class="tid">с тика ${a.since_tick}</span> ${ev}`;
    box.appendChild(e);
  }
}

// ------------------------------------------------------------------- goals

// A goal is a problem with a verdict: the world says not only whether the
// signal disappeared, but whether the PEOPLE and the LAND survived it.
const LIMIT_WORDS = {
  capacity: "ёмкость", food: "еда", soil: "земля",
  adults: "нет взрослых", pool: "резерв жизней", none: "нет",
};

const GOAL_STATUS = {
  active: ["confirmed", "идёт"],
  settling: ["hypothesis", "проверяем"],
  resolved: ["resolved", "решено"],
  resolved_with_cost: ["hypothesis", "решено с ценой"],
  collapsed: ["refuted", "катастрофа"],
  transferred: ["hypothesis", "рядом, не доказано"],
};

function renderGoals() {
  const box = $("goals");
  if (!box) return;
  const list = (state.world && state.world.goals) || [];
  if (!list.length) {
    box.innerHTML = "<h3>Цели</h3><p class='hint'>Пока нечего решать: " +
      "у мира нет открытых проблем.</p>";
    return;
  }
  box.innerHTML = "<h3>Цели <span class='hint'>(вердикт учитывает людей и землю, " +
    "а не только исчезнувший сигнал)</span></h3>";
  for (const g of list.slice(0, 10)) {
    const [cls, label] = GOAL_STATUS[g.status] || ["hypothesis", g.status];
    const e = document.createElement("div");
    e.className = "problem sev-" + (g.status === "collapsed" ? "high" : "low");
    const conf = g.confidence === "hypothesis"
      ? `<span class="badge hypothesis">предположение</span> ` : "";
    e.innerHTML = `<span class="badge ${cls}">${label}</span> ` + conf +
      `<b>${g.kind}</b> ${g.scope} · с тика ${g.opened_tick}` +
      (g.closed_tick !== null && g.closed_tick !== undefined
        ? `, закрыт ${g.closed_tick}` : "") +
      ` · люди ${g.population_open}→${g.population_close}` +
      ` · почва ${g.soil_open}→${g.soil_close}` +
      `<div class="hint">${g.reason}</div>`;
    box.appendChild(e);
  }
}

// -------------------------------------------------------------------- map

function lerp(a, b, t) { return a + (b - a) * Math.max(0, Math.min(1, t)); }
function mix(c1, c2, t) {
  const p = (h) => [1, 3, 5].map(i => parseInt(h.substr(i, 2), 16));
  const [r1, g1, b1] = p(c1), [r2, g2, b2] = p(c2);
  const h = (v) => Math.round(v).toString(16).padStart(2, "0");
  return "#" + h(lerp(r1, r2, t)) + h(lerp(g1, g2, t)) + h(lerp(b1, b2, t));
}

// One isometric tile: the top face is a rhombus, the height above the
// ground plane is the population, the colour is the soil, the bar on
// the ground is the food store.
function drawTile(g, cx, cy, tw, th, d, label, sub) {
  const soilT = d.soil || 0;
  const foodT = Math.max(0, Math.min(1, (d.food_stock || 0) / (d.food_max || 1)));
  const popT = Math.max(0, Math.min(1, (d.population || 0) / (d.pop_max || 1)));

  const h = 14 + 52 * popT;
  const groundY = cy + th * 0.5;
  const topY = groundY - h;
  const hw = tw / 2, hh = th / 2;

  const poly = document.createElementNS(SVG, "polygon");
  poly.setAttribute("class", "tile");
  poly.setAttribute("points",
    `${cx},${topY - hh} ${cx + hw},${topY} ${cx},${topY + hh} ${cx - hw},${topY}`);
  poly.setAttribute("fill", mix("#4a3524", "#c98f4e", soilT));
  poly.setAttribute("stroke", "#1b2128");
  g.appendChild(poly);

  const side = document.createElementNS(SVG, "polygon");
  side.setAttribute("points",
    `${cx - hw},${topY} ${cx},${topY + hh} ${cx},${groundY + hh} ${cx - hw},${groundY}`);
  side.setAttribute("fill", mix("#2a1f16", "#6b4526", soilT));
  side.setAttribute("stroke", "#1b2128");
  g.appendChild(side);

  const side2 = document.createElementNS(SVG, "polygon");
  side2.setAttribute("points",
    `${cx + hw},${topY} ${cx},${topY + hh} ${cx},${groundY + hh} ${cx + hw},${groundY}`);
  side2.setAttribute("fill", mix("#1f1710", "#4d3119", soilT));
  side2.setAttribute("stroke", "#1b2128");
  g.appendChild(side2);

  const bar = document.createElementNS(SVG, "rect");
  bar.setAttribute("x", cx - hw + 5);
  bar.setAttribute("y", groundY + 7);
  bar.setAttribute("width", Math.max(1, (tw - 10) * foodT));
  bar.setAttribute("height", 4);
  bar.setAttribute("fill", "#6fd08a");
  g.appendChild(bar);

  if (d.law && (d.law.labor_diversion > 0 || d.law.water_aid > 0 ||
                d.law.nursery > 0 || d.law.resting)) {
    const badge = document.createElementNS(SVG, "circle");
    badge.setAttribute("cx", cx + hw);
    badge.setAttribute("cy", topY);
    badge.setAttribute("r", 6);
    badge.setAttribute("fill", "#e07ab0");
    badge.setAttribute("stroke", "#171c22");
    g.appendChild(badge);
  }

  const title = document.createElementNS(SVG, "text");
  title.setAttribute("x", cx);
  title.setAttribute("y", topY - 2);
  title.setAttribute("text-anchor", "middle");
  title.textContent = label;
  g.appendChild(title);

  const sub2 = document.createElementNS(SVG, "text");
  sub2.setAttribute("class", "sub");
  sub2.setAttribute("x", cx);
  sub2.setAttribute("y", topY + 12);
  sub2.setAttribute("text-anchor", "middle");
  sub2.textContent = sub;
  g.appendChild(sub2);
}

function renderMap() {
  const svg = $("map");
  svg.innerHTML = "";
  if (!state.world) return;
  const cells = state.world.cells || [];
  if (cells.length) { renderCells(svg, cells); return; }
  renderRegions(svg, state.world.regions || []);
}

function renderCells(svg, cells) {
  const xs = [...new Set(cells.map(c => c.x))].sort((a, b) => a - b);
  const ys = [...new Set(cells.map(c => c.y))].sort((a, b) => a - b);
  const cols = xs.length, rows = ys.length;
  const cw = 900 / cols, ch = 520 / rows;
  const tw = Math.min(cw * 0.56, 150), th = Math.min(ch * 0.30, 90);
  const popMax = Math.max(1, ...cells.map(c => c.population || 0));
  const foodMax = Math.max(1, ...cells.map(c => c.food_stock || 0));

  for (const c of cells) {
    const cx = xs.indexOf(c.x) * cw + cw / 2;
    const cy = ys.indexOf(c.y) * ch + ch / 2;
    const g = document.createElementNS(SVG, "g");
    g.setAttribute("class", "region" + (state.selected === c.id ? " sel" : ""));
    g.onclick = () => { state.selected = c.id; renderMap(); fillEntities(); };
    if (c.land_active === 0) {
      // Wild land: part of the state, not a cell yet. Drawn flat and
      // dashed so the map never pretends it is inhabited.
      const flat = document.createElementNS(SVG, "polygon");
      flat.setAttribute("class", "tile wild");
      flat.setAttribute("points",
        `${cx},${cy - th / 2} ${cx + tw / 2},${cy} ` +
        `${cx},${cy + th / 2} ${cx - tw / 2},${cy}`);
      flat.setAttribute("fill", "#1d242b");
      flat.setAttribute("stroke", "#6b7c8c");
      flat.setAttribute("stroke-dasharray", "5 4");
      g.appendChild(flat);
      const t = document.createElementNS(SVG, "text");
      t.setAttribute("x", cx); t.setAttribute("y", cy + 4);
      t.setAttribute("text-anchor", "middle");
      t.textContent = `${c.id.replace("cell:", "")} · целина`;
      g.appendChild(t);
      const sub2 = document.createElementNS(SVG, "text");
      sub2.setAttribute("class", "sub");
      sub2.setAttribute("x", cx); sub2.setAttribute("y", cy + 18);
      sub2.setAttribute("text-anchor", "middle");
      sub2.textContent = `почва ${(c.soil_fertility || 0).toFixed(2)} · ` +
        `предел ${Math.round(c.capacity || 0)}`;
      g.appendChild(sub2);
      svg.appendChild(g);
      continue;
    }
    const d = Object.assign({}, c, {pop_max: popMax, food_max: foodMax});
    const label = c.id.replace("cell:", "");
    const sub = `почва ${(c.soil_fertility || 0).toFixed(2)} · ` +
      `еда ${Math.round(c.food_stock || 0)} · нас. ${c.population || 0}` +
      ` · предел ${Math.round(c.capacity || 0)}`;
    drawTile(g, cx, cy, tw, th, d, label, sub);
    svg.appendChild(g);
  }
}

function renderRegions(svg, regions) {
  if (!regions.length) return;
  const maxPop = Math.max(1, ...regions.map(r => r.population || 0));
  const maxFood = Math.max(1, ...regions.map(r => r.food_stock || 0));
  const cols = Math.min(4, Math.ceil(Math.sqrt(regions.length)));
  const rows = Math.ceil(regions.length / cols);
  const cw = 900 / cols, ch = 520 / rows;
  const tw = cw * 0.56, th = ch * 0.34;

  regions.forEach((r, i) => {
    const cx = (i % cols) * cw + cw / 2;
    const cy = Math.floor(i / cols) * ch + ch / 2;
    const g = document.createElementNS(SVG, "g");
    g.setAttribute("class", "region" + (state.selected === r.id ? " sel" : ""));
    g.onclick = () => { state.selected = r.id; renderMap(); fillEntities(); };
    const d = Object.assign({}, r, {pop_max: maxPop, food_max: maxFood});
    drawTile(g, cx, cy, tw, th, d, r.id,
      `почва ${(r.soil_fertility || 0).toFixed(2)} · ` +
      `еда ${Math.round(r.food_stock || 0)} · нас. ${r.population || 0}`);
    svg.appendChild(g);
  });
}

// -------------------------------------------------------- analytical mode

function fillEntities() {
  const sel = $("an-entity");
  const cells = (state.world && state.world.cells) || [];
  const regions = (state.world && state.world.regions) || [];
  const ids = cells.length ? cells.map(c => c.id) : regions.map(r => r.id);
  const current = sel.value;
  sel.innerHTML = "";
  for (const r of ids) {
    const o = document.createElement("option");
    o.value = r; o.textContent = r;
    sel.appendChild(o);
  }
  if (current && ids.includes(current)) sel.value = current;
  else if (state.selected) sel.value = state.selected;
}

async function runAnalysis() {
  const body = $("an-body");
  body.innerHTML = "<p class='hint'>считаем…</p>";
  const entity = $("an-entity").value;
  const field = $("an-field").value;
  const res = await fetch(
    `/analyze?entity=${encodeURIComponent(entity)}&field=${encodeURIComponent(field)}`);
  if (!res.ok) { body.innerHTML = `<p class="hint">ошибка ${res.status}</p>`; return; }
  const data = await res.json();
  renderAnalysis(data);
}

function renderAnalysis(data) {
  const body = $("an-body");
  body.innerHTML = "";
  if (data.error) { body.innerHTML = `<p class="hint">${data.error}</p>`; return; }

  const h = (t) => { const e = document.createElement("h3"); e.textContent = t; body.appendChild(e); };
  const p = (t, cls) => {
    const e = document.createElement("p");
    e.textContent = t; if (cls) e.className = cls; body.appendChild(e); return e;
  };

  h("Наблюдаемый факт");
  p(`Положительных приходов и отрицательных расходов: ` +
    `${data.budget.inflows.length} и ${data.budget.outflows.length}. ` +
    `Итог: ${data.budget.net.toFixed(6)}`);

  const table = document.createElement("table");
  table.innerHTML = "<tr><th>источник</th><th>переходов</th><th>сумма</th></tr>";
  for (const e of [...data.budget.inflows, ...data.budget.outflows]) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${e.system}.${e.operation}</td><td>${e.count}</td>` +
      `<td class="${e.total_delta >= 0 ? "pos" : "neg"}">` +
      `${e.total_delta >= 0 ? "+" : ""}${e.total_delta.toFixed(6)}</td>`;
    table.appendChild(tr);
  }
  body.appendChild(table);

  h("Подтверждённые причинные связи");
  if (!data.links.length) {
    p("В записанном мире нет ни одной прочитанной зависимости для этого поля.", "hint");
  } else {
    for (const l of data.links.slice(0, 24)) {
      const e = document.createElement("p");
      e.innerHTML = `<span class="badge confirmed">подтверждено</span> ` +
        `T${l.source_id} → T${l.reader_id} <span class="tid">` +
        `(${l.entity}.${l.field}, глубина ${l.depth})</span>`;
      body.appendChild(e);
    }
  }

  h("Гипотезы игрока");
  if (!data.hypotheses.length) {
    p("Гипотез нет: игрок пока ничего не утверждал.", "hint");
  } else {
    for (const hyp of data.hypotheses) {
      const e = document.createElement("p");
      e.innerHTML = `<span class="badge ${hyp.level}">${hyp.level}</span> ${hyp.text}`;
      body.appendChild(e);
    }
  }

  if (data.situations && data.situations.length) {
    h("Ситуации мира");
    for (const s of data.situations.slice(0, 12)) {
      const e = document.createElement("p");
      e.innerHTML = `<span class="badge ${s.severity > 0.75 ? "refuted" :
        (s.severity > 0.4 ? "confirmed" : "hypothesis")}">${s.kind}</span> ` +
        `${s.message} <span class="tid">${(s.evidence || []).slice(0, 3)
          .map(x => "T" + x.tid).join(" ")}</span>`;
      body.appendChild(e);
    }
  }

  if (data.goals && data.goals.length) {
    h("Цели и их исход");
    for (const g of data.goals.slice(0, 12)) {
      const [cls, label] = GOAL_STATUS[g.status] || ["hypothesis", g.status];
      const e = document.createElement("p");
      e.innerHTML = `<span class="badge ${cls}">${label}</span> ` +
        `${g.kind} <b>${g.scope}</b> · люди ${g.population_open}→` +
        `${g.population_close} · почва ${g.soil_open}→${g.soil_close} ` +
        `<span class="tid">${g.reason}</span>`;
      body.appendChild(e);
    }
  }

  if (data.series && data.series.length) {
    h("Динамика поля");
    const t = document.createElement("p");
    t.className = "tid";
    t.textContent = data.series.map(([tick, v]) => `${tick}:${Number(v).toFixed(3)}`).join("  ");
    body.appendChild(t);
  }

  if (data.population && data.population.length) {
    h("Население мира");
    const t = document.createElement("p");
    t.className = "tid";
    t.textContent = data.population.map(([tick, v]) => `${tick}:${v}`).join("  ");
    body.appendChild(t);
  }
}

// ------------------------------------------------------------------- init

$("new-world").onclick = () => {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) state.ws.close();
  state.seq = 0; state.world = null; state.selected = null;
  state.lastDirective = {kind: 0, target: "", param: 0.25};
  connect();
};
$("autoplay").onchange = (e) => {
  state.autoplay = e.target.checked;
  if (state.autoplay) scheduleStep();
  else if (state.timer) { clearInterval(state.timer); state.timer = null; }
};
$("mode-map").onclick = () => {
  $("mode-map").classList.add("on");
  $("mode-analysis").classList.remove("on");
  $("pane-map").hidden = false; $("pane-analysis").hidden = true;
};
$("mode-analysis").onclick = () => {
  $("mode-analysis").classList.add("on");
  $("mode-map").classList.remove("on");
  $("pane-analysis").hidden = false; $("pane-map").hidden = true;
  fillEntities();
};
$("an-run").onclick = runAnalysis;

connect();
