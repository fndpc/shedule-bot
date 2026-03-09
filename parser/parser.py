from __future__ import annotations

import datetime as dt
import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

from parser.convertor import get_group_schedule

TARGET_GROUP = "81/2023"
SCHEDULE_PAGE_URL = "https://chehtk.gosuslugi.ru/grafik-zanyatiy/"
PDF_CLASS_NAME = "gw-document-item__collapse-link"
DATE_IN_FILENAME_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})")


class _ScheduleLinksParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.pdf_links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return

        attrs_map = {key: value for key, value in attrs}
        href = attrs_map.get("href")
        classes = attrs_map.get("class", "") or ""
        class_tokens = classes.split()
        if href and PDF_CLASS_NAME in class_tokens:
            self.pdf_links.append(href)


def _download_text(url: str) -> str:
    with urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def _download_bytes(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:
        return response.read()


def _choose_latest_pdf_url(urls: list[str]) -> str:
    dated_urls: list[tuple[dt.datetime, int, str]] = []
    for index, url in enumerate(urls):
        match = DATE_IN_FILENAME_RE.search(url)
        if match is None:
            continue
        date_value = dt.datetime.strptime(match.group(1), "%d.%m.%Y")
        dated_urls.append((date_value, index, url))

    if dated_urls:
        # Prefer newest date. For same date keep the first occurrence from HTML.
        return sorted(dated_urls, key=lambda item: (-item[0].timestamp(), item[1]))[0][2]

    return urls[0]


def fetch_latest_pdf_url(page_url: str = SCHEDULE_PAGE_URL) -> str:
    html = _download_text(page_url)
    parser = _ScheduleLinksParser()
    parser.feed(html)
    if not parser.pdf_links:
        raise RuntimeError(
            f"Cannot find link with class '{PDF_CLASS_NAME}' on page {page_url}"
        )

    absolute_urls = [urljoin(page_url, link) for link in parser.pdf_links]
    return _choose_latest_pdf_url(absolute_urls)


def download_schedule_pdf(pdf_url: str, target_dir: str = "downloads") -> Path:
    data = _download_bytes(pdf_url)
    destination_dir = Path(target_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(urlparse(pdf_url).path).name or "schedule.pdf"
    destination_path = destination_dir / filename
    destination_path.write_bytes(data)
    return destination_path


def parse_schedule_from_pdf_url(
    pdf_url: str,
    group: str = TARGET_GROUP,
) -> dict:
    pdf_path = download_schedule_pdf(pdf_url)
    return get_group_schedule(str(pdf_path), group)


def get_latest_schedule_for_target_group(
    page_url: str = SCHEDULE_PAGE_URL,
    group: str = TARGET_GROUP,
) -> tuple[str, dict]:
    pdf_url = fetch_latest_pdf_url(page_url)
    schedule = parse_schedule_from_pdf_url(pdf_url, group)
    return pdf_url, schedule


def schedule_signature(schedule: dict) -> str:
    raw = str(schedule).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def format_schedule_message(schedule: dict, pdf_url: str) -> str:
    date_value = schedule.get("date") or "не указана"
    group = schedule.get("group") or TARGET_GROUP
    lessons = schedule.get("lessons", [])

    lines = [
        "Обновилось расписание",
        f"Группа: {group}",
        f"Дата: {date_value}",
        "",
    ]

    if not lessons:
        lines.append("На выбранную группу пар не найдено.")
    else:
        for lesson in lessons:
            time_value = lesson.get("time", "время не указано")
            subject = lesson.get("subject", "предмет не указан")
            room = lesson.get("room")
            if room:
                lines.append(f"{time_value} — {subject} ({room})")
            else:
                lines.append(f"{time_value} — {subject}")

    lines.extend(["", f"Источник: {pdf_url}"])
    return "\n".join(lines)
