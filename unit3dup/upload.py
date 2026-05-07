# -*- coding: utf-8 -*-
import requests
import json
import os
from argparse import Namespace

from common.external_services.igdb.core.models.search import Game
from common.trackers.trackers import TRACKData

from unit3dup.pvtTracker import Unit3d
from unit3dup.pvtDocu import PdfImages
from unit3dup import config_settings, Load
from unit3dup.pvtVideo import Video
from unit3dup.media import Media

from view import custom_console

class UploadBot:
    def __init__(self, content: Media, tracker_name: str, cli: Namespace):
        self.cli = cli
        self.content = content
        self.tracker_name = tracker_name
        self.tracker_data = TRACKData.load_from_module(tracker_name=tracker_name)
        self.tracker = Unit3d(tracker_name=tracker_name)
        
        # توقيع فريق AST بتنسيق BBCode احترافي
        self.sign = (
            f"\n\n[center][b][color=#FF0000]مع تحيات فريق المصدر العربي AST[/color][/b]\n")

    def message(self, tracker_response: requests.Response, torrent_archive: str):
        name_error = ''
        info_hash_error = ''
        
        try:
            _message = tracker_response.json()
        except json.JSONDecodeError:
            custom_console.bot_error_log(f"Invalid JSON response from tracker: {tracker_response.text}")
            return {}, "Invalid JSON response"

        if 'data' in _message:
            _message_data = _message['data']
        else:
            _message_data = _message

        if tracker_response.status_code == 200:
            custom_console.bot_log(
                f"\n[RESPONSE]-> '{self.tracker_name}'.....{_message.get('message', 'SUCCESS').upper()}\n\n")
            custom_console.rule()
            
            # تحديث هام من جيتهب: تحميل ملف التورنت الجديد للحصول على info_hash المولد من السيرفر
            if "data" in _message:
                self.download_file(url=_message["data"], destination_path=torrent_archive)
            
            return _message.get("data", ""), {}

        elif tracker_response.status_code == 401:
            custom_console.bot_error_log(_message_data)
            exit(_message.get('message', 'Unauthorized access'))

        elif tracker_response.status_code == 404:
            name_error = _message_data.get("type_id", "Not Found")
            error_message = f"{self.__class__.__name__} - {name_error}"
        else:
            # معالجة أخطاء التحقق من البيانات (Validation Errors)
            errors = _message_data.get("errors", _message_data)
            if isinstance(errors, dict):
                name_error = errors.get("name", [""])[0]
                info_hash_error = errors.get("info_hash", [""])[0]
                error_message = f"{name_error} {info_hash_error}".strip()
            else:
                error_message = str(errors)

        custom_console.bot_error_log(f"\n[RESPONSE ERROR]-> {error_message}\n\n")
        custom_console.rule()
        return {}, error_message

    def data(self, show_id: int, imdb_id: int, tvdb_id: int, show_keywords_list: list,
             video_info: Video) -> Unit3d:

        self.tracker.data["name"] = self.content.display_name
        self.tracker.data["tmdb"] = show_id
        self.tracker.data["imdb"] = imdb_id if imdb_id else 0
        self.tracker.data["tvdb"] = tvdb_id if tvdb_id else 0
        self.tracker.data["keywords"] = ", ".join(show_keywords_list) if isinstance(show_keywords_list, list) else show_keywords_list
        
        # القسم الذكي (V14) الذي تم تحديده في VideoManager
        self.tracker.data["category_id"] = getattr(self.content, 'custom_category_id', 12)

        # تحديد الجودة (2 للـ 4K، 3 للـ 1080p، 10 للبقية)
        res = str(self.content.screen_size) + str(self.content.resolution)
        if '2160' in res:
            self.tracker.data["resolution_id"] = 2
        elif '1080' in res:
            self.tracker.data["resolution_id"] = 3
        else:
            self.tracker.data["resolution_id"] = 10

        self.tracker.data["mediainfo"] = video_info.mediainfo
        self.tracker.data["description"] = video_info.description + self.sign
        self.tracker.data["sd"] = video_info.is_hd

        # تحديد النوع (Type ID)
        file_name_lower = self.content.file_name.lower()
        if 'web' in file_name_lower:
            self.tracker.data["type_id"] = 4
        elif 'remux' in file_name_lower:
            self.tracker.data["type_id"] = 2
        else:
            self.tracker.data["type_id"] = 3 # Encode

        self.tracker.data["season_number"] = self.content.guess_season
        self.tracker.data["episode_number"] = (self.content.guess_episode if not self.content.torrent_pack else 0)
        self.tracker.data["personal_release"] = int(getattr(self.cli, 'personal', config_settings.user_preferences.PERSONAL_RELEASE))
        self.tracker.data["anonymous"] = int(config_settings.user_preferences.ANON)
        
        return self.tracker

    def data_game(self, igdb: Game) -> Unit3d:
        self.tracker.data["name"] = self.content.display_name
        self.tracker.data["tmdb"] = 0
        self.tracker.data["category_id"] = 12 
        self.tracker.data["description"] = (igdb.description if igdb else "No description available") + self.sign
        self.tracker.data["type_id"] = 1
        self.tracker.data["igdb"] = igdb.id if igdb else 0
        self.tracker.data["personal_release"] = int(getattr(self.cli, 'personal', config_settings.user_preferences.PERSONAL_RELEASE))
        self.tracker.data["anonymous"] = int(config_settings.user_preferences.ANON)
        return self.tracker

    def data_docu(self, document_info: PdfImages) -> Unit3d:
        self.tracker.data["name"] = self.content.display_name
        self.tracker.data["tmdb"] = 0
        self.tracker.data["category_id"] = 9 
        self.tracker.data["description"] = document_info.description + self.sign
        self.tracker.data["type_id"] = 4 
        self.tracker.data["resolution_id"] = 2 
        self.tracker.data["personal_release"] = int(getattr(self.cli, 'personal', config_settings.user_preferences.PERSONAL_RELEASE))
        self.tracker.data["anonymous"] = int(config_settings.user_preferences.ANON)
        return self.tracker

    def send(self, torrent_archive: str, nfo_path=None):
        tracker_response = self.tracker.upload_t(
            data=self.tracker.data, 
            torrent_archive_path=torrent_archive,
            nfo_path=nfo_path
        )
        return self.message(tracker_response=tracker_response, torrent_archive=torrent_archive)

    @staticmethod
    def download_file(url: str, destination_path: str) -> bool:
        try:
            download = requests.get(url, timeout=30)
            if download.status_code == 200:
                with open(destination_path, "wb") as file:
                    file.write(download.content)
                return True
        except Exception as e:
            custom_console.bot_error_log(f"Failed to download torrent file: {str(e)}")
        return False
