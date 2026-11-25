import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from scripts import details_json_v1 as details


def next_page(bundle):
    payload = 'e:["$","section",null,{"bundlePage":' + json.dumps(bundle) + '}]'
    return '<script>self.__next_f.push(' + json.dumps([1, payload]) + ')</script>'


class DetailsTests(unittest.TestCase):
    def test_parses_current_bundle_page_tiers(self):
        bundle = {
            "title": "Python Bundle", "slug": "python-bundle", "startDate": "2026-11-01T19:00:00.000Z",
            "endDate": "2026-11-30T19:00:00.000Z", "tiers": [
                {"id": "1", "sku": "python_initial", "price": {"amount": 5, "currencyCode": "EUR"},
                 "bundleItems": [{"key": "python-basics", "title": "Python Basics", "bundleType": "books", "platforms": ["pdf"]}]},
                {"id": "2", "sku": "python_bt20", "price": {"amount": 20, "currencyCode": "EUR"},
                 "bundleItems": ["$e:0:props:children:props:bundlePage:tiers:0:bundleItems:0",
                                 {"key": "python-advanced", "title": "Advanced Python", "bundleType": "books", "platforms": ["epub"]}]},
            ],
        }
        source = {"url": "https://humblebundle.com/books/python-bundle", "title": "Python Bundle", "category": "books", "end_at": "2026-11-30T19:00:00"}
        with patch.object(details, "fetch_html", return_value=next_page(bundle)):
            parsed = details.parse_bundle(source)
        self.assertEqual([tier["price"]["amount"] for tier in parsed["tiers"]], [5, 20])
        self.assertEqual([item["title"] for item in parsed["tiers"][1]["items"]], ["Python Basics", "Advanced Python"])
        self.assertEqual(parsed["tiers"][1]["items"][1]["platforms_and_oses"], {"platforms": ["epub"]})

    def test_resolves_nested_nextjs_references_and_mixed_chains(self):
        bundle = {"tiers": [
            {"price": {"amount": 5, "currencyCode": "USD"},
             "bundleItems": [{"key": "base", "title": "Base Item"}]},
            {"price": {"amount": 10, "currencyCode": "USD"},
             "bundleItems": [
                 "$e:props:children:0:props:children:props:bundlePage:tiers:0:bundleItems:0"
             ]},
            {"price": {"amount": 15, "currencyCode": "USD"},
             "bundleItems": [
                 "$e:0:props:children:props:bundlePage:tiers:1:bundleItems:0"
             ]},
        ]}
        parsed = details.parse_next_bundle({"url": "https://example.com/bundle"}, bundle)
        self.assertEqual(len(parsed["tiers"]), 3)
        self.assertEqual([tier["items"][0]["title"] for tier in parsed["tiers"]],
                         ["Base Item", "Base Item", "Base Item"])

    def test_rejects_cyclic_references(self):
        ref = "$e:props:children:0:props:children:props:bundlePage:tiers:0:bundleItems:0"
        bundle = {"tiers": [{"price": {"amount": 5}, "bundleItems": [ref]}]}
        with self.assertRaisesRegex(ValueError, "cyclic bundle item reference"):
            details.parse_next_bundle({"url": "https://example.com/bundle"}, bundle)

    def test_rejects_out_of_range_references(self):
        ref = "$e:props:children:0:props:children:props:bundlePage:tiers:42:bundleItems:0"
        bundle = {"tiers": [{"price": {"amount": 5}, "bundleItems": [ref]}]}
        with self.assertRaisesRegex(ValueError, "invalid bundle item reference target"):
            details.parse_next_bundle({"url": "https://example.com/bundle"}, bundle)

    def test_rejects_unknown_reference_shapes(self):
        bundle = {"tiers": [{"price": {"amount": 5}, "bundleItems": [
            "$e:props:other:bundlePage:tiers:0:bundleItems:0"
        ]}]}
        with self.assertRaisesRegex(ValueError, "unexpected bundle item reference"):
            details.parse_next_bundle({"url": "https://example.com/bundle"}, bundle)

    def test_reuses_fresh_details_and_prunes_removed_bundles(self):
        now = datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)
        old = {"url": "https://humblebundle.com/books/old", "end_at": "2026-11-30T19:00:00", "fetched_at": "2026-11-14T17:00:00Z", "tiers": []}
        removed = {"url": "https://humblebundle.com/books/removed", "end_at": "2026-11-30T19:00:00", "fetched_at": "2026-11-14T17:00:00Z", "tiers": []}
        sources = [{"url": old["url"], "end_at": old["end_at"]}, {"url": "https://humblebundle.com/books/new", "end_at": "2026-11-30T19:00:00"}]
        fresh = {"url": sources[1]["url"], "end_at": sources[1]["end_at"], "tiers": [{"items": []}]}
        with patch.object(details, "parse_bundle", return_value=fresh) as fetch:
            output = details.build_details(sources, {"items": [old, removed]}, now, refresh_after_hours=168)
        self.assertEqual([item["url"] for item in output["items"]], [old["url"], fresh["url"]])
        self.assertEqual(output["errors"], [])
        fetch.assert_called_once_with(sources[1])


if __name__ == "__main__":
    unittest.main()
