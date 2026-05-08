# -*- coding: utf-8 -*-
from argparse import Namespace
import requests
import json

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
        self.sign = (
            f"[center][i][color=#0a589d][size=14]"
            f"مع تحيات فريق المصدر العربي AST"
            f"[/size][/color][/i][/center]"
        )

    def message(self, tracker_response: requests.Response, torrent_archive: str):
        name_error = ''
        info_hash_error = ''
        _message = json.loads(tracker_response.text)
        if 'data' in _message:
            _message = _message['data']

        if tracker_response.status_code == 200:
            tracker_response_body = json.loads(tracker_response.text)
            custom_console.bot_log(
                f"\n[RESPONSE]-> '{self.tracker_name}'.....{tracker_response_body['message'].upper()}\n\n")
            custom_console.rule()
            self.download_file(url=tracker_response_body["data"], destination_path=torrent_archive)
            return tracker_response_body["data"], {}

        elif tracker_response.status_code == 401:
            custom_console.bot_error_log(_message)
            exit(_message['message'])

        elif tracker_response.status_code == 404:
            name_error = _message.get("type_id", _message)
            error_message = f"{self.__class__.__name__} - {name_error}"
        else:
            if _message.get("name", None):
                name_error = _message["name"][0]
            if _message.get("info_hash", None):
                info_hash_error = _message["info_hash"][0]
            error_message = f"{self.__class__.__name__} - {name_error} : {info_hash_error}"

        custom_console.bot_error_log(f"\n[RESPONSE ERROR]-> {error_message}\n\n")
        custom_console.rule()
        return {}, error_message

    def data(self, show_id: int, imdb_id: int, tvdb_id: int, show_keywords_list: str,
             video_info: Video) -> Unit3d | None:

        self.tracker.data["name"] = self.content.display_name
        self.tracker.data["tmdb"] = show_id
        self.tracker.data["imdb"] = imdb_id if imdb_id else 0
        self.tracker.data["tvdb"] = tvdb_id if tvdb_id else 0

        self.tracker.data["keywords"] = show_keywords_list
        
        self.tracker.data["category_id"] = getattr(self.content, 'custom_category_id', 12)

        # --- إصلاح خطأ 'screen_size' لضمان التوافق بين الأجهزة ---
        # نحاول الحصول على الحجم من screen_size، وإذا لم يوجد نستخدم resolution، وإذا لم يوجد نأخذ نصاً فارغاً
        res_info = str(getattr(self.content, 'screen_size', getattr(self.content, 'resolution', '')))
        
        if '2160' in res_info:
            self.tracker.data["resolution_id"] = 2
        elif '1080' in res_info:
            self.tracker.data["resolution_id"] = 3
        elif '720' in res_info:
            self.tracker.data["resolution_id"] = 5 # تأكد من رقم 5 لتراكركم
        else:
            self.tracker.data["resolution_id"] = 10 # Other

        self.tracker.data["mediainfo"] = video_info.mediainfo
        self.tracker.data["description"] = video_info.description + self.sign
        self.tracker.data["sd"] = video_info.is_hd

        file_name_lower = self.content.file_name.lower()
        if 'web' in file_name_lower:
            self.tracker.data["type_id"] = 4
        elif 'remux' in file_name_lower:
            self.tracker.data["type_id"] = 2
        else:
            self.tracker.data["type_id"] = 3 # Encode

        self.tracker.data["season_number"] = getattr(self.content, 'guess_season', 0)
        self.tracker.data["episode_number"] = (getattr(self.content, 'guess_episode', 0) if not getattr(self.content, 'torrent_pack', False) else 0)
        self.tracker.data["personal_release"] = (int(config_settings.user_preferences.PERSONAL_RELEASE)
                                                 or int(self.cli.personal))
        return self.tracker

    def data_game(self, igdb: Game) -> Unit3d | None:
        self.tracker.data["name"] = self.content.display_name
        self.tracker.data["tmdb"] = 0
        self.tracker.data["category_id"] = 12 
        self.tracker.data["anonymous"] = int(config_settings.user_preferences.ANON)
        self.tracker.data["description"] = (igdb.description if igdb else "") + self.sign
        self.tracker.data["type_id"] = 1
        self.tracker.data["igdb"] = igdb.id if igdb else 1
        self.tracker.data["personal_release"] = (int(config_settings.user_preferences.PERSONAL_RELEASE)
                                                 or int(self.cli.personal))
        return self.tracker

    def data_docu(self, document_info: PdfImages) -> Unit3d | None:
        self.tracker.data["name"] = self.content.display_name
        self.tracker.data["tmdb"] = 0
        self.tracker.data["category_id"] = 9 
        self.tracker.data["anonymous"] = int(config_settings.user_preferences.ANON)
        self.tracker.data["description"] = document_info.description + self.sign
        self.tracker.data["type_id"] = 4 # WEB-DL
        self.tracker.data["resolution_id"] = 2 # 2160p
        self.tracker.data["personal_release"] = (int(config_settings.user_preferences.PERSONAL_RELEASE)
                                                 or int(self.cli.personal))
        return self.tracker

    def send(self, torrent_archive: str, nfo_path=None):
        tracker_response = self.tracker.upload_t(data=self.tracker.data, torrent_archive_path=torrent_archive,
                                                 nfo_path=nfo_path)
        return self.message(tracker_response=tracker_response, torrent_archive=torrent_archive)

    @staticmethod
    def download_file(url: str, destination_path: str) -> bool:
        download = requests.get(url)
        if download.status_code == 200:
            with open(destination_path, "wb") as file:
                file.write(download.content)
            return True
        return False
