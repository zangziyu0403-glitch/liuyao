const lineNames = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"];
const backsToTotal = { 0: 6, 1: 7, 2: 8, 3: 9 };
const backsDescription = {
  0: "0背 → 老阴 6 动",
  1: "1背 → 少阳 7 静",
  2: "2背 → 少阴 8 静",
  3: "3背 → 老阳 9 动",
};
const flowOrder = [
  "guide_prepare_coin",
  "guide_meditation",
  "guide_shake",
  "query_info",
  "record",
  "record_complete",
  "revealing",
  "result",
];

const stepMeta = {
  guide_prepare_coin: {
    index: 0,
    kicker: "第一步",
    title: "准备硬币",
    text: "取三枚硬币，先确定哪一面为“背”。",
  },
  guide_meditation: {
    index: 1,
    kicker: "第二步",
    title: "静心默问",
    text: "点香静心，默想所问之事。",
  },
  guide_shake: {
    index: 2,
    kicker: "第三步",
    title: "开始摇卦",
    text: "每次摇三枚硬币，记录背面数量。动画只是引导，不替代实际摇卦。",
  },
  query_info: {
    index: 3,
    kicker: "求测信息",
    title: "填写求测信息",
    text: "填写基本信息后进入六爻录入。",
  },
  record: {
    index: 3,
    kicker: "第四步",
    title: "录入六爻",
    text: "从初爻开始，自下而上录入六次。",
  },
  record_complete: {
    index: 4,
    kicker: "六爻已成",
    title: "生成排盘",
    text: "六次摇卦结果已录入，可生成排盘。",
  },
  revealing: {
    index: 5,
    kicker: "卦象将成",
    title: "揭示排盘",
    text: "莲花完成点亮后，排盘结果将显现。",
  },
  result: {
    index: 6,
    kicker: "排盘完成",
    title: "生成排盘",
    text: "排盘完成后，可点击任意爻位选择用神。",
  },
};

const state = {
  flow: "intro",
  gender: "女",
  backs: [null, null, null, null, null, null],
  currentLineIndex: 0,
  chart: null,
  selectedLine: null,
  timer: 30,
  timerId: null,
  meditationRunning: false,
  lotusComplete: false,
};

const $ = (selector) => document.querySelector(selector);

function setFlow(flow) {
  const previousFlow = state.flow;
  state.flow = flow;
  if (previousFlow === "guide_meditation" && flow !== "guide_meditation") {
    resetMeditationTimer();
  }
  $("#appShell").dataset.flow = flow;
  renderGuide();
  renderLotusProgress();
  renderRitualStatus();
  renderQueryPanel();
  renderRecordPanel();
}

function completeIntro() {
  $("#introOverlay").classList.add("intro-hidden");
  window.localStorage.setItem("liuyao_intro_seen", "1");
  if (state.flow === "intro") {
    setFlow("guide_prepare_coin");
  }
}

function initIntro() {
  $("#skipIntro").addEventListener("click", completeIntro);
  const replayIntro = () => {
    $("#introOverlay").classList.remove("intro-hidden");
    setTimeout(completeIntro, 4600);
  };
  $("#headerRestart").addEventListener("click", restartDivination);
  $("#ritualReplayIntro").addEventListener("click", replayIntro);

  if (window.localStorage.getItem("liuyao_intro_seen") === "1") {
    completeIntro();
    return;
  }

  setTimeout(completeIntro, 4600);
}

function initGender() {
  document.querySelectorAll("[data-gender]").forEach((button) => {
    button.addEventListener("click", () => {
      state.gender = button.dataset.gender;
      document.querySelectorAll("[data-gender]").forEach((item) => {
        item.classList.toggle("active", item === button);
      });
    });
  });
}

function resetMeditationTimer() {
  clearInterval(state.timerId);
  state.timer = 30;
  state.meditationRunning = false;
  $("#timer").textContent = state.timer;
  $("#incenseProgress").style.transform = "scaleY(1)";
  $("#startTimer").textContent = "开始静心";
}

function startMeditationTimer() {
  clearInterval(state.timerId);
  state.meditationRunning = true;
  $("#startTimer").textContent = "静心中";
  state.timerId = setInterval(() => {
    state.timer = Math.max(0, state.timer - 1);
    $("#timer").textContent = state.timer;
    $("#incenseProgress").style.transform = `scaleY(${state.timer / 30})`;
    if (state.timer === 0) {
      clearInterval(state.timerId);
      state.meditationRunning = false;
      $("#startTimer").textContent = "已完成";
      setFlow("guide_shake");
    }
  }, 1000);
}

