const SECTION_CONFIG = {
  inbox: {
    title: "A traiter",
    subtitle: "Signaux non lus a qualifier",
    params: { unread: "true" },
  },
  priority: {
    title: "Prioritaires",
    subtitle: "Score eleve, exploit probable ou impact fort",
    params: { min_score: "12" },
  },
  favorites: {
    title: "Favoris",
    subtitle: "Signaux mis de cote pour suivi",
    params: { is_favorite: "true" },
  },
  reviewed: {
    title: "Deja lus",
    subtitle: "Signaux deja qualifies ou consultes",
    params: { status: "reviewed" },
  },
  github: {
    title: "GitHub",
    subtitle: "Repos publics detectes via l'API GitHub",
    params: { source_type: "github" },
  },
  social: {
    title: "Reseaux",
    subtitle: "Signaux issus des collecteurs sociaux actives",
    params: { channel: "social" },
  },
  trash: {
    title: "Corbeille",
    subtitle: "Signaux supprimes en attente de purge definitive",
    endpoint: "/trash",
    isTrash: true,
    params: {},
  },
  all: {
    title: "Tous les signaux",
    subtitle: "Vue complete de la base locale",
    params: {},
  },
};

const state = {
  signals: [],
  selectedId: null,
  loading: false,
  currentSection: "all",
};

const els = {
  sectionTitle: document.querySelector("#section-title"),
  sectionSubtitle: document.querySelector("#section-subtitle"),
  refreshButton: document.querySelector("#refresh-button"),
  collectButton: document.querySelector("#collect-button"),
  searchInput: document.querySelector("#search-input"),
  sourceFilter: document.querySelector("#source-filter"),
  severityFilter: document.querySelector("#severity-filter"),
  scoreFilter: document.querySelector("#score-filter"),
  sourceList: document.querySelector("#source-list"),
  resultCount: document.querySelector("#result-count"),
  signalsContainer: document.querySelector("#signals-container"),
  metricTotal: document.querySelector("#metric-total"),
  metricAlerts: document.querySelector("#metric-alerts"),
  metricCritical: document.querySelector("#metric-critical"),
  keywordCloud: document.querySelector("#keyword-cloud"),
  productCloud: document.querySelector("#product-cloud"),
  detailEmpty: document.querySelector("#detail-empty"),
  detailContent: document.querySelector("#detail-content"),
  detailSeverity: document.querySelector("#detail-severity"),
  detailScore: document.querySelector("#detail-score"),
  detailTitle: document.querySelector("#detail-title"),
  detailMeta: document.querySelector("#detail-meta"),
  detailBody: document.querySelector("#detail-body"),
  detailCves: document.querySelector("#detail-cves"),
  detailKeywords: document.querySelector("#detail-keywords"),
  detailProducts: document.querySelector("#detail-products"),
  detailConfidence: document.querySelector("#detail-confidence"),
  detailLink: document.querySelector("#detail-link"),
  markReadButton: document.querySelector("#mark-read-button"),
  favoriteButton: document.querySelector("#favorite-button"),
  deleteButton: document.querySelector("#delete-button"),
  restoreButton: document.querySelector("#restore-button"),
  purgeButton: document.querySelector("#purge-button"),
  purgeAllButton: document.querySelector("#purge-all-button"),
  toast: document.querySelector("#toast"),
};

function init() {
  console.log("Initializing dashboard...");
  console.log("DOM ready, elements found:", {
    deleteButton: Boolean(els.deleteButton),
    restoreButton: Boolean(els.restoreButton),
    purgeButton: Boolean(els.purgeButton),
    purgeAllButton: Boolean(els.purgeAllButton),
  });
  initDarkMode();
  bindEvents();
  initGitHubModal();
  switchSection(state.currentSection, { resetFilters: false });
  console.log("Dashboard initialization complete");
}

function initDarkMode() {
  const savedTheme = localStorage.getItem("theme") || "light";
  applyTheme(savedTheme === "dark" ? "dark" : "light");
}

