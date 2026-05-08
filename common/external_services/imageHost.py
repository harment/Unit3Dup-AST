# -*- coding: utf-8 -*-

import json
import time
import requests
from abc import ABC, abstractmethod
from common import config_settings
from view import custom_console

class ImageUploader(ABC):
    def __init__(self, image: bytes, key: str, image_name: str):
        self.image = image
        self.key = key
        self.image_name = image_name
        self.timeout = 30

    @abstractmethod
    def get_endpoint(self):
        pass

    @abstractmethod
    def get_data(self):
        pass

    @abstractmethod
    def get_field_name(self):
        pass

    def upload(self):
        data = self.get_data()
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0"
        }
        files = {
            self.get_field_name(): (f"{self.image_name}.jpg", self.image, 'image/jpeg'),
        }

        upload_n = 0
        while upload_n < 4:
            try:
                upload_n += 1
                response = requests.post(
                    self.get_endpoint(), data=data, files=files, headers=headers, timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if upload_n >= 4:
                    custom_console.bot_log(f"[{self.__class__.__name__}] Upload failed: {e}")
                time.sleep(1)
        return None

class AstU(ImageUploader):
    priority = config_settings.user_preferences.ASTU_PRIORITY

    def get_endpoint(self) -> str:
        # ملاحظة: تأكد من تغيير "user" إلى اسم المستخدم الحقيقي في مركز الرفع لديك
        user_name = "user" 
        return f"https://arabicsource.net/U/ajax/index.php?uploadfile&api={self.key}&username={user_name}"

    def get_data(self) -> dict:
        user_name = "user"
        return {
            "api": self.key,
            "username": user_name,
            "ispublic": "1",
            "passwordfile": ""
        }

    def get_field_name(self) -> str:
        return 'uploadfile'

class ImageUploaderFallback:
    def __init__(self, uploader):
        self.uploader = uploader

    def upload(self, test=False) -> str:
        result = None
        response = self.uploader.upload()
        if response:
            result = ImageUploaderFallback.result(
                response=response, uploader_host=self.uploader.__class__.__name__
            )
        return result

    @staticmethod
    def result(response: dict, uploader_host: str) -> str | None:
        if uploader_host == "AstU":
            if response.get("success"):
                base_url = "https://arabicsource.net/U"
                upload_dir = response.get('UploadDir', '/uploads')
                file_name = response.get('FileName')
                return f"{base_url}{upload_dir}/{file_name}"
        return None

class Build:
    """
    - رفع لقطات الشاشة وإنشاء الوصف النهائي مع التنسيق الجمالي
    """
    def __init__(self, extracted_frames: list[bytes], filename: str):
        self.filename = filename
        self.extracted_frames = extracted_frames
        self.ASTU_KEY = config_settings.tracker_config.ASYU_KEY

    def description(self) -> str:
        # روابط الصور التجميلية الخاصة بك
        welcome_gif = "https://arabicsource.net/U/uploads/user/file_2026-03-28_063032.gif"
        site_logo = "https://arabicsource.net/U/uploads/user/file_2026-03-28_063943.png"
        footer_decoration = "https://arabicsource.net/U/uploads/user/file_2026-03-28_064122.gif"
        
        # 1. بداية بناء الوصف (التحية وشعار الموقع في المنتصف)
        description = "[center]\n"
        description += f"[img=600]{welcome_gif}[/img]\n"
        description += f"[img=250]{site_logo}[/img]\n\n"
        
        custom_console.bot_log("Starting image upload..")
        _number = 0
        
        # 2. رفع لقطات الشاشة (Screenshots) وإضافتها للوصف
        for img_bytes in self.extracted_frames:
            _number += 1
            image_name = f"{self.filename}.id_{_number}"
            
            uploader = AstU(img_bytes, self.ASTU_KEY, image_name=image_name)
            fallback = ImageUploaderFallback(uploader)
            url = fallback.upload()
            
            if url:
                description += f"[img=850]{url}[/img]\n"
        
        # 3. إضافة الزخرفة الختامية وإغلاق وسم المنتصف
        description += f"\n[img=500]{footer_decoration}[/img]\n"
        description += "[/center]"
        
        return description
