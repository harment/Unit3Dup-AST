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

    def __init__(self, contents: list[Media], cli: Namespace, tags_list: dict):
        self.contents = contents
        self.cli = cli
        self.tags_list = tags_list

    def clean_title_for_search(self, raw_title: str) -> str:
        # 1. تحويل الاسم لنص وتغيير النقاط لمسافات فوراً لحماية الكلمات مثل .us
        # لا نستخدم splitext هنا لأننا نتعامل مع أسماء مجلدات غالباً
        t = os.path.basename(raw_title)
        t = t.replace('.', ' ').replace('-', ' ').replace('_', ' ')

        # 2. استخراج السنة
        year_match = re.search(r'\b(19|20)\d{2}\b', t)
        year = year_match.group(0) if year_match else ""
        if year:
            t = t.replace(year, ' ')

        # 3. قائمة القمامة التقنية والعربية (التي نريد حذفها فعلاً)
        junk = [
            r'\bWEB-?DL\b', r'\b2160p\b', r'\b1080p\b', r'\b720p\b', r'\bHEVC\b', 
            r'\bx26[45]\b', r'\bH\.?26[45]\b', r'\b10BIT\b', r'\bAAC\b', r'\bREPACK\b', 
            r'\bREMUX\b', r'\bBluray\b', r'\bAST\b', r'\bROSUM\b', r'\bAOC\b',
            r'\bNF\b', r'\bDSNP\b', r'\bAMZN\b', r'حصريا?', r'نادر', r'لأول\s?مرة', r'حصري?',
            r'\bArabic\b', r'\bTranslated\b', r'\bBBC\b', r'\bDrMansoob\b' 
        ]
        
        for pattern in junk:
            t = re.sub(pattern, ' ', t, flags=re.IGNORECASE)

        # 4. تنظيف الرموز المتبقية
        t = re.sub(r'[\[\]\(\)\+\!\@\#\$\%\^\&\*]', ' ', t)

        # 5. الدمج النهائي (الحفاظ على كل الكلمات مهما كان طولها)
        final_query = ' '.join(t.split())
        
        if year:
            final_query = f"{final_query} {year}"

        custom_console.bot_log(f"DEBUG: Final Query to TMDB -> '{final_query.strip()}'")
        return final_query.strip()


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
            
            # 1. تحديد النوع (مع إضافة كلمات دلالية للمسلسلات الوثائقية)
            tv_patterns = ["S0", "S1", "S2", "SEASON", "EPISODE", "EP0", "EP1", " EP", "PART", "HISTORY", "THE", "DECADE"]
            is_tv = any(p in file_upper for p in tv_patterns) or any(p in folder_upper for p in tv_patterns)
            content.category = "tv" if is_tv else "movie"
            
            # 2. تنظيف العنوان (نستخدم المجلد لضمان وجود US و 80S)
            content.guess_title = self.clean_title_for_search(folder_name if folder_name else content.guess_title)
            custom_console.bot_log(f"Detected: {content.category.upper()} | Search Query: '{content.guess_title}'")

            try:
                if UserContent.is_preferred_language(content=content):
                    t_path = os.path.join(tracker_archive, selected_tracker, f"{content.torrent_name}.torrent")
                    os.makedirs(os.path.dirname(t_path), exist_ok=True)
                    t_res = UserContent.torrent(content, tracker_name_list, selected_tracker, t_path)

                    # 3. محاولة البحث التلقائي (البحث المزدوج الإجباري)
                    search_res = None
                    # جرب التصنيف الذي اكتشفه البوت أولاً
                    db_search = DbOnline(media=content, category=content.category, no_title=self.cli.notitle)
                    search_res = db_search.media_result
                    
                    # إذا فشل، جرب التصنيف الآخر فوراً
                    if not search_res:
                        alt_cat = "tv" if content.category == "movie" else "movie"
                        custom_console.bot_warning_log(f"No result as {content.category}. Trying as {alt_cat.upper()}...")
                        original_cat = content.category
                        content.category = alt_cat
                        db_search = DbOnline(media=content, category=content.category, no_title=self.cli.notitle)
                        search_res = db_search.media_result
                        if not search_res:
                            content.category = original_cat # إعادة الحالة الأصلية إذا فشل الاثنان

                    if not search_res:
                        custom_console.bot_error_log(f"Auto-match failed for: {content.guess_title}")
                        continue
                    
                    # 4. جلب البيانات وتحديد القسم النهائي
                    tmdb_id = getattr(search_res, 'video_id', getattr(search_res, 'id', 0))
                    tmdb_api = TmdbAPI()
                    db_details_data = tmdb_api.details(video_id=tmdb_id, category=content.category)
                    db_details = db_details_data if db_details_data else search_res

                    content.custom_category_id = self.get_custom_category(db_details, content, (content.category == "tv"))
                    custom_console.bot_log(f"SUCCESS: {content.category.upper()} | ID: {tmdb_id} | CATEGORY: {content.custom_category_id}")

                    video_info = Video(media=content, tmdb_id=tmdb_id, trailer_key=getattr(db_details, 'trailer_key', ''))
                    video_info.build_info()

                    up_bot = UploadBot(content, selected_tracker, self.cli)
                    up_bot.data(tmdb_id, getattr(db_details, 'imdb_id', None), getattr(db_details, 'tvdb_id', None), 
                               getattr(db_details, 'keywords_list', []), video_info)

                    tracker_res, tracker_msg = up_bot.send(t_path)
                    bittorrent_list.append(BittorrentData(tracker_res, t_res, content, tracker_msg, t_path))
            except Exception as e:
                custom_console.bot_error_log(f"Error: {str(e)}")
                continue
        return bittorrent_list