function initMeditation() {
  $("#startTimer").addEventListener("click", () => {
    if (state.flow !== "guide_meditation") {
      setFlow("guide_meditation");
    }
    startMeditationTimer();
  });
}

function renderGuide() {
  if (!stepMeta[state.flow]) return;

  const meta = stepMeta[state.flow];
  $("#guideCard").classList.remove("step-enter");
  void $("#guideCard").offsetWidth;
  $("#guideCard").classList.add("step-enter");
  $("#guideKicker").textContent = meta.kicker;
  $("#guideTitle").textContent = meta.title;
  $("#guideText").textContent = meta.text;
  $("#guideVisual").dataset.scene = state.flow;

  $("#prevStep").disabled = meta.index === 0;
  $("#nextStep").textContent = state.flow === "guide_shake" ? "填写求测信息" : "下一步";
  const isMeditation = state.flow === "guide_meditation";
  $("#guideCard").classList.toggle("is-meditation", isMeditation);
  $("#meditationTools").hidden = !isMeditation;
  $("#meditationTools").setAttribute("aria-hidden", String(!isMeditation));
  $("#startTimer").hidden = !isMeditation;
  document.querySelector(".incense-timer").hidden = !isMeditation;
}

function renderRitualStatus() {
  $("#ritualProgressCount").textContent = getLotusProgressText();
  $("#ritualProgressState").textContent = getRitualStateText();
}

function getLotusProgressText() {
  const completed = getCompletedLineCount();
  if (state.flow === "result") return "莲子俱明，卦象已成";
  if (state.flow === "record_complete" || state.flow === "revealing") return "六爻既成，待显卦象";
  return `莲子已明 ${completed} / 6`;
}

function getRitualStateText() {
  if (state.flow === "guide_prepare_coin" || state.flow === "intro") return "准备硬币";
  if (state.flow === "guide_meditation") return "静心默问";
  if (state.flow === "guide_shake" || state.flow === "query_info") return "开始摇卦";
  if (state.flow === "record") return `正在录入${lineNames[state.currentLineIndex]}`;
  if (state.flow === "record_complete") return "六爻已成";
  if (state.flow === "revealing") return "卦象将成";
  if (state.flow === "result") return "卦象已成";
  return "准备硬币";
}

function renderLotusProgress() {
  const progress = $("#lotusProgress");
  const ritualCompleted = getRitualCompletedCount();
  const recordedLines = getCompletedLineCount();
  const isComplete = state.flow === "revealing" || state.flow === "result";

  progress.classList.toggle("lotus-complete", isComplete && state.lotusComplete);
  progress.classList.toggle("is-complete", isComplete);
  progress.dataset.flow = state.flow;
  progress.dataset.ritualCompleted = String(ritualCompleted);
  progress.dataset.recordedLines = String(recordedLines);

  document.querySelectorAll(".lotus-ritual-petal").forEach((petal) => {
    const group = Number(petal.dataset.ritual);
    const isLit = isComplete || group <= ritualCompleted;
    const isCurrent = !isComplete && group === getCurrentRitualGroup();
    petal.classList.toggle("lit", isLit);
    petal.classList.toggle("current", isCurrent);
  });

  document.querySelectorAll(".lotus-seed").forEach((seed) => {
    const line = Number(seed.dataset.line);
    const isLit = isComplete || line <= recordedLines;
    const isCurrent = state.flow === "record" && !isLit && line === state.currentLineIndex + 1;
    seed.classList.toggle("lit", isLit);
    seed.classList.toggle("current", isCurrent);
  });

  document.querySelector(".lotus-complete-petal")?.classList.toggle("lit", isComplete);
}

function getCompletedLineCount() {
  return state.backs.filter((value) => value !== null).length;
}

function getRitualCompletedCount() {
  if (state.flow === "intro" || state.flow === "guide_prepare_coin") return 0;
  if (state.flow === "guide_meditation") return 1;
  if (state.flow === "guide_shake") return 2;
  return 3;
}

function getCurrentRitualGroup() {
  if (state.flow === "guide_prepare_coin") return 1;
  if (state.flow === "guide_meditation") return 2;
  if (state.flow === "guide_shake" || state.flow === "query_info") return 3;
  return 0;
}

