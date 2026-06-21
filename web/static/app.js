const $ = (sel) => document.querySelector(sel);

function fmt(n, digits = 0) {
  if (n === null || n === undefined) return "--";
  return Number(n).toLocaleString(undefined, {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  });
}

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(url + " -> " + r.status);
  return r.json();
}

function tickClock() {
  const now = new Date();
  $("#clock").textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  $("#date").textContent = now.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });
}

function drawSpark(hist) {
  const svg = $("#spark");
  const W = 360, H = 90, pad = 6;
  if (!hist.length) { svg.innerHTML = ""; return; }
  const downs = hist.map((h) => h.download || 0);
  const ups = hist.map((h) => h.upload || 0);
  const max = Math.max(...downs, ...ups, 1);
  const toPts = (arr) => arr.map((v, i) => {
    const x = pad + (i / (arr.length - 1 || 1)) * (W - 2 * pad);
    const y = H - pad - (v / max) * (H - 2 * pad);
    return x.toFixed(1) + "," + y.toFixed(1);
  }).join(" ");
  svg.innerHTML =
    '<polyline fill="none" stroke="#34d3ff" stroke-width="2" points="' + toPts(downs) + '"/>' +
    '<polyline fill="none" stroke="#b388ff" stroke-width="2" points="' + toPts(ups) + '"/>';
}

async function refreshSpeedtest() {
  try {
    const latest = await getJSON("/api/speedtest/latest");
    $("#dl").textContent = fmt(latest.download, 0);
    $("#ul").textContent = fmt(latest.upload, 0);
    $("#ping").textContent = fmt(latest.ping, 0);
    $("#st-meta").textContent = latest.isp ? (latest.isp + (latest.server ? " - " + latest.server : "")) : "";
    if (latest.ts) {
      const t = new Date(latest.ts);
      $("#st-updated").textContent = "updated " + t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    drawSpark(await getJSON("/api/speedtest/history?limit=96"));
  } catch (e) { /* keep last-good values on transient errors */ }
}

async function refreshPihole() {
  try {
    const s = await getJSON("/api/pihole/summary");
    $("#pct").textContent = fmt(s.percent_blocked, 1);
    $("#blocked").textContent = fmt(s.blocked_today, 0);
    $("#total").textContent = fmt(s.queries_today, 0);
    $("#domains").textContent = fmt(s.domains_blocked, 0);
    $("#ph-badge").style.display = s.mock ? "inline-block" : "none";
    $("#ph-status").classList.toggle("ok", s.status === "active");
  } catch (e) { /* keep last-good values */ }
}

function fmtUptime(sec) {
  if (sec === null || sec === undefined) return "--";
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
  if (d > 0) return d + "d " + h + "h";
  if (h > 0) return h + "h " + m + "m";
  return m + "m";
}

async function refreshSystem() {
  try {
    const s = await getJSON("/api/system");
    $("#sys-temp").textContent = fmt(s.cpu_temp_c, 1);
    $("#sys-cpu").textContent = fmt(s.cpu_load_pct, 0);
    $("#sys-mem").textContent = fmt(s.mem_used_pct, 0);
    $("#sys-up").textContent = fmtUptime(s.uptime_sec);
    $("#sys-badge").style.display = s.mock ? "inline-block" : "none";
  } catch (e) { /* keep last-good values */ }
}

tickClock();
setInterval(tickClock, 1000);
refreshSpeedtest();
setInterval(refreshSpeedtest, 60000);
refreshPihole();
setInterval(refreshPihole, 15000);
refreshSystem();
setInterval(refreshSystem, 15000);
