from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TwitterChannel:
    async def fetch(self, config, limit=20):
        return []


def get_twitter_channel():
    return TwitterChannel()