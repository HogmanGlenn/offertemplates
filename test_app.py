import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app import (
    CONFIG_PATH,
    DEFAULT_VARIABLES,
    ConfigError,
    centered_geometry,
    ensure_user_config,
    load_config,
    load_packages,
    render_offer,
    save_config,
    save_packages,
)


class ConfigTests(unittest.TestCase):
    def test_first_run_copies_a_clean_bundled_config(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundled_path = root / "bundle" / "packages.json"
            user_path = root / "user" / "packages.json"
            bundled_path.parent.mkdir()
            bundled_path.write_text('{"packages": []}\n', encoding="utf-8")

            ensure_user_config(user_path, bundled_path)

            self.assertEqual(
                user_path.read_text(encoding="utf-8"),
                bundled_path.read_text(encoding="utf-8"),
            )

    def test_first_run_does_not_overwrite_an_existing_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundled_path = root / "bundle.json"
            user_path = root / "user.json"
            bundled_path.write_text("bundled", encoding="utf-8")
            user_path.write_text("custom", encoding="utf-8")

            ensure_user_config(user_path, bundled_path)

            self.assertEqual(user_path.read_text(encoding="utf-8"), "custom")

    def test_bundled_config_loads_and_renders(self) -> None:
        packages, currencies, default_package, default_currency, variables = load_config(
            CONFIG_PATH
        )
        self.assertGreaterEqual(len(packages), 1)
        self.assertIn("€/month", currencies)
        self.assertIn(default_package, [item["title"] for item in packages])
        self.assertIn(default_currency, currencies)
        self.assertEqual(set(variables), {"broadband", "tv", "streaming"})
        for package in packages:
            message = render_offer(package, "19.90 €/month")
            self.assertNotIn("{package}", message)
            self.assertNotIn("{price}", message)

    def test_save_and_load_round_trip(self) -> None:
        packages = [
            {
                "title": "Family",
                "package": "Family package",
                "template": "Offer: {package} for {price}",
            }
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "packages.json"
            save_packages(packages, path)
            self.assertEqual(load_packages(path), packages)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["packages"], packages)

    def test_currency_is_added_to_the_formatted_price(self) -> None:
        package = {
            "title": "Sports",
            "package": "Sports package",
            "template": "Offer: {package} for {price}",
        }
        self.assertEqual(
            render_offer(package, "19.90", "€/month"),
            "Offer: Sports package for 19.90 €/month",
        )

    def test_plain_template_needs_neither_package_nor_price(self) -> None:
        package = {
            "title": "Callback",
            "package": "",
            "template": "Thanks for speaking with us today.",
        }
        self.assertEqual(
            render_offer(package, "", "€/month"),
            "Thanks for speaking with us today.",
        )

    def test_date_field_inserts_the_current_date(self) -> None:
        package = {
            "title": "Appointment",
            "package": "",
            "template": "Created {date}",
        }
        self.assertEqual(
            render_offer(package, "", today=date(2026, 9, 2)),
            "Created 02/09/2026",
        )

    def test_date_offsets_add_the_requested_number_of_days(self) -> None:
        package = {
            "title": "Appointment",
            "package": "",
            "template": "Two weeks: {date+14}; 137 days: {date+137}",
        }
        self.assertEqual(
            render_offer(package, "", today=date(2026, 12, 20)),
            "Two weeks: 03/01/2027; 137 days: 06/05/2027",
        )

    def test_negative_date_offsets_go_back_the_requested_number_of_days(self) -> None:
        package = {
            "title": "Appointment",
            "package": "",
            "template": "Two weeks ago: {date-14}",
        }
        self.assertEqual(
            render_offer(package, "", today=date(2026, 1, 10)),
            "Two weeks ago: 27/12/2025",
        )

    def test_date_override_replaces_today_for_all_date_fields(self) -> None:
        package = {
            "title": "Appointment",
            "package": "",
            "template": "Selected {date}; follow-up {date+30}",
        }
        self.assertEqual(
            render_offer(
                package,
                "",
                today=date(2026, 9, 2),
                date_override="15/01/2027",
            ),
            "Selected 15/01/2027; follow-up 14/02/2027",
        )

    def test_invalid_date_override_is_rejected_when_date_is_used(self) -> None:
        package = {
            "title": "Appointment",
            "package": "",
            "template": "Selected {date}",
        }
        for entered_date in ("2027-01-15", "30/02/2027", "15012027", "1/1/2027"):
            with self.subTest(entered_date=entered_date):
                with self.assertRaisesRegex(ConfigError, "DD/MM/YYYY"):
                    render_offer(package, "", date_override=entered_date)

    def test_date_override_is_ignored_when_template_has_no_date(self) -> None:
        package = {
            "title": "Plain",
            "package": "",
            "template": "No date here.",
        }
        self.assertEqual(
            render_offer(package, "", date_override="not-a-date"),
            "No date here.",
        )

    def test_invalid_date_expression_is_rejected(self) -> None:
        package = {
            "title": "Appointment",
            "package": "",
            "template": "Created {date--14}",
        }
        with self.assertRaisesRegex(ConfigError, "unknown field"):
            with tempfile.TemporaryDirectory() as folder:
                save_packages([package], Path(folder) / "packages.json")

    def test_unreasonably_large_date_offset_is_rejected(self) -> None:
        for offset in ("+999999999", "-999999999"):
            with self.subTest(offset=offset):
                package = {
                    "title": "Appointment",
                    "package": "",
                    "template": f"Created {{date{offset}}}",
                }
                with self.assertRaisesRegex(ConfigError, "date offset.*too large"):
                    with tempfile.TemporaryDirectory() as folder:
                        save_packages([package], Path(folder) / "packages.json")

    def test_price_is_required_only_when_template_uses_it(self) -> None:
        package = {
            "title": "Sports",
            "package": "Sports package",
            "template": "Offer: {package} for {price}",
        }
        with self.assertRaisesRegex(ConfigError, "Enter a price first"):
            render_offer(package, "", "€/month")

    def test_broadband_price_uses_the_selected_currency(self) -> None:
        package = {
            "title": "Broadband",
            "package": "",
            "template": "Broadband {broadband} for {broadband_price}",
        }
        self.assertEqual(
            render_offer(
                package,
                "",
                "KR/month",
                {"broadband": "1000/1000"},
                "429",
            ),
            "Broadband 1000/1000 for 429 KR/month",
        )

    def test_broadband_and_total_prices_are_independent(self) -> None:
        package = {
            "title": "Bundle",
            "package": "",
            "template": "Broadband {broadband_price}; total {price}",
        }
        self.assertEqual(
            render_offer(package, "999", "KR/month", broadband_price="429"),
            "Broadband 429 KR/month; total 999 KR/month",
        )

    def test_broadband_price_is_required_only_when_template_uses_it(self) -> None:
        package = {
            "title": "Broadband",
            "package": "",
            "template": "Broadband for {broadband_price}",
        }
        with self.assertRaisesRegex(ConfigError, "Enter a broadband price first"):
            render_offer(package, "", "KR/month")

        plain_package = {
            "title": "Plain",
            "package": "",
            "template": "This message has no price.",
        }
        self.assertEqual(
            render_offer(plain_package, "", "KR/month"),
            "This message has no price.",
        )

    def test_supported_service_combinations_render_selected_values(self) -> None:
        selections = {
            "broadband": "1000/1000",
            "tv": "TV Mini",
            "streaming": "Streaming Plus",
        }
        combinations = {
            "broadband": "{broadband}",
            "broadband_tv": "{broadband} + {tv}",
            "broadband_streaming": "{broadband} + {streaming}",
            "tv_streaming": "{tv} + {streaming}",
            "all_three": "{broadband} + {tv} + {streaming}",
        }
        for title, template in combinations.items():
            with self.subTest(title=title):
                package = {"title": title, "package": "", "template": template}
                rendered = render_offer(package, "", selections=selections)
                for field in ("broadband", "tv", "streaming"):
                    if "{" + field + "}" in template:
                        self.assertIn(selections[field], rendered)

    def test_campaign_fields_insert_saved_text_without_an_input_value(self) -> None:
        package = {
            "title": "Campaign",
            "package": "",
            "template": "Offer details\n{broadband2}\n{tv1}\n{tv2}",
            "broadband2": "Broadband campaign terms",
            "tv1": "Primary TV offer terms",
            "tv2": "TV campaign terms\nSecond line",
        }

        self.assertEqual(
            render_offer(package, "", active_variables={"broadband", "tv"}),
            "Offer details\nBroadband campaign terms\nPrimary TV offer terms\n"
            "TV campaign terms\nSecond line",
        )

    def test_tv1_combines_the_selected_tv_name_with_saved_offer_text(self) -> None:
        offer_text = (
            "99kr per month for 6 months then 249kr with 12 months binding period"
        )
        package = {
            "title": "TV retention",
            "package": "",
            "template": (
                "Hi I see that you want to cancel your {tv} but I have this "
                "amazing offer of: {tv1}"
            ),
            "tv1": offer_text,
        }

        self.assertEqual(
            render_offer(
                package,
                "",
                selections={"tv": "tv mini"},
                active_variables={"tv"},
            ),
            "Hi I see that you want to cancel your tv mini but I have this "
            f"amazing offer of: {offer_text}",
        )

    def test_campaign_text_is_omitted_when_its_service_is_removed(self) -> None:
        package = {
            "title": "Campaign",
            "package": "",
            "template": "{broadband2}{tv2}",
            "broadband2": "Broadband campaign",
            "tv2": "TV campaign",
        }

        self.assertEqual(
            render_offer(package, "", active_variables={"tv"}),
            "TV campaign",
        )

    def test_used_campaign_field_requires_saved_campaign_text(self) -> None:
        package = {
            "title": "Campaign",
            "package": "",
            "template": "Offer {tv2}",
        }
        with self.assertRaisesRegex(ConfigError, "TV campaign text is required"):
            with tempfile.TemporaryDirectory() as folder:
                save_packages([package], Path(folder) / "packages.json")

    def test_campaign_text_round_trips_with_its_template(self) -> None:
        packages = [
            {
                "title": "Campaign",
                "package": "",
                "template": "{broadband2}",
                "broadband2": "Campaign line one\nCampaign line two",
            }
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "packages.json"
            save_packages(packages, path)
            self.assertEqual(load_packages(path), packages)

    def test_used_service_variable_requires_a_selection(self) -> None:
        package = {
            "title": "Broadband",
            "package": "",
            "template": "Offer {broadband}",
        }
        with self.assertRaisesRegex(ConfigError, "Choose a broadband first"):
            render_offer(package, "", selections={"broadband": ""})

    def test_removed_service_variables_are_optional(self) -> None:
        package = {
            "title": "Flexible bundle",
            "package": "",
            "template": "Broadband: {broadband}\nStreaming: {streaming}",
        }
        self.assertEqual(
            render_offer(
                package,
                "",
                selections={"broadband": "", "streaming": ""},
                active_variables=set(),
            ),
            "Broadband: \nStreaming: ",
        )

    def test_services_field_joins_only_added_services(self) -> None:
        package = {
            "title": "Flexible bundle",
            "package": "",
            "template": "Offer {services} for {price}",
        }
        selections = {
            "broadband": "1000/1000",
            "tv": "TV Mini",
            "streaming": "Streaming more",
        }
        self.assertEqual(
            render_offer(
                package,
                "999",
                "KR/month",
                selections,
                active_variables={"broadband", "streaming"},
            ),
            "Offer 1000/1000 + Streaming more for 999 KR/month",
        )

    def test_removed_broadband_does_not_require_its_price(self) -> None:
        package = {
            "title": "Broadband",
            "package": "",
            "template": "{broadband} for {broadband_price}",
        }
        self.assertEqual(
            render_offer(
                package,
                "",
                "EUR/month",
                selections={"broadband": ""},
                broadband_price="",
                active_variables=set(),
            ),
            " for ",
        )

    def test_package_name_is_required_when_template_uses_it(self) -> None:
        package = {
            "title": "Sports",
            "package": "",
            "template": "Offer: {package}",
        }
        with self.assertRaisesRegex(ConfigError, "package name is required"):
            with tempfile.TemporaryDirectory() as folder:
                save_packages([package], Path(folder) / "packages.json")

    def test_saving_templates_preserves_configured_currencies(self) -> None:
        packages = [
            {"title": "Sports", "package": "Sports", "template": "{price}"}
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "packages.json"
            save_config(packages, ["EUR", "USD"], path, "Sports", "USD")
            packages[0]["package"] = "Updated Sports"
            save_packages(packages, path)
            (
                saved_packages,
                currencies,
                default_package,
                default_currency,
                variables,
            ) = load_config(path)
            self.assertEqual(saved_packages, packages)
            self.assertEqual(currencies, ["EUR", "USD"])
            self.assertEqual(default_package, "Sports")
            self.assertEqual(default_currency, "USD")
            self.assertEqual(variables, DEFAULT_VARIABLES)

    def test_service_choices_and_defaults_round_trip(self) -> None:
        packages = [
            {"title": "Bundle", "package": "", "template": "{broadband} {tv}"}
        ]
        variables = {
            "broadband": {
                "label": "Internet speed",
                "options": ["500/500", "1000/1000"],
                "default": "500/500",
            },
            "tv": {
                "label": "Channel package",
                "options": ["TV Mini", "TV Max"],
                "default": "TV Max",
            },
            "streaming": {
                "label": "Streaming",
                "options": ["Stream One"],
                "default": "Stream One",
            },
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "packages.json"
            save_config(
                packages,
                ["EUR"],
                path,
                "Bundle",
                "EUR",
                variables=variables,
            )
            self.assertEqual(load_config(path)[4], variables)

    def test_duplicate_custom_field_names_are_rejected(self) -> None:
        variables = {
            "broadband": {
                "label": "Service",
                "options": ["1000/1000"],
                "default": "1000/1000",
            },
            "tv": {
                "label": "service",
                "options": ["TV Mini"],
                "default": "TV Mini",
            },
            "streaming": {
                "label": "Streaming",
                "options": ["Streaming"],
                "default": "Streaming",
            },
        }
        with self.assertRaisesRegex(ConfigError, "field name.*used more than once"):
            with tempfile.TemporaryDirectory() as folder:
                save_config(
                    [{"title": "Offer", "package": "", "template": "Text"}],
                    ["EUR"],
                    Path(folder) / "packages.json",
                    variables=variables,
                )

    def test_existing_config_without_service_choices_gets_safe_defaults(self) -> None:
        data = {
            "default_package": "Sports",
            "default_currency": "EUR",
            "currencies": ["EUR"],
            "packages": [
                {"title": "Sports", "package": "Sports", "template": "{price}"}
            ],
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "packages.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(load_config(path)[4], DEFAULT_VARIABLES)

    def test_duplicate_service_choices_are_rejected(self) -> None:
        packages = [{"title": "Bundle", "package": "", "template": "{tv}"}]
        variables = {
            "broadband": {"options": ["1000/1000"], "default": "1000/1000"},
            "tv": {"options": ["TV Mini", "tv mini"], "default": "TV Mini"},
            "streaming": {"options": ["Streaming"], "default": "Streaming"},
        }
        with self.assertRaisesRegex(ConfigError, "used more than once"):
            with tempfile.TemporaryDirectory() as folder:
                save_config(
                    packages,
                    ["EUR"],
                    Path(folder) / "packages.json",
                    "Bundle",
                    "EUR",
                    variables,
                )

    def test_invalid_service_default_is_rejected(self) -> None:
        packages = [
            {"title": "Bundle", "package": "", "template": "{streaming}"}
        ]
        variables = {
            "broadband": {"options": ["1000/1000"], "default": "1000/1000"},
            "tv": {"options": ["TV Mini"], "default": "TV Mini"},
            "streaming": {"options": ["Streaming"], "default": "Missing"},
        }
        with self.assertRaisesRegex(ConfigError, "default streaming package"):
            with tempfile.TemporaryDirectory() as folder:
                save_config(
                    packages,
                    ["EUR"],
                    Path(folder) / "packages.json",
                    "Bundle",
                    "EUR",
                    variables,
                )

    def test_duplicate_titles_are_rejected(self) -> None:
        packages = [
            {"title": "Sports", "package": "One", "template": "{price}"},
            {"title": "sports", "package": "Two", "template": "{price}"},
        ]
        with self.assertRaisesRegex(ConfigError, "used more than once"):
            save_packages(packages, Path("unused.json"))

    def test_unknown_template_field_is_rejected(self) -> None:
        package = {"title": "Sports", "package": "Sports", "template": "Call {customer}"}
        with self.assertRaisesRegex(ConfigError, "unknown field"):
            with tempfile.TemporaryDirectory() as folder:
                save_packages([package], Path(folder) / "packages.json")

    def test_duplicate_currencies_are_rejected(self) -> None:
        packages = [
            {"title": "Sports", "package": "Sports", "template": "{price}"}
        ]
        with self.assertRaisesRegex(ConfigError, "used more than once"):
            with tempfile.TemporaryDirectory() as folder:
                save_config(packages, ["EUR", "eur"], Path(folder) / "packages.json")

    def test_invalid_default_is_rejected(self) -> None:
        packages = [
            {"title": "Sports", "package": "Sports", "template": "{price}"}
        ]
        with self.assertRaisesRegex(ConfigError, "valid default package"):
            with tempfile.TemporaryDirectory() as folder:
                save_config(
                    packages,
                    ["EUR"],
                    Path(folder) / "packages.json",
                    "Movies",
                    "EUR",
                )


class WindowGeometryTests(unittest.TestCase):
    def test_window_is_centered_in_primary_work_area(self) -> None:
        geometry = centered_geometry((0, 0, 1920, 1040), 930, 810, 36)
        self.assertEqual(geometry, (930, 810, 495, 115))

    def test_oversized_window_is_clamped_with_margin(self) -> None:
        geometry = centered_geometry((100, 50, 900, 650), 1200, 900, 20)
        self.assertEqual(geometry, (760, 560, 120, 70))


if __name__ == "__main__":
    unittest.main()
