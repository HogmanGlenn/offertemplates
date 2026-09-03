const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Core = require("../core.js");

function config(overrides = {}) {
  return {
    default_package: "Flexible",
    default_currency: "€/month",
    currencies: ["€/month", "€"],
    variables: {
      broadband: { label: "Broadband", options: ["1000/1000", "500/500"], default: "1000/1000" },
      tv: { label: "TV package", options: ["TV Mini", "TV Max"], default: "TV Mini" },
      streaming: { label: "Streaming", options: ["Streaming Mini", "Streaming Max"], default: "Streaming Mini" }
    },
    packages: [{
      title: "Flexible",
      package: "",
      template: "Offer {services} for {price}."
    }],
    ...overrides
  };
}

test("validates and normalizes a portable configuration", () => {
  const value = config();
  value.packages[0].template = "Offer {tv}: {tv1}.";
  value.packages[0].tv1_outputs = {
    "TV Mini": "Mini offer for 9.90 €/month",
    "TV Max": "Max offer for 19.90 €/month"
  };
  const result = Core.validateConfig(value);
  assert.equal(result.packages[0].title, "Flexible");
  assert.equal(result.variables.tv.default, "TV Mini");
  assert.deepEqual(result.packages[0].tv1_outputs, value.packages[0].tv1_outputs);
});

test("template editor exposes every supported field", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
  const buttons = new Set([...html.matchAll(/data-token="([^"]+)"/g)].map((match) => match[1]));
  [
    "{services}", "{broadband}", "{broadband_price}", "{broadband2}",
    "{tv}", "{tv1}", "{tv2}", "{streaming}", "{streaming1}", "{streaming2}", "{package}", "{price}",
    "{date}"
  ].forEach((field) => assert.ok(buttons.has(field), `Missing insert button for ${field}`));
  assert.match(html, /id="date-offset-tool" hidden/);
  assert.match(html, /id="date-offset-days"/);
  assert.match(html, /id="insert-date-plus"/);
  assert.match(html, /id="insert-date-minus"/);
  assert.match(html, /id="services-help"/);
  assert.match(html, /id="open-field-values"/);
  assert.match(html, /id="tv-choice-text-settings"[^>]*hidden/);
  assert.match(html, /id="tv-choice-text-list"/);
  assert.match(html, /id="streaming-choice-text-settings"[^>]*hidden/);
  assert.match(html, /id="streaming-choice-text-list"/);
});

test("loads older configuration files without variables", () => {
  const result = Core.validateConfig({
    default_package: "Plain",
    default_currency: "€",
    currencies: ["€"],
    packages: [{ title: "Plain", package: "", template: "Plain text" }]
  });
  assert.equal(result.variables.broadband.default, "1000/1000");
});

test("joins only active services and formats the price", () => {
  const item = config().packages[0];
  const result = Core.renderOffer(item, {
    price: "29.90",
    currency: "€/month",
    selections: { broadband: "1000/1000", tv: "TV Mini", streaming: "Streaming Mini" },
    activeVariables: new Set(["broadband", "streaming"])
  });
  assert.equal(result, "Offer 1000/1000 + Streaming Mini for 29.90 €/month.");
});

test("updates streaming, streaming1, and streaming2 from the same dropdown choice", () => {
  const item = {
    title: "Streaming offer",
    package: "",
    template: "{streaming}: {streaming1} {streaming2}",
    streaming1_outputs: {
      "Streaming Mini": "Mini offer for 5.90 €/month.",
      "Streaming Max": "Max offer for 12.90 €/month."
    },
    streaming2_outputs: {
      "Streaming Mini": "Mini campaign.",
      "Streaming Max": "Max campaign."
    }
  };
  assert.equal(Core.renderOffer(item, {
    selections: { streaming: "Streaming Mini" },
    activeVariables: ["streaming"]
  }), "Streaming Mini: Mini offer for 5.90 €/month. Mini campaign.");
  assert.equal(Core.renderOffer(item, {
    selections: { streaming: "Streaming Max" },
    activeVariables: ["streaming"]
  }), "Streaming Max: Max offer for 12.90 €/month. Max campaign.");
});

test("migrates older shared streaming offer text", () => {
  const value = config();
  value.packages[0] = {
    title: "Flexible",
    package: "",
    template: "{streaming}: {streaming1} {streaming2}",
    streaming1: "Shared streaming offer",
    streaming2: "Shared streaming campaign"
  };
  const result = Core.validateConfig(value).packages[0];
  assert.deepEqual(result.streaming1_outputs, {
    "Streaming Mini": "Shared streaming offer",
    "Streaming Max": "Shared streaming offer"
  });
  assert.deepEqual(result.streaming2_outputs, {
    "Streaming Mini": "Shared streaming campaign",
    "Streaming Max": "Shared streaming campaign"
  });
});

test("updates tv, tv1, and tv2 from the same dropdown choice", () => {
  const item = {
    title: "TV offer",
    package: "",
    template: "{tv}: {tv1} {tv2}",
    tv1_outputs: {
      "TV Mini": "Mini offer for 9.90 €/month.",
      "TV Max": "Max offer for 19.90 €/month."
    },
    tv2_outputs: {
      "TV Mini": "Mini campaign.",
      "TV Max": "Max campaign."
    }
  };
  assert.equal(Core.renderOffer(item, {
    selections: { tv: "TV Mini" },
    activeVariables: ["tv"]
  }), "TV Mini: Mini offer for 9.90 €/month. Mini campaign.");
  assert.equal(Core.renderOffer(item, {
    selections: { tv: "TV Max" },
    activeVariables: ["tv"]
  }), "TV Max: Max offer for 19.90 €/month. Max campaign.");
});

