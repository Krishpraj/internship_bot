from parsers.base import BaseParser
from parsers.canadian import CanadianParser
from parsers.simplifyjobs import SimplifyJobsParser

_PARSERS: dict[str, BaseParser] = {
    "canadian": CanadianParser(),
    "simplifyjobs": SimplifyJobsParser(),
}


def get_parser(name: str) -> BaseParser:
    return _PARSERS[name]
