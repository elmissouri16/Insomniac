#! rewrite for device_facade.py
from dataclasses import dataclass
from enum import Enum, unique
from os import listdir
from random import uniform
import re
from time import sleep
from typing import Optional
import uiautomator2 as u2
from insomniac import sleeper
from insomniac.utils import COLOR_ENDC, COLOR_FAIL, COLOR_OKGREEN, COLOR_REPORT
from uiautomator2 import Device, UiObject
from PIL.Image import Image

UI_TIMEOUT_LONG = 5
UI_TIMEOUT_SHORT = 1
APP_ID = "com.instagram.android"

SCREEN_RECORDS_PATH = "screen_records"


@unique
class Place(Enum):
    # TODO: add more places
    RIGHT = 0
    WHOLE = 1
    CENTER = 2
    BOTTOM = 3
    LEFT = 4


@unique
class Direction(Enum):
    TOP = 0
    BOTTOM = 1
    RIGHT = 2
    LEFT = 3


@dataclass
class DeviceInfo:
    currentPackageName: str
    displayHeight: int
    displayRotation: int
    displaySizeDpX: int
    displaySizeDpY: int
    displayWidth: int
    productName: str
    screenOn: bool
    sdkInt: int
    naturalOrientation: bool

    @staticmethod
    def from_dict(data):
        return DeviceInfo(
            currentPackageName=data["currentPackageName"],
            displayHeight=data["displayHeight"],
            displayRotation=data["displayRotation"],
            displaySizeDpX=data["displaySizeDpX"],
            displaySizeDpY=data["displaySizeDpY"],
            displayWidth=data["displayWidth"],
            productName=data["productName"],
            screenOn=data["screenOn"],
            sdkInt=data["sdkInt"],
            naturalOrientation=data["naturalOrientation"],
        )


def create_device(device_id: str, typewriter):
    try:
        return DeviceManager(device_id, typewriter)
    except ImportError as e:
        print(COLOR_FAIL + str(e) + COLOR_ENDC)
        return None


