from web.source_contract import read_source as _read_source
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = _read_source(ROOT / "static" / "app.css", encoding="utf-8")
BASE = _read_source(ROOT / "templates" / "base.html", encoding="utf-8")
DASHBOARD = _read_source(ROOT / "templates" / "dashboard.html", encoding="utf-8")
PROFILE = _read_source(ROOT / "templates" / "my_profile.html", encoding="utf-8")
APP = _read_source(ROOT / "app.py", encoding="utf-8")


def _relative_luminance(color):
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    channels = [
        value / 12.92 if value <= 0.04045
        else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(foreground, background):
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_accessible_theme_contract_markers_exist():
    assert "RB_PHASE25_ACCESSIBLE_THEME_CONTRAST_V1" in CSS
    assert 'id="rb-nav-v4-style"' in BASE
    assert ".sidebar .rb-nav-group>summary::after" in CSS
    assert ".btn:focus-visible" in CSS
    assert "input::placeholder" in CSS


def test_navigation_and_secondary_text_colors_meet_wcag_aa():
    combinations = (
        ("#b8c5d6", "#0b1220"),  # dark secondary copy
        ("#b7c6d9", "#07111f"),  # sidebar group labels
        ("#e5eef9", "#07111f"),  # sidebar links
        ("#94a3b8", "#0f192a"),  # dark input placeholder
        ("#52627a", "#f4f7fb"),  # light secondary copy
        ("#ffffff", "#2563eb"),  # primary button label
    )
    for foreground, background in combinations:
        assert _contrast(foreground, background) >= 4.5


def test_dashboard_uses_semantic_theme_colors_not_faded_fixed_copy():
    assert "var(--rb-text-muted,var(--muted))" in DASHBOARD
    assert "var(--rb-card,var(--panel))" in DASHBOARD
    assert "var(--rb-info-bg" in DASHBOARD
    assert "color:#91a8bc" not in DASHBOARD
    assert "background:#193650" not in DASHBOARD


def test_sidebar_group_controls_are_not_dimmed():
    assert 'opacity:.55' not in BASE
    for declaration in (
        "color:#b7c6d9",
        "font-size:11px",
        "opacity:1",
        "color:#9fc2ee",
    ):
        assert declaration in CSS


def test_mixed_light_dark_surfaces_keep_text_visible():
    assert "RB_PHASE25B_MIXED_SURFACE_CONTRAST_V1" in CSS
    assert "body.theme-dark .app-header" in CSS
    assert "body.theme-dark .lang-btn" in CSS
    assert "body.theme-dark .studio-card" in CSS
    assert ".sidebar .pacs-mini.online small" in CSS
    assert _contrast("#b8c5d6", "#111b2e") >= 4.5
    assert _contrast("#f3f7fc", "#162238") >= 4.5


def test_global_theme_compatibility_covers_authenticated_legacy_surfaces():
    marker = "RB_PHASE25C_GLOBAL_THEME_COMPATIBILITY_V1"
    assert marker in CSS
    compatibility = CSS.split(marker, 1)[1]
    legacy_surfaces = (
        ".management-kpis>div",
        ".exec-kpis>div",
        ".ops-kpis>div",
        ".ops-health-strip>div",
        ".metric-card",
        ".studio-shortcut-row",
        ".studio-launcher-item",
        ".si-card",
        ".status-card",
        ".ocr-card",
        ".confirm-dialog",
    )
    for selector in legacy_surfaces:
        assert compatibility.count(selector) >= 2


def test_management_kpis_follow_theme_instead_of_fixed_white_surface():
    compatibility = CSS.split("RB_PHASE25C_GLOBAL_THEME_COMPATIBILITY_V1", 1)[1]
    assert ".management-kpis>div" in compatibility
    assert "background:var(--rb-card,var(--panel))" in compatibility
    assert ") :is(h1,h2,h3,h4,b,strong){color:var(--rb-text-main" in compatibility
    assert ") :is(p,span,small,label){color:var(--rb-text-muted" in compatibility
    assert _contrast("#f3f7fc", "#111b2e") >= 4.5


def test_auto_dark_overlays_never_render_light_text_on_white():
    marker = "RB_PHASE25D_GLOBAL_OVERLAY_THEME_V1"
    assert marker in CSS
    overlays = CSS.split(marker, 1)[1]
    for selector in (
        "body.theme-auto :is(.user-trigger,.user-dropdown,.confirm-dialog)",
        "body.theme-auto .user-dropdown :is(strong,small,a)",
        "body.theme-auto .user-dropdown>a:hover",
        "body.theme-auto .user-dropdown>a.danger",
        "body.theme-auto .dropdown-divider",
    ):
        assert selector in overlays
    assert "background:var(--rb-card,#111b2e)" in overlays
    assert "color:var(--rb-text-main,#f3f7fc)" in overlays
    assert _contrast("#f3f7fc", "#111b2e") >= 4.5


def test_multi_level_theme_presets_are_selectable_and_validated():
    marker = "RB_PHASE25E_MULTI_LEVEL_THEME_PRESETS_V1"
    assert marker in CSS
    assert "['light-soft','light','dim','dark','midnight','auto']" in PROFILE
    for value in ("'light-soft'", "'dim'", "'midnight'"):
        assert value in APP
    assert "selected_theme == 'light-soft'" in BASE
    assert "selected_theme in ['dim','midnight']" in BASE


def test_added_theme_palettes_keep_normal_text_at_wcag_aa():
    combinations = (
        ("#1e2b3d", "#f8fafc"),  # soft light
        ("#52627a", "#f8fafc"),  # soft-light secondary
        ("#f1f5f9", "#223044"),  # dim
        ("#c0cad8", "#223044"),  # dim secondary
        ("#f8fafc", "#07101f"),  # midnight
        ("#bdc7d5", "#07101f"),  # midnight secondary
    )
    for foreground, background in combinations:
        assert _contrast(foreground, background) >= 4.5

    presets = CSS.split("RB_PHASE25E_MULTI_LEVEL_THEME_PRESETS_V1", 1)[1]
    for selector in (
        "body.theme-light-soft",
        "body.theme-dim",
        "body.theme-midnight",
    ):
        assert selector in presets


def test_accessible_color_palettes_are_selectable_and_validated():
    marker = "RB_PHASE25F_ACCESSIBLE_COLOR_PALETTES_V1"
    assert marker in CSS
    for value in ("default", "teal", "violet", "green", "amber", "rose"):
        assert "accent-" + value in CSS
        assert "('" + value + "'," in PROFILE
        assert "'" + value + "'" in APP
    assert "selected_accent = (user_profile.accent or 'default')" in BASE
    assert "accent-{{selected_accent}}" in BASE
    assert "Color Palette" in PROFILE


def test_palette_primary_buttons_keep_white_text_at_wcag_aa():
    button_backgrounds = (
        "#2563eb",  # RadBridge Blue
        "#0f766e",  # Clinical Teal
        "#6d28d9",  # Violet
        "#15803d",  # Emerald
        "#b45309",  # Amber
        "#be123c",  # Rose
    )
    for background in button_backgrounds:
        assert _contrast("#ffffff", background) >= 4.5

    palettes = CSS.split("RB_PHASE25F_ACCESSIBLE_COLOR_PALETTES_V1", 1)[1]
    assert "clinical\n   success, warning and danger colors remain semantically stable" in palettes
    assert "body.theme-auto.accent-teal" in palettes