function applyTheme(theme) {
  const isDark = theme === "dark";
  document.documentElement.classList.toggle("dark-mode", isDark);
  document.body.classList.toggle("dark-mode", isDark);
  document.documentElement.dataset.theme = theme;

  const themeToggle = document.querySelector("#theme-toggle");
  if (!themeToggle) return;

  themeToggle.setAttribute("aria-pressed", String(isDark));
  themeToggle.setAttribute(
    "title",
    isDark ? "Basculer le theme clair" : "Basculer le theme sombre",
  );
}

function bindEvents() {
  document.querySelectorAll(".nav-item:not(#add-github-button)").forEach((item) => {
    item.addEventListener("click", () => {
      switchSection(item.dataset.section || "inbox");
    });
  });

  document.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.addEventListener("click", () => toggleSeverityShortcut(chip));
  });

  document.querySelector("#theme-toggle")?.addEventListener("click", () => {
    const nextTheme = document.documentElement.classList.contains("dark-mode")
      ? "light"
      : "dark";
    applyTheme(nextTheme);
    localStorage.setItem("theme", nextTheme);
  });

  els.refreshButton?.addEventListener("click", loadDashboard);
  els.collectButton?.addEventListener("click", runCollection);
  els.markReadButton?.addEventListener("click", markSelectedSignalRead);
  els.favoriteButton?.addEventListener("click", toggleSelectedSignalFavorite);
  
  if (els.deleteButton) {
    console.log("Binding delete button");
    els.deleteButton.addEventListener("click", deleteSelectedSignal);
  } else {
    console.warn("Delete button not found");
  }
  
  if (els.restoreButton) {
    console.log("Binding restore button");
    els.restoreButton.addEventListener("click", restoreSelectedSignal);
  } else {
    console.warn("Restore button not found");
  }
  
  if (els.purgeButton) {
    console.log("Binding purge button");
    els.purgeButton.addEventListener("click", purgeSelectedSignal);
  } else {
    console.warn("Purge button not found");
  }
  
  if (els.purgeAllButton) {
    console.log("Binding purge all button");
    els.purgeAllButton.addEventListener("click", purgeAllTrash);
  } else {
    console.warn("Purge all button not found");
  }
  
  els.detailLink?.addEventListener("click", markSelectedSignalReadFromSource);
  els.searchInput?.addEventListener("input", debounce(loadDashboard));

  [els.sourceFilter, els.severityFilter, els.scoreFilter].forEach((input) => {
    input?.addEventListener("change", () => {
      syncSeverityChips();
      loadDashboard();
    });
  });
}

function switchSection(section, options = { resetFilters: true }) {
  state.currentSection = SECTION_CONFIG[section] ? section : "inbox";
  state.selectedId = null;

  if (options.resetFilters) resetManualFilters();
  updateSectionHeader();
  updateNavigationState();
  syncForcedFilters();
  loadDashboard();
}

function updateSectionHeader() {
  const config = SECTION_CONFIG[state.currentSection];
  els.sectionTitle.textContent = config.title;
  els.sectionSubtitle.textContent = config.subtitle;
}

function updateNavigationState() {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.section === state.currentSection);
  });
  syncSeverityChips();
}

function syncForcedFilters() {
  const params = SECTION_CONFIG[state.currentSection].params;
  const forcedSource = params.source_type;

  els.sourceFilter.disabled = Boolean(forcedSource);
  els.sourceFilter.value = forcedSource || "";
}

function resetManualFilters() {
  els.searchInput.value = "";
  els.sourceFilter.value = "";
  els.severityFilter.value = "";
  els.scoreFilter.value = "";
}

function toggleSeverityShortcut(chip) {
  const severity = chip.dataset.severity || "";
  els.severityFilter.value = els.severityFilter.value === severity ? "" : severity;
  syncSeverityChips();
  loadDashboard();
}

function syncSeverityChips() {
  document.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.severity === els.severityFilter.value);
  });
}

