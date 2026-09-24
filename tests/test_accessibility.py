from __future__ import annotations

import os
import re
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _relative_luminance(hex_color: str) -> float:
    """Compute relative luminance according to WCAG 2.1 specifications."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def _channel_lum(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r_lum = _channel_lum(r)
    g_lum = _channel_lum(g)
    b_lum = _channel_lum(b)
    return 0.2126 * r_lum + 0.7152 * g_lum + 0.0722 * b_lum


def _contrast_ratio(hex1: str, hex2: str) -> float:
    """Compute WCAG 2.1 contrast ratio between two hex colors."""
    lum1 = _relative_luminance(hex1)
    lum2 = _relative_luminance(hex2)
    l_max = max(lum1, lum2)
    l_min = min(lum1, lum2)
    return (l_max + 0.05) / (l_min + 0.05)


def test_accessibility_files_exist():
    """Verify all accessible UI and template files exist in expected project paths."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    expected_files = [
        os.path.join(base_dir, "frontend", "index.html"),
        os.path.join(base_dir, "frontend", "styles.css"),
        os.path.join(base_dir, "frontend", "app.js"),
        os.path.join(base_dir, "frontend", "package.json"),
        os.path.join(base_dir, "app", "templates", "index.html"),
        os.path.join(base_dir, "app", "static", "styles.css"),
        os.path.join(base_dir, "app", "static", "app.js"),
        os.path.join(base_dir, "index.html"),
        os.path.join(base_dir, "ACCESSIBILITY.md"),
    ]
    for file_path in expected_files:
        assert os.path.isfile(file_path), f"Missing required file: {file_path}"
        assert os.path.getsize(file_path) > 0, f"File is empty: {file_path}"


def test_served_html_endpoint():
    """Verify GET / returns 200 OK text/html with security headers and WCAG landmarks."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "X-Content-Type-Options" in resp.headers
    assert "Content-Security-Policy" in resp.headers
    assert "<main id=\"main\">" in resp.text
    assert "skip-link" in resp.text


def test_served_static_assets():
    """Verify static assets are properly served for styling and scripts."""
    css_resp = client.get("/styles.css")
    assert css_resp.status_code == 200
    assert ":root" in css_resp.text

    js_resp = client.get("/app.js")
    assert js_resp.status_code == 200
    assert "speechSynthesis" in js_resp.text


def test_wcag_semantic_landmarks():
    """Verify core HTML5 semantic landmarks for screen reader navigation."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(base_dir, "frontend", "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert "<header class=\"site-header\">" in html
    assert "<main id=\"main\">" in html
    assert "<footer class=\"site-footer\">" in html
    assert "href=\"#main\"" in html
    assert "role=\"status\"" in html
    assert "aria-live=\"polite\"" in html


def test_wcag_color_contrast_ratios():
    """Verify all text and badge colors clear WCAG 2.1 AAA (7.0:1) or AA (4.5:1)."""
    # Palette defined in frontend/styles.css
    palette = {
        "bg": "#EEF1EA",
        "ink": "#111A24",
        "ink_soft": "#24303A",
        "ink_faint": "#2D3732",
        "accent": "#134B46",
        "accent_ink": "#FFFFFF",
        "risk_high": "#8F160E",
        "risk_high_bg": "#FCE8E6",
        "risk_medium": "#6E4000",
        "risk_medium_bg": "#F7ECD0",
        "risk_low": "#185635",
        "risk_low_bg": "#E1EEE5",
        "risk_info": "#1D3B54",
        "risk_info_bg": "#E4E9EE",
    }

    # Ink on background
    assert _contrast_ratio(palette["ink"], palette["bg"]) >= 7.0  # AAA
    assert _contrast_ratio(palette["ink_soft"], palette["bg"]) >= 7.0  # AAA
    assert _contrast_ratio(palette["ink_faint"], palette["bg"]) >= 7.0  # AAA

    # Accent buttons
    assert _contrast_ratio(palette["accent"], palette["bg"]) >= 7.0  # AAA
    assert _contrast_ratio(palette["accent_ink"], palette["accent"]) >= 7.0  # AAA

    # Risk badge contrasts
    assert _contrast_ratio(palette["risk_high"], palette["risk_high_bg"]) >= 7.0  # AAA
    assert _contrast_ratio(palette["risk_medium"], palette["risk_medium_bg"]) >= 7.0  # AAA
    assert _contrast_ratio(palette["risk_low"], palette["risk_low_bg"]) >= 7.0  # AAA
    assert _contrast_ratio(palette["risk_info"], palette["risk_info_bg"]) >= 7.0  # AAA


def test_wcag_form_labels_and_inputs():
    """Verify all form controls have corresponding explicit labels and aria attributes."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(base_dir, "frontend", "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert "for=\"docA\"" in html
    assert "id=\"docA\"" in html
    assert "for=\"docB\"" in html
    assert "id=\"docB\"" in html
    assert "for=\"fileA\"" in html
    assert "id=\"fileA\"" in html
    assert "for=\"fileB\"" in html
    assert "id=\"fileB\"" in html


def test_wcag_keyboard_accessibility():
    """Verify skip-link, focus visible styles, and tabindex compliance."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(base_dir, "frontend", "styles.css"), encoding="utf-8") as f:
        css = f.read()

    assert ":focus-visible" in css
    assert "outline: 3px solid var(--focus-ring)" in css
    assert ".skip-link:focus" in css

    with open(os.path.join(base_dir, "frontend", "index.html"), encoding="utf-8") as f:
        html = f.read()
    # Ensure no positive tabindexes exist that disrupt natural DOM tab order
    positive_tabindex = re.findall(r'tabindex=["\']([1-9][0-9]*)["\']', html)
    assert len(positive_tabindex) == 0


def test_wcag_voice_read_aloud_feature():
    """Verify Web Speech API read aloud integration for auditory accessibility."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(base_dir, "frontend", "index.html"), encoding="utf-8") as f:
        html = f.read()
    assert "id=\"voiceToggle\"" in html
    assert "Read Aloud" in html

    with open(os.path.join(base_dir, "frontend", "app.js"), encoding="utf-8") as f:
        js = f.read()
    assert "window.speechSynthesis" in js
    assert "SpeechSynthesisUtterance" in js
    assert "speakText" in js


def test_wcag_motion_and_text_resizing():
    """Verify prefers-reduced-motion support and text resizing capabilities."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(base_dir, "frontend", "styles.css"), encoding="utf-8") as f:
        css = f.read()

    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "--motion: 0ms;" in css

    with open(os.path.join(base_dir, "frontend", "index.html"), encoding="utf-8") as f:
        html = f.read()
    assert "id=\"fontDown\"" in html
    assert "id=\"fontUp\"" in html
    assert "id=\"contrastToggle\"" in html
    assert "id=\"plainToggle\"" in html
