# OfferTemplates

A small Windows app for preparing broadband, TV, and streaming offers and copying them to the clipboard.
It uses a dark interface and automatically scales and centers itself for the primary display.

## Start the app

Double-click `OfferTemplates.exe` in the `release` folder. It is a self-contained Windows app: Python does not need to be installed, and no Command Prompt window opens.

To give the app to someone else, send them only `OfferTemplates.exe`. Every new user starts with the clean bundled templates.

## Daily use

1. Choose a template.
2. Use **Optional fields** to add Broadband, TV, or Streaming only when the offer needs them. Each added field can be removed again.
3. Fill in the visible values. Prices use the selected currency.
4. Check the preview and click **Copy offer**. Pressing Enter does the same thing.

## Change packages and messages

Click **Edit templates** inside the app. The **Templates** tab contains the template list plus separate editors for the message and its saved `{broadband2}`, `{tv1}`, and `{tv2}` text. The **Fields, choices & defaults** tab contains the customizable field names, every dropdown choice, and all startup defaults.

Templates can use any of these optional fields:

- `{services}` inserts only the optional fields added in the main window, joined with ` + `. This is the easiest choice for flexible Broadband, TV, and Streaming combinations.
- `{broadband}` inserts the selected broadband speed.
- `{broadband_price}` inserts the broadband price entered beside the broadband selector.
- `{tv}` inserts the selected TV package.
- `{streaming}` inserts the selected streaming package.
- `{package}` inserts the package name.
- `{price}` inserts the price entered in the main window.
- `{date}` inserts the current date in `DD/MM/YYYY` format.
- `{date+N}` inserts any whole number of days after the current date—for example, `{date+14}`.
- `{date-N}` inserts any whole number of days before the current date—for example, `{date-14}`.

For example, `We would like to offer you {services} for {price}.` works for Broadband, Broadband + TV, Broadband + Streaming, TV + Streaming, or all three. The user chooses the combination from the main window. Templates that use `{broadband}`, `{tv}`, or `{streaming}` directly initially add those fields, but each one can still be removed before copying.

Field names such as Broadband and Streaming are editable, as are their choices and defaults. Their template fields—`{broadband}`, `{tv}`, and `{streaming}`—stay unchanged so renaming a visible field does not break saved templates. A removed optional field is not required. A message without any fields is copied exactly as written. If a template uses `{package}`, its package name cannot be blank. If it uses `{price}`, a total price must be entered before copying. If Broadband is added and the template uses `{broadband_price}`, a broadband price must be entered. The two prices are independent and both use the selected currency.

Use `{broadband2}`, `{tv1}`, and `{tv2}` in a message to insert text saved with that template. For example, `{tv}` can insert `tv mini` while `{tv1}` inserts its complete prewritten offer. These saved texts are edited only in **Edit templates**; they do not add text boxes or expose the wording as fields on the main window. Each one follows its matching optional service, so removing Broadband or TV also removes its saved text from the finished offer.

Date fields use the computer's current local date each time the preview or copied offer is created. When a template contains a date field, the main window also shows an optional **Date override (DD/MM/YYYY)** entry. Leave it blank to use today, or enter another date to make `{date}` and every offset calculate from that date. For example, an override of `02/09/2026` makes `{date+14}` become `16/09/2026` and `{date-14}` become `19/08/2026`.

Changes made in the packaged app are saved to `%LOCALAPPDATA%\OfferTemplates\packages.json`. That file can also be edited directly in a text editor if needed. Keep a copy of it to back up or move your templates to another computer.

Currency choices are stored in `currencies`. Broadband, TV, and streaming names, choices, and defaults are stored in `variables`. `default_package` and `default_currency` control the initial template and currency. Currency text is placed after the entered price, so an entry such as `€/month` produces `19.90 €/month`.

## Rebuild the executable

Install the build dependency with `python -m pip install -r requirements-build.txt`, then run `powershell -ExecutionPolicy Bypass -File packaging\build.ps1`. The finished file is created at `release\OfferTemplates.exe`.