function initGuideActions() {
  $("#prevStep").addEventListener("click", () => {
    const current = stepMeta[state.flow]?.index ?? 0;
    const next = flowOrder[Math.max(0, current - 1)];
    resetMeditationTimer();
    setFlow(next);
  });

  $("#nextStep").addEventListener("click", () => {
    const current = stepMeta[state.flow]?.index ?? 0;
    const next = flowOrder[Math.min(flowOrder.length - 1, current + 1)];
    if (state.flow === "guide_meditation") {
      resetMeditationTimer();
    }
    setFlow(next);
  });

  $("#skipGuide").addEventListener("click", () => {
    resetMeditationTimer();
    setFlow("query_info");
  });
}

function initQueryPanel() {
  $("#backToGuide").addEventListener("click", () => setFlow("guide_shake"));
  $("#toRecord").addEventListener("click", () => setFlow("record"));
}

function renderQueryPanel() {
  $("#queryPanel").classList.toggle("active", state.flow === "query_info");
}

function renderRecordPanel() {
  const shouldShow = state.flow === "record" || state.flow === "record_complete";
  $("#recordPanel").classList.toggle("active", shouldShow);
  $("#ritualPanel").classList.toggle("compact", shouldShow);
  renderLineStack();
}

function renderLineStack() {
  const stack = $("#lineStack");
  stack.innerHTML = "";

  for (let index = 0; index < 6; index += 1) {
    const line = document.createElement("div");
    line.className = "record-line";
    line.classList.toggle("filled", state.backs[index] !== null);
    line.classList.toggle("current", index === state.currentLineIndex);
    line.classList.toggle("pending", state.backs[index] === null);
    line.innerHTML = `
      <span>${lineNames[index]}</span>
      <i>${state.backs[index] === null ? "待录入" : backsDescription[state.backs[index]]}</i>
    `;
    stack.appendChild(line);
  }

  const completed = getCompletedLineCount();
  $("#recordProgress").textContent =
    completed === 6 ? "六爻已成" : `第 ${state.currentLineIndex + 1} 次 / 共 6 次`;
  $("#currentLine").textContent =
    completed === 6 ? `当前可修改：${lineNames[state.currentLineIndex]}` : `当前录入：${lineNames[state.currentLineIndex]}`;
  $("#recordPrompt").textContent =
    completed === 6
      ? "六次摇卦结果已录入，可生成排盘。"
      : "请实际摇三枚硬币，记录背面数量。";
  $("#buildChart").disabled = completed !== 6;
  $("#recordPrevLine").disabled = state.currentLineIndex === 0;

  document.querySelectorAll("#singleCoinOptions .coin-option").forEach((button) => {
    const backs = Number(button.dataset.backs);
    button.classList.toggle("active", state.backs[state.currentLineIndex] === backs);
  });
}

function chooseBacks(backs) {
  const recordedIndex = state.currentLineIndex;
  state.backs[recordedIndex] = backs;
  setStatus(`已录入${lineNames[recordedIndex]}：${backsDescription[backs]}。`);

  state.currentLineIndex = recordedIndex < 5 ? recordedIndex + 1 : 5;
  if (state.backs.every((value) => value !== null)) {
    setFlow("record_complete");
    return;
  }
  renderLineStack();
  renderLotusProgress();
  renderRitualStatus();
}

function initRecorder() {
  $("#singleCoinOptions").addEventListener("click", (event) => {
    const button = event.target.closest(".coin-option");
    if (!button) return;
    chooseBacks(Number(button.dataset.backs));
  });

  $("#resetRecord").addEventListener("click", clearRecord);
  $("#clearAll").addEventListener("click", clearRecord);
  $("#recordPrevLine").addEventListener("click", () => {
    state.currentLineIndex = Math.max(0, state.currentLineIndex - 1);
    if (state.flow === "record_complete") {
      setFlow("record");
    }
    setStatus(`正在修改${lineNames[state.currentLineIndex]}。`);
    renderLineStack();
    renderLotusProgress();
    renderRitualStatus();
  });
  $("#buildChart").addEventListener("click", () => fetchChart(null));
  $("#selectedInfo").addEventListener("click", (event) => {
    if (event.target.closest("#resetYongshen")) {
      fetchChart(null);
    }
  });
}

