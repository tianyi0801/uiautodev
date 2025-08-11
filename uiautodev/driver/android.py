#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Fri Mar 01 2024 14:19:29 by codeskyblue
"""

import logging
import re
import time
from functools import cached_property, partial
from typing import Iterator, List, Optional, Tuple
from xml.etree import ElementTree

import adbutils
import uiautomator2 as u2
from PIL import Image

from uiautodev.command_types import CurrentAppResponse
from uiautodev.driver.base_driver import BaseDriver
from uiautodev.exceptions import AndroidDriverException, RequestError
from uiautodev.model import AppInfo, Node, Rect, ShellResponse, WindowSize
from uiautodev.utils.common import fetch_through_socket, adb_path, cmd_sync

logger = logging.getLogger(__name__)


class AndroidDriver(BaseDriver):
    def __init__(self, serial: str):
        super().__init__(serial)
        self.adb_device = adbutils.device(serial)
        # self.kill_utest_agent()

    def kill_utest_agent(self) -> str:
        """杀掉utest-agent进程"""
        result = self.kill_process_by_name("utest-agent")
        logger.info(f"杀掉utest-agent进程结果: {result}")
        return result if result else "杀掉utest-agent进程完成"

    def kill_process_by_name(self, process_name: str) -> str:
        """使用cmd_sync方法杀掉指定名称的进程

        Args:
            process_name (str): 要杀掉的进程名称

        Returns:
            str: 执行结果
        """
        # 使用cmd_sync方法，和命令行执行结果一致
        cmd = f'{adb_path()} -s {self.serial} shell "ps | grep {process_name} | awk \'{{print $2}}\' | xargs -r kill"'
        result = cmd_sync(cmd)
        logger.info(f"杀掉进程 {process_name} 结果: {result}")
        return result if result else f"杀掉进程 {process_name} 完成"

    def kill_process_by_pid(self, pid: str) -> str:
        """使用cmd_sync方法杀掉指定PID的进程

        Args:
            pid (str): 进程ID

        Returns:
            str: 执行结果
        """
        cmd = f'{adb_path()} -s {self.serial} shell "kill {pid}"'
        result = cmd_sync(cmd)
        logger.info(f"杀掉进程 PID {pid} 结果: {result}")
        return result if result else f"杀掉进程 PID {pid} 完成"

    @cached_property
    def ud(self) -> u2.Device:
        return u2.connect_usb(self.serial)

    def get_current_activity(self) -> str:
        ret = self.adb_device.shell2(["dumpsys", "activity", "activities"], rstrip=True, timeout=5)
        # 使用正则查找包含前台 activity 的行
        match = re.search(r"mResumedActivity:.*? ([\w\.]+\/[\w\.]+)", ret.output)
        if match:
            return match.group(1)  # 返回包名/类名，例如 com.example/.MainActivity
        else:
            return ""

    def screenshot(self, id: int) -> Image.Image:
        if id > 0:
            raise AndroidDriverException("multi-display is not supported yet for uiautomator2")

        # 首先尝试使用uiautomator2截图
        try:
            logger.debug("Attempting uiautomator2 screenshot...")
            result = self.ud.screenshot()
            logger.debug("uiautomator2 screenshot successful")
            return result
        except Exception as e:
            logger.debug(f"uiautomator2 screenshot failed: {e}")
            return self._create_empty_screenshot()

    def _create_empty_screenshot(self) -> Image.Image:
        """创建空图片作为截图失败的备用方案"""
        try:
            # 尝试获取屏幕尺寸
            try:
                w, h = self.adb_device.window_size()
                logger.info(f"Creating empty screenshot with device dimensions: {w}x{h}")
            except:
                # 如果无法获取屏幕尺寸，使用默认尺寸
                w, h = 1080, 1920
                logger.info(f"Using default dimensions for empty screenshot: {w}x{h}")

            # 创建纯色背景图片
            from PIL import Image, ImageDraw

            # 创建深灰色背景（模拟锁屏或安全界面）
            image = Image.new("RGB", (w, h), color=(64, 64, 64))
            draw = ImageDraw.Draw(image)

            # 添加提示文字
            try:
                # 尝试使用中文字体，如果失败则使用默认字体
                from PIL import ImageFont
                font_size = min(w, h) // 20
                try:
                    # 尝试使用系统字体
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()

            # 添加提示信息
            text = "截图功能被阻止"
            text2 = "可能是安全策略限制"

            # 计算文字位置（居中）
            bbox1 = draw.textbbox((0, 0), text, font=font)
            bbox2 = draw.textbbox((0, 0), text2, font=font)

            text_width1 = bbox1[2] - bbox1[0]
            text_width2 = bbox2[2] - bbox2[0]
            text_height1 = bbox1[3] - bbox1[1]
            text_height2 = bbox2[3] - bbox2[1]

            x1 = (w - text_width1) // 2
            x2 = (w - text_width2) // 2
            y1 = h // 2 - text_height1 - 10
            y2 = h // 2 + 10

            # 绘制文字（白色）
            draw.text((x1, y1), text, fill=(255, 255, 255), font=font)
            draw.text((x2, y2), text2, fill=(200, 200, 200), font=font)

            # 添加一个图标或装饰
            icon_size = min(w, h) // 8
            icon_x = (w - icon_size) // 2
            icon_y = h // 2 - icon_size - text_height1 - 30

            # 绘制一个简单的锁图标（矩形）
            draw.rectangle([icon_x, icon_y, icon_x + icon_size, icon_y + icon_size],
                           outline=(255, 255, 255), width=3)

            logger.info("Empty screenshot created successfully")
            return image

        except Exception as e:
            logger.error(f"Failed to create empty screenshot: {e}")
            # 最后的备用方案：创建一个最小的图片
            from PIL import Image
            return Image.new("RGB", (100, 100), color=(128, 128, 128))

    def shell(self, command: str) -> ShellResponse:
        try:
            ret = self.adb_device.shell2(command, rstrip=True, timeout=20)
            if ret.returncode == 0:
                return ShellResponse(output=ret.output, error=None)
            else:
                return ShellResponse(
                    output="", error=f"exit:{ret.returncode}, output:{ret.output}"
                )
        except Exception as e:
            return ShellResponse(output="", error=f"adb error: {str(e)}")

    def dump_hierarchy(self, display_id: Optional[int] = 0) -> Tuple[str, Node]:
        """returns xml string and hierarchy object"""
        start = time.time()
        xml_data = self._dump_hierarchy_raw()
        logger.debug("dump_hierarchy cost: %s", time.time() - start)

        wsize = self.adb_device.window_size()
        logger.debug("window size: %s", wsize)
        return xml_data, parse_xml(
            xml_data, WindowSize(width=wsize[0], height=wsize[1]), display_id
        )

    def _dump_hierarchy_raw(self) -> str:
        """
        uiautomator2 server is conflict with "uiautomator dump" command.

        uiautomator dump errors:
        - ERROR: could not get idle state.
        """
        try:
            return self.ud.dump_hierarchy()
        except Exception as e:
            raise AndroidDriverException(f"Failed to dump hierarchy: {str(e)}")

    def tap(self, x: int, y: int):
        self.adb_device.click(x, y)

    def window_size(self) -> Tuple[int, int]:
        w, h = self.adb_device.window_size()
        return (w, h)

    def app_install(self, app_path: str):
        self.adb_device.install(app_path)

    def app_current(self) -> CurrentAppResponse:
        info = self.adb_device.app_current()
        return CurrentAppResponse(
            package=info.package, activity=info.activity, pid=info.pid
        )

    def app_launch(self, package: str):
        if self.adb_device.package_info(package) is None:
            raise AndroidDriverException(f"App not installed: {package}")
        self.adb_device.app_start(package)

    def app_terminate(self, package: str):
        self.adb_device.app_stop(package)

    def home(self):
        self.adb_device.keyevent("HOME")

    def wake_up(self):
        self.adb_device.keyevent("WAKEUP")

    def back(self):
        self.adb_device.keyevent("BACK")

    def app_switch(self):
        self.adb_device.keyevent("APP_SWITCH")

    def volume_up(self):
        self.adb_device.keyevent("VOLUME_UP")

    def volume_down(self):
        self.adb_device.keyevent("VOLUME_DOWN")

    def volume_mute(self):
        self.adb_device.keyevent("VOLUME_MUTE")

    def get_app_version(self, package_name: str) -> Optional[dict]:
        """
        Get the version information of an app, including mainVersion and subVersion.

        Args:
            package_name (str): The package name of the app.

        Returns:
            dict: A dictionary containing mainVersion and subVersion.
        """
        output = self.adb_device.shell(["dumpsys", "package", package_name])

        # versionName
        m = re.search(r"versionName=(?P<name>[^\s]+)", output)
        version_name = m.group("name") if m else ""
        if version_name == "null":  # Java dumps "null" for null values
            version_name = None

        # versionCode
        m = re.search(r"versionCode=(?P<code>\d+)", output)
        version_code = m.group("code") if m else ""
        version_code = int(version_code) if version_code.isdigit() else None

        return {
            "versionName": version_name,
            "versionCode": version_code
        }

    def app_list(self) -> List[AppInfo]:
        results = []
        output = self.adb_device.shell(["pm", "list", "packages", '-3'])
        for m in re.finditer(r"^package:([^\s]+)\r?$", output, re.M):
            packageName = m.group(1)
            # get version
            version_info = self.get_app_version(packageName)
            app_info = AppInfo(
                packageName=packageName,
                versionName=version_info.get("versionName"),
                versionCode=version_info.get("versionCode")
            )
            results.append(app_info)
        return results

    def open_app_file(self, package: str) -> Iterator[bytes]:
        line = self.adb_device.shell(f"pm path {package}")
        if not line.startswith("package:"):
            raise AndroidDriverException(f"Failed to get package path: {line}")
        remote_path = line.split(':', 1)[1]
        yield from self.adb_device.sync.iter_content(remote_path)


def parse_xml(xml_data: str, wsize: WindowSize, display_id: Optional[int] = None) -> Node:
    root = ElementTree.fromstring(xml_data)
    node = parse_xml_element(root, wsize, display_id)
    if node is None:
        raise AndroidDriverException("Failed to parse xml")
    return node


def parse_xml_element(element, wsize: WindowSize, display_id: Optional[int], indexes: List[int] = [0]) -> Optional[
    Node]:
    """
    Recursively parse an XML element into a dictionary format.
    """
    name = element.tag
    if name == "node":
        name = element.attrib.get("class", "node")
    if display_id is not None:
        elem_display_id = int(element.attrib.get("display-id", display_id))
        if elem_display_id != display_id:
            return

    bounds = None
    rect = None
    # eg: bounds="[883,2222][1008,2265]"
    if "bounds" in element.attrib:
        bounds = element.attrib["bounds"]
        bounds = list(map(int, re.findall(r"\d+", bounds)))
        assert len(bounds) == 4
        rect = Rect(x=bounds[0], y=bounds[1], width=bounds[2] - bounds[0], height=bounds[3] - bounds[1])
        bounds = (
            bounds[0] / wsize.width,
            bounds[1] / wsize.height,
            bounds[2] / wsize.width,
            bounds[3] / wsize.height,
        )
        bounds = map(partial(round, ndigits=4), bounds)

    elem = Node(
        key="-".join(map(str, indexes)),
        name=name,
        bounds=bounds,
        rect=rect,
        properties={key: element.attrib[key] for key in element.attrib},
        children=[],
    )

    # Construct xpath for children
    for index, child in enumerate(element):
        child_node = parse_xml_element(child, wsize, display_id, indexes + [index])
        if child_node:
            elem.children.append(child_node)

    return elem
