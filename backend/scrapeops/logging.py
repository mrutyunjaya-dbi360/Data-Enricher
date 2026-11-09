import logging
import re

_RE = re.compile(r"://[^:]+:[^@]+@")


class RedactSecretsFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = _RE.sub("://***:***@", record.msg)
        if record.args:
            try:
                record.args = tuple(
                    _RE.sub("://***:***@", a) if isinstance(a, str) else a
                    for a in record.args
                )
            except Exception:
                pass
        return True
