from __future__ import annotations

import argparse
from pathlib import Path
from urllib import parse
from urllib import request


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://curri.aca.ntu.edu.tw/NTUVoxCourse/index.php/uquery/search-result"
DEFAULT_YEARS = range(110, 115)
DEFAULT_GRADES = range(1, 5)
DEPARTMENTS = {
    "3030": "經濟學系",
    "9020": "資訊工程學系",
}
USER_AGENT = "Mozilla/5.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch NTU required courses pages by grade.")
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=list(DEFAULT_YEARS),
        help="Academic years to fetch. Defaults to 110 111 112 113 114.",
    )
    parser.add_argument(
        "--departments",
        nargs="+",
        default=sorted(DEPARTMENTS),
        help="Department codes to fetch. Defaults to 3030 9020.",
    )
    parser.add_argument(
        "--grades",
        nargs="+",
        type=int,
        default=list(DEFAULT_GRADES),
        help="Grades to fetch. Defaults to 1 2 3 4.",
    )
    parser.add_argument(
        "--output-root",
        default="data/raw/template-family/dpt-required-courses",
        help="Root directory for downloaded HTML files.",
    )
    return parser.parse_args()


def build_url(*, year: int, department_code: str, grade: int) -> str:
    query = parse.urlencode(
        {
            "semester": str(year),
            "dpt": "{0} ".format(department_code),
            "inqudata": "Academic",
            "lang": "zh",
            "MSLGRD": str(grade),
        }
    )
    return "{0}?{1}".format(BASE_URL, query)


def fetch_html(url: str) -> str:
    req = request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "zh-TW,zh;q=0.9",
        },
    )
    with request.urlopen(req, timeout=120) as response:
        return response.read().decode("utf-8", errors="replace")


def output_path(output_root: Path, *, year: int, department_code: str, grade: int) -> Path:
    department_name = DEPARTMENTS[department_code]
    year_dir = output_root / "{0}-{1}".format(department_code, department_name) / str(year)
    file_name = "{0}-{1}學年度-{2}年級系訂必修科目及學分表.html".format(
        department_code,
        year,
        grade,
    )
    return year_dir / file_name


def main() -> None:
    args = parse_args()
    output_root = (REPO_ROOT / args.output_root).resolve()

    for department_code in args.departments:
        if department_code not in DEPARTMENTS:
            raise ValueError("Unsupported department code: {0}".format(department_code))
        for year in args.years:
            for grade in args.grades:
                url = build_url(year=year, department_code=department_code, grade=grade)
                html = fetch_html(url)
                path = output_path(
                    output_root,
                    year=year,
                    department_code=department_code,
                    grade=grade,
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(html, encoding="utf-8")
                print(path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
