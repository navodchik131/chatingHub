"""Dump remaining Cyrillic strings from about-service.en.html."""
import re
from pathlib import Path

text = Path("frontend/public/about-service.en.html").read_text(encoding="utf-8")
seen: set[str] = set()
for line in text.splitlines():
    if "base64" in line or len(line) > 800:
        continue
    for m in re.finditer(r"[а-яА-ЯёЁ][^<]{0,120}[а-яА-ЯёЁ]|[а-яА-ЯёЁ]{2,}", line):
        s = m.group(0).strip()
        if len(s) > 2:
            seen.add(s)

out = Path("scripts/about_service_ru_strings.txt")
out.write_text("\n".join(sorted(seen, key=len)), encoding="utf-8")
print(len(seen), "strings ->", out)