async function loadDashboard() {
  setLoading(true);
  try {
    const isTrash = SECTION_CONFIG[state.currentSection].isTrash;
    const endpoint = isTrash ? "/trash" : "/signals";
    const query = isTrash ? `?${new URLSearchParams({ limit: "100" }).toString()}` : `?${buildSignalQuery()}`;
    
    console.log("Loading dashboard:", { section: state.currentSection, isTrash, endpoint, query });
    
    const [stats, signals] = await Promise.all([
      isTrash ? Promise.resolve(null) : fetchJson("/stats"),
      fetchJson(`${endpoint}${query}`),
    ]);

    console.log("Dashboard loaded:", { statsCount: stats?.total_signals, signalsCount: signals.length });
    
    state.signals = signals;
    if (stats) {
      renderStats(stats);
      renderTrends(stats);
      renderSourceBreakdown(stats.count_by_source_type ?? {});
    }
    renderSignals(signals);
    syncSelectedSignal();
    updateTrashVisibility();
  } catch (error) {
    showToast("Erreur de chargement", true);
    console.error("Dashboard load error:", error);
  } finally {
    setLoading(false);
  }
}

function updateTrashVisibility() {
  const isTrash = state.currentSection === "trash";
  els.purgeAllButton.classList.toggle("hidden", !isTrash);
  els.sourceFilter.classList.toggle("hidden", isTrash);
  els.severityFilter.classList.toggle("hidden", isTrash);
  els.scoreFilter.classList.toggle("hidden", isTrash);
}

function buildSignalQuery() {
  const params = new URLSearchParams({ limit: "100" });
  const sectionParams = SECTION_CONFIG[state.currentSection].params;

  Object.entries(sectionParams).forEach(([key, value]) => params.set(key, value));

  if (!params.has("source_type") && els.sourceFilter.value) {
    params.set("source_type", els.sourceFilter.value);
  }
  if (els.severityFilter.value) {
    params.set("severity", els.severityFilter.value);
  }
  if (!params.has("min_score") && els.scoreFilter.value) {
    params.set("min_score", els.scoreFilter.value);
  }
  if (els.searchInput.value.trim()) {
    params.set("q", els.searchInput.value.trim());
  }

  return params.toString();
}

async function runCollection() {
  setLoading(true);
  showToast("Collecte en cours...");
  try {
    const summary = await fetchJson("/collect/run", { method: "POST" });
    showToast(`${summary.new} nouveau, ${summary.duplicates} doublon`);
    await loadDashboard();
  } catch (error) {
    showToast("Erreur de collecte", true);
    console.error(error);
  } finally {
    setLoading(false);
  }
}

async function markSelectedSignalRead() {
  const signal = getSelectedSignal();
  if (!signal) return;

  try {
    await markSignalRead(signal.id);
    showToast("Signal marque comme lu");
    await loadDashboard();
  } catch (error) {
    showToast("Impossible de marquer le signal comme lu", true);
    console.error(error);
  }
}

function markSelectedSignalReadFromSource() {
  const signal = getSelectedSignal();
  if (!signal || signal.status === "reviewed") return;

  markSignalRead(signal.id)
    .then(() => loadDashboard())
    .catch((error) => {
      console.error(error);
    });
}

async function markSignalRead(signalId) {
  return fetchJson(`/signals/${signalId}/read`, { method: "POST" });
}

async function toggleSelectedSignalFavorite() {
  const signal = getSelectedSignal();
  if (!signal) return;

  try {
    const updated = await fetchJson(`/signals/${signal.id}/favorite`, { method: "POST" });
    showToast(updated.is_favorite ? "Ajoute aux favoris" : "Retire des favoris");
    await loadDashboard();
  } catch (error) {
    showToast("Impossible de modifier le favori", true);
    console.error(error);
  }
}

function getSelectedSignal() {
  if (!state.selectedId) return null;
  return state.signals.find((signal) => signal.id === state.selectedId) ?? null;
}

