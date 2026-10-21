// 아침 지식 신문 웹 페이지
// data/index.json(날짜 목록) → data/digests/YYYY-MM-DD.json(하루치 글)을 읽어 보여 주고,
// 읽음 체크는 이 브라우저의 localStorage에 저장한다.

// ===== Settings =====
// localStorage에 읽음 기록을 저장할 이름. 형식: { "arxiv:2610.26223": { at: "2026-10-22T07:10:00Z", date, topic_id, area } }
const READ_KEY = "kd-read-v1";
// 출처 표시 이름 (digest.py의 SOURCE_LABELS와 같음)
const SOURCE_LABELS = { arxiv: "arXiv", pubmed: "PubMed", iacr: "IACR ePrint", rss: "뉴스" };
// 안 읽은 글을 며칠 전까지 거슬러 올라가 넘겨 올지 / 최대 몇 건까지 보여 줄지
const CARRY_DAYS = 6;
const CARRY_MAX = 10;

// ===== State =====
const state = { dates: [], topics: [], topicById: {}, date: null, items: [], carried: [] };

// ===== Read log (localStorage) =====
// 사생활 보호 모드 등에서는 localStorage가 막혀 있을 수 있어 try/catch로 감쌈 → 막혀 있으면 기록 없이 동작
function loadRead() {
  try {
    return JSON.parse(localStorage.getItem(READ_KEY)) || {};
  } catch {
    return {};
  }
}
function saveRead(log) {
  try {
    localStorage.setItem(READ_KEY, JSON.stringify(log));
  } catch {
    // 저장할 수 없는 환경이면 이번 화면에서만 체크가 유지됨
  }
}
let readLog = loadRead();

// 글 하나의 고유 이름 (seen.json과 같은 "출처:ID")
const keyOf = (item) => `${item.source}:${item.id}`;

// ===== Helpers =====
// 태그를 만들고 글자는 textContent로 넣음 → 외부 제목에 HTML이 섞여 있어도 실행되지 않음
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
// http/https 링크만 허용 (javascript: 같은 위험한 주소 차단)
function safeLink(url) {
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : "#";
  } catch {
    return "#";
  }
}
async function getJSON(path) {
  // cache: "no-cache" → 매일 바뀌는 파일이라 브라우저가 옛 버전을 쓰지 않게 서버에 확인
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}
// 예전 데이터(section 없음)도 digest.py와 같은 규칙으로 칸을 정함
function sectionOf(item) {
  if (item.section) return item.section;
  if (item.dup_of) return "dup";
  if (item.pick) return "main";
  return item.summarized ? "rest" : "main";
}
function formatAuthors(authors) {
  if (!authors || authors.length === 0) return "";
  return authors.length <= 3 ? authors.join(", ") : `${authors.slice(0, 3).join(", ")} 외 ${authors.length - 3}명`;
}

// ===== Render item =====
function renderItem(item) {
  const key = keyOf(item);
  const li = el("li", item.pick ? "item" : "item plain");
  if (readLog[key]) li.classList.add("read");

  // 읽음 체크박스: 누르면 기록에 추가/삭제하고 진행 막대를 다시 계산
  const box = el("input");
  box.type = "checkbox";
  box.checked = Boolean(readLog[key]);
  box.setAttribute("aria-label", `읽음: ${item.title}`);
  box.addEventListener("change", () => {
    if (box.checked) {
      const topic = state.topicById[item.topic_id];
      // 넘겨 온 글은 원래 신문 날짜(item._date)로 기록
      readLog[key] = { at: new Date().toISOString(), date: item._date || state.date, topic_id: item.topic_id, area: topic ? topic.area : "" };
    } else {
      delete readLog[key];
    }
    saveRead(readLog);
    li.classList.toggle("read", box.checked);
    updateProgress();
  });
  li.append(box);

  const body = el("div", "body");
  const a = el("a", "title", item.title);
  a.href = safeLink(item.link);
  // 새 탭에서 열고, 열린 페이지가 이 페이지를 조작하지 못하게 함
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  body.append(a);

  const where = [SOURCE_LABELS[item.source] || item.source, item.venue].filter(Boolean).join(" · ");
  // 넘겨 온 글은 맨 앞에 "10/21 신문"처럼 원래 날짜를 붙임
  const from = item._date ? `${item._date.slice(5).replace("-", "/")} 신문` : "";
  body.append(el("div", "meta", [from, formatAuthors(item.authors), where, item.published].filter(Boolean).join(" · ")));

  if (item.pick) {
    const p = item.pick;
    const badges = el("div", "badges");
    badges.append(el("span", "badge", p.difficulty));
    badges.append(el("span", "stars", "★".repeat(p.importance) + "☆".repeat(5 - p.importance)));
    body.append(badges);

    const ol = el("ol", "summary-lines");
    p.summary.forEach((s) => ol.append(el("li", "", s)));
    body.append(ol);

    const why = el("p", "why");
    why.append(el("b", "", "읽을 이유 "), document.createTextNode(p.why));
    body.append(why);

    if (p.related && p.related.length) {
      const rel = el("p", "related", "같은 소식: ");
      p.related.forEach((r, i) => {
        const link = el("a", "", r.venue || "링크");
        link.href = safeLink(r.link);
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        if (i) rel.append(", ");
        rel.append(link);
      });
      body.append(rel);
    }
  }
  li.append(body);
  return li;
}

