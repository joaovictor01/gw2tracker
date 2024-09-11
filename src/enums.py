from enum import Enum


class TradingPostModeEnum(str, Enum):
    sell = "sells"
    buy = "buys"
