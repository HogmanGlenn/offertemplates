(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.OfferCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const VARIABLE_KEYS = ["broadband", "tv", "streaming"];
  const CAMPAIGN_FIELDS = {
    broadband2: { service: "broadband", label: "Broadband campaign text" },
    tv1: { service: "tv", label: "TV offer text", perChoice: true, legacyOutputs: "tv_outputs" },
    tv2: { service: "tv", label: "TV campaign text", perChoice: true },
    streaming1: { service: "streaming", label: "Streaming offer text", perChoice: true },
    streaming2: { service: "streaming", label: "Streaming campaign text", perChoice: true }
  };
  const ALLOWED_FIELDS = new Set([
    "package", "price", "services", "broadband_price",
    ...VARIABLE_KEYS, ...Object.keys(CAMPAIGN_FIELDS)
  ]);
  const MAX_DATE_OFFSET_DAYS = 365000;
  const DEFAULT_CURRENCIES = ["€/month", "€", "$/month", "$", "£/month", "£"];
  const DEFAULT_VARIABLES = {
    broadband: { label: "Broadband", options: ["1000/1000"], default: "1000/1000" },
    tv: { label: "TV package", options: ["TV Mini"], default: "TV Mini" },
    streaming: { label: "Streaming package", options: ["Streaming package"], default: "Streaming package" }
  };

  class ConfigError extends Error {
    constructor(message) {
      super(message);
      this.name = "ConfigError";
    }
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function fallbackConfig() {
    return {
      default_package: "Flexible offer",
      default_currency: "€/month",
      currencies: clone(DEFAULT_CURRENCIES),
      variables: clone(DEFAULT_VARIABLES),
      packages: [{
        title: "Flexible offer",
        package: "",
        template: "Hi! We would like to offer you {services} for a discounted price of {price}."
      }]
    };
  }

  function parseTemplate(template) {
    if (typeof template !== "string") throw new ConfigError("The message template must be text.");
    const parts = [];
    let text = "";

    for (let index = 0; index < template.length; index += 1) {
      const char = template[index];
      if (char === "{") {
        if (template[index + 1] === "{") {
          text += "{";
          index += 1;
          continue;
        }
        const close = template.indexOf("}", index + 1);
        if (close === -1) throw new ConfigError("This template has invalid braces.");
        const field = template.slice(index + 1, close);
        if (!field || field.includes("{") || field.includes("}") || field.includes(":") || field.includes("!")) {
          throw new ConfigError("This template has invalid braces.");
        }
        if (text) parts.push({ type: "text", value: text });
        parts.push({ type: "field", value: field });
        text = "";
        index = close;
      } else if (char === "}") {
        if (template[index + 1] === "}") {
          text += "}";
          index += 1;
        } else {
          throw new ConfigError("This template has invalid braces.");
        }
      } else {
        text += char;
      }
    }
    if (text) parts.push({ type: "text", value: text });
    return parts;
  }

  function templateFields(template) {
    return new Set(parseTemplate(template).filter((part) => part.type === "field").map((part) => part.value));
  }

  function dateOffset(field) {
    const match = /^date(?:([+-]\d+))?$/.exec(field);
    return match ? Number(match[1] || 0) : null;
  }

  function unsupportedFields(fields) {
    return [...fields].filter((field) => !ALLOWED_FIELDS.has(field) && dateOffset(field) === null);
  }

  function cleanUniqueList(value, emptyMessage, itemLabel) {
    if (!Array.isArray(value) || value.length === 0) throw new ConfigError(emptyMessage);
    const result = [];
    const seen = new Set();
    value.forEach((item, index) => {
      if (typeof item !== "string" || !item.trim()) {
        throw new ConfigError(`${itemLabel} ${index + 1} must be text.`);
      }
      const cleaned = item.trim();
      const key = cleaned.toLocaleLowerCase();
      if (seen.has(key)) throw new ConfigError(`The ${itemLabel.toLowerCase()} "${cleaned}" is used more than once.`);
      seen.add(key);
      result.push(cleaned);
    });
    return result;
  }

  function validateVariables(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new ConfigError("The configuration needs a variables section.");
    }
    const result = {};
    const labels = new Set();
    VARIABLE_KEYS.forEach((key) => {
      const source = value[key];
      const fallback = DEFAULT_VARIABLES[key];
      if (!source || typeof source !== "object" || Array.isArray(source)) {
        throw new ConfigError(`The ${fallback.label.toLowerCase()} choices are missing.`);
      }
      const label = typeof source.label === "string" && source.label.trim() ? source.label.trim() : fallback.label;
      const normalized = label.toLocaleLowerCase();
      if (normalized === "currency" || labels.has(normalized)) {
        throw new ConfigError(`The field name "${label}" is used more than once.`);
      }
      labels.add(normalized);
      const options = cleanUniqueList(
        source.options,
        `The ${label.toLowerCase()} field needs at least one choice.`,
        `${label} choice`
      );
      const defaultValue = source.default === undefined ? options[0] : source.default;
      if (!options.includes(defaultValue)) {
        throw new ConfigError(`The default ${label.toLowerCase()} must match one of its choices.`);
      }
      result[key] = { label, options, default: defaultValue };
    });
    return result;
  }

  function validatePackages(value, variables) {
    if (!Array.isArray(value) || value.length === 0) {
      throw new ConfigError("The configuration must contain at least one template.");
    }
    const titles = new Set();
    return value.map((source, index) => {
      if (!source || typeof source !== "object" || Array.isArray(source)) {
        throw new ConfigError(`Template ${index + 1} is not a valid entry.`);
      }
      if (typeof source.title !== "string" || !source.title.trim()) {
        throw new ConfigError(`Template ${index + 1} needs a title.`);
      }
      if (typeof source.template !== "string" || !source.template.trim()) {
        throw new ConfigError(`Template ${index + 1} needs a message.`);
      }
      if (source.package !== undefined && typeof source.package !== "string") {
        throw new ConfigError(`Template ${index + 1} has an invalid package name.`);
      }
      const item = {
        title: source.title.trim(),
        package: (source.package || "").trim(),
        template: source.template.trim()
      };
      Object.keys(CAMPAIGN_FIELDS).forEach((field) => {
        if (source[field] !== undefined && typeof source[field] !== "string") {
          throw new ConfigError(`Template ${index + 1} has invalid ${CAMPAIGN_FIELDS[field].label.toLowerCase()}.`);
        }
        if (typeof source[field] === "string" && source[field].trim()) item[field] = source[field].trim();
      });
      Object.entries(CAMPAIGN_FIELDS).forEach(([field, details]) => {
        if (!details.perChoice) return;
        const outputField = `${field}_outputs`;
        const sourceOutputs = source[outputField] === undefined && details.legacyOutputs
          ? source[details.legacyOutputs]
          : source[outputField];
        if (sourceOutputs !== undefined && (!sourceOutputs || typeof sourceOutputs !== "object" || Array.isArray(sourceOutputs))) {
          throw new ConfigError(`Template ${index + 1} has invalid ${details.label.toLowerCase()} by ${details.service} choice.`);
        }
        const outputs = {};
        variables[details.service].options.forEach((choice) => {
          let output = item[field] || "";
          if (sourceOutputs && Object.prototype.hasOwnProperty.call(sourceOutputs, choice)) {
            if (typeof sourceOutputs[choice] !== "string") {
              throw new ConfigError(`The ${details.label.toLowerCase()} for "${choice}" must be text.`);
            }
            output = sourceOutputs[choice].trim();
          }
          if (output) outputs[choice] = output;
        });
        if (Object.keys(outputs).length) item[outputField] = outputs;
        delete item[field];
      });

      const normalizedTitle = item.title.toLocaleLowerCase();
      if (titles.has(normalizedTitle)) throw new ConfigError(`The title "${item.title}" is used more than once.`);
      titles.add(normalizedTitle);

      let fields;
      try {
        fields = templateFields(item.template);
      } catch (error) {
        if (error instanceof ConfigError) throw new ConfigError(`The template for "${item.title}" has invalid braces.`);
        throw error;
      }
      const unsupported = unsupportedFields(fields);
      if (unsupported.length) {
        throw new ConfigError(`The template for "${item.title}" uses an unknown field: ${unsupported.sort().join(", ")}.`);
      }
      fields.forEach((field) => {
        const offset = dateOffset(field);
        if (offset !== null && Math.abs(offset) > MAX_DATE_OFFSET_DAYS) {
          throw new ConfigError(`The date offset in "{${field}}" is too large.`);
        }
      });
      if (fields.has("package") && !item.package) {
        throw new ConfigError(`The template for "${item.title}" uses {package}, so a package name is required.`);
      }
      Object.entries(CAMPAIGN_FIELDS).forEach(([field, details]) => {
        if (!fields.has(field)) return;
        if (details.perChoice) {
          const outputs = item[`${field}_outputs`] || {};
          const missingChoice = variables[details.service].options.find((choice) => !outputs[choice]);
          if (missingChoice) {
            throw new ConfigError(`The template for "${item.title}" uses {${field}}, so add ${details.label.toLowerCase()} for "${missingChoice}".`);
          }
        } else if (!item[field]) {
          throw new ConfigError(`The template for "${item.title}" uses {${field}}, so ${details.label} is required.`);
        }
      });
      return item;
    });
  }

  function validateConfig(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new ConfigError("The imported file must contain an OfferTemplates configuration.");
    }
    const currencies = cleanUniqueList(
      value.currencies === undefined ? DEFAULT_CURRENCIES : value.currencies,
      "The configuration must contain at least one currency.",
      "Currency"
    );
    const variables = validateVariables(value.variables === undefined ? clone(DEFAULT_VARIABLES) : value.variables);
    const packages = validatePackages(value.packages, variables);
    const defaultPackage = value.default_package === undefined ? packages[0].title : value.default_package;
    const defaultCurrency = value.default_currency === undefined ? currencies[0] : value.default_currency;
    if (!packages.some((item) => item.title === defaultPackage)) {
      throw new ConfigError("The default template must match one of the template titles.");
    }
    if (!currencies.includes(defaultCurrency)) {
      throw new ConfigError("The default currency must match one of the currencies.");
    }
    return {
      default_package: defaultPackage,
      default_currency: defaultCurrency,
      currencies,
      variables,
      packages
    };
  }

  function parseDisplayDate(value) {
    const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value);
    if (!match) throw new ConfigError("Enter the date as DD/MM/YYYY.");
    const day = Number(match[1]);
    const month = Number(match[2]);
    const year = Number(match[3]);
    const date = new Date(Date.UTC(year, month - 1, day));
    if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
      throw new ConfigError("Enter the date as DD/MM/YYYY.");
    }
    return date;
  }

  function todayUtc() {
    const now = new Date();
    return new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
  }

  function formatDisplayDate(date) {
    const day = String(date.getUTCDate()).padStart(2, "0");
    const month = String(date.getUTCMonth() + 1).padStart(2, "0");
    return `${day}/${month}/${date.getUTCFullYear()}`;
  }

  function addDays(date, amount) {
    const result = new Date(date.getTime());
    result.setUTCDate(result.getUTCDate() + amount);
    if (Number.isNaN(result.getTime())) throw new ConfigError("The date offset is too large.");
    return result;
  }

  function renderOffer(item, options = {}) {
    const fields = templateFields(item.template || "");
    const unsupported = unsupportedFields(fields);
    if (unsupported.length) throw new ConfigError("This template uses an unknown field. Edit the template before copying it.");

    const active = options.activeVariables === undefined
      ? new Set(VARIABLE_KEYS)
      : new Set(options.activeVariables);
    const selections = options.selections || {};
    const labels = options.variableLabels || Object.fromEntries(VARIABLE_KEYS.map((key) => [key, DEFAULT_VARIABLES[key].label]));
    const currency = String(options.currency || "").trim();
    const price = String(options.price || "").trim();
    const broadbandPrice = String(options.broadbandPrice || "").trim();
    const packageName = String(item.package || "").trim();

    if (fields.has("package") && !packageName) throw new ConfigError("Add a package name in Edit templates.");
    if (fields.has("price") && !price) throw new ConfigError("Enter a price first.");
    if (fields.has("broadband_price") && active.has("broadband") && !broadbandPrice) {
      throw new ConfigError("Enter a broadband price first.");
    }

    const withCurrency = (value) => value && currency ? `${value} ${currency}` : value;
    const replacements = {
      package: packageName,
      price: withCurrency(price),
      broadband_price: active.has("broadband") ? withCurrency(broadbandPrice) : "",
      services: VARIABLE_KEYS
        .filter((key) => active.has(key) && String(selections[key] || "").trim())
        .map((key) => String(selections[key]).trim())
        .join(" + ")
    };

    Object.entries(CAMPAIGN_FIELDS).forEach(([field, details]) => {
      const selectedChoice = String(selections[details.service] || "").trim();
      const choiceOutputs = item[`${field}_outputs`];
      const content = String(choiceOutputs?.[selectedChoice] || item[field] || "").trim();
      if (fields.has(field) && !content) throw new ConfigError(`Add ${details.label} in Edit templates.`);
      replacements[field] = active.has(details.service) ? content : "";
    });

    VARIABLE_KEYS.forEach((key) => {
      const value = String(selections[key] || "").trim();
      if (fields.has(key) && active.has(key) && !value) {
        throw new ConfigError(`Choose ${String(labels[key] || key).toLowerCase()} first.`);
      }
      replacements[key] = active.has(key) ? value : "";
    });

    const dateFields = [...fields].filter((field) => dateOffset(field) !== null);
    let baseDate = options.today instanceof Date ? options.today : todayUtc();
    const override = String(options.dateOverride || "").trim();
    if (dateFields.length && override) baseDate = parseDisplayDate(override);
    dateFields.forEach((field) => {
      const offset = dateOffset(field);
      if (Math.abs(offset) > MAX_DATE_OFFSET_DAYS) throw new ConfigError(`The date offset in "{${field}}" is too large.`);
      replacements[field] = formatDisplayDate(addDays(baseDate, offset));
    });

    return parseTemplate(item.template).map((part) => {
      if (part.type === "text") return part.value;
      return replacements[part.value] === undefined ? "" : replacements[part.value];
    }).join("");
  }

  return {
    VARIABLE_KEYS,
    CAMPAIGN_FIELDS,
    MAX_DATE_OFFSET_DAYS,
    ConfigError,
    clone,
    fallbackConfig,
    parseTemplate,
    templateFields,
    unsupportedFields,
    validateConfig,
    renderOffer,
    parseDisplayDate,
    formatDisplayDate
  };
});
