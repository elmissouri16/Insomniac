#! rewrite for device_facade.py
from dataclasses import dataclass
from enum import Enum, unique
from os import listdir
from random import uniform
import re
import uiautomator2 as u2
from insomniac import sleeper
from insomniac.utils import COLOR_ENDC, COLOR_FAIL, COLOR_OKGREEN
from uiautomator2 import Device

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

    def find(self, *args, **kwargs):
        # TODO check if need to implement
        pass

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
        self.swipe(DeviceFacade.Direction.TOP, 0.8)
        if self.is_screen_locked():
            self.swipe(DeviceFacade.Direction.RIGHT, 0.8)

    def get_info(self) -> DeviceInfo:
        return DeviceInfo.from_dict(self.device.info)
