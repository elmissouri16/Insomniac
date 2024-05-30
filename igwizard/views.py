import datetime
from enum import Enum, unique
from typing import Optional
from PIL.Image import Image
from igwizard.device_manager import DeviceManager
from insomniac import hardban_indicator, sleeper
from insomniac.actions_types import GetProfileAction
import re

from insomniac.utils import COLOR_ENDC, COLOR_FAIL, COLOR_OKGREEN, Timer
from insomniac.views import LanguageNotEnglishException

TEXTVIEW_OR_BUTTON_REGEX = "android.widget.TextView|android.widget.Button"
VIEW_OR_VIEWGROUP_REGEX = "android.view.View|android.view.ViewGroup"
RECYCLERVIEW_OR_LISTVIEW_REGEX = (
    "androidx.recyclerview.widget.RecyclerView|android.widget.ListView"
)


def case_insensitive_re(str_list):
    if isinstance(str_list, str):
        strings = str_list
    else:
        strings = "|".join(str_list)
    re_str = f"(?i)({strings})"
    return re_str


class TabBarTabs(Enum):
    HOME = 0
    SEARCH = 1
    ADD = 2
    ACTIVITY = 3
    PROFILE = 4


class SearchTabs(Enum):
    FOR_YOU = 0
    ACCOUNTS = 1
    AUDIO = 2
    TAGS = 3
    PLACES = 4
    REELS = 5


class ProfileTabs(Enum):
    POSTS = 0
    REELS = 1
    MENTIONS = 2


class InstagramView:
    ACTION_BAR_TITLE_ID = "{0}:id/action_bar_title"
    USERNAME_ALLOWED_SYMBOLS_REGEX = re.compile(r"[a-z0-9._-]+")

    def __init__(self, device: DeviceManager):
        self.device = device

    # TODO not sure if necessary
    def is_visible(self):
        raise NotImplementedError()

    def wait_until_visible(self):
        raise NotImplementedError()

    def get_title(self) -> Optional[str]:
        action_bar_title = self.device.find(
            resourceId=f"{self.device.app_id}:id/action_bar_title",
            className="android.widget.TextView",
        )
        if action_bar_title.exists():
            return action_bar_title.get_text()
        else:
            return None

    def press_back_arrow(self) -> "InstagramView":
        button_back = self.device.find(
            resourceId=f"{self.device.app_id}:id/action_bar_button_back",
            className="android.widget.ImageView",
        )
        if button_back.exists():
            button_back.click()
        else:
            print(
                COLOR_FAIL
                + f"Cannot find back arrow in {self.__class__.__name__}, press hardware back"
                + COLOR_ENDC
            )
            if not self.device.back():
                raise RuntimeError("Unexpected app state: want to go back but can't")
        return self.on_back_pressed()

    def on_back_pressed(self) -> "InstagramView":
        return self

    def format_username(self, raw_text: str) -> str:
        return "".join(re.findall(self.USERNAME_ALLOWED_SYMBOLS_REGEX, raw_text))


