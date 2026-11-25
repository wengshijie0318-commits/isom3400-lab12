"""Wikipedia Article Extractor.

Programming assistance: ChatGPT provided the initial implementation.
"""

from datetime import datetime
import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


class WikipediaExtractor:
    def __init__(self, topic):
        self.error = None
        self.title = None
        self.url = ""
        self.sections = []
        try:
            self.fetch_article(topic)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                self.error = "Article not found. Try another title."
            else:
                self.error = "Wikipedia could not serve this request. Please try again later."
        except requests.RequestException:
            self.error = "Could not reach Wikipedia. Please try again."
        except ValueError as exc:
            self.error = str(exc)

    def fetch_article(self, topic):
        article = quote(topic.strip().replace(" ", "_"), safe="")
        url = "https://en.wikipedia.org/wiki/" + article
        response = requests.get(
            url, timeout=15,
            headers={"User-Agent": "WikipediaArticleExtractor/1.0 (educational use)"}
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        heading = soup.find("h1", id="firstHeading") or soup.find("h1")
        content = soup.select_one("#mw-content-text .mw-parser-output")
        if content is None:
            content = soup.select_one(".mw-parser-output")
        if content is None:
            content = soup.find("main", id="content")
        if heading is None:
            heading = soup.title
        if content is None or heading is None:
            raise ValueError("The article could not be parsed.")

        self.title = heading.get_text(" ", strip=True).removesuffix(" - Wikipedia")
        self.url = response.url
        self.sections = self.parse_sections(content)


    @staticmethod
    def parse_sections(content):
        # Remove article navigation, edit controls and citation markers.
        unwanted = content.select(
            ".mw-editsection, sup.reference, .reflist, .navbox, .toc, "
            ".infobox, .sidebar, .hatnote, .metadata, .noprint, style, script"
        )
        for item in unwanted:
            if item.parent is not None:
                item.decompose()

        sections = []
        current = None
        tags = ["h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table"]
        for element in content.find_all(tags):
            # A list or table is handled as a whole, avoiding duplicate text.
            if element.find_parent(["ul", "ol", "table"]):
                continue

            if element.name == "h2":
                title = clean_text(element)
                if title:
                    current = {"title": title, "blocks": []}
                    sections.append(current)
                else:
                    current = None
            elif current is not None:
                if element.name in ["h3", "h4", "h5", "h6"]:
                    text = clean_text(element)
                    if text:
                        current["blocks"].append({"type": "subheading", "text": text})
                elif element.name == "p":
                    text = clean_text(element)
                    if text:
                        current["blocks"].append({"type": "paragraph", "text": text})
                elif element.name in ["ul", "ol"]:
                    lines = format_list(element)
                    if lines:
                        current["blocks"].append({"type": "list", "lines": lines})
                elif element.name == "table":
                    lines = format_table(element)
                    if lines:
                        current["blocks"].append({"type": "table", "rows": lines, "caption": clean_text(element.caption) if element.caption else ""})

        return sections

    def section_titles(self):
        return [section["title"] for section in self.sections]

    def extract(self, title):
        return next(section for section in self.sections if section["title"] == title)


def clean_text(element):
    text = element.get_text(" ", strip=True)
    text = re.sub(r"\[\s*\d+[a-z]?\s*\]", "", text)
    text = re.sub(r"\[edit\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return " ".join(text.split())


def format_list(element, level=0):
    lines = []
    for index, item in enumerate(element.find_all("li", recursive=False), start=1):
        parts = []
        for child in item.contents:
            if getattr(child, "name", None) in ["ul", "ol"]:
                continue
            if hasattr(child, "get_text"):
                parts.append(child.get_text(" ", strip=True))
            else:
                parts.append(str(child).strip())
        text = " ".join(" ".join(parts).split())
        text = re.sub(r"\[\s*\d+[a-z]?\s*\]", "", text).strip()
        prefix = f"{index}. " if element.name == "ol" else "- "
        if text:
            lines.append("  " * level + prefix + text)
        for nested in item.find_all(["ul", "ol"], recursive=False):
            lines.extend(format_list(nested, level + 1))
    return lines


def format_table(table):
    lines = []
    for row in table.find_all("tr"):
        if row.find_parent("table") is not table:
            continue
        cells = row.find_all(["th", "td"], recursive=False)
        if cells:
            lines.append([clean_text(cell) for cell in cells])
    return lines


def safe_filename(title):
    filename = re.sub(r'[^\w .-]', "_", title).strip(" .")
    return re.sub(r"\s+", "_", filename)[:100] or "Wikipedia_article"


def numbered_filename(stem, used):
    filename = f"{stem}.txt"
    index = 2
    while filename in used:
        filename = f"{stem} ({index}).txt"
        index += 1
    return filename


def format_txt(article_title, article_url, sections):
    lines = [article_title, "=" * len(article_title), "Source: " + article_url,
             "Extracted: " + datetime.now().astimezone().isoformat(timespec="seconds"),
             "Licence: CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/)"]
    for section in sections:
        title = section["title"]
        lines.extend(["", title, "=" * len(title)])
        if not section["blocks"]:
            lines.append("(No extractable content.)")
        for block in section["blocks"]:
            lines.append("")
            if block["type"] == "table":
                if block["caption"]:
                    lines.append(block["caption"])
                lines.extend(" | ".join(row) for row in block["rows"])
            elif block["type"] == "list":
                lines.extend(block["lines"])
            else:
                lines.append(block["text"])
                if block["type"] == "subheading":
                    lines.append("-" * len(block["text"]))
    return "\n".join(lines) + "\n"
