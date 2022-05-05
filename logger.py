from typing import Any
from util import SCRIPT_DIRECTORY
from datetime import datetime as dt
import atexit

class Logger:
    LOG_DIRECTORY = SCRIPT_DIRECTORY.joinpath("logs")
    __log_counter__ = 0

    def __init__(self) -> None:
        self.LOG_DIRECTORY.mkdir(exist_ok=True)
        date = dt.strftime(dt.now(), "%Y-%m-%d")
        self.log_file = open(self.LOG_DIRECTORY.joinpath(date).with_suffix(".log"), "a+", encoding="utf-8")
    
    def __log__(self, why: str, who: str, what: str):
        date = dt.strftime(dt.now(), "%H:%M:%S")
        for line in what.splitlines():
            self.log_file.write(f"[{date}] [{who}/{why}]: {line}\n")
            self.__log_counter__ += 1
        if self.__log_counter__ >= 5:
            self.__log_counter__ = 0
            self.log_file.flush()
    
    def __getattr__(self, name: str) -> Any:
        if name in ["debug", "info", "warn", "error"]:
            return lambda who, what: self.__log__(name.upper(), who, what)
        return object.__getattribute__(self, name)

    # def debug(self, who: str, what: Any):
    #     self.__log__("DEBUG", who, what)

    # def info(self, who: str, what: Any):
    #     self.__log__("INFO", who, what)

    # def error(self, who: str, what: Any):
    #     self.__log__("ERROR", who, what)

    # def warn(self, who: str, what: Any):
    #     self.__log__("WARN", who, what)

    def close(self):
        self.log_file.close()

logger = Logger()
atexit.register(lambda: logger.close())