class TabBarView(InstagramView):
    HOME_CONTENT_DESC = "Home"
    SEARCH_CONTENT_DESC = "[Ss]earch and [Ee]xplore"
    REELS_CONTENT_DESC = "Reels"
    ORDERS_CONTENT_DESC = "Orders"
    ACTIVITY_CONTENT_DESC = "Activity"
    PROFILE_CONTENT_DESC = "Profile"

    top = None

    def __init__(self, device: DeviceManager):
        super().__init__(device)
        self.top = None

    def is_visible(self) -> bool:
        if self._get_tab_bar().exists(quick=True):
            return True
        self.device.close_keyboard()
        return self._get_tab_bar().exists()

    def _get_tab_bar(self):
        tab_bar = self.device.find(
            resourceIdMatches=case_insensitive_re(f"{self.device.app_id}:id/tab_bar"),
            className="android.widget.LinearLayout",
        )
        return tab_bar

    def get_top(self):
        top = self._get_top()
        if top is not None:
            return top
        self.device.close_keyboard()
        return self._get_top()

    def navigate_to_home(self):
        self.navigate_to(TabBarTabs.HOME)
        return HomeView(self.device)

    def navigate_to_search(self):
        self.navigate_to(TabBarTabs.SEARCH)
        return SearchView(self.device)

    def navigate_to_reels(self):
        self.navigate_to(TabBarTabs.REELS)

    def navigate_to_orders(self):
        self.navigate_to(TabBarTabs.ORDERS)

    def navigate_to_activity(self):
        self.navigate_to(TabBarTabs.ACTIVITY)

    def navigate_to_profile(self):
        self.navigate_to(TabBarTabs.PROFILE)
        return ProfileView(self.device, is_own_profile=True)

    def navigate_to(self, tab: TabBarTabs):
        tab_name = tab.name
        print(f"Navigate to {tab_name}")
        button = None
        tab_bar_view = self._get_tab_bar()

        if not self.is_visible():
            # There may be no TabBarView if Instagram was opened via a deeplink. Then we have to clear the backstack.
            is_backstack_cleared = self._clear_backstack()
            if not is_backstack_cleared:
                raise RuntimeError("Unexpected app state: cannot clear back stack")

        if tab == TabBarTabs.HOME:
            button = tab_bar_view.child(
                descriptionMatches=case_insensitive_re(TabBarView.HOME_CONTENT_DESC)
            )
        elif tab == TabBarTabs.SEARCH:
            button = tab_bar_view.child(
                descriptionMatches=case_insensitive_re(TabBarView.SEARCH_CONTENT_DESC)
            )
            if not button.exists():
                # Some accounts display the search btn only in Home -> action bar
                print("Didn't find search in the tab bar...")
                home_view = self.navigate_to_home()
                home_view.navigate_to_search()
                return
        elif tab == TabBarTabs.REELS:
            button = tab_bar_view.child(
                descriptionMatches=case_insensitive_re(TabBarView.REELS_CONTENT_DESC)
            )
        elif tab == TabBarTabs.ORDERS:
            button = tab_bar_view.child(
                descriptionMatches=case_insensitive_re(TabBarView.ORDERS_CONTENT_DESC)
            )
        elif tab == TabBarTabs.ACTIVITY:
            button = tab_bar_view.child(
                descriptionMatches=case_insensitive_re(TabBarView.ACTIVITY_CONTENT_DESC)
            )
        elif tab == TabBarTabs.PROFILE:
            button = tab_bar_view.child(
                descriptionMatches=case_insensitive_re(TabBarView.PROFILE_CONTENT_DESC)
            )

        timer = Timer(seconds=20)
        while not timer.is_expired():
            if button.exists():
                # Two clicks to reset tab content
                button.click()
                button.click()
                if self._is_correct_tab_opened(tab):
                    return
                else:
                    print(
                        COLOR_OKGREEN
                        + f"{tab_name} tab is not opened, will try again."
                        + COLOR_ENDC
                    )
                    sleeper.random_sleep()
            else:
                seconds_left = timer.get_seconds_left()
                if seconds_left > 0:
                    print(
                        COLOR_OKGREEN
                        + f"Opening {tab_name}, {seconds_left} seconds left..."
                        + COLOR_ENDC
                    )
                    # Maybe we are banned?
                    hardban_indicator.detect_webview(self.device)

        print(
            COLOR_FAIL + f"Didn't find tab {tab_name} in the tab bar... "
            f"Maybe English language is not set!?" + COLOR_ENDC
        )

        raise LanguageNotEnglishException()

    def _clear_backstack(self):
        attempt = 0
        max_attempts = 10
        is_message_printed = False
        while not self.is_visible():
            if not is_message_printed:
                print(COLOR_OKGREEN + "Clearing the back stack..." + COLOR_ENDC)
                is_message_printed = True
            if attempt > 0 and attempt % 2 == 0:
                hardban_indicator.detect_webview(self.device)
            if attempt >= max_attempts:
                return False
            self.press_back_arrow()
            # On fresh apps there may be a location request window after a backpress
            DialogView(self.device).close_location_access_dialog_if_visible()
            attempt += 1
        return True

    def _is_correct_tab_opened(self, tab: TabBarTabs) -> bool:
        if tab == TabBarTabs.HOME:
            return HomeView(self.device).is_visible()
        elif tab == TabBarTabs.SEARCH:
            return SearchView(self.device).is_visible()
        elif tab == TabBarTabs.PROFILE:
            return ProfileView(self.device, is_own_profile=True).is_visible()
        else:
            # We can support more tabs' checks here
            return True

    def _get_top(self):
        if self.top is None:
            try:
                self.top = self._get_tab_bar().get_bounds()["top"]
            except:
                return None
        return self.top