function renderStats(stats) {
  els.metricTotal.textContent = stats.total_signals ?? 0;
  els.metricAlerts.textContent = stats.total_alerts ?? 0;
  els.metricCritical.textContent = stats.count_by_severity?.critical ?? 0;
}

function renderTrends(stats) {
  renderCloud(els.keywordCloud, stats.top_keywords);
  renderCloud(els.productCloud, stats.top_products);
}

function renderSourceBreakdown(counts) {
  els.sourceList.replaceChildren();
  const entries = Object.entries(counts);
  if (!entries.length) {
    els.sourceList.appendChild(emptyInline("Aucune source"));
    return;
  }

  for (const [source, count] of entries) {
    const item = document.createElement("div");
    item.className = "source-item";
    item.appendChild(textElement("span", "source-item-name", source.toUpperCase()));
    item.appendChild(textElement("span", "source-item-count", count));
    els.sourceList.appendChild(item);
  }
}

function renderCloud(container, items = []) {
  container.replaceChildren();
  if (!items.length) {
    container.appendChild(emptyInline("Aucune donnee"));
    return;
  }

  for (const [label, count] of items) {
    const tag = document.createElement("div");
    tag.className = "tag";
    tag.appendChild(document.createTextNode(label));
    tag.appendChild(textElement("small", "", count));
    container.appendChild(tag);
  }
}

function renderSignals(signals) {
  els.signalsContainer.replaceChildren();
  els.resultCount.textContent = `${signals.length} resultat${signals.length !== 1 ? "s" : ""}`;

  if (!signals.length) {
    const empty = document.createElement("div");
    empty.className = "timeline-empty";
    empty.textContent = "Aucun signal dans cette rubrique";
    els.signalsContainer.appendChild(empty);
    showEmptyDetail();
    return;
  }

  for (const signal of signals) {
    els.signalsContainer.appendChild(signalRow(signal));
  }
}

function signalRow(signal) {
  const row = document.createElement("button");
  row.type = "button";
  row.className = [
    "signal-row",
    signal.id === state.selectedId ? "active" : "",
    signal.status === "reviewed" ? "reviewed" : "",
    signal.is_favorite ? "favorite" : "",
  ].filter(Boolean).join(" ");
  row.addEventListener("click", () => selectSignal(signal.id));

  row.appendChild(textElement("div", "signal-title", signal.title || "Sans titre"));
  row.appendChild(
    textElement("div", "signal-preview", compactText(signal.content || signal.url || "", 120)),
  );
  row.appendChild(signalMeta(signal));
  row.appendChild(signalFooter(signal));
  return row;
}

function signalMeta(signal) {
  const meta = document.createElement("div");
  meta.className = "signal-meta";
  const sourceType = signal.source_type === "x" ? "twitter" : signal.source_type;

  meta.appendChild(makeBadge(sourceType.toUpperCase(), `source-${sourceType}`));
  meta.appendChild(makeBadge(signal.severity, `severity-pill ${signal.severity}`));
  if (signal.is_favorite) meta.appendChild(makeBadge("Favori", "favorite-badge"));
  if (signal.status === "reviewed") meta.appendChild(makeBadge("Lu", "reviewed-badge"));
  for (const cve of signal.cves.slice(0, 1)) meta.appendChild(makeBadge(cve));

  return meta;
}

function signalFooter(signal) {
  const footer = document.createElement("div");
  footer.className = "signal-footer";
  footer.appendChild(
    textElement("span", "signal-time", formatDate(signal.published_at || signal.collected_at)),
  );
  footer.appendChild(textElement("span", "score-pill", signal.score));
  return footer;
}

function selectSignal(id, rerender = true) {
  state.selectedId = id;
  const signal = getSelectedSignal();
  if (!signal) {
    showEmptyDetail();
    return;
  }

  renderDetail(signal);
  if (rerender) renderSignals(state.signals);
}

function syncSelectedSignal() {
  if (state.selectedId && state.signals.some((signal) => signal.id === state.selectedId)) {
    selectSignal(state.selectedId, false);
    return;
  }
  if (state.signals[0]) {
    selectSignal(state.signals[0].id, false);
    return;
  }
  showEmptyDetail();
}

