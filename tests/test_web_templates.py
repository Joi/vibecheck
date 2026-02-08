"""Tests for template rendering - verifying block inheritance works."""

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader


@pytest.fixture
def jinja_env():
    """Create a Jinja2 environment pointing at the templates directory."""
    templates_dir = Path(__file__).parent.parent / "src" / "vibecheck" / "templates"
    return Environment(loader=FileSystemLoader(str(templates_dir)))


class TestTemplateBlockInheritance:
    """Verify that child templates' style blocks are actually rendered."""

    def test_discover_styles_present_in_rendered_html(self, jinja_env):
        template = jinja_env.get_template("discover.html")
        html = template.render(request=None, active_page="discover", items=[], mode="mixed")
        assert ".discover-container" in html
        assert ".swipe-card" in html

    def test_bookmarks_styles_present_in_rendered_html(self, jinja_env):
        template = jinja_env.get_template("bookmarks.html")
        html = template.render(request=None, active_page="bookmarks")
        assert ".bookmark-card" in html


class TestAccessibility:
    """Verify accessibility requirements are met in templates."""

    def test_base_template_has_reduced_motion_css(self, jinja_env):
        """base.html must include a prefers-reduced-motion media query."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "prefers-reduced-motion" in html, (
            "base.html must include @media (prefers-reduced-motion: reduce) "
            "to respect user motion preferences (WCAG 2.1 AA)."
        )

    def test_discover_js_checks_reduced_motion(self, jinja_env):
        """Discover page JS must check prefers-reduced-motion for gesture animations."""
        template = jinja_env.get_template("discover.html")
        html = template.render(request=None, active_page="discover", items=[], mode="mixed")
        assert "prefers-reduced-motion" in html, (
            "Discover page JS must check prefers-reduced-motion to disable "
            "spring animations and fly-off effects."
        )


class TestResponsiveCSS:
    """Verify responsive CSS patterns in templates."""

    def test_card_grid_is_mobile_first(self, jinja_env):
        """Card grid must use 1fr default (not minmax(350px)) to prevent phone overflow."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "minmax(350px" not in html, (
            "Card grid still uses minmax(350px, 1fr) as default. "
            "This overflows on phones < 400px wide. Use 1fr default."
        )


class TestMobileNavigation:
    """Verify mobile navigation elements exist."""

    def test_hamburger_button_exists(self, jinja_env):
        """base.html must have a hamburger menu button for mobile."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "nav-toggle" in html, (
            "base.html must include a hamburger menu button (class=nav-toggle) "
            "for mobile viewports."
        )

    def test_hamburger_has_aria_attributes(self, jinja_env):
        """Hamburger button must have proper ARIA attributes."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "aria-expanded" in html, "Hamburger button must have aria-expanded attribute."
        assert "aria-label" in html, "Hamburger button must have aria-label attribute."


class TestNavigation:
    """Verify navigation completeness."""

    def test_bookmarks_link_in_nav(self, jinja_env):
        """Navigation must include a link to the bookmarks page."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "/bookmarks" in html, (
            "Navigation must include a link to /bookmarks. "
            "The route exists (web.py) and Discover saves bookmarks, "
            "but users can't find them."
        )

    def test_bookmarks_link_active_state(self, jinja_env):
        """Bookmarks nav link must have active class when on bookmarks page."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="bookmarks")
        import re

        bookmarks_link = re.search(r'<a[^>]*href="/bookmarks"[^>]*>', html)
        assert bookmarks_link is not None, "Bookmarks link not found in nav"
        assert "active" in bookmarks_link.group(), (
            "Bookmarks link should have 'active' class when active_page='bookmarks'"
        )


class TestAdminTemplates:
    """Verify admin templates extend admin/base.html."""

    def test_admin_base_template_exists(self, jinja_env):
        """admin/base.html must exist as a shared admin template."""
        template = jinja_env.get_template("admin/base.html")
        html = template.render(request=None, active_page="admin")
        assert "admin" in html.lower(), "admin/base.html must render admin content"

    def test_admin_login_extends_admin_base(self, jinja_env):
        """Admin login template should extend admin/base.html."""
        template = jinja_env.get_template("admin/login.html")
        html = template.render(request=None, active_page="admin")
        # After refactoring, admin pages should share the admin shell
        assert "admin-nav" in html or "admin-header" in html or "Admin" in html, (
            "Admin login should render admin shell from admin/base.html"
        )


