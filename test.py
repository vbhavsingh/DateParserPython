"""Example script showcasing basic usage of dateparserpython."""

from dateparserpython import Parser


def main() -> None:
    parser = Parser()
    data = parser.parse(
        """
        12/12/2025 (Common in the US, using MM/DD/YYYY format)
        12/12/25 (Shortened numerical format)
        2025/12/12 (ISO 8601 standard format, often used in data systems)
        12 Dec 2025 (Abbreviated alpha-numeric format)
        December 12, 2025 (Full alpha-numeric, common in formal documents)
        12 December, 2025 (Variation with comma placement)
        Fri, Dec 12, 2025 (Includes the day of the week)
        Friday, December 12, 2025 (Full textual representation)
        12.12.2025 (Common in many parts of Europe, using DD.MM.YYYY)
        12-12-2025 (Using hyphens as separators, often MM-DD-YYYY or DD-MM-YYYY)
        2025-12-12 (Another ISO 8601 variation with hyphens)
        """
    )
    for parsed in data:
        print(parsed)


if __name__ == "__main__":
    main()
