#!/usr/bin/env python3
"""
اسکریپت دریافت زیرنویس ویدیوی یوتیوب به زبان‌های فارسی و انگلیسی
و ذخیره‌سازی در قالب SRT و TXT
"""

import os
import re
import sys
import json
from datetime import timedelta

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


def extract_video_id(url: str) -> str:
    """استخراج شناسه ۱۱ کاراکتری ویدیو از URL یوتیوب"""
    # الگوهای رایج
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"(?:youtube\.com/v/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("شناسه ویدیو در URL داده شده یافت نشد.")


def get_video_title(video_url: str) -> str:
    """
    دریافت عنوان ویدیو از API عمومی oEmbed یوتیوب
    بدون نیاز به کلید API
    """
    oembed_url = f"https://www.youtube.com/oembed?url={video_url}&format=json"
    try:
        response = requests.get(oembed_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("title", "بدون عنوان")
    except Exception as e:
        print(f"⚠️ دریافت عنوان ویدیو با خطا مواجه شد: {e}")
        print("🔹 از عنوان پیش‌فرض 'video' استفاده می‌شود.")
        return "video"


def sanitize_filename(name: str) -> str:
    """
    تبدیل عنوان به نام فایل امن:
    - جایگزینی فاصله با زیرخط
    - حذف کاراکترهای غیرمجاز در سیستم‌فایل
    """
    # حذف کاراکترهای غیرمجاز برای ویندوز و لینوکس
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # جایگزینی فاصله (و فاصله‌های چندگانه) با زیرخط
    name = re.sub(r"\s+", "_", name)
    # حذف زیرخط‌های اضافی
    name = re.sub(r"_+", "_", name)
    # حذف زیرخط ابتدا یا انتها
    name = name.strip("_")
    # اگر خالی شد، یک نام پیش‌فرض بده
    if not name:
        name = "video"
    return name


def format_timestamp(seconds: float) -> str:
    """تبدیل ثانیه به فرمت HH:MM:SS,mmm مخصوص SRT"""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def fetch_transcript(video_id: str, lang: str):
    """
    دریافت زیرنویس برای یک زبان مشخص.
    در صورت نبود، خطا برمی‌گرداند (متناسب با کتابخانه).
    """
    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
    return transcript


def generate_srt(transcript: list, lang: str) -> str:
    """ساخت محتوای فایل SRT از لیست قطعات زیرنویس"""
    srt_content = []
    for i, segment in enumerate(transcript, start=1):
        start = segment["start"]
        duration = segment["duration"]
        end = start + duration
        text = segment["text"].strip()
        srt_content.append(
            f"{i}\n"
            f"{format_timestamp(start)} --> {format_timestamp(end)}\n"
            f"{text}\n"
        )
    return "\n".join(srt_content)


def generate_txt(transcript: list) -> str:
    """ساخت محتوای فایل TXT شامل متن‌های زیرنویس (هر قطعه در یک خط)"""
    lines = [segment["text"].strip() for segment in transcript]
    return "\n".join(lines)


def main():
    if len(sys.argv) != 2:
        print("❌ نحوه استفاده: python get_transcript.py <URL_ویدیو>")
        sys.exit(1)

    video_url = sys.argv[1].strip()
    print(f"🎬 آدرس ویدیو: {video_url}")

    # استخراج شناسه ویدیو
    try:
        video_id = extract_video_id(video_url)
        print(f"🆔 شناسه ویدیو: {video_id}")
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # دریافت عنوان ویدیو
    print("📡 دریافت عنوان ویدیو...")
    title = get_video_title(video_url)
    safe_title = sanitize_filename(title)
    print(f"📝 عنوان: {title}")
    print(f"💾 نام فایل امن: {safe_title}")

    # ایجاد پوشه subtitle در ریشه مخزن (محل اجرای اسکریپت)
    output_dir = "subtitle"
    os.makedirs(output_dir, exist_ok=True)

    languages = {
        "fa": "فارسی",
        "en": "انگلیسی",
    }

    any_success = False

    for lang_code, lang_name in languages.items():
        print(f"\n🔍 تلاش برای دریافت زیرنویس {lang_name} ({lang_code})...")
        try:
            transcript = fetch_transcript(video_id, lang_code)
        except (NoTranscriptFound, TranscriptsDisabled) as e:
            print(f"⚠️ زیرنویس {lang_name} در دسترس نیست: {e}")
            continue
        except VideoUnavailable:
            print("❌ ویدیو در دسترس نیست یا خصوصی است.")
            sys.exit(1)
        except Exception as e:
            print(f"⚠️ خطای غیرمنتظره برای زبان {lang_name}: {e}")
            continue

        if not transcript:
            print(f"⚠️ زیرنویس {lang_name} خالی است.")
            continue

        # تولید محتوای فایل‌ها
        srt_data = generate_srt(transcript, lang_code)
        txt_data = generate_txt(transcript)

        # ذخیره فایل‌ها
        srt_filename = os.path.join(output_dir, f"{safe_title}_{lang_code}.srt")
        txt_filename = os.path.join(output_dir, f"{safe_title}_{lang_code}.txt")

        with open(srt_filename, "w", encoding="utf-8") as f:
            f.write(srt_data)
        with open(txt_filename, "w", encoding="utf-8") as f:
            f.write(txt_data)

        print(f"✅ زیرنویس {lang_name} با موفقیت ذخیره شد:")
        print(f"   📄 {srt_filename}")
        print(f"   📄 {txt_filename}")
        any_success = True

    if not any_success:
        print("\n❌ هیچ زیرنویسی (فارسی یا انگلیسی) برای این ویدیو یافت نشد.")
        sys.exit(1)

    print("\n🎉 عملیات با موفقیت به پایان رسید.")


if __name__ == "__main__":
    main()
