/* ============================================================
   SevenStar Limo — Finance Dashboard
   static/finances.js
   ============================================================ */

(function () {
  "use strict";

  /* ── Helpers ── */
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
  const fmt = (n) =>
    "$" +
    Number(n || 0).toLocaleString("en-AU", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  const serviceLabels = {
    ptp: "Point to Point",
    oh: "1 Hour Hire",
    th: "2 Hour Hire",
    fair: "From Airport",
    tair: "To Airport",
  };

  /* ── Date utilities ── */
  function todayStr() {
    return new Date().toISOString().slice(0, 10);
  }

  function monthBounds(offset = 0) {
    const now = new Date();
    const y = now.getFullYear();
    const m = now.getMonth() + offset;
    const first = new Date(y, m, 1);
    const last = new Date(y, m + 1, 0);
    return {
      from: first.toISOString().slice(0, 10),
      to: last.toISOString().slice(0, 10),
    };
  }

  /* ── State ── */
  let currentTab = "this_month";
  let customFrom = "";
  let customTo = "";

  /* ── DOM refs ── */
  const tabs = $$(".fin__tab");
  const customPanel = $(".fin__custom-range");
  const inputFrom = $("#fin-from");
  const inputTo = $("#fin-to");
  const applyBtn = $("#fin-apply");
  const periodLabel = $(".fin__period-label");
  const tableBody = $(".fin__tbody");
  const totalEarnings = $("#fin-total-earnings");
  const totalCost = $("#fin-total-cost");
  const totalProfit = $("#fin-total-profit");
  const cardEarnings = $("#fin-card-earnings");
  const cardCost = $("#fin-card-cost");
  const cardProfit = $("#fin-card-profit");
  const cardCount = $("#fin-card-count");
  const tsEl = $(".fin__timestamp");

  /* ── Tab switching ── */
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      currentTab = tab.dataset.tab;

      if (currentTab === "custom") {
        customPanel.classList.add("visible");
        // Pre-fill inputs
        if (!inputFrom.value) inputFrom.value = monthBounds(0).from;
        if (!inputTo.value) inputTo.value = todayStr();
      } else {
        customPanel.classList.remove("visible");
        loadOrders();
      }
    });
  });

  applyBtn.addEventListener("click", () => {
    customFrom = inputFrom.value;
    customTo = inputTo.value;
    if (!customFrom || !customTo) return;
    loadOrders();
  });

  /* ── Timestamp ── */
  function updateTimestamp() {
    const now = new Date();
    tsEl.textContent =
      "Updated " +
      now.toLocaleDateString("en-AU", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
  }

  /* ── Build query params ── */
  function getParams() {
    const p = new URLSearchParams();
    p.set("tab", currentTab);
    if (currentTab === "custom") {
      p.set("from", customFrom);
      p.set("to", customTo);
    }
    return p.toString();
  }

  /* ── Period label text ── */
  function getPeriodLabel() {
    switch (currentTab) {
      case "this_month": {
        const now = new Date();
        return now.toLocaleDateString("en-AU", { month: "long", year: "numeric" });
      }
      case "prev_month": {
        const d = new Date();
        d.setMonth(d.getMonth() - 1);
        return d.toLocaleDateString("en-AU", { month: "long", year: "numeric" });
      }
      case "lifetime":
        return "All Time";
      case "custom":
        return customFrom && customTo
          ? `${customFrom}  →  ${customTo}`
          : "Custom Range";
      default:
        return "";
    }
  }

  /* ── Render table ── */
  function renderTable(orders) {
    periodLabel.textContent = getPeriodLabel();

    if (!orders.length) {
      tableBody.innerHTML = `
        <tr><td colspan="6">
          <div class="fin__empty">
            <div class="fin__empty-icon">◈</div>
            <div class="fin__empty-text">No orders in this period</div>
          </div>
        </td></tr>`;
      updateSummary([]);
      return;
    }

    let totalE = 0,
      totalC = 0;

    const rows = orders
      .map((o, i) => {
        const price = parseFloat(o.total_price || 0);
        const cost = parseFloat(o.driver_fee || 0);
        const profit = price - cost;
        totalE += price;
        totalC += cost;

        const profitClass = profit >= 0 ? "fin__profit" : "fin__loss";
        const svcLabel = serviceLabels[o.service_type] || o.service_type;

        return `
        <tr>
          <td class="muted">${i + 1}</td>
          <td>
            <div style="font-weight:500">${escHtml(o.passenger_name)}</div>
            <div style="font-size:11px;color:var(--text-dim);margin-top:2px">${escHtml(o.passenger_email || "")}</div>
          </td>
          <td><span class="fin__badge">${escHtml(svcLabel)}</span></td>
          <td class="muted">${o.pickup_date || "—"}</td>
          <td class="right fin__earnings">${fmt(price)}</td>
          <td class="right fin__cost">${fmt(cost)}</td>
          <td class="right ${profitClass}">${profit >= 0 ? "" : "−"}${fmt(Math.abs(profit))}</td>
        </tr>`;
      })
      .join("");

    const totalProfit2 = totalE - totalC;
    const totalProfitClass = totalProfit2 >= 0 ? "fin__profit" : "fin__loss";

    tableBody.innerHTML =
      rows +
      `
      <tr class="fin__totals-row">
        <td colspan="4" class="fin__totals-label">Totals — ${orders.length} order${orders.length !== 1 ? "s" : ""}</td>
        <td class="right fin__earnings">${fmt(totalE)}</td>
        <td class="right fin__cost">${fmt(totalC)}</td>
        <td class="right ${totalProfitClass}">${totalProfit2 >= 0 ? "" : "−"}${fmt(Math.abs(totalProfit2))}</td>
      </tr>`;

    updateSummary(orders, totalE, totalC);
  }

  /* ── Update summary cards ── */
  function updateSummary(orders, totalE = 0, totalC = 0) {
    const profit = totalE - totalC;
    cardEarnings.textContent = fmt(totalE);
    cardCost.textContent = fmt(totalC);
    cardProfit.textContent = (profit < 0 ? "−" : "") + fmt(Math.abs(profit));
    cardCount.textContent = `${orders.length} booking${orders.length !== 1 ? "s" : ""}`;

    // Update DOM totals row refs too
    if (totalEarnings) totalEarnings.textContent = fmt(totalE);
    if (totalCost) totalCost.textContent = fmt(totalC);
    if (totalProfit) totalProfit.textContent = fmt(profit);
  }

  /* ── Fetch from Django endpoint ── */
  function loadOrders() {
    tableBody.innerHTML = `
      <tr><td colspan="6">
        <div class="fin__loading">
          <div class="fin__spinner"></div><br>Loading records…
        </div>
      </td></tr>`;

    fetch(`/admin/finances/data/?${getParams()}`, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        renderTable(data.orders || []);
        updateTimestamp();
      })
      .catch((err) => {
        tableBody.innerHTML = `
          <tr><td colspan="6">
            <div class="fin__empty">
              <div class="fin__empty-icon">✕</div>
              <div class="fin__empty-text">Failed to load data — ${escHtml(err.message)}</div>
            </div>
          </td></tr>`;
      });
  }

  /* ── XSS helper ── */
  function escHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* ── Boot ── */
  updateTimestamp();
  loadOrders();
})();