class TestUnifiedComponents:
    """Verify unified component system exists."""

    def test_base_has_card_modifier_classes(self, jinja_env):
        """base.html must define card modifier CSS classes."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert ".card--compact" in html, "Missing .card--compact modifier class"

    def test_base_has_button_states(self, jinja_env):
        """Buttons must have disabled, focus-visible, and active states."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert ":disabled" in html or "[disabled]" in html, "Buttons missing :disabled state"
        assert "focus-visible" in html, "Buttons missing :focus-visible state"

    def test_base_has_unified_tag_system(self, jinja_env):
        """base.html must define a unified .tag with modifier classes."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert ".tag" in html, "Missing base .tag class"


class TestDesignTokens:
    """Verify design token system exists."""

    def test_spacing_scale_custom_properties(self, jinja_env):
        """base.html must define spacing scale CSS custom properties."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "--space-1" in html, "Missing --space-1 custom property"
        assert "--space-4" in html, "Missing --space-4 custom property"
        assert "--space-8" in html, "Missing --space-8 custom property"

    def test_fluid_typography(self, jinja_env):
        """h1 must use clamp() for fluid sizing instead of breakpoint jumps."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "clamp(" in html, "Typography should use clamp() for fluid sizing"

    def test_tool_page_no_inline_margin_styles(self, jinja_env):
        """tool.html should not use inline style for margins."""
        template = jinja_env.get_template("tool.html")
        # Render with minimal context - we just need to check CSS/HTML structure
        try:
            html = template.render(
                request=None,
                active_page="tools",
                tool={
                    "name": "Test",
                    "slug": "test",
                    "description": "test",
                    "url": "http://test.com",
                    "category": "test",
                    "tags": [],
                    "avg_score": 0,
                    "total_votes": 0,
                },
                evaluations=[],
                mentions=[],
                links=[],
                communities=[],
            )
        except Exception:
            # If template needs more context, just read the source
            import pathlib

            html = pathlib.Path(
                "/Users/joi/vibecheck/src/vibecheck/templates/tool.html"
            ).read_text()
        assert 'style="margin-bottom' not in html, (
            "tool.html still uses inline margin-bottom styles. Use .tool-section class instead."
        )


class TestA11yEnhancements:
    """Verify accessibility enhancements."""

    def test_skip_to_content_link(self, jinja_env):
        """base.html must have a skip-to-content link for keyboard users."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "skip-to-content" in html or "skip-link" in html, (
            "base.html must include a skip-to-content link."
        )

    def test_nav_has_aria_label(self, jinja_env):
        """Nav element must have an aria-label."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        # Check that <nav has aria-label (not just the hamburger button's aria-label)
        import re

        nav_tag = re.search(r"<nav[^>]*>", html)
        assert nav_tag is not None, "No <nav> element found"
        assert "aria-label" in nav_tag.group(), "Nav must have aria-label attribute"

    def test_focus_visible_styles_exist(self, jinja_env):
        """base.html must define :focus-visible styles for all interactive elements."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "a:focus-visible" in html, "Missing a:focus-visible global style in base.html"

    def test_search_has_role(self, jinja_env):
        """Search box must have role=search."""
        template = jinja_env.get_template("index.html")
        html = template.render(
            request=None,
            active_page="tools",
            tools=[],
            total_tools=0,
            total_articles=0,
            communities=[],
        )
        assert 'role="search"' in html, 'Search box must have role="search"'

    def test_main_has_id_for_skip_link(self, jinja_env):
        """Main element must have id for skip-to-content link target."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert 'id="main-content"' in html, "Main element must have id='main-content'"

    def test_hover_hover_media_query(self, jinja_env):
        """Card hover effects should be guarded with @media (hover: hover)."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "hover: hover" in html, (
            "Card hover effects must be wrapped in @media (hover: hover) "
            "to prevent sticky hover on touch devices."
        )


class TestLoadingAndFeedback:
    """Verify loading states and error feedback exist."""

    def test_skeleton_css_exists(self, jinja_env):
        """base.html must define skeleton loading animation."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "skeleton" in html, "Missing skeleton loading CSS in base.html"
        assert "@keyframes" in html and "shimmer" in html, "Missing shimmer animation"

    def test_toast_component_exists(self, jinja_env):
        """base.html must define a toast/notification component."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "toast" in html, "Missing toast notification CSS in base.html"

    def test_empty_state_component_exists(self, jinja_env):
        """base.html must define an empty state component."""
        template = jinja_env.get_template("base.html")
        html = template.render(request=None, active_page="tools")
        assert "empty-state" in html, "Missing .empty-state component CSS in base.html"