function resetChartState() {
  state.backs = [null, null, null, null, null, null];
  state.currentLineIndex = 0;
  state.chart = null;
  state.selectedLine = null;
  state.lotusComplete = false;
  $("#hexagramName").textContent = "未排盘";
  $("#hexagramMeta").textContent = "完成六次录入后生成排盘";
  $("#timeBox").innerHTML = "";
  $("#lines").innerHTML = "";
  $("#relationships").innerHTML = "";
  $("#selectedInfo").textContent = "";
  setStatus("");
}

function clearAll() {
  resetChartState();
  setFlow("record");
  renderLineStack();
}

function clearRecord() {
  clearAll();
}

function restartDivination() {
  resetChartState();
  resetMeditationTimer();
  setFlow("guide_prepare_coin");
  renderLineStack();
}

function totals() {
  return state.backs.map((backs) => (backs === null ? null : backsToTotal[backs]));
}

async function fetchChart(selectedLine = null) {
  if (window.location.protocol === "file:") {
    setStatus("当前是直接打开文件，无法排盘。请使用 http://127.0.0.1:8000。");
    return;
  }

  const result = totals();
  if (result.some((item) => item === null)) {
    setStatus("请先完成六次摇卦。");
    return;
  }

  const response = await fetch("/api/divination", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      gender: state.gender,
      totals: result,
      yongshen_line: selectedLine,
    }),
  });

  const data = await response.json();
  if (!response.ok) {
    setStatus(data.error || "排盘失败。");
    return;
  }

  const shouldReveal = state.flow !== "result";
  state.chart = data;
  state.selectedLine = selectedLine;
  state.lotusComplete = shouldReveal;
  setStatus("");
  renderChart(data);
  if (shouldReveal) {
    setFlow("revealing");
    window.setTimeout(() => {
      state.lotusComplete = false;
      setFlow("result");
    }, prefersReducedMotion() ? 80 : 1900);
    return;
  }
  setFlow("result");
}

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
}

function setStatus(text) {
  $("#status").textContent = text;
}

function ensureServedLocally() {
  if (window.location.protocol === "file:") {
    setStatus("请通过 http://127.0.0.1:8000 打开本地排盘软件。");
  }
}

function renderChart(data) {
  const original = data.original_hexagram;
  $("#hexagramName").textContent = original.name;
  $("#hexagramMeta").textContent = `${original.palace}宫 · ${original.relation_type}`;

  const calendarInfo = buildCalendarInfo(data.time);
  $("#timeBox").innerHTML = `
    <div class="calendar-title">历法信息</div>
    ${renderCalendarRow("公历", calendarInfo.gregorian)}
    ${renderCalendarRow("农历", calendarInfo.lunar)}
    ${renderCalendarRow("干支", calendarInfo.ganzhi)}
    ${renderCalendarRow("节气", calendarInfo.solarTerm)}
    ${renderCalendarRow("月建", calendarInfo.monthJian, true)}
    ${renderCalendarRow("日辰", calendarInfo.dayChen, true)}
    ${renderCalendarRow("旬空", calendarInfo.xunKong, true)}
  `;

  const changingByIndex = new Map(data.changing_lines.map((item) => [item.index, item]));
  const lines = $("#lines");
  lines.innerHTML = "";

  [...original.lines].reverse().forEach((line) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `line-row${state.selectedLine === line.index ? " selected" : ""}`;
    row.dataset.line = line.index;
    row.innerHTML = `
      <span class="yao-index">${line.index}爻</span>
      <span class="six-spirit">${line.six_spirit}</span>
      <span class="yao-symbol">${line.yao}${line.change_symbol ? " " + line.change_symbol : ""}</span>
      <span class="line-body">
        ${line.six_relative}${line.heavenly_stem}${line.earthly_branch}${line.element}
        ${renderMarkers(line)}
        ${renderRoles(line.roles)}
        ${renderTags(line.tags)}
        ${line.hidden_spirit ? `<span class="tag">${line.hidden_spirit.display}</span>` : ""}
      </span>
    `;
    row.addEventListener("click", () => fetchChart(line.index));
    lines.appendChild(row);

    const change = changingByIndex.get(line.index);
    const changeCell = document.createElement("div");
    changeCell.className = "change-cell";
    changeCell.innerHTML = change
      ? `→ ${change.to.display}${renderTags(change.to.tags)}`
      : "";
    lines.appendChild(changeCell);
  });

  renderSelectedInfo(data);
  renderRelationships(data.relationship_hints || [], data);
}

