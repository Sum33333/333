const STATUS_LABEL = {
  in_use: "使用中",
  idle: "待机",
  offline: "离线",
  fault: "故障",
};

let token = "";
let rooms = [];
let summary = {};
let selectedId = null;
let viewMode = "grid"; // grid | single
let ws = null;

let siteConfig = {};

const $ = (id) => document.getElementById(id);

async function loadSiteConfig() {
  try {
    const res = await fetch("/api/config");
    siteConfig = await res.json();
    if (siteConfig.cas_enabled && siteConfig.cas_login_url) {
      $("casLoginBtn").classList.remove("hidden");
      $("loginDivider").classList.remove("hidden");
      $("casLoginBtn").onclick = () => {
        window.location.href = siteConfig.cas_login_url;
      };
    }
    $("footerMeta").textContent = `${siteConfig.campus} · 服务热线 ${siteConfig.support_phone}`;
    if (siteConfig.demo_mode) {
      $("demoBadge").classList.remove("hidden");
    } else {
      $("demoBadge").classList.add("hidden");
    }
  } catch (_) {
    /* ignore */
  }
}

loadSiteConfig();

function authHeaders() {
  return { Authorization: `Bearer ${token}` };
}

async function api(path) {
  const res = await fetch(path, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function frameUrl(roomId, bust = true) {
  const q = bust ? `?t=${Date.now()}` : "";
  return `/api/rooms/${roomId}/frame.jpg${q}`;
}

function mjpegUrl(roomId) {
  return `/api/rooms/${roomId}/mjpeg?token=${encodeURIComponent(token)}`;
}

function setConn(ok) {
  const el = $("connBadge");
  el.textContent = ok ? "实时连接" : "未连接";
  el.className = `badge ${ok ? "online" : "offline"}`;
}

function renderSummary() {
  const cards = [
    ["教室总数", summary.total],
    ["在线", summary.online],
    ["使用中", summary.in_use],
    ["故障", summary.fault],
  ];
  $("summaryCards").innerHTML = cards
    .map(
      ([lbl, num]) => `
      <div class="card"><div class="num">${num ?? "—"}</div><div class="lbl">${lbl}</div></div>`
    )
    .join("");
  if ($("footerMeta") && (siteConfig.support_phone || summary.updated_at)) {
    $("footerMeta").textContent = `${summary.campus || siteConfig.campus || "番禺校区"} · 课室约 ${summary.classroom_capacity_est || siteConfig.classroom_capacity_est || "—"} 间 · 更新 ${summary.updated_at || "—"}`;
  }
  $("demoBadge").classList.toggle("hidden", !summary.demo_mode);
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
  $("roomList").innerHTML = list
    .map(
      (r) => `
    <div class="room-item ${r.id === selectedId ? "active" : ""}" data-id="${r.id}">
      <div class="row1">
        <span class="name">${r.building} · ${r.room}</span>
        <span><span class="status-dot status-${r.status}"></span>${STATUS_LABEL[r.status] || r.status}</span>
      </div>
      <div class="row2">CPU ${r.cpu_pct}% · ${r.devices.join(" / ")}${r.note ? " · " + r.note : ""}</div>
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
    .map(
      ([name, ok]) => `<span class="chip ${ok ? "ok" : "bad"}">${name}: ${ok ? "正常" : "异常"}</span>`
    )
    .join("");
}

function renderStream() {
  const area = $("streamArea");
  const list = viewMode === "grid" ? filteredRooms().slice(0, 12) : rooms.filter((r) => r.id === selectedId);

  if (viewMode === "single" && selectedId) {
    const room = rooms.find((r) => r.id === selectedId);
    area.innerHTML = `
      <div class="stream-single">
        <img src="${mjpegUrl(selectedId)}" alt="${room.building} ${room.room}" />
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
  $("detailMeta").textContent = `座位 ${room.seats} · ${room.devices.join(" / ")} · 最后上报 ${room.last_seen || "—"}`;
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
    renderRoomList();
    if (selectedId && viewMode === "single") renderStream();
    if (viewMode === "grid") renderStream();
  };
}

async function bootstrap() {
  summary = await api("/api/summary");
  rooms = await api("/api/rooms");
  populateBuildings();
  renderSummary();
  renderRoomList();
  connectWs();
  viewMode = "grid";
  $("emptyState").classList.add("hidden");
  $("detailPane").classList.remove("hidden");
  $("detailTitle").textContent = "网格总览";
  $("detailMeta").textContent = "点击任意教室进入单画面 MJPEG 预览";
  $("deviceChips").innerHTML = "";
  renderStream();
}

$("loginBtn").addEventListener("click", async () => {
  token = $("tokenInput").value.trim();
  if (!token) return alert("请输入令牌");
  try {
    await bootstrap();
    $("loginPanel").classList.add("hidden");
    $("app").classList.remove("hidden");
  } catch (e) {
    alert("登录失败：" + e.message);
  }
});

$("refreshBtn").addEventListener("click", async () => {
  if (!token) return;
  try {
    await bootstrap();
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

// Auto-refresh grid snapshots
setInterval(() => {
  if (!token || viewMode !== "grid") return;
  document.querySelectorAll(".grid-card img").forEach((img) => {
    const id = img.closest(".grid-card")?.dataset.id;
    if (id) img.src = frameUrl(id);
  });
}, 3000);