class DeviceManager:
    device: Device = None
    device_id = None
    typewriter = None

    def __init__(self, device_id: str, typewriter):
        self.device_id = device_id
        self.typewriter = typewriter
        self.width = 0
        self.height = 0
        self.device = self
        try:
            self.device = u2.connect(self.device_id)
        except Exception as e:
            print(COLOR_FAIL + str(e) + COLOR_ENDC)
            self.device = None

    def find(self, *args, **kwargs) -> "View":
        view = self.device(*args, **kwargs)
        return View(view, self)

    def back(self):
        max_attempts = 2

        def normalize(hierarchy: str):
            """
            Remove all texts from hierarchy. It may contain some changing data, e.g. current time.
            """
            return re.sub(r'text=".*"', 'text=""', hierarchy)

        succeed = False
        attempts = 0
        while not succeed:
            if attempts >= max_attempts:
                print(
                    COLOR_FAIL
                    + f"Tried to press back {attempts} times with no success. Will proceed next..."
                    + COLOR_ENDC
                )
                break
            hierarchy_before = normalize(self.dump_hierarchy())
            self._press_back()
            hierarchy_after = normalize(self.dump_hierarchy())
            succeed = hierarchy_before != hierarchy_after
            if not succeed:
                print(
                    COLOR_OKGREEN
                    + "Pressed back but nothing changed on the screen. Will try again."
                    + COLOR_ENDC
                )
                sleeper.random_sleep()
            attempts += 1
        return succeed

    def _press_back(self):
        self.device.press("back")

    def _get_screen_size(self) -> tuple[int, int]:
        if self.width is not None and self.height is not None:
            return self.width, self.height
        self.width = self.deviceV2.info["displayWidth"]
        self.height = self.deviceV2.info["displayHeight"]
        return self.width, self.height

    def open_notifications(self):
        self.device.open_notification()

    def hide_notifications(self):
        self._press_back()

    def screen_click(self, place: Place):
        w, h = self._get_screen_size()
        if place == Place.RIGHT:
            left = int(w * 3 / 4)
            top = int(h / 2)
        else:
            return
        self.screen_click_by_coordinates(left, top)

    def screen_click_by_coordinates(self, left, top):
        self.device.click(left, top)

    def dump_hierarchy(self, path: str = None):
        xml_dump = self.device.dump_hierarchy()
        if path is not None:
            with open(path, "w") as file:
                file.write(xml_dump)
        return xml_dump

    def screenshot(self, path: str):
        self.device.screenshot(path)

    def is_screen_on(self) -> bool:
        return self.get_info().screenOn

    def is_screen_locked(self) -> bool:
        res = self.device.shell("dumpsys window")
        data = res.output.strip()
        flag = re.search("mDreamingLockscreen=(true|false)", data)
        return True if flag.group(1) == "true" else False

    def is_alive(self) -> bool:
        return self.device._check_alive()

    def wake_up(self):
        """Make sure agent is alive or bring it back up before starting."""
        attempts = 0
        while not self.is_alive() and attempts < 5:
            self.get_info()
            attempts += 1

    def get_brand(self) -> str:
        return self.get_info().productName

    def unlock(self):
        self.swipe(Direction.TOP, 0.8)
        if self.is_screen_locked():
            self.swipe(Direction.RIGHT, 0.8)

    def screen_off(self):
        self.device.screen_off()

    def swipe(self, direction: Direction, scale: float = 0.5):
        swipe_dir = ""
        if direction == Direction.TOP:
            swipe_dir = "up"
        elif direction == Direction.RIGHT:
            swipe_dir = "right"
        elif direction == Direction.LEFT:
            swipe_dir = "left"
        elif direction == Direction.BOTTOM:
            swipe_dir = "down"
        self.device.swipe_ext(swipe_dir, scale=scale)

    def get_info(self) -> DeviceInfo:
        return DeviceInfo.from_dict(self.device.info)

    def swipe_points(self, sx, sy, ex, ey, duration=None):
        if duration:
            self.device.swipe_points([[sx, sy], [ex, ey]], duration)
        else:
            self.device.swipe_points([[sx, sy], [ex, ey]], uniform(0.2, 0.6))

    def is_keyboard_open(self) -> bool:
        res = self.device.shell("dumpsys input_method")
        data = res.output.strip()
        #  return "mInputShown=true" in data
        flag = re.search("mInputShown=(true|false)", data)
        if flag is not None:
            return True if flag.group(1) == "true" else False
        return False

    def close_keyboard(self):
        if self.is_keyboard_open():
            self.device.press("back")
            print("Verifying again that keyboard is closed")
            if self.is_keyboard_open():
                print(
                    COLOR_FAIL
                    + "Keyboard is still open. Please close it manually and restart the script."
                    + COLOR_ENDC
                )
            else:
                print("Keyboard is closed now.")
            return
        print("Keyboard is already closed.")

    def _get_screen_size(self) -> tuple[int, int]:
        if self.width is not None and self.height is not None:
            return self.width, self.height
        _deviceInfo = self.get_info()
        return _deviceInfo.displayWidth, _deviceInfo.displayHeight


