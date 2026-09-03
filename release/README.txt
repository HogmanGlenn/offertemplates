OfferTemplates - Simple User Guide
==================================

START THE APP
-------------
Double-click OfferTemplates.exe. Python is not required, and no command window
will open. The app uses a dark theme, scales with Windows display scaling, and
opens in the centre of the main monitor.

CREATE AND COPY AN OFFER
------------------------
1. Choose a template from the Template dropdown.
2. Add any optional fields you need, such as Broadband, TV, or Streaming.
3. Choose the field values and enter any visible prices.
4. Choose the currency.
5. Check the preview.
6. Click Copy offer, then paste the message where you need it.

Optional fields can be removed again. A removed field is not required and is
left out of the completed message. Pressing Enter also copies the offer.

DATE OVERRIDE
-------------
If a template uses a date parameter, a Date override (DD/MM/YYYY) box appears.
Leave it blank to use today's date. Enter another date, such as 15/01/2027, to
use that as the starting date for every date parameter in the template.

EDIT TEMPLATES AND DROPDOWNS
----------------------------
Click Edit templates.

The Templates tab lets you add, rename, remove, and edit offer templates and
their optional package name. It also has separate editors for {broadband2},
{tv1}, and {tv2}. Those saved texts never appear as editable fields on the
main window.

The Fields, choices & defaults tab lets you:
- rename the visible Broadband, TV, and Streaming fields;
- edit every choice shown in those dropdowns;
- edit the available currencies;
- choose the default template, currency, and field choices.

Save changes when finished. Each user's changes are stored in:
%LOCALAPPDATA%\OfferTemplates\packages.json

TEMPLATE PARAMETERS
-------------------
Parameters are words inside braces. Put them anywhere in the template text.

{services}
  Inserts all optional services currently added to the main page, joined with
  " + ". This is useful for any Broadband, TV, and Streaming combination.

{broadband}
  Inserts the selected broadband choice.

{broadband_price}
  Inserts the separate broadband price and selected currency.

{broadband2}
  Inserts the Broadband campaign text saved with this template. Removing the
  Broadband field also removes this campaign text from the completed message.

{tv}
  Inserts the selected TV choice.

{tv1}
  Inserts the primary TV offer text saved with this template. For example,
  {tv} can insert "tv mini" while {tv1} inserts the complete offer wording.
  Removing the TV field also removes this text from the completed message.

{tv2}
  Inserts the TV campaign text saved with this template. Removing the TV field
  also removes this campaign text from the completed message.

{streaming}
  Inserts the selected streaming choice.

{package}
  Inserts the package name saved with the selected template. The package name
  is required only when this parameter is used.

{price}
  Inserts the main price and selected currency. The price is required only when
  this parameter is used.

{date}
  Inserts today's date, or the optional date override, as DD/MM/YYYY.

{date+N}
  Adds any whole number of days. Replace N with the number you want. Examples:
  {date+1}, {date+14}, {date+30}, {date+137}, and {date+365}.

{date-N}
  Goes back any whole number of days. For example, {date-14} inserts the date
  from two weeks before the current date or date override.

Templates do not need to contain any parameters. Plain text is copied exactly
as written. If a template contains a parameter, its corresponding value must be
available before the offer can be copied.

EXAMPLE
-------
Template:
We offer {services} for {price}. The offer is valid until {date+30}.

With Broadband and TV added, price 999, currency KR/month, and a date override
of 15/01/2027, the result could be:
We offer 1000/1000 + TV Mini for 999 KR/month. The offer is valid until
14/02/2027.

DISTRIBUTION
------------
Zip OfferTemplates.exe and this README.txt together. The recipient can extract
the two files anywhere and run OfferTemplates.exe directly.
