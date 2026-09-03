from __future__ import annotations

import copy
import ctypes
import json
import os
import re
import shutil
import string
import sys
import tkinter as tk
from ctypes import wintypes
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk


APP_TITLE = "OfferTemplates"
SOURCE_DIR = Path(__file__).resolve().parent
BUNDLED_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR))
BUNDLED_CONFIG_PATH = BUNDLED_DIR / "packages.json"
if os.environ.get("OFFERTEMPLATES_DATA_DIR"):
    DATA_DIR = Path(os.environ["OFFERTEMPLATES_DATA_DIR"])
elif getattr(sys, "frozen", False):
    local_app_data = Path(
        os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    )
    DATA_DIR = local_app_data / APP_TITLE
else:
    DATA_DIR = SOURCE_DIR
CONFIG_PATH = DATA_DIR / "packages.json"
VARIABLE_KEYS = ("broadband", "tv", "streaming")
VARIABLE_LABELS = {
    "broadband": "Broadband",
    "tv": "TV package",
    "streaming": "Streaming package",
}
BROADBAND_PRICE_FIELD = "broadband_price"
CAMPAIGN_FIELDS = {
    "broadband2": ("broadband", "Broadband campaign text"),
    "tv1": ("tv", "TV offer text"),
    "tv2": ("tv", "TV campaign text"),
}
ALLOWED_FIELDS = {
    "package",
    "price",
    "services",
    BROADBAND_PRICE_FIELD,
    *CAMPAIGN_FIELDS,
    *VARIABLE_KEYS,
}
DATE_FIELD_PATTERN = re.compile(r"date(?:([+-]\d+))?\Z")
MAX_DATE_OFFSET_DAYS = 365000
DEFAULT_CURRENCIES = ["€/month", "€", "$/month", "$", "£/month", "£"]
DEFAULT_VARIABLES = {
    "broadband": {
        "label": "Broadband",
        "options": ["1000/1000"],
        "default": "1000/1000",
    },
    "tv": {"label": "TV package", "options": ["TV Mini"], "default": "TV Mini"},
    "streaming": {
        "label": "Streaming package",
        "options": ["Streaming package"],
        "default": "Streaming package",
    },
}
COLORS = {
    "window": "#111419",
    "surface": "#1a1e25",
    "input": "#12161c",
    "raised": "#252b34",
    "border": "#343c47",
    "text": "#f0f2f5",
    "muted": "#98a2af",
    "accent": "#4f8ff7",
    "accent_hover": "#65a0ff",
    "accent_pressed": "#3977dd",
    "success": "#66d19e",
    "error": "#ff818b",
}

_dpi_awareness_requested = False


class ConfigError(ValueError):
    pass


def template_fields(template: str) -> set[str]:
    return {
        field_name
        for _, field_name, _, _ in string.Formatter().parse(template)
        if field_name is not None
    }


def unsupported_template_fields(fields: set[str]) -> set[str]:
    return {
        field
        for field in fields
        if field not in ALLOWED_FIELDS and DATE_FIELD_PATTERN.fullmatch(field) is None
    }


def ensure_user_config(
    path: Path = CONFIG_PATH,
    bundled_path: Path = BUNDLED_CONFIG_PATH,
) -> None:
    if path.exists() or path == bundled_path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundled_path, path)
    except OSError as exc:
        raise ConfigError(f"Could not create the configuration file: {path}") from exc


def validate_packages(packages: object) -> list[dict[str, str]]:
    if not isinstance(packages, list) or not packages:
        raise ConfigError("The configuration must contain at least one package.")

    validated: list[dict[str, str]] = []
    titles: set[str] = set()

    for number, item in enumerate(packages, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"Package {number} is not a valid entry.")

        title = item.get("title")
        template = item.get("template")
        package_name = item.get("package", "")
        if not isinstance(title, str) or not title.strip():
            raise ConfigError(f"Package {number} needs a title.")
        if not isinstance(template, str) or not template.strip():
            raise ConfigError(f"Package {number} needs a template.")
        if not isinstance(package_name, str):
            raise ConfigError(f"Package {number} has an invalid package name.")
        values = {
            "title": title.strip(),
            "package": package_name.strip(),
            "template": template.strip(),
        }
        for field, (_, label) in CAMPAIGN_FIELDS.items():
            campaign_text = item.get(field, "")
            if not isinstance(campaign_text, str):
                raise ConfigError(f"Package {number} has invalid {label.lower()}.")
            if campaign_text.strip():
                values[field] = campaign_text.strip()

        normalized_title = values["title"].casefold()
        if normalized_title in titles:
            raise ConfigError(f'The title "{values["title"]}" is used more than once.')
        titles.add(normalized_title)

        try:
            fields = template_fields(values["template"])
        except ValueError as exc:
            raise ConfigError(f'The template for "{values["title"]}" has invalid braces.') from exc

        unsupported = unsupported_template_fields(fields)
        if unsupported:
            names = ", ".join(sorted(unsupported))
            raise ConfigError(
                f'The template for "{values["title"]}" uses an unknown field: {names}. '
                "Use the fields shown in Edit templates."
            )
        for field in fields:
            date_match = DATE_FIELD_PATTERN.fullmatch(field)
            if (
                date_match
                and abs(int(date_match.group(1) or 0)) > MAX_DATE_OFFSET_DAYS
            ):
                raise ConfigError(
                    f'The date offset in "{{{field}}}" is too large.'
                )
        if "package" in fields and not values["package"]:
            raise ConfigError(
                f'The template for "{values["title"]}" uses {{package}}, '
                "so a package name is required."
            )
        for field, (_, label) in CAMPAIGN_FIELDS.items():
            if field in fields and not values.get(field):
                raise ConfigError(
                    f'The template for "{values["title"]}" uses {{{field}}}, '
                    f"so {label} is required."
                )

        validated.append(values)

    return validated


def validate_currencies(currencies: object) -> list[str]:
    if not isinstance(currencies, list) or not currencies:
        raise ConfigError("The configuration must contain at least one currency.")

    validated: list[str] = []
    seen: set[str] = set()
    for number, currency in enumerate(currencies, start=1):
        if not isinstance(currency, str) or not currency.strip():
            raise ConfigError(f"Currency {number} must be text.")
        currency = currency.strip()
        normalized = currency.casefold()
        if normalized in seen:
            raise ConfigError(f'The currency "{currency}" is used more than once.')
        seen.add(normalized)
        validated.append(currency)
    return validated


def validate_variables(variables: object) -> dict[str, dict[str, object]]:
    if not isinstance(variables, dict):
        raise ConfigError('The configuration needs a "variables" section.')

    validated: dict[str, dict[str, object]] = {}
    labels: set[str] = set()
    for key in VARIABLE_KEYS:
        variable = variables.get(key)
        fallback_label = VARIABLE_LABELS[key]
        if not isinstance(variable, dict):
            raise ConfigError(f"The {fallback_label.lower()} choices are missing.")
        label = variable.get("label", fallback_label)
        if not isinstance(label, str) or not label.strip():
            raise ConfigError(f"The {fallback_label.lower()} field needs a name.")
        label = label.strip()
        normalized_label = label.casefold()
        if normalized_label == "currency" or normalized_label in labels:
            raise ConfigError(f'The field name "{label}" is used more than once.')
        labels.add(normalized_label)
        try:
            options = validate_currencies(variable.get("options"))
        except ConfigError as exc:
            raise ConfigError(f"Invalid {label.lower()} choices: {exc}") from exc
        default = variable.get("default", options[0])
        if default not in options:
            raise ConfigError(f"The default {label.lower()} must match one of its choices.")
        validated[key] = {"label": label, "options": options, "default": default}
    return validated