function renderDetail(signal) {
  els.detailEmpty.classList.add("hidden");
  els.detailContent.classList.remove("hidden");
  els.detailSeverity.className = `badge-pill severity-pill ${signal.severity}`;
  els.detailSeverity.textContent = signal.severity;
  els.detailScore.textContent = signal.score;
  els.detailTitle.textContent = signal.title || "Sans titre";
  els.detailMeta.textContent = [
    signal.source_type?.toUpperCase(),
    signal.source,
    formatDate(signal.published_at || signal.collected_at),
  ].filter(Boolean).join(" / ");
  els.detailBody.textContent = signal.content || "Aucun contenu.";
  els.detailCves.textContent = joinOrDash(signal.cves);
  els.detailKeywords.textContent = joinOrDash(signal.keywords);
  els.detailProducts.textContent = joinOrDash(signal.products);
  els.detailConfidence.textContent = signal.confidence || "low";
  updateDetailActionButtons(signal);

  if (signal.url) {
    els.detailLink.href = signal.url;
    els.detailLink.classList.remove("hidden");
  } else {
    els.detailLink.classList.add("hidden");
  }
}

function showEmptyDetail() {
  state.selectedId = null;
  els.detailEmpty.classList.remove("hidden");
  els.detailContent.classList.add("hidden");
}

function updateDetailActionButtons(signal) {
  const isReviewed = signal.status === "reviewed";
  const isFavorite = Boolean(signal.is_favorite);
  const isDeleted = Boolean(signal.deleted_at);

  if (els.markReadButton) {
    els.markReadButton.classList.toggle("active", isReviewed);
    els.markReadButton.disabled = isReviewed || isDeleted;
    els.markReadButton.title = isReviewed ? "Deja lu" : "Marquer comme lu";
    els.markReadButton.setAttribute("aria-pressed", String(isReviewed));
  }

  if (els.favoriteButton) {
    els.favoriteButton.classList.toggle("active", isFavorite);
    els.favoriteButton.disabled = isDeleted;
    els.favoriteButton.title = isFavorite ? "Retirer des favoris" : "Ajouter aux favoris";
    els.favoriteButton.setAttribute("aria-pressed", String(isFavorite));
  }

  if (els.deleteButton) {
    els.deleteButton.classList.toggle("hidden", isDeleted);
  }
  if (els.restoreButton) {
    els.restoreButton.classList.toggle("hidden", !isDeleted);
  }
  if (els.purgeButton) {
    els.purgeButton.classList.toggle("hidden", !isDeleted);
  }
}

async function deleteSelectedSignal() {
  const signal = getSelectedSignal();
  if (!signal) {
    console.warn("No signal selected");
    return;
  }

  console.log("Deleting signal:", signal.id, signal.title);
  try {
    await fetchJson(`/signals/${signal.id}/delete`, { method: "POST" });
    showToast("Signal envoye a la corbeille");
    await loadDashboard();
  } catch (error) {
    showToast("Impossible de supprimer le signal", true);
    console.error("Delete error:", error);
  }
}

async function restoreSelectedSignal() {
  const signal = getSelectedSignal();
  if (!signal) {
    console.warn("No signal selected");
    return;
  }

  console.log("Restoring signal:", signal.id, signal.title);
  try {
    await fetchJson(`/signals/${signal.id}/restore`, { method: "POST" });
    showToast("Signal restaure");
    await loadDashboard();
  } catch (error) {
    showToast("Impossible de restaurer le signal", true);
    console.error("Restore error:", error);
  }
}

async function purgeSelectedSignal() {
  const signal = getSelectedSignal();
  if (!signal) {
    console.warn("No signal selected");
    return;
  }

  if (!confirm(`Confirmer la suppression definitive de: "${signal.title}"?`)) return;

  console.log("Purging signal:", signal.id, signal.title);
  try {
    await fetchJson(`/trash/${signal.id}/purge`, { method: "POST" });
    showToast("Signal supprime definitivement");
    await loadDashboard();
  } catch (error) {
    showToast("Impossible de purger le signal", true);
    console.error("Purge error:", error);
  }
}

