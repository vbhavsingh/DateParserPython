# DateParserPython

A lightweight Python port of the DateParser logic used to identify and normalize dates and times in natural-language text. The package exposes a single `Parser` class that scans free-form strings and returns structured `LocalDateModel` results containing normalized values, the detected format, and the source offsets.

## Installation

```bash
pip install dateparserpython
```

To work with a local clone, install the project in editable mode (this also makes the `dateparserpython` package importable straight from the repo):

```bash
python -m pip install -e .
```

## Quickstart

```python
from dateparserpython import Parser

parser = Parser()
for local_date in parser.parse("12/12/2025"):  # Pass any free‑form text
    print(local_date.date_time_string, local_date.identified_date_format)
```

Running `python test.py` prints a set of parsed examples for convenience.

## Development

1. Create a virtual environment and activate it.
2. Install editable dependencies: `python -m pip install -e .[dev]` (dev extras coming soon; currently empty).
3. Run unit tests / scripts from the project root. For ad-hoc checks you can run `python test.py` or create your own fixtures.

Please open an issue or PR if you hit a parsing case that is not currently supported.
