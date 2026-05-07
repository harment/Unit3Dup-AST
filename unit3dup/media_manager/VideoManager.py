# -*- coding: utf-8 -*-
import re
from argparse import Namespace
import os

from common.external_services.theMovieDB.core.api import DbOnline, TmdbAPI
from common.bittorrent import BittorrentData
from common.tags import SearchTags
from common import title

from unit3dup.media_manager.common import UserContent
from unit3dup.upload import UploadBot
from unit3dup import config_settings
from unit3dup.pvtVideo import Video
from unit3dup.media import Media

from view import custom_console

class VideoManager:

    def __init__(self, contents: list[Media], cli: Namespace, tags_list: dict, sign_list: dict, ban_list: dict):
        self.contents = contents
        self.cli = cli
        self.tags_list = tags_list
        self.sign_list = sign_list  # تخزين القائمة لاستخدامها لاحقاً
        self.ban_list = ban_list    # تخزين القائمة لاستخدامها لاحقاً

    def clean_title_for_search(self, raw_title: str) -> str:
        # 1. الحصول على الاسم وتحويله لحروف صغيرة
        t = os.path.basename(raw_title).lower()
        
        # 2. إزالة الامتدادات
        for ext in ['.mkv', '.mp4', '.avi', '.ts', '.mov']:
            if t.endswith(ext): t = t[:-len(ext)]

        # 3. حذف السنة نهائياً من نص البحث (لأن TMDB يفضل ذلك)
        t = re.sub(r'\b(19|20)\d{2}\b', ' ', t)

        # 4. استبدال كل الرموز بمسافات
        t = re.sub(r'[\.\-\_\[\]\(\)\+\!\@\#\$\%\^\&\*]', ' ', t)

        # 5. قائمة القمامة
        junk_list = [
            r'\bweb\s?dl\b', r'\b2160p\b', r'\b1080p\b', r'\b720p\b', r'\b480p\b',
            r'\bhevc\b', r'\bx26\d\b', r'\bh26\d\b', r'\b10bit\b', r'\baac\b',
            r'\brepack\b', r'\bproper\b', r'\bremux\b', r'\bbluray\b', r'\bdual\b', 
            r'\baudio\b', r'\bmulti\b', r'\bast\b', r'\brosum\b', r'\baoc\b',
            r'\bby\b', r'\bdrmansoob\b', r'\btranslated\b', r'\barabic\b', r'\bdsnp\b',
            r'\bamzn\b', r'\bnf\b', r'\bhdr\d*\b', r'\bdv\b'
        ]
        
        for pattern in junk_list:
            t = re.sub(pattern, ' ', t, flags=re.IGNORECASE)

        # 6. تجميع الكلمات (الحفاظ على الأرقام مثل 3)
        words = t.split()
        cleaned_words = []
        for w in words:
            if len(w) >= 2 or w.isdigit() or w in ['a', 'i']:
                if w not in ['by', 'dl', 'web']:
                    cleaned_words.append(w)
        
        final_query = ' '.join(cleaned_words).strip().title()

        custom_console.bot_log(f"DEBUG: Final Query to TMDB -> '{final_query}'")
        return final_query


    def get_custom_category(self, db_details, content, is_tv_show: bool) -> int:
        """التصنيف الاحترافي V14 - فحص شامل للمدبلج والمترجم مع كافة الأقسام"""
        from common.mediainfo import MediaFile
        import re

        is_movie = not is_tv_show
        file_name = content.file_name.lower()
        
        # 1. تحليل الميديا انفو (فحص مرن لا يتقيد بصيغة نصية محددة)
        media_info = MediaFile(content.file_name)
        full_mi_text = str(media_info.info).lower()
        # فحص وجود كلمة arabic في أي مكان في بيانات الميديا انفو (صوت أو ترجمة)
        mi_has_arabic = "arabic" in full_mi_text

        # 2. تجميع بيانات TMDB الشاملة
        all_tmdb_text = ""
        genre_ids = []
        details_list = db_details if isinstance(db_details, list) else [db_details]
        for item in details_list:
            if hasattr(item, '__dict__'):
                all_tmdb_text += " " + " ".join([str(v).lower() for v in item.__dict__.values()])
            ids = getattr(item, 'genre_ids', [])
            if not ids and hasattr(item, 'genres'):
                ids = [getattr(g, 'id', 0) for g in item.genres if hasattr(g, 'id')]
            if ids: genre_ids.extend(ids)

        # دمج اسم الملف مع بيانات TMDB للتحليل الكامل
        full_analysis = f"{file_name} {all_tmdb_text}".lower()

        # 3. فحص "اللغة العربية" (توسيع المرشحات لتشمل Dual-Audio وفرق الدبلجة)
        # أضفنا Rosum, Dual-Audio, Multi لضمان التقاطها من اسم الملف
        arabic_triggers = [
            'arabic', 'dubbed', 'ara', 'ar', 'multi', 'dub', 
            'مدبلج', 'عربي', 'ar-dub', 'dual-audio', 'dual.audio', 'rosum', 'aoc'
        ]
        
        # البحث عن الكلمات كأجزاء من النص أو ككلمات كاملة (Regex)
        found_ar_tag = any(re.search(rf"\b{w}\b", full_analysis) for w in ['arabic', 'ara', 'ar', 'multi', 'dub']) or \
                       any(w in full_analysis for w in ['مدبلج', 'عربي', 'ar-dub', 'dual-audio', 'rosum'])
        
        is_arabic_audio = mi_has_arabic or found_ar_tag

        # فحص بلد المنشأ (مثلاً EG لمصر، KW للكويت، SA السعودية، AE الإمارات، JO الأردن، LB لبنان)
        origin_country = getattr(db_details if isinstance(db_details, list) else db_details, 'origin_country', [])
        if any(country in origin_country for country in ['EG', 'KW', 'SA', 'AE', 'JO', 'LB', 'SY', 'MA', 'DZ', 'TN']):
            is_arabic_audio = True
            
        # 4. استخراج السنة (للكلاسيك)
        date = str(getattr(db_details if isinstance(db_details, list) else db_details, 'release_date', 
                   getattr(db_details if isinstance(db_details, list) else db_details, 'first_air_date', '2020')))
        try: year = int(date[:4])
        except: year = 2020

        # --- البدء في التصنيف حسب المعرفات (IDs) المطلوبة ---

        # مسرحيات (8)
        if any(word in full_analysis for word in ['مسرحية', 'theater', 'play']): 
            return 8

        # وثائقي (أفلام 9، مسلسلات 20)
        if 99 in genre_ids or 'documentary' in full_analysis or 'وثائقي' in full_analysis:
            return 9 if is_movie else 20

        # الرسوم المتحركة والأنمي
        is_animation = (16 in genre_ids) or any(t in full_analysis for t in ['animation', 'anime', 'انمي', 'رسوم', 'cartoon', 'كرتون', 'stop motion', 'pixar', 'disney'])
        if is_animation:
            # كرتون كلاسيك (قبل 2000): أفلام 21، مسلسلات 14
            if year < 2000:
                return 21 if is_movie else 14
            
            # كرتون جديد (أفلام 1 مدبلج، 2 مترجم)
            if is_movie:
                return 1 if is_arabic_audio else 2
            # كرتون جديد (مسلسلات 5 مدبلج، 6 مترجم)
            return 5 if is_arabic_audio else 6

        # المحتوى العربي (أفلام 3، مسلسلات 7)
        lang_origin = getattr(db_details if isinstance(db_details, list) else db_details, 'original_language', 'en')
        if lang_origin == 'ar' or is_arabic_audio:
            if is_movie: return 3
            return 7

        # المحتوى الأجنبي (أفلام 4، مسلسلات 22)
        if is_movie:
            return 4
        if is_tv_show:
            return 22

        # المصيدة النهائية: منوعات (12)
        return 12

    def process(self, selected_tracker: str, tracker_name_list: list, tracker_archive: str) -> list[BittorrentData]:
        if self.cli.mt: tracker_name_list = [selected_tracker.upper()]
        bittorrent_list = []

        for content in self.contents:
            file_upper = content.file_name.upper()
            folder_name = content.torrent_name if content.torrent_name else ""
            folder_upper = folder_name.upper()
            
            # 1. تحديد النوع (Movie/TV) - استبعاد كلمة THE لضمان دقة الأفلام
            tv_patterns = ["S0", "S1", "S2", "SEASON", "EPISODE", "EP0", "EP1", " EP", "PART", "HISTORY", "DECADE"]
            is_tv = any(p in file_upper for p in tv_patterns) or any(p in folder_upper for p in tv_patterns)
            content.category = "tv" if is_tv else "movie"
            
            # 2. تنظيف العنوان الابتدائي (يحتوي على السنة عادةً)
            original_folder_name = folder_name if folder_name else content.guess_title
            content.guess_title = self.clean_title_for_search(original_folder_name)
            
            custom_console.bot_log(f"Detected: {content.category.upper()} | Search Query: '{content.guess_title}'")

            try:
                if UserContent.is_preferred_language(content=content):
                    t_path = os.path.join(tracker_archive, selected_tracker, f"{content.torrent_name}.torrent")
                    os.makedirs(os.path.dirname(t_path), exist_ok=True)
                    t_res = UserContent.torrent(content, tracker_name_list, selected_tracker, t_path)

                    # --- استراتيجية البحث الذكي الثلاثي ---
                    search_res = None
                    
                    # المحاولة 1: البحث بالعنوان كما هو (غالباً مع السنة)
                    db_search = DbOnline(media=content, category=content.category, no_title=self.cli.notitle)
                    search_res = db_search.media_result
                    
                    # المحاولة 2: إذا فشل، جرب حذف السنة (لأجل سونيك 3 وأمثاله)
                    if not search_res:
                            clean_no_year = re.sub(r'\b(19|20)\d{2}\b', '', content.guess_title).strip()
                            custom_console.bot_log(f"DEBUG: Trying secondary search -> {clean_no_year}") # أضف هذا السطر
                            content.guess_title = clean_no_year
                            db_search = DbOnline(media=content, category=content.category, no_title=self.cli.notitle)
                            search_res = db_search.media_result

                    # المحاولة 3: إذا فشل، جرب الفئة الأخرى (Movie <-> TV)
                    if not search_res:
                        alt_cat = "tv" if content.category == "movie" else "movie"
                        custom_console.bot_warning_log(f"Still no result. Retrying as {alt_cat.upper()}...")
                        old_cat = content.category
                        content.category = alt_cat
                        db_search = DbOnline(media=content, category=content.category, no_title=self.cli.notitle)
                        search_res = db_search.media_result
                        if not search_res:
                            content.category = old_cat # إعادة الفئة الأصلية لو فشل تماماً

                    # إذا فشل كل ما سبق
                    if not search_res:
                        custom_console.bot_error_log(f"Auto-match failed for: {content.guess_title}")
                        continue

                    # 4. جلب البيانات النهائية والتصنيف
                    tmdb_id = getattr(search_res, 'video_id', getattr(search_res, 'id', 0))
                    tmdb_api = TmdbAPI()
                    db_details_data = tmdb_api.details(video_id=tmdb_id, category=content.category)
                    db_details = db_details_data if db_details_data else search_res

                    content.custom_category_id = self.get_custom_category(db_details, content, (content.category == "tv"))
                    custom_console.bot_log(f"SUCCESS: {content.category.upper()} | ID: {tmdb_id} | CATEGORY: {content.custom_category_id}")

                    # 5. بناء وصف الفيديو والرفع
                    video_info = Video(media=content, tmdb_id=tmdb_id, trailer_key=getattr(db_details, 'trailer_key', ''))
                    video_info.build_info()

                    up_bot = UploadBot(content, selected_tracker, self.cli)
                    up_bot.data(tmdb_id, getattr(db_details, 'imdb_id', None), getattr(db_details, 'tvdb_id', None), 
                               getattr(db_details, 'keywords_list', []), video_info)

                    tracker_res, tracker_msg = up_bot.send(t_path)
                    bittorrent_list.append(BittorrentData(tracker_res, t_res, content, tracker_msg, t_path))

            except Exception as e:
                custom_console.bot_error_log(f"Error processing '{content.file_name}': {str(e)}")
                continue
                
        return bittorrent_list