test("keeps tv as the dropdown label", () => {
  const item = {
    title: "TV offer",
    package: "",
    template: "Watch {tv}.",
    tv_outputs: { "TV Mini": "This old value must not replace {tv}." }
  };
  assert.equal(Core.renderOffer(item, {
    selections: { tv: "TV Mini" },
    activeVariables: ["tv"]
  }), "Watch TV Mini.");
});

test("migrates older shared and choice-specific TV offer text", () => {
  const shared = config();
  shared.packages[0] = {
    title: "Flexible",
    package: "",
    template: "{tv}: {tv1}",
    tv1: "Shared offer"
  };
  assert.deepEqual(Core.validateConfig(shared).packages[0].tv1_outputs, {
    "TV Mini": "Shared offer",
    "TV Max": "Shared offer"
  });

  const choiceSpecific = config();
  choiceSpecific.packages[0] = {
    title: "Flexible",
    package: "",
    template: "{tv}: {tv1}",
    tv_outputs: {
      "TV Mini": "Mini offer",
      "TV Max": "Max offer"
    }
  };
  assert.deepEqual(Core.validateConfig(choiceSpecific).packages[0].tv1_outputs, {
    "TV Mini": "Mini offer",
    "TV Max": "Max offer"
  });
});

test("supports package, service, and independent broadband price fields", () => {
  const item = {
    title: "Bundle",
    package: "Home bundle",
    template: "{package}: {broadband} {broadband_price}; total {price}"
  };
  const result = Core.renderOffer(item, {
    price: "39.90",
    broadbandPrice: "19.90",
    currency: "€/month",
    selections: { broadband: "500/500" },
    activeVariables: ["broadband"]
  });
  assert.equal(result, "Home bundle: 500/500 19.90 €/month; total 39.90 €/month");
});

test("omits campaign text when its service is removed", () => {
  const item = {
    title: "Campaign",
    package: "",
    template: "{broadband2}{tv2}",
    broadband2: "Broadband campaign",
    tv2: "TV campaign"
  };
  assert.equal(Core.renderOffer(item, { activeVariables: ["tv"] }), "TV campaign");
});

test("renders positive and negative date offsets as DD/MM/YYYY", () => {
  const item = {
    title: "Dates",
    package: "",
    template: "Today {date}; next {date+137}; before {date-40}"
  };
  const result = Core.renderOffer(item, { today: new Date(Date.UTC(2026, 0, 10)) });
  assert.equal(result, "Today 10/01/2026; next 27/05/2026; before 01/12/2025");
});

test("date override is strict and applies to every date field", () => {
  const item = { title: "Date", package: "", template: "{date} / {date+30}" };
  assert.equal(Core.renderOffer(item, { dateOverride: "15/01/2027" }), "15/01/2027 / 14/02/2027");
  assert.throws(() => Core.renderOffer(item, { dateOverride: "2027-01-15" }), /DD\/MM\/YYYY/);
  assert.throws(() => Core.renderOffer(item, { dateOverride: "30/02/2027" }), /DD\/MM\/YYYY/);
});

test("allows escaped literal braces", () => {
  const item = { title: "Literal", package: "", template: "Use {{price}} then {price}." };
  assert.equal(Core.renderOffer(item, { price: "10", currency: "€" }), "Use {price} then 10 €.");
});

test("rejects duplicate titles, choices, and unknown fields", () => {
  assert.throws(() => Core.validateConfig(config({
    packages: [
      { title: "Same", package: "", template: "One" },
      { title: "same", package: "", template: "Two" }
    ]
  })), /used more than once/);

  const duplicateChoices = config();
  duplicateChoices.variables.tv.options = ["TV Mini", "tv mini"];
  assert.throws(() => Core.validateConfig(duplicateChoices), /used more than once/);

  assert.throws(() => Core.validateConfig(config({
    packages: [{ title: "Unknown", package: "", template: "Hello {customer}" }]
  })), /unknown field/);

  const missingTvText = config();
  missingTvText.packages[0] = {
    title: "Flexible",
    package: "",
    template: "{tv}: {tv1}",
    tv1_outputs: { "TV Mini": "Mini offer" }
  };
  assert.throws(() => Core.validateConfig(missingTvText), /tv offer text for "TV Max"/i);

  const missingStreamingText = config();
  missingStreamingText.packages[0] = {
    title: "Flexible",
    package: "",
    template: "{streaming}: {streaming1}",
    streaming1_outputs: { "Streaming Mini": "Mini offer" }
  };
  assert.throws(() => Core.validateConfig(missingStreamingText), /streaming offer text for "Streaming Max"/i);
});

test("requires values only when their active fields use them", () => {
  const item = { title: "TV", package: "", template: "Watch {tv} for {price}" };
  assert.throws(() => Core.renderOffer(item, {
    activeVariables: ["tv"],
    selections: { tv: "" },
    price: "10"
  }), /Choose tv package first/);
  assert.equal(Core.renderOffer(item, {
    activeVariables: [],
    selections: { tv: "" },
    price: "10",
    currency: "€"
  }), "Watch  for 10 €");
});

test("rejects invalid braces and unsafe date offsets", () => {
  assert.throws(() => Core.templateFields("Broken {price"), /invalid braces/);
  assert.throws(() => Core.validateConfig(config({
    packages: [{ title: "Far", package: "", template: "{date+365001}" }]
  })), /too large/);
});
