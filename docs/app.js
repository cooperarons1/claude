// EX Deoxys Report Dashboard (Static / GitHub Pages version)

(function () {
  "use strict";

  // --- State ---
  let cards = [];
  let sortCol = "number";
  let sortDir = "asc";

  // --- DOM refs ---
  const $ = (sel) => document.querySelector(sel);
  const loading = $("#loading");
  const tableSection = $("#tableSection");
  const tableHead = $("#tableHead");
  const tableBody = $("#tableBody");
  const searchInput = $("#searchInput");
  const rarityFilter = $("#rarityFilter");
  const variantFilter = $("#variantFilter");
  const statTotal = $("#statTotal");
  const statVariants = $("#statVariants");
  const statHolo = $("#statHolo");
  const statReverse = $("#statReverse");

  // --- Init ---
  fetchData();
  searchInput.addEventListener("input", renderTable);
  rarityFilter.addEventListener("change", renderTable);
  variantFilter.addEventListener("change", renderTable);

  // --- Fetch static data ---
  function fetchData() {
    loading.style.display = "";
    tableSection.style.display = "none";

    fetch("data.json")
      .then((r) => r.json())
      .then((data) => {
        loading.style.display = "none";
        cards = normalizeCards(data);
        updateStats();
        renderTable();
        tableSection.style.display = "";
      })
      .catch((err) => {
        loading.style.display = "none";
        console.error("Failed to load data.json:", err);
      });
  }

  // --- Normalize card data ---
  function normalizeCards(raw) {
    return raw.map((c) => ({
      number: c.number || 0,
      name: c.name || "Unknown",
      rarity: c.rarity || "",
      variant: c.variant || "Regular",
    }));
  }

  // --- Update stats ---
  function updateStats() {
    const uniqueNums = new Set(cards.map((c) => c.number));
    statTotal.textContent = uniqueNums.size;
    statVariants.textContent = cards.length;
    statHolo.textContent = cards.filter(
      (c) => c.variant === "Holo" && (c.rarity.includes("Holo") || c.rarity.includes("EX") || c.rarity.includes("Secret"))
    ).length;
    statReverse.textContent = cards.filter(
      (c) => c.variant === "Reverse Holo"
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
        av = rarityOrder(a.rarity);
        bv = rarityOrder(b.rarity);
      } else if (sortCol === "variant") {
        av = a.variant;
        bv = b.variant;
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

  function rarityOrder(r) {
    const order = { "Common": 0, "Uncommon": 1, "Rare": 2, "Holo Rare": 3, "Rare Holo EX": 4, "Secret Rare": 5 };
    return order[r] ?? 99;
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
    const filtered = sortCards(getFiltered());

    const cols = [
      { key: "number", label: "#" },
      { key: "name", label: "Card Name" },
      { key: "rarity", label: "Rarity" },
      { key: "variant", label: "Variant" },
    ];

    let headHtml = "<tr>";
    cols.forEach((col) => {
      const cls = [];
      if (sortCol === col.key)
        cls.push(sortDir === "asc" ? "sort-asc" : "sort-desc");
      headHtml += '<th class="' + cls.join(" ") + '" data-col="' + col.key + '">' + col.label + "</th>";
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
      bodyHtml += '<td class="col-num">' + card.number + "</td>";

      // Name
      bodyHtml += "<td><strong>" + esc(card.name) + "</strong></td>";

      // Rarity
      const rarCls = "rarity-" + card.rarity.replace(/\s+/g, "-");
      bodyHtml += '<td><span class="rarity-badge ' + rarCls + '">' + esc(card.rarity) + "</span></td>";

      // Variant
      const varCls = "variant-" + card.variant.replace(/\s+/g, "-");
      bodyHtml += '<td><span class="variant-badge ' + varCls + '">' + esc(card.variant) + "</span></td>";

      bodyHtml += "</tr>";
    });

    if (filtered.length === 0) {
      bodyHtml = '<tr><td colspan="4" style="text-align:center;padding:40px;color:var(--text-muted);">No cards match your filters.</td></tr>';
    }

    tableBody.innerHTML = bodyHtml;
  }

  // --- Helpers ---
  function esc(s) {
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }
})();