function renderMarkers(line) {
  const markers = [];
  if (line.is_shi) markers.push("世");
  if (line.is_ying) markers.push("应");
  if (!markers.length) return "";
  return `<span class="marker">${markers.map((item) => `<span class="mark">${item}</span>`).join("")}</span>`;
}

function renderRoles(roles = []) {
  if (!roles.length) return "";
  return `<span class="roles">${roles.map((role) => `<span class="role">${role}</span>`).join("")}</span>`;
}

function renderTags(tags = []) {
  if (!tags.length) return "";
  return `<span class="tags">${tags.map((tag) => `<span class="tag">${tag}</span>`).join("")}</span>`;
}

function renderSelectedInfo(data) {
  const query = data.query || {};
  if (!query.yongshen_line) {
    $("#selectedInfo").innerHTML = `
      <div class="yongshen-card">
        <div class="yongshen-card-title">请选择用神</div>
        <p>请根据所问事项，点击卦中对应的一爻作为用神。选择后，系统将标记用神、原神、忌神、仇神。</p>
        <small>若不确定用神，可先不选择，仅查看排盘结果。</small>
      </div>
    `;
    return;
  }

  const selectedLine = data.original_hexagram.lines.find((line) => line.index === query.yongshen_line);
  const selectedDisplay = selectedLine
    ? `${query.yongshen_line}爻 ${selectedLine.six_relative}${selectedLine.heavenly_stem}${selectedLine.earthly_branch}${selectedLine.element}`
    : `${query.yongshen_line}爻 ${query.primary_yongshen}`;

  $("#selectedInfo").innerHTML = `
    <div class="yongshen-card selected">
      <div class="yongshen-card-title">已选择用神</div>
      <p>当前用神：${selectedDisplay}</p>
      <small>系统已根据所选用神标记原神、忌神、仇神。</small>
      <button class="paper-button yongshen-reset" type="button" id="resetYongshen">重新选择用神</button>
    </div>
  `;
}

function relationshipScore(item, data) {
  const lines = data.original_hexagram?.lines || [];
  const roleByLine = new Map(lines.map((line) => [line.index, line.roles || []]));
  const roleWeight = {
    用神: 70,
    原神: 60,
    忌神: 50,
    仇神: 40,
  };

  let score = 0;
  for (const ref of item.refs || []) {
    if (ref.source === "month") score += 1000;
    if (ref.source === "day") score += 100;
    if (ref.line_index !== null && ref.line_index !== undefined) {
      const roles = roleByLine.get(ref.line_index) || [];
      for (const role of roles) {
        score += roleWeight[role] || 0;
      }
    }
  }
  return score;
}

function renderRelationships(items, data) {
  const list = $("#relationships");
  if (!items.length) {
    list.innerHTML = `<span class="empty">暂无关系提示</span>`;
    return;
  }

  const sorted = [...items].sort((left, right) => {
    const scoreDiff = relationshipScore(right, data) - relationshipScore(left, data);
    if (scoreDiff !== 0) return scoreDiff;
    return items.indexOf(left) - items.indexOf(right);
  });

  list.innerHTML = sorted
    .map((item) => `<div class="relationship-item">${item.display}</div>`)
    .join("");
}

function formatDateTime(value) {
  if (!value) return "";
  return value.replace("T", " ").replace(/\.\d+/, "").replace(/\+\d\d:\d\d$/, "").slice(0, 16);
}

function buildCalendarInfo(time = {}) {
  const monthJian = `${time.month_branch || ""}${time.month_element || ""}` || "待接入万年历";
  const dayChen = `${time.day_ganzhi || ""}${time.day_element || ""}` || "待接入万年历";
  return {
    gregorian: formatDateTime(time.qigua_datetime) || "待接入万年历",
    lunar: "待接入万年历",
    ganzhi: "待接入万年历",
    solarTerm: time.month_term ? `${time.month_term}后` : "待接入万年历",
    monthJian,
    dayChen,
    xunKong: Array.isArray(time.void_branches) && time.void_branches.length
      ? time.void_branches.join("、")
      : "待接入万年历",
  };
}

function renderCalendarRow(label, value, important = false) {
  return `
    <div class="calendar-row${important ? " important" : ""}">
      <span>${label}：</span>
      <strong>${value}</strong>
    </div>
  `;
}

initIntro();
initGender();
initMeditation();
initGuideActions();
initQueryPanel();
initRecorder();
renderLineStack();
renderGuide();
renderLotusProgress();
renderRecordPanel();
ensureServedLocally();