class View:
    device = None

    def __init__(self, view: UiObject, deviceManager: DeviceManager):
        self.deviceManager: DeviceManager = deviceManager
        self.view: UiObject = view

    def __iter__(self):
        children = []
        for item in self.view:
            children.append(View(item, self.device))
        return iter(children)

    def child(self, *args, **kwargs) -> Optional["View"]:
        view = self.view.child(*args, **kwargs)
        return View(view, self.device)

    def right(self, *args, **kwargs) -> Optional["View"]:
        view = self.view.right(*args, **kwargs)
        return View(view, self.device)

    def left(self, *args, **kwargs) -> Optional["View"]:
        view = self.view.left(*args, **kwargs)
        return View(view, self.device)

    def up(self, *args, **kwargs) -> Optional["View"]:
        view = self.view.up(*args, **kwargs)
        return View(view, self.device)

    def down(self, *args, **kwargs) -> Optional["View"]:
        view = self.view.down(*args, **kwargs)
        return View(view, self.device)

    def click(
        self, mode: Optional[Place] = None, ignore_if_missing: bool = False
    ) -> None:
        if ignore_if_missing and not self.exists(quick=True):
            return
        mode = Place.WHOLE if mode is None else mode
        if mode == Place.WHOLE:
            x_offset: float = uniform(0.15, 0.85)
            y_offset: float = uniform(0.15, 0.85)

        elif mode == Place.LEFT:
            x_offset: float = uniform(0.15, 0.4)
            y_offset: float = uniform(0.15, 0.85)

        elif mode == Place.CENTER:
            x_offset: float = uniform(0.4, 0.6)
            y_offset: float = uniform(0.15, 0.85)

        elif mode == Place.RIGHT:
            x_offset: float = uniform(0.6, 0.85)
            y_offset: float = uniform(0.15, 0.85)

        else:
            x_offset: float = 0.5
            y_offset: float = 0.5
        self.view.click(UI_TIMEOUT_LONG, offset=(x_offset, y_offset))

    def long_click(self):
        self.view.long_click()

    def double_click(self, padding=0.3):
        self._double_click(padding)

    def exists(self, quick: bool = False) -> bool:
        return self.view.exists(UI_TIMEOUT_SHORT if quick else UI_TIMEOUT_LONG)

    def get_bounds(self):
        return self.view.info["bounds"]

    def get_width(self):
        return self.get_bounds()["right"] - self.get_bounds()["left"]

    def get_height(self):
        return self.get_bounds()["bottom"] - self.get_bounds()["top"]

    def get_text(self, retry=True):
        max_attempts = 1 if not retry else 3
        attempts = 0
        while attempts < max_attempts:
            attempts += 1

            text = self.viewV2.info["text"]
            if text is None:
                if attempts < max_attempts:
                    print(
                        COLOR_REPORT + "Could not get text. "
                        "Waiting 2 seconds and trying again..." + COLOR_ENDC
                    )
                    sleep(2)  # wait 2 seconds and retry
                    continue
            else:
                return text
            # print(
            #     COLOR_FAIL
            #     + f"Attempted to get text {attempts} times. You may have a slow network or are "
            #     f"experiencing another problem." + COLOR_ENDC
            # )
            # return ""

    def set_text(self, text: str):
        self.view.set_text(text)

    def get_selected(self) -> bool:
        return self.view.info["selected"]

    def is_enabled(self) -> bool:
        return self.view.info["enabled"]

    def is_focused(self) -> bool:
        return self.view.info["focused"]

    def get_image(self) -> Optional[Image]:
        screenshot = self.view.screenshot()
        bounds = self.get_bounds()
        return screenshot.crop(
            (bounds["left"], bounds["top"], bounds["right"], bounds["bottom"])
        )

    def _double_click(self, padding: float):
        visible_bounds = self.get_bounds()
        horizontal_len = visible_bounds["right"] - visible_bounds["left"]
        vertical_len = visible_bounds["bottom"] - visible_bounds["top"]
        horizintal_padding = int(padding * horizontal_len)
        vertical_padding = int(padding * vertical_len)
        random_x = int(
            uniform(
                visible_bounds["left"] + horizintal_padding,
                visible_bounds["right"] - horizintal_padding,
            )
        )
        random_y = int(
            uniform(
                visible_bounds["top"] + vertical_padding,
                visible_bounds["bottom"] - vertical_padding,
            )
        )
        time_between_clicks = uniform(0.050, 0.200)
        self.deviceManager.device.double_click(random_x, random_y, time_between_clicks)
