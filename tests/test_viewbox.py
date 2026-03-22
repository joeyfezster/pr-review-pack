"""Tests for ViewBox calculation edge cases in _calculate_viewbox."""

from __future__ import annotations

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from render_review_pack import _calculate_viewbox


class TestViewBox:
    def test_default_fallback_empty_arch(self):
        """Empty architecture dict returns the fallback viewBox."""
        assert _calculate_viewbox({}) == "0 0 780 360"

    def test_default_fallback_none(self):
        """None architecture returns the fallback viewBox."""
        assert _calculate_viewbox(None) == "0 0 780 360"

    def test_default_fallback_no_zones(self):
        """Architecture with empty zones list returns fallback."""
        assert _calculate_viewbox({"zones": []}) == "0 0 780 360"

    def test_fits_zones(self):
        """All zones should be enclosed within the computed viewBox."""
        arch = {
            "zones": [
                {
                    "id": "zone-alpha",
                    "position": {"x": 100, "y": 50, "width": 120, "height": 70},
                },
                {
                    "id": "zone-beta",
                    "position": {"x": 300, "y": 200, "width": 120, "height": 70},
                },
            ],
            "arrows": [],
        }
        viewbox = _calculate_viewbox(arch)
        parts = viewbox.split()
        vb_x, vb_y, vb_w, vb_h = float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])

        # All zone positions must fit within the viewBox
        for zone in arch["zones"]:
            pos = zone["position"]
            zx, zy = pos["x"], pos["y"]
            zw, zh = pos["width"], pos["height"]
            # Zone left edge must be >= viewBox left edge
            assert zx >= vb_x, f"Zone {zone['id']} left edge {zx} outside viewBox left {vb_x}"
            # Zone top edge must be >= viewBox top edge
            assert zy >= vb_y, f"Zone {zone['id']} top edge {zy} outside viewBox top {vb_y}"
            # Zone right edge must be <= viewBox right edge
            assert zx + zw <= vb_x + vb_w, f"Zone {zone['id']} right edge outside viewBox"
            # Zone bottom edge must be <= viewBox bottom edge
            assert zy + zh <= vb_y + vb_h, f"Zone {zone['id']} bottom edge outside viewBox"

    def test_label_margin(self):
        """ViewBox should reserve ~120px left margin for row labels."""
        arch = {
            "zones": [
                {
                    "id": "zone-alpha",
                    "position": {"x": 100, "y": 50, "width": 120, "height": 70},
                },
            ],
            "arrows": [],
        }
        viewbox = _calculate_viewbox(arch)
        parts = viewbox.split()
        vb_x = float(parts[0])
        # The viewBox x should be at least 120px to the left of the leftmost zone
        # min_x=100, label_margin=120, pad=20 → vb_x = min(100-120, 0) - 20 = -40
        assert vb_x <= 100 - 120, f"Label margin insufficient: vb_x={vb_x}"

    def test_includes_arrows(self):
        """Arrow endpoints should be considered in viewBox bounds."""
        arch = {
            "zones": [
                {
                    "id": "zone-alpha",
                    "position": {"x": 100, "y": 50, "width": 120, "height": 70},
                },
            ],
            "arrows": [
                {
                    "from": {"x": 160, "y": 120},
                    "to": {"x": 500, "y": 300},
                },
            ],
        }
        viewbox = _calculate_viewbox(arch)
        parts = viewbox.split()
        vb_x, vb_y = float(parts[0]), float(parts[1])
        vb_w, vb_h = float(parts[2]), float(parts[3])

        # Arrow endpoint at (500, 300) must be within the viewBox
        assert 500 <= vb_x + vb_w, "Arrow x endpoint outside viewBox"
        assert 300 <= vb_y + vb_h, "Arrow y endpoint outside viewBox"

    def test_single_zone(self):
        """ViewBox works correctly with just one zone."""
        arch = {
            "zones": [
                {
                    "id": "zone-alpha",
                    "position": {"x": 50, "y": 80, "width": 120, "height": 70},
                },
            ],
            "arrows": [],
        }
        viewbox = _calculate_viewbox(arch)
        parts = viewbox.split()
        assert len(parts) == 4
        vb_x, vb_y, vb_w, vb_h = [float(p) for p in parts]

        # Zone must fit inside the viewBox
        assert 50 >= vb_x
        assert 80 >= vb_y
        assert 50 + 120 <= vb_x + vb_w
        assert 80 + 70 <= vb_y + vb_h

    def test_viewbox_format(self):
        """ViewBox string should have exactly 4 space-separated numeric values."""
        arch = {
            "zones": [
                {
                    "id": "zone-alpha",
                    "position": {"x": 20, "y": 160, "width": 120, "height": 70},
                },
            ],
            "arrows": [],
        }
        viewbox = _calculate_viewbox(arch)
        parts = viewbox.split()
        assert len(parts) == 4
        # All parts should be parseable as numbers
        for part in parts:
            float(part)  # will raise ValueError if not a number

    def test_zones_at_origin(self):
        """Zones positioned at (0,0) should still get proper padding."""
        arch = {
            "zones": [
                {
                    "id": "zone-alpha",
                    "position": {"x": 0, "y": 0, "width": 120, "height": 70},
                },
            ],
            "arrows": [],
        }
        viewbox = _calculate_viewbox(arch)
        parts = viewbox.split()
        vb_x, vb_y = float(parts[0]), float(parts[1])
        # vb_x should be negative (label_margin + pad)
        assert vb_x < 0, "ViewBox should extend left for label margin"
        # vb_y should be negative (pad)
        assert vb_y < 0, "ViewBox should extend up for padding"
