"""Static regression checks for 5-page Android layout and preserved UI controls.

Runs in Windows Gateway pytest without an Android emulator or Android SDK.
These checks do not replace Gradle resource compilation and on-device navigation.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

ANDROID = "{http://schemas.android.com/apk/res/android}"
ROOT = Path(__file__).resolve().parents[2] / "android_project" / "app" / "src" / "main"
LAYOUT = ROOT / "res" / "layout" / "activity_main.xml"
MENU = ROOT / "res" / "menu" / "menu_main_navigation.xml"
CONTROLLER = ROOT / "java" / "com" / "ittrader" / "smarthub" / "DashboardNavigation.kt"


def get_id(element):
    return element.get(ANDROID + "id", "").removeprefix("@+id/")


def test_five_separate_scrollable_pages_with_fixed_bottom_bar():
    root = ET.parse(LAYOUT).getroot()
    assert root.tag == "LinearLayout"
    frame = root.find("FrameLayout")
    assert frame is not None
    pages = frame.findall("ScrollView")
    expected = ["pageHome", "pageAccounts", "pageResearch", "pageRisk", "pageSettings"]
    assert [get_id(page) for page in pages] == expected
    assert all(page.get(ANDROID + "visibility") == "gone" for page in pages)
    nav = root.find("com.google.android.material.bottomnavigation.BottomNavigationView")
    assert nav is not None
    assert get_id(nav) == "bottomNavigation"
    # A root LinearLayout allows the content pane to grow independently of tabs.
    assert frame.get(ANDROID + "layout_weight") == "1"
    assert frame.get(ANDROID + "layout_height") == "0dp"


def test_original_feature_controls_remain_in_correct_sections():
    root = ET.parse(LAYOUT).getroot()
    page_by_id = {get_id(page): page for page in root.findall("./FrameLayout/ScrollView")}

    def inner_xml(page_name):
        return ET.tostring(page_by_id[page_name], encoding="unicode")

    assertions = {
        "pageHome": ("txtLivePrice", "txtAnalysisOutput", "btnOpenAccounts", "btnOpenResearch", "btnOpenRisk"),
        "pageAccounts": ("section_mt5_accounts",),
        "pageResearch": ("section_ai_intelligence", "section_nas100_research", "btnQueryAlerts", "btnQueryResearch"),
        "pageRisk": ("btnBotEmergencyStop", "btnPipnexCalc", "btnPipnexPropFirm", "btnSyncMt5"),
        "pageSettings": ("btnEnrollDevice", "btnLogout", "edtGatewayIp", "edtLogs", "btnProcess"),
    }
    for page, needles in assertions.items():
        markup = inner_xml(page)
        assert all(needle in markup for needle in needles), page

    ids = [
        get_id(node) for node in root.iter()
        if node.get(ANDROID + "id") is not None
    ]
    assert len(ids) == len(set(ids)), "Duplicate Android view id in main layout"


def test_navigation_menu_and_controller_match_all_five_pages():
    root = ET.parse(MENU).getroot()
    items = root.findall("item")
    ids = [get_id(i) for i in items]
    assert ids == ["nav_home", "nav_accounts", "nav_research", "nav_risk", "nav_settings"]
    controller = CONTROLLER.read_text(encoding="utf-8")
    for nav_id, screen_id in zip(
        ids, ["pageHome", "pageAccounts", "pageResearch", "pageRisk", "pageSettings"]
    ):
        assert "R.id." + nav_id in controller
        assert "R.id." + screen_id in controller
    # Navigation is a view-only action, never a trading side effect.
    assert "order_send(" not in controller
    assert "setBotMode(" not in controller


def test_visible_header_never_claims_ready_trading():
    root = ET.parse(LAYOUT).getroot()
    title = root.find(".//TextView[@{" + "http://schemas.android.com/apk/res/android" + "}id='@+id/txtGlobalFeedback']")
    assert title is not None
    labels = (ROOT / "res" / "values" / "nav_labels.xml").read_text(encoding="utf-8")
    assert "RESEARCH ONLY" in labels
    assert "ORDERS DISABLED" in labels
