# OfferTemplates

OfferTemplates is a static browser application for preparing reusable broadband, TV, and streaming offers. It runs entirely in the browser and can be hosted directly on GitHub Pages. There is no backend, account, build step, or external dependency.

## Use it

Open the site, choose a template, add the services included in the offer, fill in the visible values, and select **Copy offer**. The preview updates while you type. `Ctrl + Enter` (`Cmd + Enter` on macOS) also copies the finished message.

Only the fields used by the selected template are shown. A service can still be removed from an offer even when the template supports it.

## Edit templates and choices

Select **Edit templates** to change:

- template titles, package names, messages, and saved campaign text;
- currencies;
- broadband, TV, and streaming field names and choices;
- different `{tv1}` and `{tv2}` text for each TV package;
- the default template, currency, and service choices.

Changes are validated before they are saved. Settings stay in that browser's local storage and are not sent anywhere.

## Transfer or back up templates

Use **Export** to download one JSON file containing every template, choice, field name, and default. Use **Import** on another browser or device to load it. A JSON backup can also be dragged onto the page.

The **Transfer** tab in the editor additionally lets you copy the complete JSON as text or restore the configuration from `packages.json` bundled with the site.

Existing `packages.json` files from the Windows version are accepted, so current templates can be moved into the browser app without manual conversion.

## Template fields

| Field | Result |
| --- | --- |
| `{services}` | Active service choices joined with ` + ` |
| `{broadband}` | Selected broadband choice |
| `{broadband_price}` | Broadband price plus the selected currency |
| `{tv}` | Selected TV package name |
| `{streaming}` | Selected streaming choice |
| `{package}` | Package name saved with the template |
| `{price}` | Offer price plus the selected currency |
| `{broadband2}` | Saved broadband campaign text |
| `{tv1}` | TV offer text saved for the selected package |
| `{tv2}` | TV campaign text saved for the selected package |
| `{date}` | Current date, or the entered override, as `DD/MM/YYYY` |
| `{date+N}` | The date any whole number of days later, such as `{date+137}` |
| `{date-N}` | The date any whole number of days earlier, such as `{date-14}` |

Use doubled braces for literal braces: `{{price}}` produces `{price}` instead of inserting a price. Date offsets are limited to 365,000 days as a safety bound.

`{tv}` always uses the name selected in the TV dropdown. When a template contains `{tv1}` or `{tv2}`, its editor shows **TV text by package**. Enter the matching offer or campaign text for each TV package. Changing the TV dropdown then updates `{tv}`, `{tv1}`, and `{tv2}` together.

## Publish on GitHub Pages

This repository includes a manual **Publish GitHub Pages** workflow. It validates the application and publishes only the browser files.

Before the first publication:

1. Push the repository to GitHub.
2. Open **Settings → Pages** and set **Source** to **GitHub Actions**. This is required once by GitHub.

To publish:

1. Open **Actions → Publish GitHub Pages**.
2. Select **Run workflow**, then confirm with the green **Run workflow** button.

The workflow checks the application before publishing it. GitHub shows the public address when the run finishes. Future publications use the same **Run workflow** button.

## Run locally

The app should be served over HTTP so the bundled JSON and clipboard APIs behave like they do on GitHub Pages. From the project folder, use either:

```powershell
python -m http.server 8000
```

or any other static file server, then open `http://localhost:8000`.

## Validate changes

Node.js is needed only for the automated checks, not for users of the app.

```powershell
node --test
node --check core.js
node --check app.js
```

The test suite covers template validation, optional services, campaign text, independent prices, date overrides and offsets, legacy JSON compatibility, and invalid configuration handling.