async function purgeAllTrash() {
  if (!confirm("Confirmer la suppression definitive de TOUS les signaux de la corbeille?")) return;

  console.log("Purging all trash");
  setLoading(true);
  try {
    const result = await fetchJson("/trash/purge-all", { method: "POST" });
    showToast(`${result.count} signaux supprimes definitivement`);
    await loadDashboard();
  } catch (error) {
    showToast("Impossible de vider la corbeille", true);
    console.error("Purge all error:", error);
  } finally {
    setLoading(false);
  }
}

async function fetchJson(url, options = {}) {
  const { headers = {}, ...fetchOptions } = options;
  const response = await fetch(url, {
    ...fetchOptions,
    headers: { Accept: "application/json", ...headers },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `HTTP ${response.status}`);
  }
  return response.json();
}

function makeBadge(text, extraClass = "") {
  const element = document.createElement("span");
  element.className = ["badge", extraClass].filter(Boolean).join(" ");
  element.textContent = text || "-";
  return element;
}

function textElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = text ?? "";
  return element;
}

function emptyInline(text) {
  return textElement("span", "empty-inline", text);
}

function joinOrDash(items) {
  return items?.length ? items.join(", ") : "-";
}

function formatDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function compactText(text, maxLength) {
  const clean = String(text).replace(/\s+/g, " ").trim();
  if (clean.length <= maxLength) return clean;
  return `${clean.slice(0, maxLength - 3)}...`;
}

function debounce(fn, delay = 250) {
  let timeoutId;
  return (...args) => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => fn(...args), delay);
  };
}

function setLoading(isLoading) {
  state.loading = isLoading;
  els.refreshButton.disabled = isLoading;
  els.collectButton.disabled = isLoading;
}

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.classList.toggle("error", isError);
  els.toast.classList.remove("hidden");
  window.clearTimeout(showToast.timeoutId);
  showToast.timeoutId = window.setTimeout(() => {
    els.toast.classList.add("hidden");
  }, 3000);
}

// GitHub Repo Modal
function initGitHubModal() {
  const modal = document.getElementById("add-github-modal");
  const openButton = document.getElementById("add-github-button");
  
  if (!modal || !openButton) {
    console.error("Modal elements not found");
    return;
  }

  const closeButton = modal.querySelector(".modal-close");
  const cancelButton = modal.querySelector(".modal-cancel");
  const submitButton = modal.querySelector(".modal-submit");
  const urlInput = modal.querySelector("#github-url-input");
  const backdrop = modal.querySelector(".modal-backdrop");

  if (!closeButton || !cancelButton || !submitButton || !urlInput || !backdrop) {
    console.error("Modal child elements not found");
    return;
  }

  const openModal = () => {
    modal.classList.remove("hidden");
    urlInput.focus();
  };

  const closeModal = () => {
    modal.classList.add("hidden");
    urlInput.value = "";
  };

  const submitRepo = async () => {
    const url = urlInput.value.trim();
    if (!url) {
      showToast("Entrez une URL valide", true);
      return;
    }

    submitButton.disabled = true;
    try {
      const result = await fetchJson("/github/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: url }),
      });
      showToast(`Repo ajoute: ${result.title}`);
      closeModal();
      await loadDashboard();
    } catch (error) {
      showToast(`Erreur: ${error.message}`, true);
    } finally {
      submitButton.disabled = false;
    }
  };

  openButton.addEventListener("click", openModal);
  closeButton.addEventListener("click", closeModal);
  cancelButton.addEventListener("click", closeModal);
  backdrop.addEventListener("click", closeModal);
  submitButton.addEventListener("click", submitRepo);

  urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submitRepo();
    if (e.key === "Escape") closeModal();
  });
  
  console.log("GitHub modal initialized successfully");
}

init();
