// EX Deoxys Report Dashboard

(function () {
  "use strict";

  // --- State ---
  let cards = [];
  let sortCol = "number";
  let sortDir = "asc";

  // --- DOM refs ---
  const $ = (sel) => document.querySelector(sel);
  const loading = $("#loading");
  const emptyState = $("#emptyState");
  const tableSection = $("#tableSection");
  const tableHead = $("#tableHead");
  const tableBody = $("#tableBody");
  const searchInput = $("#searchInput");
  const rarityFilter = $("#rarityFilter");
  const variantFilter = $("#variantFilter");
  const viewMode = $("#viewMode");
  const refreshBtn = $("#refreshBtn");
  const logPanel = $("#logPanel");
  const logContent = $("#logContent");
  const closeLog = $("#closeLog");
  const statTotal = $("#statTotal");
  const statVariants = $("#statVariants");
  const statPriced = $("#statPriced");
  const statPop = $("#statPop");

  // --- Grade columns ---
  const PRICE_GRADES = [5, 6, 7, 8, 9, 10];
  const POP_GRADES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

  // --- Init ---
  fetchData();
  searchInput.addEventListener("input", renderTable);
  rarityFilter.addEventListener("change", renderTable);
  variantFilter.addEventListener("change", renderTable);
  viewMode.addEventListener("change", renderTable);
  refreshBtn.addEventListener("click", refreshData);
  closeLog.addEventListener("click", () => (logPanel.style.display = "none"));

  // --- Fetch data ---
  function fetchData() {
    loading.style.display = "";
    emptyState.style.display = "none";
    tableSection.style.display = "none";

    fetch("/api/data")
      .then((r) => r.json())
      .then((data) => {
        loading.style.display = "none";
        if (data.status === "ok" && data.cards && data.cards.length) {
          cards = normalizeCards(data.cards);
          updateStats();
          renderTable();
          tableSection.style.display = "";
        } else {
          emptyState.style.display = "";
        }
      })
      .catch(() => {
        loading.style.display = "none";
        emptyState.style.display = "";
      });
  }

  // --- Refresh data from APIs ---
  function refreshData() {
    refreshBtn.disabled = true;
    refreshBtn.classList.add("refreshing");
    refreshBtn.innerHTML =
      '<span class="btn-icon">&#8635;</span> Fetching...';

    fetch("/api/refresh")
      .then((r) => r.json())
      .then((data) => {
        refreshBtn.disabled = false;
        refreshBtn.classList.remove("refreshing");
        refreshBtn.innerHTML =
          '<span class="btn-icon">&#8635;</span> Refresh Data';

        if (data.log) {
          logContent.textContent = data.log;
          logPanel.style.display = "";
        }

        if (data.status === "ok" && data.cards && data.cards.length) {
          cards = normalizeCards(data.cards);
          updateStats();
          renderTable();
          emptyState.style.display = "none";
          tableSection.style.display = "";
        } else if (data.message) {
          logContent.textContent = data.message + "\n\n" + (data.log || "");
          logPanel.style.display = "";
        }
      })
      .catch((err) => {
        refreshBtn.disabled = false;
        refreshBtn.classList.remove("refreshing");
        refreshBtn.innerHTML =
          '<span class="btn-icon">&#8635;</span> Refresh Data';
        logContent.textContent = "Network error: " + err.message;
        logPanel.style.display = "";
      });
  }

  // --- Normalize card data ---
  function normalizeCards(raw) {
    return raw.map((c) => {
      const prices = {};
      const pop = {};

      // Parse prices from psa_prices
      if (c.psa_prices) {
        Object.entries(c.psa_prices).forEach(([k, v]) => {
          const m = k.match(/(\d+)/);
          if (m) prices[parseInt(m[1])] = typeof v === "number" ? v : null;
        });
      }

      // Parse pop from psa_pop
      if (c.psa_pop) {
        Object.entries(c.psa_pop).forEach(([k, v]) => {
          const m = k.match(/(\d+)/);
          if (m) pop[parseInt(m[1])] = typeof v === "number" ? v : 0;
        });
      }

      return {
        number: c.number || 0,
        name: c.name || "Unknown",
        rarity: c.rarity || "",
        variant: c.variant || "Regular",
        prices,
        pop,
      };
    });
  }

  // --- Update stats ---
  function updateStats() {
    const uniqueNums = new Set(cards.map((c) => c.number));
    statTotal.textContent = uniqueNums.size;
    statVariants.textContent = cards.length;
    statPriced.textContent = cards.filter(
      (c) => Object.keys(c.prices).length > 0
    ).length;
    statPop.textContent = cards.filter(
      (c) => Object.keys(c.pop).length > 0
    ).length;
  }

  // --- Filter ---
  function getFiltered() {
    const q = searchInput.value.toLowerCase().trim();
    const rar = rarityFilter.value;
    const vari = variantFilter.value;

    return cards.filter((c) => {
      if (q && !c.name.toLowerCase().includes(q) && !String(c.number).includes(q))
        return false;
      if (rar && c.rarity !== rar) return false;
      if (vari && c.variant !== vari) return false;
      return true;
    });
  }

  // --- Sort ---
  function sortCards(list) {
    const dir = sortDir === "asc" ? 1 : -1;

    return list.slice().sort((a, b) => {
      let av, bv;

      if (sortCol === "number") {
        av = a.number;
        bv = b.number;
      } else if (sortCol === "name") {
        av = a.name.toLowerCase();
        bv = b.name.toLowerCase();
      } else if (sortCol === "rarity") {
        av = a.rarity;
        bv = b.rarity;
      } else if (sortCol === "variant") {
        av = a.variant;
        bv = b.variant;
      } else if (sortCol.startsWith("price_")) {
        const g = parseInt(sortCol.split("_")[1]);
        av = a.prices[g] ?? -1;
        bv = b.prices[g] ?? -1;
      } else if (sortCol.startsWith("pop_")) {
        const g = parseInt(sortCol.split("_")[1]);
        av = a.pop[g] ?? -1;
        bv = b.pop[g] ?? -1;
      } else {
        return 0;
      }

      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;

      // Secondary sort by number, then variant
      if (a.number !== b.number) return a.number - b.number;
      return a.variant < b.variant ? -1 : 1;
    });
  }

  function handleSort(col) {
    if (sortCol === col) {
      sortDir = sortDir === "asc" ? "desc" : "asc";
    } else {
      sortCol = col;
      sortDir = "asc";
    }
    renderTable();
  }

  // --- Render ---
  function renderTable() {
    const mode = viewMode.value;
    const grades = mode === "pricing" ? PRICE_GRADES : POP_GRADES;
    const filtered = sortCards(getFiltered());

    // Build header
    const cols = [
      { key: "number", label: "#" },
      { key: "name", label: "Card Name" },
      { key: "rarity", label: "Rarity" },
      { key: "variant", label: "Variant" },
    ];

    grades.forEach((g) => {
      const prefix = mode === "pricing" ? "price_" : "pop_";
      cols.push({
        key: prefix + g,
        label: "PSA " + g,
        isGrade: true,
      });
    });

    if (mode === "pop") {
      cols.push({ key: "pop_total", label: "Total", isGrade: true });
    }

    let headHtml = "<tr>";
    cols.forEach((col) => {
      const cls = [];
      if (col.isGrade) cls.push("grade-col");
      if (sortCol === col.key)
        cls.push(sortDir === "asc" ? "sort-asc" : "sort-desc");
      headHtml += `<th class="${cls.join(" ")}" data-col="${col.key}">${col.label}</th>`;
    });
    headHtml += "</tr>";
    tableHead.innerHTML = headHtml;

    // Bind sort handlers
    tableHead.querySelectorAll("th").forEach((th) => {
      th.addEventListener("click", () => handleSort(th.dataset.col));
    });

    // Build rows
    let bodyHtml = "";
    filtered.forEach((card) => {
      bodyHtml += "<tr>";

      // Number
      bodyHtml += `<td class="col-num">${card.number}</td>`;

      // Name
      bodyHtml += `<td><strong>${esc(card.name)}</strong></td>`;

      // Rarity
      const rarCls = "rarity-" + card.rarity.replace(/\s+/g, "-");
      bodyHtml += `<td><span class="rarity-badge ${rarCls}">${esc(card.rarity)}</span></td>`;

      // Variant
      const varCls = "variant-" + card.variant.replace(/\s+/g, "-");
      bodyHtml += `<td><span class="variant-badge ${varCls}">${esc(card.variant)}</span></td>`;

      // Grade columns
      if (mode === "pricing") {
        grades.forEach((g) => {
          const val = card.prices[g];
          if (val != null && typeof val === "number") {
            const cls = val >= 500 ? "high-value" : "has-value";
            bodyHtml += `<td class="grade-cell ${cls}">$${fmtNum(val)}</td>`;
          } else {
            bodyHtml += `<td class="grade-cell no-value">--</td>`;
          }
        });
      } else {
        let total = 0;
        grades.forEach((g) => {
          const val = card.pop[g];
          if (val != null && val > 0) {
            total += val;
            const cls = val >= 1000 ? "high-pop" : "has-pop";
            bodyHtml += `<td class="pop-cell ${cls}">${fmtInt(val)}</td>`;
          } else {
            bodyHtml += `<td class="pop-cell">--</td>`;
          }
        });
        const totCls = total >= 5000 ? "high-pop" : total > 0 ? "has-pop" : "";
        bodyHtml += `<td class="pop-cell ${totCls}">${total > 0 ? fmtInt(total) : "--"}</td>`;
      }

      bodyHtml += "</tr>";
    });

    if (filtered.length === 0) {
      const colspan = cols.length;
      bodyHtml = `<tr><td colspan="${colspan}" style="text-align:center;padding:40px;color:var(--text-muted);">No cards match your filters.</td></tr>`;
    }

    tableBody.innerHTML = bodyHtml;
  }

  // --- Helpers ---
  function esc(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function fmtNum(n) {
    if (n >= 1000) return n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    if (n >= 100) return n.toFixed(0);
    return n.toFixed(2);
  }

  function fmtInt(n) {
    return n.toLocaleString("en-US");
  }
})();