def load_config(
    path: Path = CONFIG_PATH,
) -> tuple[
    list[dict[str, str]],
    list[str],
    str,
    str,
    dict[str, dict[str, object]],
]:
    if path == CONFIG_PATH:
        ensure_user_config(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration file not found: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Could not read {path.name}: line {exc.lineno} contains invalid JSON.") from exc

    if not isinstance(data, dict) or "packages" not in data:
        raise ConfigError(f'{path.name} must contain a "packages" list.')
    packages = validate_packages(data["packages"])
    currencies = validate_currencies(data.get("currencies", DEFAULT_CURRENCIES))
    variables = validate_variables(data.get("variables", copy.deepcopy(DEFAULT_VARIABLES)))
    default_package = data.get("default_package", packages[0]["title"])
    default_currency = data.get("default_currency", currencies[0])
    if default_package not in [item["title"] for item in packages]:
        raise ConfigError("The default package must match one of the package titles.")
    if default_currency not in currencies:
        raise ConfigError("The default currency must match one of the currencies.")
    return packages, currencies, default_package, default_currency, variables


def load_packages(path: Path = CONFIG_PATH) -> list[dict[str, str]]:
    return load_config(path)[0]


def save_config(
    packages: list[dict[str, str]],
    currencies: list[str],
    path: Path = CONFIG_PATH,
    default_package: str | None = None,
    default_currency: str | None = None,
    variables: dict[str, dict[str, object]] | None = None,
) -> None:
    validated_packages = validate_packages(packages)
    validated_currencies = validate_currencies(currencies)
    validated_variables = validate_variables(
        copy.deepcopy(DEFAULT_VARIABLES) if variables is None else variables
    )
    if default_package is None:
        default_package = validated_packages[0]["title"]
    if default_currency is None:
        default_currency = validated_currencies[0]
    if default_package not in [item["title"] for item in validated_packages]:
        raise ConfigError("Choose a valid default package.")
    if default_currency not in validated_currencies:
        raise ConfigError("Choose a valid default currency.")
    content = json.dumps(
        {
            "default_package": default_package,
            "default_currency": default_currency,
            "currencies": validated_currencies,
            "variables": validated_variables,
            "packages": validated_packages,
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


def save_packages(packages: list[dict[str, str]], path: Path = CONFIG_PATH) -> None:
    try:
        _, currencies, default_package, default_currency, variables = load_config(path)
    except ConfigError:
        currencies = list(DEFAULT_CURRENCIES)
        default_package = packages[0]["title"]
        default_currency = currencies[0]
        variables = copy.deepcopy(DEFAULT_VARIABLES)
    save_config(
        packages,
        currencies,
        path,
        default_package=default_package,
        default_currency=default_currency,
        variables=variables,
    )


def render_offer(
    package: dict[str, str],
    price: str,
    currency: str = "",
    selections: dict[str, str] | None = None,
    broadband_price: str = "",
    active_variables: set[str] | None = None,
    today: date | None = None,
    date_override: str = "",
) -> str:
    template = package.get("template", "")
    try:
        fields = template_fields(template)
    except ValueError as exc:
        raise ConfigError("This template has invalid braces.") from exc

    unsupported = unsupported_template_fields(fields)
    if unsupported:
        raise ConfigError(
            "This template could not be filled in. Check the available fields in Edit templates."
        )

    package_name = package.get("package", "").strip()
    formatted_price = price.strip()
    formatted_broadband_price = broadband_price.strip()
    selected_values = selections or {}
    active = set(VARIABLE_KEYS) if active_variables is None else active_variables
    if "package" in fields and not package_name:
        raise ConfigError(
            "This template uses {package}, so add a package name in Edit templates."
        )
    if "price" in fields and not formatted_price:
        raise ConfigError("Enter a price first.")
    if (
        BROADBAND_PRICE_FIELD in fields
        and "broadband" in active
        and not formatted_broadband_price
    ):
        raise ConfigError("Enter a broadband price first.")
    if formatted_price and currency.strip():
        formatted_price = f"{formatted_price} {currency.strip()}"
    if formatted_broadband_price and currency.strip():
        formatted_broadband_price = (
            f"{formatted_broadband_price} {currency.strip()}"
        )
    replacements = {
        "package": package_name,
        "price": formatted_price,
        "services": " + ".join(
            selected_values.get(key, "").strip()
            for key in VARIABLE_KEYS
            if key in active and selected_values.get(key, "").strip()
        ),
        BROADBAND_PRICE_FIELD: (
            formatted_broadband_price if "broadband" in active else ""
        ),
    }
    for field, (variable_key, label) in CAMPAIGN_FIELDS.items():
        campaign_text = package.get(field, "").strip()
        if field in fields and not campaign_text:
            raise ConfigError(
                f"This template uses {{{field}}}, so add {label} in Edit templates."
            )
        replacements[field] = campaign_text if variable_key in active else ""
    date_fields = [field for field in fields if DATE_FIELD_PATTERN.fullmatch(field)]
    current_date = today or date.today()
    entered_date = date_override.strip()
    if date_fields and entered_date:
        try:
            current_date = datetime.strptime(entered_date, "%d/%m/%Y").date()
        except ValueError as exc:
            raise ConfigError("Enter the date as DD/MM/YYYY.") from exc
        if current_date.strftime("%d/%m/%Y") != entered_date:
            raise ConfigError("Enter the date as DD/MM/YYYY.")
    for field in fields:
        date_match = DATE_FIELD_PATTERN.fullmatch(field)
        if date_match is None:
            continue
        offset = int(date_match.group(1) or 0)
        if abs(offset) > MAX_DATE_OFFSET_DAYS:
            raise ConfigError(f'The date offset in "{{{field}}}" is too large.')
        try:
            replacements[field] = (current_date + timedelta(days=offset)).strftime(
                "%d/%m/%Y"
            )
        except OverflowError as exc:
            raise ConfigError(f'The date offset in "{{{field}}}" is too large.') from exc
    for key in VARIABLE_KEYS:
        value = selected_values.get(key, "").strip()
        if key in fields and key in active and not value:
            raise ConfigError(f"Choose a {VARIABLE_LABELS[key].lower()} first.")
        replacements[key] = value if key in active else ""
    try:
        return template.format(**replacements)
    except (KeyError, ValueError) as exc:
        raise ConfigError(
            "This template could not be filled in. Check the available fields in Edit templates."
        ) from exc


def enable_dpi_awareness() -> None:
    global _dpi_awareness_requested
    if _dpi_awareness_requested or sys.platform != "win32":
        return
    _dpi_awareness_requested = True

    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass

    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return
    except (AttributeError, OSError):
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def get_primary_dpi(window: tk.Misc) -> int:
    if sys.platform == "win32":
        try:
            return max(96, int(ctypes.windll.user32.GetDpiForSystem()))
        except (AttributeError, OSError):
            pass
    return max(96, round(window.winfo_fpixels("1i")))


def get_primary_work_area(window: tk.Misc) -> tuple[int, int, int, int]:
    if sys.platform == "win32":
        try:
            rect = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(
                0x0030, 0, ctypes.byref(rect), 0
            ):
                return rect.left, rect.top, rect.right, rect.bottom
        except (AttributeError, OSError):
            pass
    return 0, 0, window.winfo_screenwidth(), window.winfo_screenheight()


def centered_geometry(
    work_area: tuple[int, int, int, int],
    width: int,
    height: int,
    margin: int,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = work_area
    available_width = max(1, right - left)
    available_height = max(1, bottom - top)
    width = min(width, max(1, available_width - margin * 2))
    height = min(height, max(1, available_height - margin * 2))
    x = left + (available_width - width) // 2
    y = top + (available_height - height) // 2
    return width, height, x, y


def get_outer_window_rect(window: tk.Misc) -> tuple[int, int, int, int] | None:
    if sys.platform != "win32":
        return None
    try:
        hwnd = ctypes.windll.user32.GetAncestor(window.winfo_id(), 2)
        rect = wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return rect.left, rect.top, rect.right, rect.bottom
    except (AttributeError, OSError, tk.TclError):
        pass
    return None


def center_window(window: tk.Toplevel | tk.Tk, parent: tk.Misc | None = None) -> None:
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    work_area = get_primary_work_area(window)
    margin = max(16, round(24 * getattr(window, "ui_scale", 1.0)))

    if parent is None:
        width, height, x, y = centered_geometry(work_area, width, height, margin)
    else:
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        left, top, right, bottom = work_area
        x = min(max(left + margin, x), max(left + margin, right - width - margin))
        y = min(max(top + margin, y), max(top + margin, bottom - height - margin))
    window.geometry(f"{width}x{height}+{x}+{y}")
    window.update_idletasks()

    outer_rect = get_outer_window_rect(window)
    if outer_rect is None:
        return
    if parent is None:
        target_x = (work_area[0] + work_area[2]) // 2
        target_y = (work_area[1] + work_area[3]) // 2
    else:
        parent_rect = get_outer_window_rect(parent)
        if parent_rect is None:
            return
        target_x = (parent_rect[0] + parent_rect[2]) // 2
        target_y = (parent_rect[1] + parent_rect[3]) // 2
    actual_x = (outer_rect[0] + outer_rect[2]) // 2
    actual_y = (outer_rect[1] + outer_rect[3]) // 2
    x += target_x - actual_x
    y += target_y - actual_y
    window.geometry(f"{width}x{height}+{x}+{y}")


def use_dark_title_bar(window: tk.Misc) -> None:
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetAncestor(window.winfo_id(), 2)
        enabled = ctypes.c_int(1)
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(enabled), ctypes.sizeof(enabled)
        )
        if result != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 19, ctypes.byref(enabled), ctypes.sizeof(enabled)
            )
    except (AttributeError, OSError, tk.TclError):
        pass


class Dropdown(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        variable: tk.StringVar,
        scale: float,
        on_change=None,
    ) -> None:
        border = max(1, round(scale))
        super().__init__(
            parent,
            background=COLORS["input"],
            highlightthickness=border,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
            takefocus=0,
        )
        self.variable = variable
        self.on_change = on_change
        self.ui_scale = scale
        self.items: list[str] = []
        self.popup: tk.Toplevel | None = None
        self.popup_list: tk.Listbox | None = None
        self.owner = self.winfo_toplevel()

        button_options = {
            "command": self.open_menu,
            "relief": "flat",
            "overrelief": "flat",
            "borderwidth": 0,
            "background": COLORS["input"],
            "foreground": COLORS["text"],
            "activebackground": COLORS["raised"],
            "activeforeground": COLORS["text"],
            "font": ("Segoe UI", 10),
            "cursor": "arrow",
        }
        self.label_button = tk.Button(
            self,
            textvariable=variable,
            anchor="w",
            padx=round(10 * scale),
            pady=round(7 * scale),
            takefocus=True,
            **button_options,
        )
        self.label_button.grid(row=0, column=0, sticky="nsew")
        self.arrow_button = tk.Button(
            self,
            text="▾",
            width=1,
            padx=0,
            pady=round(7 * scale),
            takefocus=False,
            **button_options,
        )
        self.arrow_button.configure(font=("Segoe UI Semibold", 11))
        self.arrow_button.grid(row=0, column=1, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, minsize=round(46 * scale))

        for button in (self.label_button, self.arrow_button):
            button.bind("<Return>", self.open_menu)
            button.bind("<space>", self.open_menu)
            button.bind("<Down>", self.open_menu)
            button.bind("<FocusIn>", self._focus_in)
            button.bind("<FocusOut>", self._focus_out)
        self.owner.bind("<ButtonPress-1>", self._owner_clicked, add="+")

    def _contains_widget(self, widget: tk.Misc | None) -> bool:
        while widget is not None:
            if widget is self:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _owner_clicked(self, event: tk.Event) -> None:
        if self._contains_widget(event.widget):
            return

        self.configure(highlightbackground=COLORS["border"])
        focused = self.owner.focus_get()
        if self._contains_widget(focused):
            try:
                event.widget.focus_set()
            except tk.TclError:
                self.owner.focus_set()

    def set_items(self, items: list[str]) -> None:
        self.items = list(items)
        if self.variable.get() not in self.items and self.items:
            self.variable.set(self.items[0])

    def _select(self, value: str) -> None:
        self.variable.set(value)
        if self.on_change is not None:
            self.on_change()

    def open_menu(self, _event: tk.Event | None = None) -> str:
        if not self.items:
            return "break"
        if self.popup is not None and self.popup.winfo_exists():
            self.close_menu()
            return "break"

        self.update_idletasks()
        popup = tk.Toplevel(self)
        popup.withdraw()
        popup.overrideredirect(True)
        popup.transient(self.winfo_toplevel())
        popup.configure(background=COLORS["border"])
        self.popup = popup

        visible_items = min(len(self.items), 9)
        listbox = tk.Listbox(
            popup,
            height=visible_items,
            activestyle="none",
            exportselection=False,
            relief="flat",
            borderwidth=0,
            highlightthickness=max(1, round(self.ui_scale)),
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["border"],
            background=COLORS["raised"],
            foreground=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            font=("Segoe UI", 10),
        )
        self.popup_list = listbox
        listbox.grid(row=0, column=0, sticky="nsew")
        popup.columnconfigure(0, weight=1)
        popup.rowconfigure(0, weight=1)
        for item in self.items:
            listbox.insert(tk.END, item)

        try:
            selected = self.items.index(self.variable.get())
        except ValueError:
            selected = 0
        listbox.selection_set(selected)
        listbox.activate(selected)
        listbox.see(selected)

        listbox.bind("<ButtonRelease-1>", self._choose_item)
        listbox.bind("<Motion>", self._highlight_hovered_item)
        listbox.bind("<Leave>", self._restore_selected_item)
        listbox.bind("<Return>", self._choose_item)
        listbox.bind("<Escape>", lambda _event: self.close_menu())
        listbox.bind("<MouseWheel>", self._scroll_menu)
        popup.bind(
            "<ButtonRelease-1>",
            lambda event: self.close_menu() if event.widget is popup else None,
        )
        popup.bind("<Escape>", lambda _event: self.close_menu())
        popup.bind("<FocusOut>", self._close_if_focus_left)

        popup.update_idletasks()
        popup_width = self.winfo_width()
        popup_height = popup.winfo_reqheight()
        left, top, right, bottom = get_primary_work_area(self)
        x = min(max(left, self.winfo_rootx()), max(left, right - popup_width))
        below = self.winfo_rooty() + self.winfo_height()
        y = below if below + popup_height <= bottom else self.winfo_rooty() - popup_height
        y = min(max(top, y), max(top, bottom - popup_height))
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        popup.deiconify()
        popup.lift()
        popup.focus_force()
        listbox.focus_set()
        self.arrow_button.configure(text="▴")
        return "break"

    def _choose_item(self, event: tk.Event) -> str:
        if self.popup_list is None:
            return "break"
        selection = self.popup_list.curselection()
        if selection:
            self._select(self.items[selection[0]])
        self.close_menu()
        return "break"

    def _scroll_menu(self, event: tk.Event) -> str:
        if self.popup_list is not None:
            self.popup_list.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _highlight_hovered_item(self, event: tk.Event) -> None:
        if self.popup_list is None:
            return
        index = self.popup_list.nearest(event.y)
        bounds = self.popup_list.bbox(index)
        if bounds is None or not (bounds[1] <= event.y < bounds[1] + bounds[3]):
            return
        self.popup_list.selection_clear(0, tk.END)
        self.popup_list.selection_set(index)
        self.popup_list.activate(index)

    def _restore_selected_item(self, _event: tk.Event) -> None:
        if self.popup_list is None:
            return
        try:
            selected = self.items.index(self.variable.get())
        except ValueError:
            selected = 0
        self.popup_list.selection_clear(0, tk.END)
        self.popup_list.selection_set(selected)
        self.popup_list.activate(selected)

    def _close_if_focus_left(self, _event: tk.Event) -> None:
        popup = self.popup
        if popup is None:
            return

        def check_focus() -> None:
            if self.popup is not popup or not popup.winfo_exists():
                return
            focused = popup.focus_get()
            if focused is None or focused.winfo_toplevel() is not popup:
                self.close_menu(restore_focus=False)

        popup.after_idle(check_focus)

    def close_menu(self, restore_focus: bool = True) -> str:
        popup = self.popup
        self.popup = None
        self.popup_list = None
        self.arrow_button.configure(text="▾")
        if popup is not None and popup.winfo_exists():
            popup.destroy()
        if restore_focus:
            owner = self.winfo_toplevel()

            def restore_owner_focus() -> None:
                if not owner.winfo_exists():
                    return
                owner.focus_force()
                self.label_button.focus_set()

            owner.after_idle(restore_owner_focus)
        return "break"

    def _focus_in(self, _event: tk.Event) -> None:
        self.configure(highlightbackground=COLORS["accent"])

    def _focus_out(self, _event: tk.Event) -> None:
        self.configure(highlightbackground=COLORS["border"])


class TemplateEditor(tk.Toplevel):
    def __init__(self, parent: "OfferApp") -> None:
        super().__init__(parent)
        self.withdraw()
        self.parent = parent
        self.ui_scale = parent.ui_scale
        s = parent.px
        self.items = copy.deepcopy(parent.packages)
        self.currencies = list(parent.currencies)
        self.variable_options = {
            key: list(parent.variables[key]["options"]) for key in VARIABLE_KEYS
        }
        self.variable_names = {
            key: str(parent.variables[key]["label"]) for key in VARIABLE_KEYS
        }
        self.current_index: int | None = None
        self.current_value_index: int | None = None
        self.current_value_group = "currency"
        self.loading = False
        self.default_package_var = tk.StringVar(value=parent.default_package)
        self.default_value_vars = {
            "currency": tk.StringVar(value=parent.default_currency),
            **{
                key: tk.StringVar(value=str(parent.variables[key]["default"]))
                for key in VARIABLE_KEYS
            },
        }

        self.title("Edit OfferTemplates")
        self.geometry(f"{s(1000)}x{s(740)}")
        self.minsize(s(850), s(650))
        self.configure(background=COLORS["window"])
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        shell = ttk.Frame(
            self,
            style="Shell.TFrame",
            padding=(s(20), s(18), s(20), s(18)),
        )
        shell.grid(row=0, column=0, sticky="nsew", padx=s(14), pady=s(14))
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        ttk.Label(shell, text="Edit OfferTemplates", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, s(13))
        )

        self.notebook = ttk.Notebook(shell)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        templates_tab = ttk.Frame(
            self.notebook, style="Shell.TFrame", padding=s(16)
        )
        settings_tab = ttk.Frame(
            self.notebook, style="Shell.TFrame", padding=s(16)
        )
        self.notebook.add(templates_tab, text="Templates")
        self.notebook.add(settings_tab, text="Fields, choices & defaults")

        templates_tab.columnconfigure(1, weight=1)
        templates_tab.rowconfigure(0, weight=1)
        sidebar = ttk.Frame(templates_tab, style="Shell.TFrame")
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, s(18)))
        sidebar.rowconfigure(1, weight=1)

        ttk.Label(sidebar, text="Your templates", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, s(10))
        )
        self.listbox = tk.Listbox(
            sidebar,
            width=25,
            activestyle="none",
            exportselection=False,
            relief="flat",
            borderwidth=0,
            highlightthickness=s(1),
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
            background=COLORS["input"],
            foreground=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            font=("Segoe UI", 10),
        )
        self.listbox.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        ttk.Button(sidebar, text="Add", command=self._add).grid(
            row=2, column=0, sticky="ew", pady=(s(10), 0), padx=(0, s(4))
        )
        ttk.Button(sidebar, text="Delete", command=self._delete).grid(
            row=2, column=1, sticky="ew", pady=(s(10), 0), padx=(s(4), 0)
        )

        form = ttk.Frame(
            templates_tab,
            style="Shell.TFrame",
        )
        form.grid(row=0, column=1, sticky="nsew")
        form.columnconfigure(0, weight=1)
        form.rowconfigure(6, weight=1)

        ttk.Label(form, text="Template details", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, s(12))
        )
        ttk.Label(form, text="Menu title").grid(row=1, column=0, sticky="w")
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(form, textvariable=self.title_var)
        self.title_entry.grid(row=2, column=0, sticky="ew", pady=(s(5), s(12)))
        self.title_entry.bind("<FocusOut>", self._template_focus_out)

        ttk.Label(form, text="Package name (needed only for {package})").grid(
            row=3, column=0, sticky="w"
        )
        self.package_var = tk.StringVar()
        self.package_entry = ttk.Entry(form, textvariable=self.package_var)
        self.package_entry.grid(row=4, column=0, sticky="ew", pady=(s(5), s(12)))

        ttk.Label(form, text="Template content").grid(row=5, column=0, sticky="w")
        content_tabs = ttk.Notebook(form)
        content_tabs.grid(row=6, column=0, sticky="nsew", pady=(s(5), 0))

        message_tab = ttk.Frame(content_tabs, style="Shell.TFrame", padding=s(10))
        message_tab.columnconfigure(0, weight=1)
        message_tab.rowconfigure(1, weight=1)
        content_tabs.add(message_tab, text="Message")
        ttk.Label(
            message_tab,
            text=(
                "Fields: {services}, {broadband}, {broadband_price}, {tv}, "
                "{streaming}, {package}, and {price}. Saved text: "
                "{broadband2}, {tv1}, and {tv2}. Dates: {date}, {date+N}, "
                "or {date-N}."
            ),
            style="Hint.TLabel",
            wraplength=s(380),
        ).grid(row=0, column=0, sticky="w", pady=(0, s(8)))
        self.template_text = self._create_text_editor(message_tab)
        self.template_text.grid(row=1, column=0, sticky="nsew")

        self.campaign_texts: dict[str, tk.Text] = {}
        for field, (_, label) in CAMPAIGN_FIELDS.items():
            campaign_tab = ttk.Frame(
                content_tabs, style="Shell.TFrame", padding=s(10)
            )
            campaign_tab.columnconfigure(0, weight=1)
            campaign_tab.rowconfigure(1, weight=1)
            content_tabs.add(campaign_tab, text=f"{{{field}}}")
            ttk.Label(
                campaign_tab,
                text=(
                    f"Inserted by {{{field}}} when the matching service is included. "
                    "It does not add an editable field to the main window."
                ),
                style="Hint.TLabel",
                wraplength=s(380),
            ).grid(row=0, column=0, sticky="w", pady=(0, s(8)))
            editor = self._create_text_editor(campaign_tab)
            editor.grid(row=1, column=0, sticky="nsew")
            self.campaign_texts[field] = editor

        settings_tab.columnconfigure(0, weight=3)
        settings_tab.columnconfigure(1, weight=2)
        settings_tab.rowconfigure(0, weight=1)
        values = ttk.Frame(settings_tab, style="Shell.TFrame")
        values.grid(row=0, column=0, sticky="nsew", padx=(0, s(24)))
        values.columnconfigure(0, weight=1)
        values.rowconfigure(6, weight=1)

        ttk.Label(values, text="Fields and choices", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            values,
            text="Rename a field or change the choices shown in its dropdown.",
            style="Hint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(s(3), s(10)))
        self.value_group_var = tk.StringVar(value="Currency")
        self.value_group_dropdown = Dropdown(
            values,
            variable=self.value_group_var,
            scale=self.ui_scale,
            on_change=self._on_value_group_changed,
        )
        self.value_group_dropdown.grid(row=2, column=0, sticky="ew")

        self.field_name_frame = ttk.Frame(values, style="Shell.TFrame")
        self.field_name_frame.grid(row=3, column=0, sticky="ew", pady=(s(12), 0))
        self.field_name_frame.columnconfigure(0, weight=1)
        ttk.Label(self.field_name_frame, text="Field name").grid(
            row=0, column=0, sticky="w"
        )
        self.field_name_var = tk.StringVar()
        self.field_name_entry = ttk.Entry(
            self.field_name_frame, textvariable=self.field_name_var
        )
        self.field_name_entry.grid(row=1, column=0, sticky="ew", pady=(s(5), 0))
        self.field_name_entry.bind("<FocusOut>", self._field_name_focus_out)
        self.field_token_var = tk.StringVar()
        ttk.Label(
            self.field_name_frame,
            textvariable=self.field_token_var,
            style="Hint.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(s(4), 0))

        ttk.Label(values, text="Choices").grid(
            row=4, column=0, sticky="w", pady=(s(13), s(5))
        )
        self.value_listbox = tk.Listbox(
            values,
            height=9,
            activestyle="none",
            exportselection=False,
            relief="flat",
            borderwidth=0,
            highlightthickness=s(1),
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
            background=COLORS["input"],
            foreground=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            font=("Segoe UI", 10),
        )
        self.value_listbox.grid(row=6, column=0, sticky="nsew")
        self.value_listbox.bind("<<ListboxSelect>>", self._on_value_select)
        ttk.Label(values, text="Selected choice", style="Hint.TLabel").grid(
            row=7, column=0, sticky="w", pady=(s(9), s(5))
        )
        self.value_edit_var = tk.StringVar()
        self.value_entry = ttk.Entry(values, textvariable=self.value_edit_var)
        self.value_entry.grid(row=8, column=0, sticky="ew")
        self.value_entry.bind("<FocusOut>", self._value_focus_out)
        value_actions = ttk.Frame(values, style="Shell.TFrame")
        value_actions.grid(row=9, column=0, sticky="w", pady=(s(9), 0))
        ttk.Button(value_actions, text="Add choice", command=self._add_value).grid(
            row=0, column=0, padx=(0, s(8))
        )
        ttk.Button(
            value_actions, text="Delete choice", command=self._delete_value
        ).grid(row=0, column=1)

        defaults = ttk.Frame(settings_tab, style="Shell.TFrame")
        defaults.grid(row=0, column=1, sticky="nsew")
        defaults.columnconfigure(0, weight=1)
        ttk.Label(defaults, text="Startup defaults", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            defaults,
            text="These values are selected when the app opens.",
            style="Hint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(s(3), s(12)))
        default_specs = [
            ("Default template", "template", self.default_package_var),
            ("Default currency", "currency", self.default_value_vars["currency"]),
            *[
                (
                    f"Default {self.variable_names[key]}",
                    key,
                    self.default_value_vars[key],
                )
                for key in VARIABLE_KEYS
            ],
        ]
        self.default_dropdowns: dict[str, Dropdown] = {}
        self.default_name_vars: dict[str, tk.StringVar] = {}
        for index, (label, key, variable) in enumerate(default_specs, start=2):
            label_var = tk.StringVar(value=label)
            ttk.Label(defaults, textvariable=label_var).grid(
                row=index * 2, column=0, sticky="w", pady=(s(2), 0)
            )
            dropdown = Dropdown(defaults, variable, self.ui_scale)
            dropdown.grid(
                row=index * 2 + 1,
                column=0,
                sticky="ew",
                pady=(s(5), s(8)),
            )
            self.default_dropdowns[key] = dropdown
            self.default_name_vars[key] = label_var

        actions = ttk.Frame(shell, style="Shell.TFrame")
        actions.grid(row=2, column=0, sticky="e", pady=(s(14), 0))
        ttk.Button(actions, text="Cancel", command=self.destroy).grid(
            row=0, column=0, padx=(0, s(8))
        )
        ttk.Button(
            actions,
            text="Save changes",
            style="Accent.TButton",
            command=self._save,
        ).grid(row=0, column=1)

        self._refresh_list()
        self.listbox.selection_set(0)
        self._load_item(0)
        self._refresh_value_list()
        self.value_listbox.selection_set(0)
        self._load_value(0)
        self._refresh_value_group_items()
        self._load_field_name()
        self._refresh_default_options()
        center_window(self, parent)
        use_dark_title_bar(self)
        self.deiconify()
        self.lift()
        self.after(10, lambda: use_dark_title_bar(self))
        self.after_idle(self._activate_editor)

    def _create_text_editor(self, parent: tk.Misc) -> tk.Text:
        s = self.parent.px
        return tk.Text(
            parent,
            height=9,
            wrap="word",
            undo=True,
            relief="flat",
            borderwidth=0,
            highlightthickness=s(1),
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
            background=COLORS["input"],
            foreground=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            padx=s(10),
            pady=s(9),
            font=("Segoe UI", 10),
        )

    def _activate_editor(self) -> None:
        if self.winfo_exists():
            self.focus_force()
            self.title_entry.focus_set()

    def _refresh_list(self) -> None:
        selected = self.current_index
        self.listbox.delete(0, tk.END)
        for item in self.items:
            self.listbox.insert(tk.END, item["title"] or "Untitled template")
        if selected is not None and selected < len(self.items):
            self.listbox.selection_set(selected)

    def _store_current(self) -> None:
        if self.current_index is None or self.loading:
            return
        old_title = self.items[self.current_index]["title"]
        new_title = self.title_var.get().strip()
        self.items[self.current_index] = {
            "title": new_title,
            "package": self.package_var.get().strip(),
            "template": self.template_text.get("1.0", "end-1c").strip(),
            **{
                field: editor.get("1.0", "end-1c").strip()
                for field, editor in self.campaign_texts.items()
                if editor.get("1.0", "end-1c").strip()
            },
        }
        if self.default_package_var.get() == old_title:
            self.default_package_var.set(new_title)

    def _template_focus_out(self, _event: tk.Event) -> None:
        self._store_current()
        self._refresh_list()
        self._refresh_default_options()

    def _load_item(self, index: int) -> None:
        self.loading = True
        self.current_index = index
        item = self.items[index]
        self.title_var.set(item["title"])
        self.package_var.set(item["package"])
        self.template_text.delete("1.0", tk.END)
        self.template_text.insert("1.0", item["template"])
        for field, editor in self.campaign_texts.items():
            editor.delete("1.0", tk.END)
            editor.insert("1.0", item.get(field, ""))
        self.loading = False

    def _on_select(self, _event: tk.Event) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        new_index = selection[0]
        if new_index == self.current_index:
            return
        self._store_current()
        self._refresh_list()
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(new_index)
        self._load_item(new_index)
        self._refresh_default_options()

    def _add(self) -> None:
        self._store_current()
        number = len(self.items) + 1
        self.items.append(
            {
                "title": f"New template {number}",
                "package": "",
                "template": (
                    "We would like to offer you {services} for {price}."
                ),
            }
        )
        self.current_index = len(self.items) - 1
        self._refresh_list()
        self.listbox.see(self.current_index)
        self._load_item(self.current_index)
        self._refresh_default_options()
        self.title_entry.focus_set()
        self.title_entry.select_range(0, tk.END)

    def _delete(self) -> None:
        if self.current_index is None:
            return
        if len(self.items) == 1:
            messagebox.showinfo(
                "Keep one template", "At least one template is required.", parent=self
            )
            return
        title = self.items[self.current_index]["title"] or "this template"
        if not messagebox.askyesno("Delete template", f'Delete "{title}"?', parent=self):
            return
        deleted_title = self.items[self.current_index]["title"]
        del self.items[self.current_index]
        if self.default_package_var.get() == deleted_title:
            self.default_package_var.set(self.items[0]["title"])
        self.current_index = min(self.current_index, len(self.items) - 1)
        self._refresh_list()
        self._load_item(self.current_index)
        self._refresh_default_options()

    def _value_group_label(self, key: str) -> str:
        if key == "currency":
            return "Currency"
        return self.variable_names[key] or VARIABLE_LABELS[key]

    def _refresh_value_group_items(self) -> None:
        items = [self._value_group_label("currency")]
        items.extend(self._value_group_label(key) for key in VARIABLE_KEYS)
        self.value_group_dropdown.set_items(items)
        self.value_group_var.set(self._value_group_label(self.current_value_group))

    def _load_field_name(self) -> None:
        if self.current_value_group == "currency":
            self.field_name_frame.grid_remove()
            return
        self.field_name_frame.grid()
        self.field_name_var.set(self.variable_names[self.current_value_group])
        self.field_token_var.set(
            f"Use {{{self.current_value_group}}} in a message template."
        )

    def _store_field_name(self) -> None:
        if self.current_value_group == "currency" or self.loading:
            return
        self.variable_names[self.current_value_group] = self.field_name_var.get().strip()
        self.default_name_vars[self.current_value_group].set(
            f"Default {self._value_group_label(self.current_value_group)}"
        )

    def _field_name_focus_out(self, _event: tk.Event) -> None:
        self._store_field_name()
        self._refresh_value_group_items()

    def _current_values(self) -> list[str]:
        if self.current_value_group == "currency":
            return self.currencies
        return self.variable_options[self.current_value_group]

    def _refresh_value_list(self) -> None:
        selected = self.current_value_index
        self.value_listbox.delete(0, tk.END)
        for value in self._current_values():
            self.value_listbox.insert(tk.END, value or "Untitled value")
        if selected is not None and selected < len(self._current_values()):
            self.value_listbox.selection_set(selected)

    def _store_value(self) -> None:
        values = self._current_values()
        if self.current_value_index is None or self.loading:
            return
        old_value = values[self.current_value_index]
        new_value = self.value_edit_var.get().strip()
        values[self.current_value_index] = new_value
        default_var = self.default_value_vars[self.current_value_group]
        if default_var.get() == old_value:
            default_var.set(new_value)

    def _load_value(self, index: int) -> None:
        self.loading = True
        self.current_value_index = index
        self.value_edit_var.set(self._current_values()[index])
        self.loading = False

    def _value_focus_out(self, _event: tk.Event) -> None:
        self._store_value()
        self._refresh_value_list()
        self._refresh_default_options()

    def _on_value_group_changed(self) -> None:
        self._store_value()
        self._store_field_name()
        selected_label = self.value_group_var.get()
        matching_key = next(
            (
                key
                for key in ("currency", *VARIABLE_KEYS)
                if self._value_group_label(key) == selected_label
            ),
            None,
        )
        if matching_key is None:
            return
        self.current_value_group = matching_key
        self.current_value_index = 0
        self._refresh_value_list()
        self.value_listbox.selection_set(0)
        self._load_value(0)
        self._load_field_name()

    def _on_value_select(self, _event: tk.Event) -> None:
        selection = self.value_listbox.curselection()
        if not selection:
            return
        new_index = selection[0]
        if new_index == self.current_value_index:
            return
        self._store_value()
        self._refresh_value_list()
        self.value_listbox.selection_clear(0, tk.END)
        self.value_listbox.selection_set(new_index)
        self._load_value(new_index)
        self._refresh_default_options()

    def _add_value(self) -> None:
        self._store_value()
        values = self._current_values()
        base = f"New {self._value_group_label(self.current_value_group).lower()}"
        value = base
        number = 2
        while value.casefold() in {item.casefold() for item in values}:
            value = f"{base} {number}"
            number += 1
        values.append(value)
        self.current_value_index = len(values) - 1
        self._refresh_value_list()
        self.value_listbox.see(self.current_value_index)
        self._load_value(self.current_value_index)
        self._refresh_default_options()
        self.value_entry.focus_set()
        self.value_entry.select_range(0, tk.END)

    def _delete_value(self) -> None:
        values = self._current_values()
        if self.current_value_index is None:
            return
        label = self._value_group_label(self.current_value_group).lower()
        if len(values) == 1:
            messagebox.showinfo(
                "Keep one value", f"At least one {label} value is required.", parent=self
            )
            return
        value = values[self.current_value_index]
        if not messagebox.askyesno("Delete value", f'Delete "{value}"?', parent=self):
            return
        del values[self.current_value_index]
        default_var = self.default_value_vars[self.current_value_group]
        if default_var.get() == value:
            default_var.set(values[0])
        self.current_value_index = min(self.current_value_index, len(values) - 1)
        self._refresh_value_list()
        self._load_value(self.current_value_index)
        self._refresh_default_options()

    def _refresh_default_options(self) -> None:
        package_titles = [item["title"] for item in self.items if item["title"]]
        if len(package_titles) == len(self.items):
            self.default_dropdowns["template"].set_items(package_titles)
        for key in ("currency", *VARIABLE_KEYS):
            values = self.currencies if key == "currency" else self.variable_options[key]
            if values and all(values):
                self.default_dropdowns[key].set_items(values)

    def _variables_for_save(self) -> dict[str, dict[str, object]]:
        return {
            key: {
                "label": self.variable_names[key],
                "options": self.variable_options[key],
                "default": self.default_value_vars[key].get(),
            }
            for key in VARIABLE_KEYS
        }

    def _save(self) -> None:
        self._store_current()
        self._store_value()
        self._store_field_name()
        variables = self._variables_for_save()
        try:
            save_config(
                self.items,
                self.currencies,
                CONFIG_PATH,
                default_package=self.default_package_var.get(),
                default_currency=self.default_value_vars["currency"].get(),
                variables=variables,
            )
        except (ConfigError, OSError) as exc:
            messagebox.showerror("Could not save", str(exc), parent=self)
            return
        self.parent.set_config(
            validate_packages(self.items),
            validate_currencies(self.currencies),
            self.default_package_var.get(),
            self.default_value_vars["currency"].get(),
            validate_variables(variables),
        )
        self.parent.set_status("Templates saved.", "success")
        self.destroy()


class OfferApp(tk.Tk):
    def __init__(self) -> None:
        enable_dpi_awareness()
        super().__init__()
        self.withdraw()
        primary_dpi = get_primary_dpi(self)
        self.ui_scale = primary_dpi / 96
        self.tk.call("tk", "scaling", primary_dpi / 72)
        self.title(APP_TITLE)
        self.geometry(f"{self.px(620)}x{self.px(840)}")
        work_left, work_top, work_right, work_bottom = get_primary_work_area(self)
        self.minsize(
            min(self.px(540), round((work_right - work_left) * 0.85)),
            min(self.px(600), round((work_bottom - work_top) * 0.85)),
        )
        self.configure(background=COLORS["window"])
        self._configure_style()

        try:
            (
                self.packages,
                self.currencies,
                self.default_package,
                self.default_currency,
                self.variables,
            ) = load_config()
            initial_status = ""
        except ConfigError as exc:
            self.packages = [
                {
                    "title": "Example package",
                    "package": "Example TV package",
                    "template": "Hi! We would like to offer you {package} for a discounted price of {price}.",
                }
            ]
            self.currencies = list(DEFAULT_CURRENCIES)
            self.default_package = self.packages[0]["title"]
            self.default_currency = self.currencies[0]
            self.variables = copy.deepcopy(DEFAULT_VARIABLES)
            initial_status = str(exc)
            error_message = str(exc)
            self.after(
                100,
                lambda message=error_message: messagebox.showerror(
                    "Configuration problem", message, parent=self
                ),
            )

        self.package_title = tk.StringVar(value=self.default_package)
        self.price = tk.StringVar()
        self.broadband_price = tk.StringVar()
        self.date_override = tk.StringVar()
        self.currency = tk.StringVar(value=self.default_currency)
        self.selection_vars = {
            key: tk.StringVar(value=str(self.variables[key]["default"]))
            for key in VARIABLE_KEYS
        }
        self.active_variables: set[str] = set()
        self.add_field_var = tk.StringVar()
        self.status = tk.StringVar(value=initial_status)
        self.status_kind = "normal"
        self.editor_window: TemplateEditor | None = None

        shell = ttk.Frame(
            self,
            style="Shell.TFrame",
            padding=(self.px(30), self.px(26), self.px(30), self.px(24)),
        )
        shell.pack(
            fill="both",
            expand=True,
            padx=self.px(18),
            pady=self.px(18),
        )
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(7, weight=1)

        ttk.Label(shell, text=APP_TITLE, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(shell, text="Choose a template, fill in its fields, and copy the finished message.", style="Hint.TLabel").grid(
            row=1, column=0, sticky="w", pady=(self.px(4), self.px(21))
        )

        ttk.Label(shell, text="Template").grid(row=2, column=0, sticky="w")
        self.package_dropdown = Dropdown(
            shell,
            variable=self.package_title,
            scale=self.ui_scale,
            on_change=self._template_changed,
        )
        self.package_dropdown.grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(self.px(6), self.px(16)),
        )

        self.optional_controls = ttk.Frame(shell, style="Shell.TFrame")
        self.optional_controls.grid(
            row=4, column=0, sticky="ew", pady=(0, self.px(13))
        )
        self.optional_controls.columnconfigure(0, weight=1)
        ttk.Label(
            self.optional_controls, text="Optional fields", style="Section.TLabel"
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        self.add_field_dropdown = Dropdown(
            self.optional_controls,
            variable=self.add_field_var,
            scale=self.ui_scale,
        )
        self.add_field_dropdown.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(self.px(7), 0),
        )
        self.add_field_button = ttk.Button(
            self.optional_controls, text="Add", command=self._add_variable
        )
        self.add_field_button.grid(
            row=1,
            column=1,
            padx=(self.px(9), 0),
            pady=(self.px(7), 0),
        )
        self.optional_hint = tk.StringVar(
            value="Add only the services needed for this offer."
        )
        self.optional_hint_label = ttk.Label(
            self.optional_controls,
            textvariable=self.optional_hint,
            style="Hint.TLabel",
        )
        self.optional_hint_label.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(self.px(5), 0),
        )

        self.variable_fields = ttk.Frame(shell, style="Shell.TFrame")
        self.variable_fields.grid(
            row=5, column=0, sticky="ew", pady=(0, self.px(14))
        )
        self.variable_fields.columnconfigure(0, weight=1)
        self.variable_rows: dict[str, ttk.Frame] = {}
        self.variable_labels: dict[str, ttk.Label] = {}
        self.variable_dropdowns: dict[str, Dropdown] = {}
        self.variable_remove_buttons: dict[str, ttk.Button] = {}
        for row, key in enumerate(VARIABLE_KEYS):
            field = ttk.Frame(self.variable_fields, style="Shell.TFrame")
            field.grid(row=row, column=0, sticky="ew", pady=(0, self.px(12)))
            field.columnconfigure(0, weight=1)
            label = ttk.Label(field, text=str(self.variables[key]["label"]))
            label.grid(
                row=0, column=0, sticky="w"
            )
            dropdown = Dropdown(
                field,
                variable=self.selection_vars[key],
                scale=self.ui_scale,
                on_change=self.update_preview,
            )
            dropdown.grid(row=1, column=0, sticky="ew", pady=(self.px(6), 0))
            remove_button = ttk.Button(
                field,
                text="Remove",
                command=lambda variable_key=key: self._remove_variable(variable_key),
            )
            remove_button.grid(
                row=1,
                column=2,
                padx=(self.px(9), 0),
                pady=(self.px(6), 0),
            )
            self.variable_rows[key] = field
            self.variable_labels[key] = label
            self.variable_dropdowns[key] = dropdown
            self.variable_remove_buttons[key] = remove_button

        broadband_row = self.variable_rows["broadband"]
        self.broadband_price_label = ttk.Label(
            broadband_row, text="Broadband price"
        )
        self.broadband_price_entry = ttk.Entry(
            broadband_row,
            textvariable=self.broadband_price,
            font=("Segoe UI", 10),
            width=10,
        )
        self.broadband_price.trace_add(
            "write", lambda *_args: self.update_preview()
        )

        price_fields = ttk.Frame(shell, style="Shell.TFrame")
        price_fields.grid(row=6, column=0, sticky="w", pady=(0, self.px(16)))
        price_fields.columnconfigure(0, minsize=self.px(126))
        price_fields.columnconfigure(1, minsize=self.px(150))
        price_fields.columnconfigure(2, minsize=self.px(176))

        ttk.Label(price_fields, text="Price").grid(row=0, column=0, sticky="w")
        ttk.Label(price_fields, text="Currency").grid(
            row=0, column=1, sticky="w", padx=(self.px(10), 0)
        )
        self.price_entry = ttk.Entry(
            price_fields,
            textvariable=self.price,
            font=("Segoe UI", 10),
            width=10,
        )
        self.price_entry.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(self.px(6), 0),
        )
        self.currency_dropdown = Dropdown(
            price_fields,
            variable=self.currency,
            scale=self.ui_scale,
            on_change=self.update_preview,
        )
        self.currency_dropdown.grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(self.px(10), 0),
            pady=(self.px(6), 0),
        )
        self.price.trace_add("write", lambda *_args: self.update_preview())
        self.date_override_label = ttk.Label(
            price_fields, text="Date override (DD/MM/YYYY)"
        )
        self.date_override_label.grid(
            row=0,
            column=2,
            sticky="w",
            padx=(self.px(10), 0),
        )
        self.date_override_entry = ttk.Entry(
            price_fields,
            textvariable=self.date_override,
            font=("Segoe UI", 10),
            width=12,
        )
        self.date_override_entry.grid(
            row=1,
            column=2,
            sticky="ew",
            padx=(self.px(10), 0),
            pady=(self.px(6), 0),
        )
        self.date_override.trace_add("write", lambda *_args: self.update_preview())

        preview_frame = ttk.Frame(
            shell, style="Preview.TFrame", padding=self.px(1)
        )
        preview_frame.grid(row=7, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.preview = tk.Text(
            preview_frame,
            height=5,
            wrap="word",
            state="disabled",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            background=COLORS["input"],
            foreground=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            padx=self.px(12),
            pady=self.px(11),
            font=("Segoe UI", 10),
            cursor="arrow",
        )
        self.preview.grid(row=0, column=0, sticky="nsew")

        actions = ttk.Frame(shell, style="Shell.TFrame")
        actions.grid(row=8, column=0, sticky="ew", pady=(self.px(17), 0))
        actions.columnconfigure(1, weight=1)
        ttk.Button(actions, text="Edit templates", command=self.open_editor).grid(row=0, column=0)
        ttk.Label(actions, textvariable=self.status, style="Status.TLabel").grid(
            row=0, column=1, sticky="w", padx=self.px(12)
        )
        ttk.Button(actions, text="Copy offer", style="Accent.TButton", command=self.copy_offer).grid(
            row=0, column=2
        )

        self.bind("<Return>", lambda _event: self.copy_offer())
        self.set_config(
            self.packages,
            self.currencies,
            self.default_package,
            self.default_currency,
            self.variables,
        )
        center_window(self)
        use_dark_title_bar(self)
        self.deiconify()
        self.after(10, lambda: use_dark_title_bar(self))
        self.price_entry.focus_set()
        if os.environ.get("OFFERTEMPLATES_SMOKE_TEST") == "1":
            self.after(100, self.destroy)

    def px(self, logical_pixels: int) -> int:
        return max(1, round(logical_pixels * self.ui_scale))

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            ".",
            font=("Segoe UI", 10),
            background=COLORS["surface"],
            foreground=COLORS["text"],
        )
        style.configure("TFrame", background=COLORS["surface"])
        style.configure("TLabel", background=COLORS["surface"], foreground=COLORS["text"])
        style.configure("Shell.TFrame", background=COLORS["surface"])
        style.configure("Preview.TFrame", background=COLORS["border"])
        style.configure("TSeparator", background=COLORS["border"])
        style.configure(
            "TNotebook",
            background=COLORS["surface"],
            borderwidth=0,
            tabmargins=0,
        )
        style.configure(
            "TNotebook.Tab",
            background=COLORS["raised"],
            foreground=COLORS["muted"],
            borderwidth=0,
            padding=(self.px(16), self.px(9)),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLORS["accent"]), ("active", "#303743")],
            foreground=[("selected", "#ffffff"), ("active", COLORS["text"])],
        )
        style.configure(
            "Title.TLabel",
            font=("Segoe UI Semibold", 18),
            background=COLORS["surface"],
            foreground=COLORS["text"],
        )
        style.configure("Section.TLabel", font=("Segoe UI Semibold", 12))
        style.configure(
            "Hint.TLabel",
            foreground=COLORS["muted"],
            background=COLORS["surface"],
        )
        style.configure(
            "Status.TLabel",
            foreground=COLORS["muted"],
            background=COLORS["surface"],
        )
        style.configure(
            "TButton",
            background=COLORS["raised"],
            foreground=COLORS["text"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["raised"],
            darkcolor=COLORS["raised"],
            focuscolor=COLORS["accent"],
            focusthickness=self.px(1),
            padding=(self.px(13), self.px(7)),
        )
        style.map(
            "TButton",
            background=[
                ("pressed", COLORS["input"]),
                ("active", "#303743"),
            ],
            bordercolor=[("focus", COLORS["accent"]), ("active", "#46505e")],
            foreground=[("disabled", "#69727e")],
        )
        style.configure(
            "Accent.TButton",
            font=("Segoe UI Semibold", 10),
            background=COLORS["accent"],
            foreground="#ffffff",
            bordercolor=COLORS["accent"],
            lightcolor=COLORS["accent"],
            darkcolor=COLORS["accent"],
            padding=(self.px(17), self.px(8)),
        )
        style.map(
            "Accent.TButton",
            background=[
                ("pressed", COLORS["accent_pressed"]),
                ("active", COLORS["accent_hover"]),
            ],
            bordercolor=[
                ("pressed", COLORS["accent_pressed"]),
                ("active", COLORS["accent_hover"]),
            ],
        )
        style.configure(
            "TEntry",
            fieldbackground=COLORS["input"],
            background=COLORS["input"],
            foreground=COLORS["text"],
            insertcolor=COLORS["text"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
            focuscolor=COLORS["accent"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            padding=self.px(7),
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", COLORS["accent"])],
            lightcolor=[("focus", COLORS["accent"])],
            darkcolor=[("focus", COLORS["accent"])],
        )

    def set_config(
        self,
        packages: list[dict[str, str]],
        currencies: list[str],
        default_package: str,
        default_currency: str,
        variables: dict[str, dict[str, object]],
    ) -> None:
        self.packages = packages
        self.currencies = currencies
        self.default_package = default_package
        self.default_currency = default_currency
        self.variables = variables
        self.package_title.set(default_package)
        self.currency.set(default_currency)
        self.package_dropdown.set_items([item["title"] for item in packages])
        self.currency_dropdown.set_items(currencies)
        for key in VARIABLE_KEYS:
            self.selection_vars[key].set(str(variables[key]["default"]))
            self.variable_dropdowns[key].set_items(list(variables[key]["options"]))
            self.variable_labels[key].configure(text=str(variables[key]["label"]))
        self.broadband_price_label.configure(
            text=f'{variables["broadband"]["label"]} price'
        )
        self._template_changed()

    def selected_package(self) -> dict[str, str]:
        selected = self.package_title.get()
        return next(item for item in self.packages if item["title"] == selected)

    def selected_values(self) -> dict[str, str]:
        return {key: variable.get() for key, variable in self.selection_vars.items()}

    def _template_changed(self) -> None:
        try:
            fields = template_fields(self.selected_package()["template"])
        except (StopIteration, ValueError):
            fields = set()
        self.active_variables = set(VARIABLE_KEYS) & fields
        if BROADBAND_PRICE_FIELD in fields:
            self.active_variables.add("broadband")
        for campaign_field, (variable_key, _) in CAMPAIGN_FIELDS.items():
            if campaign_field in fields:
                self.active_variables.add(variable_key)
        date_used = any(DATE_FIELD_PATTERN.fullmatch(field) for field in fields)
        if date_used:
            self.date_override_label.grid()
            self.date_override_entry.grid()
        else:
            self.date_override_label.grid_remove()
            self.date_override_entry.grid_remove()
        self._refresh_variable_rows()

    def _refresh_variable_rows(self) -> None:
        try:
            fields = template_fields(self.selected_package()["template"])
        except (StopIteration, ValueError):
            fields = set()
        broadband_used = "broadband" in self.active_variables
        broadband_price_used = BROADBAND_PRICE_FIELD in fields
        broadband_row = self.variable_rows["broadband"]
        broadband_row.columnconfigure(
            1, minsize=self.px(126) if broadband_price_used and broadband_used else 0
        )
        if broadband_used:
            self.variable_labels["broadband"].grid(
                row=0, column=0, sticky="w"
            )
            self.variable_dropdowns["broadband"].grid(
                row=1,
                column=0,
                columnspan=1 if broadband_price_used else 2,
                sticky="ew",
                pady=(self.px(6), 0),
            )
        else:
            self.variable_labels["broadband"].grid_remove()
            self.variable_dropdowns["broadband"].grid_remove()
        if broadband_price_used and broadband_used:
            self.broadband_price_label.grid(
                row=0,
                column=1,
                sticky="w",
                padx=(self.px(10), 0),
            )
            self.broadband_price_entry.grid(
                row=1,
                column=1,
                sticky="ew",
                padx=(self.px(10), 0),
                pady=(self.px(6), 0),
            )
        else:
            self.broadband_price_label.grid_remove()
            self.broadband_price_entry.grid_remove()

        visible = broadband_used
        for key in VARIABLE_KEYS:
            if key == "broadband":
                if visible:
                    self.variable_rows[key].grid()
                else:
                    self.variable_rows[key].grid_remove()
                continue
            if key in self.active_variables:
                self.variable_dropdowns[key].grid_configure(columnspan=2)
                self.variable_rows[key].grid()
                visible = True
            else:
                self.variable_rows[key].grid_remove()
        if visible:
            self.variable_fields.grid()
        else:
            self.variable_fields.grid_remove()
        self._refresh_add_field_choices()
        self.update_preview()

    def _refresh_add_field_choices(self) -> None:
        try:
            fields = template_fields(self.selected_package()["template"])
        except (StopIteration, ValueError):
            fields = set()
        supported = set(VARIABLE_KEYS) if "services" in fields else set(VARIABLE_KEYS) & fields
        if BROADBAND_PRICE_FIELD in fields:
            supported.add("broadband")
        for campaign_field, (variable_key, _) in CAMPAIGN_FIELDS.items():
            if campaign_field in fields:
                supported.add(variable_key)
        choices = [
            str(self.variables[key]["label"])
            for key in VARIABLE_KEYS
            if key in supported and key not in self.active_variables
        ]
        self.add_field_dropdown.set_items(choices)
        if choices:
            self.add_field_dropdown.grid()
            self.add_field_button.grid()
            if self.add_field_var.get() not in choices:
                self.add_field_var.set(choices[0])
            self.add_field_button.configure(state="normal")
            self.optional_hint.set("Add only the services needed for this offer.")
        else:
            if supported:
                self.add_field_var.set("All available fields added")
                self.optional_hint.set("Remove any field that is not needed.")
                self.add_field_dropdown.grid_remove()
                self.add_field_button.grid_remove()
            else:
                self.add_field_dropdown.grid()
                self.add_field_button.grid()
                self.add_field_var.set("No optional fields in this template")
                self.optional_hint.set(
                    "Use {services} in the template to enable optional fields."
                )
            self.add_field_button.configure(state="disabled")

    def _add_variable(self) -> None:
        selected = self.add_field_var.get()
        key = next(
            (
                item_key
                for item_key in VARIABLE_KEYS
                if self.variables[item_key]["label"] == selected
            ),
            None,
        )
        if key is None:
            return
        self.active_variables.add(key)
        self._refresh_variable_rows()
        self.variable_dropdowns[key].label_button.focus_set()

    def _remove_variable(self, key: str) -> None:
        self.active_variables.discard(key)
        self._refresh_variable_rows()
        self.add_field_dropdown.label_button.focus_set()

    def update_preview(self) -> None:
        if not hasattr(self, "preview"):
            return
        shown_price = self.price.get().strip() or "[price]"
        shown_broadband_price = (
            self.broadband_price.get().strip() or "[broadband price]"
        )
        try:
            text = render_offer(
                self.selected_package(),
                shown_price,
                self.currency.get(),
                self.selected_values(),
                shown_broadband_price,
                self.active_variables,
                date_override=self.date_override.get(),
            )
        except (ConfigError, StopIteration) as exc:
            text = str(exc)
        else:
            if self.status_kind == "error":
                self.set_status("")
        self.preview.configure(state="normal")
        self.preview.delete("1.0", tk.END)
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def copy_offer(self) -> None:
        price = self.price.get().strip()
        try:
            text = render_offer(
                self.selected_package(),
                price,
                self.currency.get(),
                self.selected_values(),
                self.broadband_price.get(),
                self.active_variables,
                date_override=self.date_override.get(),
            )
        except (ConfigError, StopIteration) as exc:
            if str(exc) == "Enter a price first.":
                self.set_status(str(exc), "error")
                self.price_entry.focus_set()
                return
            if str(exc) == "Enter a broadband price first.":
                self.set_status(str(exc), "error")
                self.broadband_price_entry.focus_set()
                return
            if str(exc) == "Enter the date as DD/MM/YYYY.":
                self.set_status(str(exc), "error")
                self.date_override_entry.focus_set()
                return
            for key in VARIABLE_KEYS:
                expected = f"Choose a {VARIABLE_LABELS[key].lower()} first."
                if str(exc) == expected:
                    self.set_status(str(exc), "error")
                    self.variable_dropdowns[key].label_button.focus_set()
                    return
            messagebox.showerror("Could not create offer", str(exc), parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()
        self.set_status("Copied to clipboard.", "success")

    def set_status(self, message: str, kind: str = "normal") -> None:
        self.status_kind = kind
        self.status.set(message)
        color = {
            "success": COLORS["success"],
            "error": COLORS["error"],
        }.get(kind, COLORS["muted"])
        ttk.Style(self).configure(
            "Status.TLabel", foreground=color, background=COLORS["surface"]
        )

    def open_editor(self) -> None:
        if self.editor_window is not None:
            try:
                if self.editor_window.winfo_exists():
                    self.editor_window.lift()
                    self.editor_window.focus_force()
                    return
            except tk.TclError:
                pass
        self.editor_window = TemplateEditor(self)


if __name__ == "__main__":
    OfferApp().mainloop()