// ===== Carry over unread =====
// 이 날짜보다 앞선 CARRY_DAYS일치 신문에서, 본문에 있었는데 아직 안 읽은 글을 모음
async function loadCarried(date) {
  const idx = state.dates.indexOf(date);
  // dates는 최신이 앞이므로, 뒤쪽(idx+1부터)이 더 이전 날짜
  const earlier = state.dates.slice(idx + 1, idx + 1 + CARRY_DAYS);
  // Promise.all: 여러 날짜 파일을 동시에 받음. 못 받은 날은 빈 목록으로
  const days = await Promise.all(earlier.map((d) => getJSON(`data/digests/${d}.json`).catch(() => [])));
  const unread = [];
  days.forEach((items, i) => {
    items
      .filter((it) => sectionOf(it) === "main" && !readLog[keyOf(it)])
      // _date: 원래 신문 날짜 (저장되지 않는 화면용 표시)
      .forEach((it) => unread.push({ ...it, _date: earlier[i] }));
  });
  // 정렬: AI가 고른 글 → 중요도 높은 순 → 최근 날짜 순
  unread.sort((a, b) =>
    (b.pick ? 1 : 0) - (a.pick ? 1 : 0) ||
    (b.pick ? b.pick.importance : 0) - (a.pick ? a.pick.importance : 0) ||
    b._date.localeCompare(a._date));
  return unread.slice(0, CARRY_MAX);
  // → 안 읽고 지나간 글이 사라지지 않고, 다음 날 신문 맨 위에 다시 나오게 하겠다
}

// ===== Render day =====
// 본문 글을 taxonomy 순서대로 영역 → 주제로 묶어 보여 줌
function renderGrouped(items, container) {
  const byTopic = {};
  items.forEach((i) => (byTopic[i.topic_id] ||= []).push(i));
  let currentArea = null;
  state.topics.forEach((t) => {
    const list = byTopic[t.id];
    if (!list) return;
    if (t.area !== currentArea) {
      currentArea = t.area;
      container.append(el("h2", "area", currentArea));
    }
    const h3 = el("h3", "topic", t.topic);
    h3.append(el("span", "tid", t.id));
    container.append(h3);
    const ul = el("ul", "items");
    // 고른 글을 중요도 높은 순으로 먼저
    list.sort((a, b) => (b.pick ? b.pick.importance : 0) - (a.pick ? a.pick.importance : 0));
    list.forEach((i) => ul.append(renderItem(i)));
    container.append(ul);
  });
}

function renderFold(title, items, container, withTopic) {
  if (!items.length) return;
  const det = el("details", "fold");
  det.append(el("summary", "", title));
  const ul = el("ul", "items");
  items.forEach((i) => {
    if (withTopic) {
      const t = state.topicById[i.topic_id];
      ul.append(el("h3", "topic", t ? t.topic : i.topic_id));
    }
    ul.append(renderItem(i));
  });
  det.append(ul);
  container.append(det);
}

