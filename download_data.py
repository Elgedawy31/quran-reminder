"""Download the complete Quran and Al-Muyassar tafsir from Al Quran Cloud."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.request import urlopen

BASE = "https://api.alquran.cloud/v1/quran/"

def download(edition):
    with urlopen(BASE + edition, timeout=60) as response:
        payload = json.load(response)
    if payload.get("code") != 200 or payload["data"]["edition"]["identifier"] != edition:
        raise ValueError(f"Unexpected edition: {edition}")
    return payload

def combine(quran, tafsir):
    def flatten(payload):
        rows = {}
        surahs = payload["data"]["surahs"]
        if len(surahs) != 114:
            raise ValueError("Expected 114 surahs")
        for surah in surahs:
            for ayah in surah["ayahs"]:
                number = ayah["number"]
                if number in rows or not ayah["text"].strip():
                    raise ValueError(f"Duplicate or empty ayah: {number}")
                rows[number] = (surah, ayah)
        if set(rows) != set(range(1, 6237)):
            raise ValueError("Expected all 6236 unique ayahs")
        return rows
    arabic, meanings = flatten(quran), flatten(tafsir)
    verses = []
    for number in range(1, 6237):
        surah, ayah = arabic[number]
        meaning_surah, meaning = meanings[number]
        if (surah["number"], ayah["numberInSurah"]) != (meaning_surah["number"], meaning["numberInSurah"]):
            raise ValueError(f"Reference mismatch: {number}")
        verses.append({
            "number": number, "surah_number": surah["number"],
            "surah_name": surah["name"], "ayah": ayah["numberInSurah"],
            "arabic": ayah["text"], "tafsir": meaning["text"],
        })
    return {
        "source": "https://alquran.cloud/api",
        "endpoints": [BASE + "quran-uthmani", BASE + "ar.muyassar"],
        "quran_edition": "quran-uthmani", "tafsir_edition": "ar.muyassar",
        "downloaded_at": datetime.now(timezone.utc).isoformat(), "verses": verses,
    }

if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "data" / "verses.json"
    with ThreadPoolExecutor(max_workers=2) as executor:
        quran = executor.submit(download, "quran-uthmani")
        tafsir = executor.submit(download, "ar.muyassar")
        result = combine(quran.result(), tafsir.result())
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False))
    temporary.replace(output)
    print(f"Saved {len(result['verses'])} verified verse/tafsir pairs to {output}")
