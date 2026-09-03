(function () {
  "use strict";

  const Core = window.OfferCore;
  const STORAGE_KEY = "offerTemplates.config.v1";
  const state = {
    config: null,
    bundledConfig: null,
    selectedTitle: "",
    activeVariables: new Set(),
    values: {
      price: "",
      broadbandPrice: "",
      currency: "",
      dateOverride: "",
      selections: {}
    },
    previewText: "",
    draft: null,
    draftIndex: 0,
    storageAvailable: true
  };

  const elements = {};

  function byId(id) {
    return document.getElementById(id);
  }

  function cacheElements() {
    [
      "app", "app-bar", "template-select", "standard-fields", "service-section", "service-toggles",
      "service-fields", "preview", "preview-placeholder", "preview-shell", "character-count",
      "status", "copy-offer", "save-indicator", "open-settings", "settings-modal",
      "close-settings", "cancel-settings", "save-settings", "settings-status", "template-list",
      "template-count", "add-template", "duplicate-template", "delete-template", "template-editor",
      "edit-title", "edit-package", "edit-message", "edit-broadband2", "edit-tv1", "edit-tv2",
      "field-settings", "currency-settings", "default-template", "default-currency", "copy-settings", "reset-settings",
      "open-instructions", "instructions-modal", "close-instructions", "done-instructions", "open-field-values", "services-help",
      "date-offset-tool", "date-offset-days", "insert-date-plus", "insert-date-minus", "date-offset-status",
      "import-file", "drop-overlay"
    ].forEach((id) => { elements[id] = byId(id); });
  }

  async function loadBundledConfig() {
    try {
      const response = await fetch("packages.json", { cache: "no-cache" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return Core.validateConfig(await response.json());
    } catch (error) {
      console.warn("Could not load packages.json; using the built-in starter template.", error);
      return Core.validateConfig(Core.fallbackConfig());
    }
  }

  function loadStoredConfig() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? Core.validateConfig(JSON.parse(saved)) : null;
    } catch (error) {
      console.warn("Saved settings could not be loaded.", error);
      return null;
    }
  }

  function persistConfig(config) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
      state.storageAvailable = true;
      elements["save-indicator"].textContent = "Saved in this browser";
      return true;
    } catch (error) {
      state.storageAvailable = false;
      elements["save-indicator"].textContent = "Browser storage unavailable";
      console.warn("Settings could not be stored in this browser.", error);
      return false;
    }
  }

  function selectedTemplate() {
    return state.config.packages.find((item) => item.title === state.selectedTitle) || state.config.packages[0];
  }

  function fieldSet(item = selectedTemplate()) {
    try {
      return Core.templateFields(item.template);
    } catch (_error) {
      return new Set();
    }
  }

  function supportedServices(fields) {
    if (fields.has("services")) return new Set(Core.VARIABLE_KEYS);
    const supported = new Set(Core.VARIABLE_KEYS.filter((key) => fields.has(key)));
    if (fields.has("broadband_price")) supported.add("broadband");
    Object.entries(Core.CAMPAIGN_FIELDS).forEach(([field, details]) => {
      if (fields.has(field)) supported.add(details.service);
    });
    return supported;
  }

  function initiallyActiveServices(fields) {
    const active = new Set(Core.VARIABLE_KEYS.filter((key) => fields.has(key)));
    if (fields.has("broadband_price")) active.add("broadband");
    Object.entries(Core.CAMPAIGN_FIELDS).forEach(([field, details]) => {
      if (fields.has(field)) active.add(details.service);
    });
    return active;
  }

  function initializeValues(config, preserve = false) {
    const previous = preserve ? state.values : null;
    state.values.currency = previous && config.currencies.includes(previous.currency)
      ? previous.currency
      : config.default_currency;
    Core.VARIABLE_KEYS.forEach((key) => {
      const variable = config.variables[key];
      const oldValue = previous && previous.selections[key];
      state.values.selections[key] = variable.options.includes(oldValue) ? oldValue : variable.default;
    });
    if (!preserve) {
      state.values.price = "";
      state.values.broadbandPrice = "";
      state.values.dateOverride = "";
    }
  }

  function applyConfig(config, options = {}) {
    const previousTitle = state.selectedTitle;
    state.config = Core.validateConfig(config);
    initializeValues(state.config, Boolean(options.preserveValues));
    const preferredTitle = options.preferredTitle;
    state.selectedTitle = state.config.packages.some((item) => item.title === preferredTitle)
      ? preferredTitle
      : state.config.packages.some((item) => item.title === previousTitle)
        ? previousTitle
        : state.config.default_package;
    renderTemplateSelect();
    changeTemplate(Boolean(options.preserveActive));
  }

  function renderTemplateSelect() {
    const select = elements["template-select"];
    select.replaceChildren();
    state.config.packages.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.title;
      option.textContent = item.title;
      select.append(option);
    });
    select.value = state.selectedTitle;
  }

  function makeField(labelText, control, options = {}) {
    const label = document.createElement("label");
    label.className = `field${options.fullWidth ? " full-width" : ""}`;
    const text = document.createElement("span");
    text.textContent = labelText;
    label.append(text, control);
    return label;
  }

  function makeInput(id, value, placeholder, inputMode) {
    const input = document.createElement("input");
    input.id = id;
    input.value = value;
    input.placeholder = placeholder || "";
    input.autocomplete = "off";
    if (inputMode) input.inputMode = inputMode;
    return input;
  }

  function makeSelect(options, value) {
    const select = document.createElement("select");
    options.forEach((item) => {
      const option = document.createElement("option");
      option.value = item;
      option.textContent = item;
      select.append(option);
    });
    select.value = value;
    return select;
  }

  function changeTemplate(keepActive) {
    state.selectedTitle = elements["template-select"].value || state.config.default_package;
    const fields = fieldSet();
    if (!keepActive) state.activeVariables = initiallyActiveServices(fields);
    else state.activeVariables = new Set([...state.activeVariables].filter((key) => supportedServices(fields).has(key)));
    renderComposer(fields);
    updatePreview();
  }

  function renderComposer(fields) {
    const standard = elements["standard-fields"];
    standard.replaceChildren();
    const usesPrice = fields.has("price");
    const usesBroadbandPrice = fields.has("broadband_price");
    const usesCurrency = usesPrice || usesBroadbandPrice;

    if (usesPrice) {
      const input = makeInput("price-input", state.values.price, "e.g. 19.90", "decimal");
      input.addEventListener("input", () => { state.values.price = input.value; updatePreview(); });
      standard.append(makeField("Price", input));
    }
    if (usesCurrency) {
      const select = makeSelect(state.config.currencies, state.values.currency);
      select.id = "currency-select";
      select.addEventListener("change", () => { state.values.currency = select.value; updatePreview(); });
      standard.append(makeField("Currency", select));
    }
    const hasDate = [...fields].some((field) => /^date(?:[+-]\d+)?$/.test(field));
    if (hasDate) {
      const input = makeInput("date-input", state.values.dateOverride, "DD/MM/YYYY", "numeric");
      input.addEventListener("input", () => { state.values.dateOverride = input.value; updatePreview(); });
      standard.append(makeField("Date override (optional)", input, { fullWidth: !usesPrice && !usesCurrency }));
    }

    renderServices(fields, usesBroadbandPrice);
  }

  function renderServices(fields, usesBroadbandPrice) {
    const supported = supportedServices(fields);
    const section = elements["service-section"];
    section.hidden = supported.size === 0;
    elements["service-toggles"].replaceChildren();
    elements["service-fields"].replaceChildren();
    if (!supported.size) return;

    Core.VARIABLE_KEYS.filter((key) => supported.has(key)).forEach((key) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "service-toggle";
      button.textContent = state.config.variables[key].label;
      button.setAttribute("aria-pressed", String(state.activeVariables.has(key)));
      button.addEventListener("click", () => {
        if (state.activeVariables.has(key)) state.activeVariables.delete(key);
        else state.activeVariables.add(key);
        renderServices(fields, usesBroadbandPrice);
        updatePreview();
      });
      elements["service-toggles"].append(button);
    });

    Core.VARIABLE_KEYS.filter((key) => state.activeVariables.has(key) && supported.has(key)).forEach((key) => {
      const variable = state.config.variables[key];
      const row = document.createElement("div");
      row.className = `service-row${key === "broadband" && usesBroadbandPrice ? " with-price" : ""}`;
      const select = makeSelect(variable.options, state.values.selections[key]);
      select.addEventListener("change", () => { state.values.selections[key] = select.value; updatePreview(); });
      row.append(makeField(variable.label, select));
      if (key === "broadband" && usesBroadbandPrice) {
        const input = makeInput("broadband-price-input", state.values.broadbandPrice, "e.g. 9.90", "decimal");
        input.addEventListener("input", () => { state.values.broadbandPrice = input.value; updatePreview(); });
        row.append(makeField("Broadband price", input));
      }
      elements["service-fields"].append(row);
    });
  }

  function renderOptions(previewMode) {
    const labels = Object.fromEntries(Core.VARIABLE_KEYS.map((key) => [key, state.config.variables[key].label]));
    return {
      price: previewMode && !state.values.price.trim() ? "[price]" : state.values.price,
      broadbandPrice: previewMode && !state.values.broadbandPrice.trim() ? "[broadband price]" : state.values.broadbandPrice,
      currency: state.values.currency,
      selections: state.values.selections,
      activeVariables: state.activeVariables,
      dateOverride: state.values.dateOverride,
      variableLabels: labels
    };
  }

  function updatePreview() {
    setStatus("");
    try {
      state.previewText = Core.renderOffer(selectedTemplate(), renderOptions(true));
      elements.preview.textContent = state.previewText;
      elements.preview.hidden = false;
      elements["preview-placeholder"].hidden = true;
      elements["preview-shell"].classList.remove("invalid");
      elements["character-count"].textContent = `${state.previewText.length} character${state.previewText.length === 1 ? "" : "s"}`;
    } catch (error) {
      state.previewText = "";
      elements.preview.textContent = "";
      elements.preview.hidden = true;
      elements["preview-placeholder"].hidden = false;
      elements["preview-placeholder"].textContent = error.message;
      elements["preview-shell"].classList.add("invalid");
      elements["character-count"].textContent = "";
    }
  }

  function setStatus(message, kind = "") {
    elements.status.textContent = message;
    elements.status.className = `status${kind ? ` ${kind}` : ""}`;
    elements.status.setAttribute("role", kind === "error" ? "alert" : "status");
  }

  function setSettingsStatus(message, kind = "") {
    elements["settings-status"].textContent = message;
    elements["settings-status"].className = `settings-status${kind ? ` ${kind}` : ""}`;
    elements["settings-status"].setAttribute("role", kind === "error" ? "alert" : "status");
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const helper = document.createElement("textarea");
    helper.value = text;
    helper.setAttribute("readonly", "");
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.append(helper);
    helper.select();
    const copied = document.execCommand("copy");
    helper.remove();
    if (!copied) throw new Error("Clipboard access was blocked.");
  }

  async function copyOffer() {
    try {
      const text = Core.renderOffer(selectedTemplate(), renderOptions(false));
      await copyText(text);
      setStatus("Copied to clipboard.", "success");
    } catch (error) {
      const message = error.message || "";
      if (elements["preview-placeholder"].textContent === message && !elements["preview-placeholder"].hidden) {
        setStatus("");
      } else {
        setStatus(message || "Could not copy the offer.", "error");
      }
      if (message.includes("price first")) byId("price-input")?.focus();
      else if (message.includes("broadband price")) byId("broadband-price-input")?.focus();
      else if (message.includes("DD/MM/YYYY")) byId("date-input")?.focus();
    }
  }

  function switchTab(name) {
    document.querySelectorAll(".tab").forEach((tab) => {
      const selected = tab.dataset.tab === name;
      tab.classList.toggle("active", selected);
      tab.setAttribute("aria-selected", String(selected));
    });
    document.querySelectorAll(".tab-panel").forEach((panel) => {
      const selected = panel.id === `tab-${name}`;
      panel.classList.toggle("active", selected);
      panel.hidden = !selected;
    });
  }

  function setPageInert(inert) {
    elements.app.inert = inert;
    elements["app-bar"].inert = inert;
    document.body.classList.toggle("modal-open", inert);
  }

  function activeModal() {
    if (!elements["settings-modal"].hidden) return elements["settings-modal"];
    if (!elements["instructions-modal"].hidden) return elements["instructions-modal"];
    return null;
  }

  function openInstructions() {
    elements["instructions-modal"].hidden = false;
    setPageInert(true);
    elements["close-instructions"].focus();
  }

  function closeInstructions() {
    elements["instructions-modal"].hidden = true;
    setPageInert(false);
    elements["open-instructions"].focus();
  }

  function openSettings() {
    state.draft = Core.clone(state.config);
    state.draftIndex = Math.max(0, state.draft.packages.findIndex((item) => item.title === state.selectedTitle));
    renderDraftTemplates();
    renderFieldSettings();
    switchTab("templates");
    setSettingsStatus("");
    elements["settings-modal"].hidden = false;
    setPageInert(true);
    elements["close-settings"].focus();
  }

  function closeSettings() {
    elements["settings-modal"].hidden = true;
    setPageInert(false);
    state.draft = null;
    elements["open-settings"].focus();
  }

  function currentDraftTemplate() {
    return state.draft.packages[state.draftIndex];
  }

  function renderDraftTemplates() {
    elements["template-list"].replaceChildren();
    state.draft.packages.forEach((item, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.index = String(index);
      button.textContent = item.title || "Untitled template";
      button.classList.toggle("selected", index === state.draftIndex);
      button.setAttribute("role", "option");
      button.setAttribute("aria-selected", String(index === state.draftIndex));
      button.addEventListener("click", () => {
        state.draftIndex = index;
        renderDraftTemplates();
      });
      elements["template-list"].append(button);
    });
    elements["template-count"].textContent = String(state.draft.packages.length);
    elements["delete-template"].disabled = state.draft.packages.length === 1;
    loadDraftTemplate();
    updateDefaultSelects();
  }

  function loadDraftTemplate() {
    const item = currentDraftTemplate();
    if (!item) return;
    elements["edit-title"].value = item.title || "";
    elements["edit-package"].value = item.package || "";
    elements["edit-message"].value = item.template || "";
    elements["edit-broadband2"].value = item.broadband2 || "";
    elements["edit-tv1"].value = item.tv1 || "";
    elements["edit-tv2"].value = item.tv2 || "";
    updateTemplateFieldHelp();
  }

  function updateTemplateFieldHelp() {
    try {
      const fields = Core.templateFields(elements["edit-message"].value);
      elements["services-help"].hidden = !fields.has("services");
      elements["date-offset-tool"].hidden = ![...fields].some((field) => /^date(?:[+-]\d+)?$/.test(field));
    } catch (_error) {
      elements["services-help"].hidden = true;
      elements["date-offset-tool"].hidden = true;
    }
  }

  function updateDraftField(field, value) {
    if (!state.draft) return;
    const item = currentDraftTemplate();
    const previousValue = item[field];
    if (value) item[field] = value;
    else if (["broadband2", "tv1", "tv2"].includes(field)) delete item[field];
    else item[field] = value;
    if (field === "title") {
      if (state.draft.default_package === previousValue) state.draft.default_package = value;
      const listItem = elements["template-list"].querySelector(`[data-index="${state.draftIndex}"]`);
      if (listItem) listItem.textContent = value || "Untitled template";
      updateDefaultSelects();
    }
    if (field === "template") updateTemplateFieldHelp();
  }

  function addTemplate() {
    let number = state.draft.packages.length + 1;
    const used = new Set(state.draft.packages.map((item) => item.title.toLocaleLowerCase()));
    while (used.has(`new template ${number}`)) number += 1;
    state.draft.packages.push({
      title: `New template ${number}`,
      package: "",
      template: "Write your message here."
    });
    state.draftIndex = state.draft.packages.length - 1;
    renderDraftTemplates();
    elements["edit-title"].select();
  }

  function duplicateTemplate() {
    const copy = Core.clone(currentDraftTemplate());
    const base = copy.title.replace(/ copy(?: \d+)?$/i, "");
    let suffix = 1;
    let title = `${base} copy`;
    const used = new Set(state.draft.packages.map((item) => item.title.toLocaleLowerCase()));
    while (used.has(title.toLocaleLowerCase())) {
      suffix += 1;
      title = `${base} copy ${suffix}`;
    }
    copy.title = title;
    state.draft.packages.splice(state.draftIndex + 1, 0, copy);
    state.draftIndex += 1;
    renderDraftTemplates();
    elements["edit-title"].select();
  }

  function deleteTemplate() {
    if (state.draft.packages.length === 1) return;
    const item = currentDraftTemplate();
    if (!window.confirm(`Delete "${item.title || "this template"}"?`)) return;
    state.draft.packages.splice(state.draftIndex, 1);
    state.draftIndex = Math.min(state.draftIndex, state.draft.packages.length - 1);
    renderDraftTemplates();
  }

  function updateDefaultSelects() {
    const templateSelect = elements["default-template"];
    const currencySelect = elements["default-currency"];
    templateSelect.replaceChildren();
    state.draft.packages.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.title;
      option.textContent = item.title || "Untitled template";
      templateSelect.append(option);
    });
    if (!state.draft.packages.some((item) => item.title === state.draft.default_package)) {
      state.draft.default_package = state.draft.packages[0].title;
    }
    templateSelect.value = state.draft.default_package;

    currencySelect.replaceChildren();
    state.draft.currencies.forEach((currency) => {
      const option = document.createElement("option");
      option.value = currency;
      option.textContent = currency;
      currencySelect.append(option);
    });
    if (!state.draft.currencies.includes(state.draft.default_currency)) {
      state.draft.default_currency = state.draft.currencies[0] || "";
    }
    currencySelect.value = state.draft.default_currency;
  }

  function linesFromTextarea(value) {
    return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
  }

  function renderFieldSettings() {
    const container = elements["field-settings"];
    container.replaceChildren();

    const currencyCard = elements["currency-settings"];
    currencyCard.replaceChildren();
    const currencyTitle = document.createElement("h3");
    currencyTitle.textContent = "Currencies";
    const currencyArea = document.createElement("textarea");
    currencyArea.rows = 5;
    currencyArea.value = state.draft.currencies.join("\n");
    currencyArea.setAttribute("aria-label", "Currency choices, one per line");
    currencyArea.addEventListener("input", () => {
      state.draft.currencies = linesFromTextarea(currencyArea.value);
      updateDefaultSelects();
    });
    currencyCard.append(currencyTitle, makeField("Choices, one per line", currencyArea));

    Core.VARIABLE_KEYS.forEach((key) => {
      const variable = state.draft.variables[key];
      const card = document.createElement("section");
      card.className = "settings-card";
      const title = document.createElement("h3");
      title.textContent = variable.label;
      const nameInput = makeInput(`field-name-${key}`, variable.label, "Field name");
      const choicesArea = document.createElement("textarea");
      choicesArea.rows = 5;
      choicesArea.value = variable.options.join("\n");
      choicesArea.setAttribute("aria-label", `${variable.label} choices, one per line`);
      const defaultSelect = makeSelect(variable.options, variable.default);
      nameInput.addEventListener("input", () => {
        variable.label = nameInput.value;
        title.textContent = nameInput.value || "Unnamed field";
      });
      choicesArea.addEventListener("input", () => {
        variable.options = linesFromTextarea(choicesArea.value);
        const previous = variable.default;
        defaultSelect.replaceChildren();
        variable.options.forEach((choice) => {
          const option = document.createElement("option");
          option.value = choice;
          option.textContent = choice;
          defaultSelect.append(option);
        });
        variable.default = variable.options.includes(previous) ? previous : (variable.options[0] || "");
        defaultSelect.value = variable.default;
      });
      defaultSelect.addEventListener("change", () => { variable.default = defaultSelect.value; });
      card.append(
        title,
        makeField("Field name", nameInput),
        makeField("Choices, one per line", choicesArea),
        makeField("Default choice", defaultSelect)
      );
      container.append(card);
    });
    updateDefaultSelects();
  }

  function saveSettings() {
    try {
      const selectedDraftTitle = currentDraftTemplate().title.trim();
      const configToSave = Core.clone(state.draft);
      const defaultTemplate = configToSave.packages.find(
        (item) => item.title === configToSave.default_package
      );
      if (defaultTemplate) configToSave.default_package = defaultTemplate.title.trim();
      const validated = Core.validateConfig(configToSave);
      const stored = persistConfig(validated);
      applyConfig(validated, {
        preserveValues: true,
        preserveActive: true,
        preferredTitle: selectedDraftTitle
      });
      closeSettings();
      setStatus(stored ? "Changes saved in this browser." : "Changes applied, but browser storage is unavailable.", stored ? "success" : "error");
    } catch (error) {
      setSettingsStatus(error.message || "Could not save these settings.", "error");
    }
  }

  function transferableConfig() {
    return Core.validateConfig(state.draft || state.config);
  }

  function downloadConfig() {
    try {
      const config = transferableConfig();
      const blob = new Blob([`${JSON.stringify(config, null, 2)}\n`], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const date = new Date().toISOString().slice(0, 10);
      link.href = url;
      link.download = `offertemplates-backup-${date}.json`;
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      if (state.draft) setSettingsStatus("Backup downloaded.", "success");
      else setStatus("Backup downloaded.", "success");
    } catch (error) {
      if (state.draft) setSettingsStatus(error.message, "error");
      else setStatus(error.message, "error");
    }
  }

  async function copySettings() {
    try {
      await copyText(`${JSON.stringify(transferableConfig(), null, 2)}\n`);
      setSettingsStatus("Settings copied to the clipboard.", "success");
    } catch (error) {
      setSettingsStatus(error.message || "Could not copy the settings.", "error");
    }
  }

  async function importConfigFile(file) {
    if (!file) return;
    try {
      const imported = Core.validateConfig(JSON.parse(await file.text()));
      const stored = persistConfig(imported);
      applyConfig(imported);
      if (state.draft) {
        state.draft = Core.clone(imported);
        state.draftIndex = 0;
        renderDraftTemplates();
        renderFieldSettings();
        setSettingsStatus(
          stored
            ? `Imported ${imported.packages.length} template${imported.packages.length === 1 ? "" : "s"}.`
            : "Imported for this session, but browser storage is unavailable.",
          stored ? "success" : "error"
        );
      } else {
        setStatus(
          stored
            ? `Imported ${imported.packages.length} template${imported.packages.length === 1 ? "" : "s"}.`
            : "Imported for this session, but browser storage is unavailable.",
          stored ? "success" : "error"
        );
      }
    } catch (error) {
      const message = error instanceof SyntaxError ? "That file is not valid JSON." : (error.message || "Could not import that file.");
      if (state.draft) setSettingsStatus(message, "error");
      else setStatus(message, "error");
    } finally {
      elements["import-file"].value = "";
    }
  }

  function restoreDefaults() {
    if (!window.confirm("Restore the bundled defaults? Your browser changes will be replaced.")) return;
    const restored = Core.clone(state.bundledConfig);
    const stored = persistConfig(restored);
    applyConfig(restored);
    if (state.draft) {
      state.draft = Core.clone(restored);
      state.draftIndex = 0;
      renderDraftTemplates();
      renderFieldSettings();
      setSettingsStatus(
        stored ? "Bundled defaults restored." : "Defaults restored for this session, but browser storage is unavailable.",
        stored ? "success" : "error"
      );
    }
  }

  function insertToken(token) {
    const textarea = elements["edit-message"];
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    textarea.focus();
    textarea.setSelectionRange(start, end);
    const inserted = document.execCommand("insertText", false, token);
    if (!inserted) {
      textarea.setRangeText(token, start, end, "end");
      textarea.dispatchEvent(new InputEvent("input", {
        bubbles: true,
        inputType: "insertText",
        data: token
      }));
    }
    currentDraftTemplate().template = textarea.value;
    updateTemplateFieldHelp();
  }

  function readDateOffsetDays() {
    const raw = elements["date-offset-days"].value.trim();
    if (!/^\d+$/.test(raw)) {
      throw new Error(`Enter a whole number from 0 to ${Core.MAX_DATE_OFFSET_DAYS.toLocaleString("en-US")}.`);
    }
    const days = Number(raw);
    if (days > Core.MAX_DATE_OFFSET_DAYS) {
      throw new Error(`Enter a whole number from 0 to ${Core.MAX_DATE_OFFSET_DAYS.toLocaleString("en-US")}.`);
    }
    return days;
  }

  function updateDateOffsetButtons() {
    let value = "N";
    try {
      value = String(readDateOffsetDays());
    } catch (_error) {
      value = "N";
    }
    elements["insert-date-plus"].textContent = `Insert {date+${value}}`;
    elements["insert-date-minus"].textContent = `Insert {date-${value}}`;
    elements["date-offset-status"].hidden = true;
    elements["date-offset-days"].removeAttribute("aria-invalid");
  }

  function insertDateOffset(sign) {
    try {
      const days = readDateOffsetDays();
      elements["date-offset-status"].hidden = true;
      elements["date-offset-days"].removeAttribute("aria-invalid");
      insertToken(`{date${sign}${days}}`);
    } catch (error) {
      elements["date-offset-status"].textContent = error.message;
      elements["date-offset-status"].hidden = false;
      elements["date-offset-days"].setAttribute("aria-invalid", "true");
      elements["date-offset-days"].focus();
      elements["date-offset-days"].select();
    }
  }

  function openFieldValues() {
    switchTab("fields");
    const firstServiceChoices = elements["field-settings"].querySelector("textarea");
    if (firstServiceChoices) firstServiceChoices.focus();
  }

  function bindEvents() {
    elements["template-select"].addEventListener("change", () => changeTemplate(false));
    elements["copy-offer"].addEventListener("click", copyOffer);
    elements["open-instructions"].addEventListener("click", openInstructions);
    elements["close-instructions"].addEventListener("click", closeInstructions);
    elements["done-instructions"].addEventListener("click", closeInstructions);
    elements["open-settings"].addEventListener("click", openSettings);
    elements["close-settings"].addEventListener("click", closeSettings);
    elements["cancel-settings"].addEventListener("click", closeSettings);
    elements["save-settings"].addEventListener("click", saveSettings);
    elements["add-template"].addEventListener("click", addTemplate);
    elements["duplicate-template"].addEventListener("click", duplicateTemplate);
    elements["delete-template"].addEventListener("click", deleteTemplate);
    elements["copy-settings"].addEventListener("click", copySettings);
    elements["reset-settings"].addEventListener("click", restoreDefaults);
    elements["open-field-values"].addEventListener("click", openFieldValues);
    elements["date-offset-days"].addEventListener("input", updateDateOffsetButtons);
    elements["insert-date-plus"].addEventListener("click", () => insertDateOffset("+"));
    elements["insert-date-minus"].addEventListener("click", () => insertDateOffset("-"));
    elements["default-template"].addEventListener("change", (event) => { state.draft.default_package = event.target.value; });
    elements["default-currency"].addEventListener("change", (event) => { state.draft.default_currency = event.target.value; });
    elements["import-file"].addEventListener("change", (event) => importConfigFile(event.target.files[0]));

    [
      ["edit-title", "title"], ["edit-package", "package"], ["edit-message", "template"],
      ["edit-broadband2", "broadband2"], ["edit-tv1", "tv1"], ["edit-tv2", "tv2"]
    ].forEach(([id, field]) => {
      elements[id].addEventListener("input", (event) => updateDraftField(field, event.target.value));
    });

    document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => switchTab(tab.dataset.tab)));
    document.querySelectorAll("[data-action='import']").forEach((button) => button.addEventListener("click", () => elements["import-file"].click()));
    document.querySelectorAll("[data-action='export']").forEach((button) => button.addEventListener("click", downloadConfig));
    document.querySelectorAll("[data-token]").forEach((button) => button.addEventListener("click", () => insertToken(button.dataset.token)));

    elements["settings-modal"].addEventListener("click", (event) => {
      if (event.target === elements["settings-modal"]) closeSettings();
    });
    elements["instructions-modal"].addEventListener("click", (event) => {
      if (event.target === elements["instructions-modal"]) closeInstructions();
    });
    document.addEventListener("keydown", (event) => {
      const modal = activeModal();
      if (event.key === "Escape" && modal) {
        if (modal === elements["settings-modal"]) closeSettings();
        else closeInstructions();
      }
      if (event.key === "Tab" && modal && !event.ctrlKey && !event.metaKey && !event.altKey) {
        const focusable = [...modal.querySelectorAll(
          "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
        )].filter((item) => item.offsetParent !== null);
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && !modal) copyOffer();
    });

    let dragDepth = 0;
    window.addEventListener("dragenter", (event) => {
      if (![...event.dataTransfer.types].includes("Files")) return;
      dragDepth += 1;
      elements["drop-overlay"].classList.add("visible");
    });
    window.addEventListener("dragleave", () => {
      dragDepth -= 1;
      if (dragDepth <= 0) {
        dragDepth = 0;
        elements["drop-overlay"].classList.remove("visible");
      }
    });
    window.addEventListener("dragover", (event) => event.preventDefault());
    window.addEventListener("drop", (event) => {
      event.preventDefault();
      dragDepth = 0;
      elements["drop-overlay"].classList.remove("visible");
      const file = [...event.dataTransfer.files].find((item) => item.name.toLocaleLowerCase().endsWith(".json"));
      if (file) importConfigFile(file);
      else setStatus("Drop a JSON backup file to import settings.", "error");
    });
  }

  async function boot() {
    cacheElements();
    bindEvents();
    state.bundledConfig = await loadBundledConfig();
    const stored = loadStoredConfig();
    applyConfig(stored || state.bundledConfig);
    if (!stored) persistConfig(state.config);
    elements.app.setAttribute("aria-busy", "false");
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