async function renderDay(date) {
  state.date = date;
  const content = document.getElementById("content");
  content.replaceChildren(el("p", "empty", "불러오는 중…"));
  try {
    state.items = await getJSON(`data/digests/${date}.json`);
  } catch {
    content.replaceChildren(el("p", "empty", "이 날의 신문을 불러오지 못했습니다."));
    return;
  }
  const by = { main: [], overflow: [], rest: [], dup: [] };
  state.items.forEach((i) => by[sectionOf(i)].push(i));
  state.carried = await loadCarried(date);

  content.replaceChildren();
  if (state.carried.length) {
    content.append(el("h2", "area", `지난 글 — 아직 안 읽음 ${state.carried.length}건`));
    const ul = el("ul", "items carried");
    state.carried.forEach((i) => ul.append(renderItem(i)));
    content.append(ul);
  }
  if (!state.items.length) content.append(el("p", "empty", "이 날은 새 항목이 없습니다."));
  renderGrouped(by.main, content);
  renderFold(`시간 여유가 있으면 — 요약 ${by.overflow.length}건 더 보기`, by.overflow, content, true);
  renderFold(`그 밖의 수집 항목 ${by.rest.length}건 (AI가 고르지 않음)`, by.rest, content, false);

  // 날짜 이동 버튼·선택 상자를 현재 날짜에 맞춤 (dates는 최신이 앞)
  const idx = state.dates.indexOf(date);
  document.getElementById("date").value = date;
  document.getElementById("prev").disabled = idx >= state.dates.length - 1;
  document.getElementById("next").disabled = idx <= 0;
  // 주소 끝에 #날짜를 붙여, 새로고침하거나 링크를 공유해도 같은 날이 열리게 함
  history.replaceState(null, "", `#${date}`);
  updateProgress();
}

// 본문 글 중 읽은 비율을 위쪽 문구·막대에 표시
function updateProgress() {
  const main = state.items.filter((i) => sectionOf(i) === "main");
  const done = main.filter((i) => readLog[keyOf(i)]).length;
  const picks = main.filter((i) => i.pick).length;
  const label = picks ? `오늘의 글 ${main.length}건` : `새 항목 ${main.length}건`;
  document.getElementById("summary").textContent = `${state.date} · ${label} 중 ${done}건 읽음`;
  document.getElementById("progress-bar").style.width = main.length ? `${(done / main.length) * 100}%` : "0";
}

// ===== Export / import =====
function exportLog() {
  // Blob: 메모리 속 파일. 임시 링크를 만들어 눌러서 내려받게 함
  const blob = new Blob([JSON.stringify(readLog, null, 1)], { type: "application/json" });
  const a = el("a");
  a.href = URL.createObjectURL(blob);
  a.download = `knowledge-daily-read-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}
async function importLog(file) {
  try {
    const incoming = JSON.parse(await file.text());
    // 합치기: 이미 있는 기록은 그대로 두고 새 기록만 더함
    readLog = { ...incoming, ...readLog };
    saveRead(readLog);
    renderDay(state.date);
  } catch {
    document.getElementById("summary").textContent = "기록 파일을 읽지 못했습니다.";
  }
}

// ===== Init =====
async function init() {
  try {
    const [index, topics] = await Promise.all([getJSON("data/index.json"), getJSON("data/taxonomy.json")]);
    state.dates = index.dates;
    state.topics = topics;
    topics.forEach((t) => (state.topicById[t.id] = t));
  } catch {
    document.getElementById("content").replaceChildren(el("p", "empty", "신문 목록을 불러오지 못했습니다."));
    return;
  }
  if (!state.dates.length) {
    document.getElementById("content").replaceChildren(el("p", "empty", "아직 신문이 없습니다."));
    return;
  }
  const select = document.getElementById("date");
  state.dates.forEach((d) => select.append(new Option(d, d)));
  select.addEventListener("change", () => renderDay(select.value));
  document.getElementById("prev").addEventListener("click", () => renderDay(state.dates[state.dates.indexOf(state.date) + 1]));
  document.getElementById("next").addEventListener("click", () => renderDay(state.dates[state.dates.indexOf(state.date) - 1]));
  document.getElementById("export").addEventListener("click", exportLog);
  document.getElementById("import").addEventListener("change", (e) => e.target.files[0] && importLog(e.target.files[0]));

  // 주소에 #날짜가 있고 목록에 있으면 그날, 아니면 가장 최근 날
  const fromHash = location.hash.slice(1);
  renderDay(state.dates.includes(fromHash) ? fromHash : state.dates[0]);
}
init();
