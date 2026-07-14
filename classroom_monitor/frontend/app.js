const STATUS_LABEL = {
  in_use: "使用中",
  idle: "待机",
  offline: "离线",
  fault: "故障",
};

let token = localStorage.getItem("cm_token") || "jnu-demo-admin";
let apiUrl = localStorage.getItem("cm_api_url") || "";
let apiKey = localStorage.getItem("cm_api_key") || "";
let rooms = [];
let summary = {};
let selectedId = null;
let viewMode = "grid";
let ws = null;
let siteConfig = {};
let externalConnected = false;

const $ = (id) => document.getElementById(id);

function authHeaders(json = false) {
  const h = { Authorization: `Bearer ${token}` };
  if (json) h["Content-Type"] = "application/json";
  return h;
}

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { ...authHeaders(opts.body != null), ...opts.headers } });
  if (!res.ok) {
    let msg = await res.text();
    try {
      const j = JSON.parse(msg);
      msg = j.detail || j.message || msg;
    } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

function frameUrl(roomId) {
  return `/api/rooms/${roomId}/frame.jpg?t=${Date.now()}`;
}

function mjpegUrl(roomId) {
  return `/api/rooms/${roomId}/mjpeg?token=${encodeURIComponent(token)}`;
}

function absoluteMockApi() {
  return `${location.origin}/api/mock-platform`;
}

function setConn(ok) {
  const el = $("connBadge");
  el.textContent = ok ? "实时连接" : "未连接";
  el.className = `badge ${ok ? "online" : "offline"}`;
}

function updateApiBadge() {
  const el = $("apiBadge");
  el.classList.remove("hidden");
  if (externalConnected && apiUrl) {
    el.textContent = "API 已连接";
    el.className = "badge online";
    $("apiBanner").classList.remove("hidden");
    $("apiBanner").textContent = `已连接：${apiUrl}`;
    $("demoBadge").classList.add("hidden");
  } else {
    el.textContent = "演示数据";
    el.className = "badge demo";
    $("apiBanner").classList.add("hidden");
    if (siteConfig.demo_mode !== false) $("demoBadge").classList.remove("hidden");
  }
}

function showConnectStatus(msg, ok) {
  const el = $("connectStatus");
  el.classList.remove("hidden", "ok", "err");
  el.classList.add(ok ? "ok" : "err");
  el.textContent = msg;
}

async function loadSiteConfig() {
  try {
    siteConfig = await fetch("/api/config").then((r) => r.json());
    if (siteConfig.default_token) token = token || siteConfig.default_token;
    $("tokenInput").value = token;
    const mock = absoluteMockApi();
    $("mockApiExample").textContent = mock;
    if (!apiUrl) $("apiUrlInput").placeholder = mock;
    $("apiUrlInput").value = apiUrl;
    $("apiKeyInput").value = apiKey;
    $("footerMeta").textContent = `${siteConfig.campus} · ${siteConfig.support_phone}`;
    if (siteConfig.public_url) {
      const box = document.getElementById("publicUrlBox");
      if (box) {
        box.classList.remove("hidden");
        box.innerHTML = `临时公网入口：<a href="${siteConfig.public_url}" target="_blank" rel="noopener">${siteConfig.public_url}</a>`;
      }
    }
    if (siteConfig.technician_device_mac) {
      const macBox = document.getElementById("deviceMacBox");
      const macVal = document.getElementById("deviceMacValue");
      if (macBox && macVal) {
        macBox.classList.remove("hidden");
        macVal.textContent = siteConfig.technician_device_mac;
      }
    }
  } catch (_) {}
}

loadSiteConfig();

function renderSummary() {
  const cards = [
    ["教室总数", summary.total],
    ["在线", summary.online],
    ["使用中", summary.in_use],
    ["故障", summary.fault],
  ];
  $("summaryCards").innerHTML = cards
    .map(([lbl, num]) => `<div class="card"><div class="num">${num ?? "—"}</div><div class="lbl">${lbl}</div></div>`)
    .join("");
  if ($("footerMeta")) {
    const src = summary.external_api ? `API: ${summary.external_api}` : "演示模式";
    $("footerMeta").textContent = `${summary.campus || "番禺校区"} · ${src} · ${summary.updated_at || ""}`;
  }
  externalConnected = !!summary.external_mode;
  updateApiBadge();
}

function filteredRooms() {
  const building = $("buildingFilter").value;
  const status = $("statusFilter").value;
  const q = $("searchInput").value.trim().toLowerCase();
  return rooms.filter((r) => {
    if (building && r.building !== building) return false;
    if (status && r.status !== status) return false;
    if (q && !(`${r.building}${r.room}${r.id}`.toLowerCase().includes(q))) return false;
    return true;
  });
}

function renderRoomList() {
  const list = filteredRooms();
  $("roomList").innerHTML =
    (list.length ? `<div class="list-meta">显示 ${list.length} / ${rooms.length} 间</div>` : `<div class="list-meta">暂无教室</div>`) +
    list
      .map(
        (r) => `
    <div class="room-item ${r.id === selectedId ? "active" : ""}" data-id="${r.id}">
      <div class="row1">
        <span class="name">${r.building} · ${r.room}</span>
        <span><span class="status-dot status-${r.status}"></span>${STATUS_LABEL[r.status] || r.status}</span>
      </div>
      <div class="row2">${(r.devices || []).join(" / ")}${r.note ? " · " + r.note : ""}</div>
    </div>`
      )
      .join("");
  document.querySelectorAll(".room-item").forEach((el) => {
    el.addEventListener("click", () => selectRoom(el.dataset.id));
  });
}

function renderChips(room) {
  const chips = [
    ["PC", room.pc_on],
    ["投影", room.projector_on],
    ["HDMI", room.hdmi_ok],
    ["麦克风", room.mic_ok],
  ];
  $("deviceChips").innerHTML = chips
    .map(([name, ok]) => `<span class="chip ${ok ? "ok" : "bad"}">${name}: ${ok ? "正常" : "异常"}</span>`)
    .join("");
}

function renderStream() {
  const area = $("streamArea");
  const list = viewMode === "grid" ? filteredRooms().slice(0, 12) : rooms.filter((r) => r.id === selectedId);

  if (viewMode === "single" && selectedId) {
    const room = rooms.find((r) => r.id === selectedId);
    area.innerHTML = `
      <div class="stream-single">
        <img src="${mjpegUrl(selectedId)}" alt="${room?.building} ${room?.room}" />
        <p class="stream-note">MJPEG 实时流 · ${externalConnected ? "外部 API" : "本地演示"}</p>
      </div>`;
    return;
  }

  area.innerHTML = `<div class="grid-view">${list
    .map(
      (r) => `
      <div class="grid-card" data-id="${r.id}">
        <img src="${frameUrl(r.id)}" alt="${r.room}" loading="lazy" />
        <div class="cap"><span>${r.building} ${r.room}</span><span>${STATUS_LABEL[r.status]}</span></div>
      </div>`
    )
    .join("")}</div>`;

  area.querySelectorAll(".grid-card").forEach((el) => {
    el.addEventListener("click", () => {
      selectRoom(el.dataset.id);
      viewMode = "single";
      renderStream();
    });
  });
}

function selectRoom(id) {
  selectedId = id;
  const room = rooms.find((r) => r.id === id);
  if (!room) return;
  $("emptyState").classList.add("hidden");
  $("detailPane").classList.remove("hidden");
  $("detailTitle").textContent = `${room.building} · ${room.room}`;
  $("detailMeta").textContent = `座位 ${room.seats} · ${(room.devices || []).join(" / ")}`;
  renderChips(room);
  renderRoomList();
  renderStream();
}

function populateBuildings() {
  const buildings = [...new Set(rooms.map((r) => r.building))];
  $("buildingFilter").innerHTML =
    `<option value="">全部</option>` + buildings.map((b) => `<option value="${b}">${b}</option>`).join("");
}

function connectWs() {
  if (ws) ws.close();
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`);
  ws.onopen = () => setConn(true);
  ws.onclose = () => setConn(false);
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.summary) summary = msg.summary;
    if (msg.rooms) rooms = msg.rooms;
    renderSummary();
    populateBuildings();
    renderRoomList();
    if (selectedId && viewMode === "single") renderStream();
    if (viewMode === "grid") renderStream();
  };
}

async function connectExternalApi(url, key) {
  const result = await api("/api/connect", {
    method: "POST",
    body: JSON.stringify({ api_url: url, api_key: key || "" }),
  });
  apiUrl = url;
  apiKey = key || "";
  localStorage.setItem("cm_api_url", apiUrl);
  localStorage.setItem("cm_api_key", apiKey);
  externalConnected = true;
  return result;
}

async function bootstrap(useDemoOnly = false) {
  token = $("tokenInput").value.trim() || token;
  localStorage.setItem("cm_token", token);

  if (!useDemoOnly && apiUrl) {
    try {
      const r = await connectExternalApi(apiUrl, apiKey);
      showConnectStatus(r.message, true);
    } catch (e) {
      throw new Error("API 连接失败：" + e.message);
    }
  } else if (!useDemoOnly) {
  }

  summary = await api("/api/summary");
  rooms = await api("/api/rooms");
  externalConnected = !!summary.external_mode;
  populateBuildings();
  renderSummary();
  renderRoomList();
  connectWs();
  viewMode = "grid";
  $("emptyState").classList.add("hidden");
  $("detailPane").classList.remove("hidden");
  $("detailTitle").textContent = externalConnected ? "已连接 · 网格总览" : "演示模式 · 网格总览";
  $("detailMeta").textContent = "点击教室查看 MJPEG 实时画面";
  $("deviceChips").innerHTML = "";
  renderStream();
  $("loginPanel").classList.add("hidden");
  $("app").classList.remove("hidden");
  $("refreshBtn").classList.remove("hidden");
  $("apiSettingsBtn").classList.remove("hidden");
}

$("connectBtn").addEventListener("click", async () => {
  apiUrl = $("apiUrlInput").value.trim();
  apiKey = $("apiKeyInput").value.trim();
  if (!apiUrl) {
    showConnectStatus("请填写 API 地址", false);
    return;
  }
  token = $("tokenInput").value.trim() || token;
  $("connectBtn").disabled = true;
  try {
    await bootstrap(false);
  } catch (e) {
    showConnectStatus(e.message, false);
    alert(e.message);
  } finally {
    $("connectBtn").disabled = false;
  }
});

$("demoBtn").addEventListener("click", async () => {
  apiUrl = "";
  localStorage.removeItem("cm_api_url");
  token = $("tokenInput").value.trim() || token;
  try {
    await bootstrap(true);
  } catch (e) {
    alert(e.message);
  }
});

$("quickDemoBtn").addEventListener("click", async () => {
  apiUrl = absoluteMockApi();
  $("apiUrlInput").value = apiUrl;
  apiKey = "";
  $("apiKeyInput").value = "";
  token = $("tokenInput").value.trim() || token;
  $("quickDemoBtn").disabled = true;
  try {
    showConnectStatus("正在连接测试 API…", true);
    await bootstrap(false);
  } catch (e) {
    showConnectStatus(e.message, false);
    alert(e.message);
  } finally {
    $("quickDemoBtn").disabled = false;
  }
});

$("refreshBtn").addEventListener("click", async () => {
  try {
    summary = await api("/api/summary");
    rooms = await api("/api/rooms");
    renderSummary();
    renderRoomList();
    if (viewMode === "grid") renderStream();
  } catch (e) {
    alert(e.message);
  }
});

$("apiSettingsBtn").addEventListener("click", () => {
  $("apiUrlDialog").value = apiUrl;
  $("apiKeyDialog").value = apiKey;
  $("apiDialog").showModal();
});

$("apiDialogConnect").addEventListener("click", async () => {
  apiUrl = $("apiUrlDialog").value.trim();
  apiKey = $("apiKeyDialog").value.trim();
  if (!apiUrl) return alert("请填写 API 地址");
  try {
    await connectExternalApi(apiUrl, apiKey);
    summary = await api("/api/summary");
    rooms = await api("/api/rooms");
    populateBuildings();
    renderSummary();
    renderRoomList();
    renderStream();
    $("apiDialog").close();
  } catch (e) {
    alert(e.message);
  }
});

$("apiDialogDisconnect").addEventListener("click", async () => {
  try {
    await api("/api/disconnect", { method: "POST", body: JSON.stringify({}) });
    apiUrl = "";
    localStorage.removeItem("cm_api_url");
    summary = await api("/api/summary");
    rooms = await api("/api/rooms");
    populateBuildings();
    renderSummary();
    renderRoomList();
    renderStream();
    $("apiDialog").close();
  } catch (e) {
    alert(e.message);
  }
});

["buildingFilter", "statusFilter", "searchInput"].forEach((id) => {
  $(id).addEventListener("input", () => {
    renderRoomList();
    if (viewMode === "grid") renderStream();
  });
});

$("gridViewBtn").addEventListener("click", () => {
  viewMode = "grid";
  renderStream();
});
$("singleViewBtn").addEventListener("click", () => {
  if (!selectedId && rooms.length) selectedId = rooms[0].id;
  viewMode = "single";
  if (selectedId) selectRoom(selectedId);
});

setInterval(() => {
  if (!token || viewMode !== "grid") return;
  document.querySelectorAll(".grid-card img").forEach((img) => {
    const id = img.closest(".grid-card")?.dataset.id;
    if (id) img.src = frameUrl(id);
  });
}, 3000);

// 一键填入测试 API
$("mockApiExample").addEventListener("click", () => {
  $("apiUrlInput").value = absoluteMockApi();
});
