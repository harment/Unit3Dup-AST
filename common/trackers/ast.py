# -*- coding: utf-8 -*-

ast_data = {
    "CATEGORY": {
        # أقسام الأفلام
        "أفلام رسوم مدبلجة": 1,
        "أفلام رسوم مترجمة": 2,
        "أفلام عربية": 3,
        "أفلام أجنبية": 4,
        "أفلام وثائقية": 9,
        "أفلام كرتون كلاسيك": 21,
        "مسرحيات": 8,

        # أقسام المسلسلات
        "مسلسلات رسوم مدبلجة": 5,
        "مسلسلات رسوم مترجمة": 6,
        "مسلسلات عربية": 7,
        "كرتون كلاسيك": 14,
        "مسلسلات وثائقية": 20,
        "مسلسلات أجنبية": 22,

        # أقسام عامة أخرى
        "إسلاميات": 10,
        "رمضانيات": 11,
        "منوعات": 12,
        "صوتيات": 13,
        "تورنت خام": 15,
    },

    "FREELECH": {
        "size20": 100,
        "size15": 75,
        "size10": 50,
        "size5": 25,
    },

    "TYPE_ID": {
        "full-disc": 1,
        "fulldisc": 1,
        "remux": 2,
        "bdremux": 2,
        "encode": 3,
        "x264": 3,
        "x265": 3,
        "hevc": 3,
        "bluray": 3,
        "web-dl": 4,
        "webdl": 4,
        "web": 4,
        "webrip": 5,
        "hdtv": 6,
        "hdr": 7,
        "dv": 8,
        "dolby-vision": 8,
        "3d": 9,
    },

    "TYPE_ID_AUDIO": {
        "flac": 7,
        "alac": 8,
        "ac3": 9,
        "aac": 10,
        "mp3": 11,
    },

    "TAGS": {
        "SD": 1,
        "HD": 0,
    },

    "RESOLUTION": {
        "4320p": 1,
        "2160p": 2,
        "1080p": 3,
        "1080i": 4,
        "720p": 5,
        "576p": 6,
        "576i": 7,
        "480p": 8,
        "480i": 9,
        "other": 10,
        "tvrip": 11,
        "dvbrip": 12,
        "hdtv1080p": 13,
        "dvd": 14,
        "altro": 10,
    },

    "CODEC": [
        "h261", "h262", "h263", "h264", "x264", "x265", "avc", "h265", "hevc",
        "vp8", "vp9", "av1", "mpeg-1", "mpeg-4", "wmv", "theora", "divx", "xvid",
        "prores", "dnxhd", "cinepak", "indeo", "dv", "ffv1", "sorenson", "rv40",
        "cineform", "huffyuv", "mjpeg", "lagarith", "msu", "rle", "dirac", "wmv3",
        "vorbis", "smpte", "mjpeg", "ffvhuff", "v210", "yuv4:2:2", "yuv4:4:4", "hap",
        "sheervideo", "ut", "quicktime", "rududu", "h.266", "vvc", "mjpeg 4:2:0",
        "h.263+", "h.263++", "vp4", "vp5", "vp6", "vp7", "vp8", "vp9", "vp10",
        "vp11", "vp12", "vp3", "vp2", "vp1", "amv", "daala", "gecko", "nvenc", "bluray"
    ],
}
