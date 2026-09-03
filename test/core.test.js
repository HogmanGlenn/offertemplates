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
      streaming: { label: "Streaming", options: ["Streaming Plus"], default: "Streaming Plus" }
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
  const result = Core.validateConfig(config());
  assert.equal(result.packages[0].title, "Flexible");
  assert.equal(result.variables.tv.default, "TV Mini");
});

test("template editor exposes every supported field", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
  const buttons = new Set([...html.matchAll(/data-token="([^"]+)"/g)].map((match) => match[1]));
  [
    "{services}", "{broadband}", "{broadband_price}", "{broadband2}",
    "{tv}", "{tv1}", "{tv2}", "{streaming}", "{package}", "{price}",
    "{date}"
  ].forEach((field) => assert.ok(buttons.has(field), `Missing insert button for ${field}`));
  assert.match(html, /id="date-offset-tool" hidden/);
  assert.match(html, /id="date-offset-days"/);
  assert.match(html, /id="insert-date-plus"/);
  assert.match(html, /id="insert-date-minus"/);
  assert.match(html, /id="services-help"/);
  assert.match(html, /id="open-field-values"/);
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
    selections: { broadband: "1000/1000", tv: "TV Mini", streaming: "Streaming Plus" },
    activeVariables: new Set(["broadband", "streaming"])
  });
  assert.equal(result, "Offer 1000/1000 + Streaming Plus for 29.90 €/month.");
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

test("renders positive and negative date offsets as DD.MM.YYYY", () => {
  const item = {
    title: "Dates",
    package: "",
    template: "Today {date}; next {date+137}; before {date-40}"
  };
  const result = Core.renderOffer(item, { today: new Date(Date.UTC(2026, 0, 10)) });
  assert.equal(result, "Today 10.01.2026; next 27.05.2026; before 01.12.2025");
});

test("date override is strict and applies to every date field", () => {
  const item = { title: "Date", package: "", template: "{date} / {date+30}" };
  assert.equal(Core.renderOffer(item, { dateOverride: "15.01.2027" }), "15.01.2027 / 14.02.2027");
  assert.throws(() => Core.renderOffer(item, { dateOverride: "2027-01-15" }), /DD\.MM\.YYYY/);
  assert.throws(() => Core.renderOffer(item, { dateOverride: "30.02.2027" }), /DD\.MM\.YYYY/);
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
