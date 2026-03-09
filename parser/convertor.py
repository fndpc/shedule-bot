from __future__ import annotations

import argparse
import json
import re
import subprocess
from typing import Any

DATE_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")
GROUP_TOKEN_RE = re.compile(r"\d+[a-zа-я]?/\d{4}", flags=re.IGNORECASE)
HEADER_RE = re.compile(r"^\s*№\s+")
ROW_RE = re.compile(r"^\s*(\d+)\s+(\d{2}\.\d{2}\s*-\s*\d{2}\.\d{2})(.*)$")
HEADER_CLUSTER_GAP = 14


def normalize_group(group: str) -> str:
    return group.replace(" ", "").lower()


def extract_text_lines(pdf_path: str) -> list[str]:
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Command `pdftotext` is not installed.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Failed to read PDF: {exc.stderr.strip()}") from exc

    return proc.stdout.splitlines()


def extract_group_columns_from_header(line: str) -> list[dict[str, Any]]:
    token_matches = [(m.group(), m.start()) for m in GROUP_TOKEN_RE.finditer(line)]
    if not token_matches:
        return []

    clustered: list[list[tuple[str, int]]] = []
    for token, start in token_matches:
        if not clustered:
            clustered.append([(token, start)])
            continue

        previous_start = clustered[-1][-1][1]
        if start - previous_start <= HEADER_CLUSTER_GAP:
            clustered[-1].append((token, start))
        else:
            clustered.append([(token, start)])

    columns: list[dict[str, Any]] = []
    for cluster in clustered:
        groups = [token for token, _ in cluster]
        anchor = sum(start for _, start in cluster) / len(cluster)
        columns.append(
            {
                "groups": groups,
                "groups_normalized": [normalize_group(group) for group in groups],
                "anchor": anchor,
            }
        )

    return columns


def extract_available_groups(lines: list[str]) -> list[str]:
    groups: set[str] = set()
    for line in lines:
        if not HEADER_RE.match(line):
            continue
        for group in GROUP_TOKEN_RE.findall(line):
            groups.add(group)
    return sorted(groups)


def detect_shift(lines: list[str], header_index: int) -> str | None:
    for idx in range(header_index, -1, -1):
        line = lines[idx]
        if "1 смена" in line:
            return "1 смена"
        if "2 смена" in line:
            return "2 смена"
    return None


def parse_cell_text(cell_text: str) -> dict[str, str | None] | None:
    text = cell_text.strip()
    if not text:
        return None

    parts = [part.strip() for part in re.split(r"\s{2,}", text) if part.strip()]
    if not parts:
        return None

    if len(parts) == 1:
        return {"subject": parts[0], "room": None}

    return {"subject": " ".join(parts[:-1]), "room": parts[-1]}


def is_valid_subject(subject: str | None) -> bool:
    if subject is None:
        return False
    normalized = subject.strip()
    if len(normalized) < 3:
        return False
    return len(re.findall(r"[A-Za-zА-Яа-я]", normalized)) >= 3


def find_group_columns(
    lines: list[str], normalized_group: str
) -> list[tuple[int, int, list[float]]]:
    matches: list[tuple[int, int, list[float]]] = []

    for header_index, line in enumerate(lines):
        if not HEADER_RE.match(line):
            continue

        columns = extract_group_columns_from_header(line)
        if not columns:
            continue

        anchors = [column["anchor"] for column in columns]
        for column_index, column in enumerate(columns):
            if normalized_group in column["groups_normalized"]:
                matches.append((header_index, column_index, anchors))

    return matches


def parse_lessons_for_column(
    lines: list[str], header_index: int, column_index: int, anchors: list[float]
) -> list[dict[str, Any]]:
    lessons: list[dict[str, Any]] = []
    shift = detect_shift(lines, header_index)
    column_left = (
        int((anchors[column_index - 1] + anchors[column_index]) / 2)
        if column_index > 0
        else 0
    )
    column_right = (
        int((anchors[column_index] + anchors[column_index + 1]) / 2)
        if column_index + 1 < len(anchors)
        else None
    )

    for row_index in range(header_index + 1, len(lines)):
        line = lines[row_index]

        if HEADER_RE.match(line):
            break

        row_match = ROW_RE.match(line)
        if not row_match:
            continue

        lesson_number = row_match.group(1)
        time_interval = row_match.group(2)
        row_rest = row_match.group(3)
        row_rest_start = row_match.start(3)
        marker_pattern = re.compile(rf"(?<!\S){re.escape(lesson_number)}(?=\s{{2,}})")
        markers = list(marker_pattern.finditer(row_rest))

        if not markers:
            continue

        parsed_by_column: dict[int, dict[str, str | None]] = {}
        for marker_index, marker in enumerate(markers):
            abs_position = row_rest_start + marker.start()
            nearest_column = min(
                range(len(anchors)),
                key=lambda idx: abs(anchors[idx] - abs_position),
            )

            content_start = marker.end()
            while content_start < len(row_rest) and row_rest[content_start].isspace():
                content_start += 1

            content_end = (
                markers[marker_index + 1].start()
                if marker_index + 1 < len(markers)
                else len(row_rest)
            )

            parsed_cell = parse_cell_text(row_rest[content_start:content_end])
            if parsed_cell is None:
                continue
            if not is_valid_subject(parsed_cell["subject"]):
                continue

            existing = parsed_by_column.get(nearest_column)
            if existing is None:
                parsed_by_column[nearest_column] = parsed_cell
                continue

            old_subject = existing["subject"] or ""
            new_subject = parsed_cell["subject"] or ""
            if len(new_subject) > len(old_subject):
                parsed_by_column[nearest_column] = parsed_cell

        parsed_cell = parsed_by_column.get(column_index)
        if parsed_cell is None:
            left = max(column_left, row_rest_start)
            right = column_right if column_right is not None else len(line)
            raw_slice = line[left:right]
            cleaned_slice = re.sub(
                rf"^\s*{re.escape(lesson_number)}\s+",
                "",
                raw_slice,
            ).strip()
            parsed_cell = parse_cell_text(cleaned_slice)
            if parsed_cell is None:
                continue
            if not is_valid_subject(parsed_cell["subject"]):
                continue

        lesson: dict[str, Any] = {
            "lesson_number": lesson_number,
            "time": time_interval,
            "subject": parsed_cell["subject"],
            "room": parsed_cell["room"],
        }
        if shift is not None:
            lesson["shift"] = shift

        lessons.append(lesson)

    return lessons


def get_group_schedule(pdf_path: str, group: str) -> dict[str, Any]:
    lines = extract_text_lines(pdf_path)
    normalized_group = normalize_group(group)
    date = None

    for line in lines:
        date_match = DATE_RE.search(line)
        if date_match:
            date = date_match.group(0)
            break

    columns = find_group_columns(lines, normalized_group)
    if not columns:
        available_groups = extract_available_groups(lines)
        raise ValueError(
            f"Group '{group}' not found. Available groups: {', '.join(available_groups)}"
        )

    lessons: list[dict[str, Any]] = []
    for header_index, column_index, anchors in columns:
        lessons.extend(parse_lessons_for_column(lines, header_index, column_index, anchors))

    return {
        "group": group,
        "date": date,
        "lessons": lessons,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract schedule for one group from a PDF timetable."
    )
    parser.add_argument("--pdf", required=True, help="Path to timetable PDF.")
    parser.add_argument("--group", required=True, help="Group name, e.g. 21/2025.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    schedule = get_group_schedule(args.pdf, args.group)
    print(json.dumps(schedule, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
