#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Fri Mar 01 2024 14:00:10 by codeskyblue
"""

import io
import logging
import time
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from uiautodev import command_proxy
from uiautodev.command_types import Command, CurrentAppResponse, InstallAppRequest, InstallAppResponse, TapRequest
from uiautodev.model import DeviceInfo, Node, ShellResponse
from uiautodev.provider import BaseProvider

logger = logging.getLogger(__name__)


def make_router(provider: BaseProvider) -> APIRouter:
    router = APIRouter()

    @router.get("/list")
    def _list() -> List[DeviceInfo]:
        """List devices"""
        try:
            return provider.list_devices()
        except NotImplementedError as e:
            return Response(content="list_devices not implemented", media_type="text/plain", status_code=501)
        except Exception as e:
            logger.exception("list_devices failed")
            return Response(content=str(e), media_type="text/plain", status_code=500)

    @router.get(
        "/{serial}/screenshot/{id}",
        responses={200: {"content": {"image/jpeg": {}}}},
        response_class=Response,
    )
    def _screenshot(serial: str, id: int) -> Response:
        """Take a screenshot of device"""
        try:
            driver = provider.get_device_driver(serial)
            pil_img = driver.screenshot(id).convert("RGB")
            
            # 检查是否是空图片（截图失败时的备用方案）
            if pil_img.size == (100, 100) and pil_img.getpixel((50, 50)) == (128, 128, 128):
                # 这是最小的备用图片，说明截图失败了
                logger.warning("Screenshot failed, returning fallback image")
            
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG")
            image_bytes = buf.getvalue()
            return Response(content=image_bytes, media_type="image/jpeg")
            
        except Exception as e:
            logger.exception("screenshot failed")
            # 即使截图完全失败，也尝试返回一个基本的空图片
            try:
                from PIL import Image, ImageDraw
                
                # 创建一个基本的错误提示图片
                error_img = Image.new("RGB", (400, 300), color=(64, 64, 64))
                draw = ImageDraw.Draw(error_img)
                
                # 添加错误信息
                try:
                    from PIL import ImageFont
                    font = ImageFont.truetype("arial.ttf", 20)
                except:
                    font = ImageFont.load_default()
                
                error_text = f"截图失败: {str(e)[:50]}"
                draw.text((20, 20), error_text, fill=(255, 255, 255), font=font)
                
                # 转换为JPEG
                buf = io.BytesIO()
                error_img.save(buf, format="JPEG")
                image_bytes = buf.getvalue()
                
                return Response(content=image_bytes, media_type="image/jpeg")
                
            except Exception as fallback_error:
                logger.error(f"Even fallback image creation failed: {fallback_error}")
                # 最后的备用方案：返回纯文本错误
                return Response(
                    content=f"截图失败: {str(e)}", 
                    media_type="text/plain", 
                    status_code=500
                )

    @router.get("/{serial}/hierarchy")
    def dump_hierarchy(serial: str, format: str = "json") -> Node:
        """Dump the view hierarchy of an Android device"""
        try:
            driver = provider.get_device_driver(serial)
            xml_data, hierarchy = driver.dump_hierarchy()
            if format == "xml":
                return Response(content=xml_data, media_type="text/xml")
            elif format == "json":
                return hierarchy
            else:
                return Response(content=f"Invalid format: {format}", media_type="text/plain", status_code=400)
        except Exception as e:
            #logger.exception("dump_hierarchy failed")
            logger.error(f"Error dumping hierarchy: {str(e)}")
            return Response(content=str(e), media_type="text/plain", status_code=500)
    
    @router.post('/{serial}/command/tap')
    def command_tap(serial: str, params: TapRequest):
        """Run a command on the device"""
        driver = provider.get_device_driver(serial)
        command_proxy.tap(driver, params)
        return {"status": "ok"}
    
    @router.post('/{serial}/command/installApp')
    def install_app(serial: str, params: InstallAppRequest) -> InstallAppResponse:
        """Install app"""
        driver = provider.get_device_driver(serial)
        return command_proxy.app_install(driver, params)

    @router.get('/{serial}/command/currentApp')
    def current_app(serial: str) -> CurrentAppResponse:
        """Get current app"""
        driver = provider.get_device_driver(serial)
        return command_proxy.app_current(driver)

    @router.post('/{serial}/command/{command}')
    def _command_proxy_other(serial: str, command: Command, params: Dict[str, Any] = None):
        """Run a command on the device"""
        driver = provider.get_device_driver(serial)
        response = command_proxy.send_command(driver, command, params)
        return response
    
    @router.get('/{serial}/backupApp')
    def _backup_app(serial: str, packageName: str):
        """Backup app
        
        Added in 0.5.0
        """
        driver = provider.get_device_driver(serial)
        file_name = f"{packageName}.apk"
        headers = {
            'Content-Disposition': f'attachment; filename="{file_name}"'
        }
        return StreamingResponse(driver.open_app_file(packageName), headers=headers)
        


    return router
