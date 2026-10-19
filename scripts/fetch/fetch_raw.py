from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from urllib import request


REPO_ROOT = Path(__file__).resolve().parents[2]
FETCH_DIR = Path(__file__).resolve().parent
RAW_ROOT = REPO_ROOT / "data" / "raw"
DRIVE_DOWNLOAD_URL = "https://drive.google.com/uc?export=download&id={0}"
USER_AGENT = "Mozilla/5.0"

# Scraped from the NTU curriculum site.
HTML_FETCHERS = [
    "fetch_credit_required.py",
    "fetch_required_courses.py",
]

# Collected by hand and mirrored to a public Google Drive folder:
# https://drive.google.com/drive/folders/1OzPoFpoHOW788gPTNMOxmDl039We1qDm
DRIVE_FILES = {
    "source-specific/台大經濟雙主修_輔系常見Q_A.pdf": "1jYpBnn2ndr7Ti29pPB8ubr9nQJ5f2yjS",
    "source-specific/國立臺灣大學轉系、輔系及雙主修相關規定查詢網頁.pdf": "1F2sb9Z6bLjT93RceZ5hJG3yqLwx0RD1C",
    "source-specific/台大經濟系轉雙輔招生頁面.html": "1J9QC08GfPiGszTCeCCPk0WUm_kvK06Wf",
    "template-family/dpt-double-major-policy/國立臺灣大學111學年度經濟學系雙主修相關規定.pdf": "1lYspnZGcpzpnAkw2jNAbRwDK0wjC2Ffy",
    "template-family/dpt-double-major-policy/國立臺灣大學112學年度經濟學系雙主修相關規定.pdf": "1T8MdbUAIr1btFNMICMJvSfzYMaPAuz6N",
    "template-family/dpt-double-major-policy/國立臺灣大學113學年度經濟學系雙主修相關規定 .pdf": "1j-upYrn_V11tdIGQnpegh3CGfg7XcOtg",
    "template-family/dpt-double-major-policy/國立臺灣大學114學年度經濟學系雙主修相關規定.pdf": "1HK_TGG6ozH5RjbwzXK3Gz5S-6n2FIu94",
    "template-family/dpt-double-major-policy/國立臺灣大學115學年度經濟學系雙主修相關規定.pdf": "1FcIu8CAWsMj1KnwQqmQtfF4qFwmaqQi6",
}


def run_html_fetchers() -> None:
    for script in HTML_FETCHERS:
        subprocess.run([sys.executable, str(FETCH_DIR / script)], check=True)


def download_drive_file(file_id: str) -> bytes:
    req = request.Request(
        DRIVE_DOWNLOAD_URL.format(file_id),
        headers={"User-Agent": USER_AGENT},
    )
    with request.urlopen(req, timeout=120) as response:
        # Files that are not shared publicly redirect to the Google sign-in page.
        if "accounts.google.com" in response.geturl():
            raise RuntimeError("Google Drive did not return the file (is it shared publicly?): {0}".format(file_id))
        return response.read()


def download_drive_files() -> None:
    for relative_path, file_id in DRIVE_FILES.items():
        path = RAW_ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(download_drive_file(file_id))
        print(path.relative_to(REPO_ROOT))


def main() -> None:
    run_html_fetchers()
    download_drive_files()


if __name__ == "__main__":
    main()
