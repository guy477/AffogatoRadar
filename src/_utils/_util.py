from ._config import *

import os
import re
import numpy as np
import asyncio  # Add asyncio
import aiohttp
import pandas as pd
import sqlite3, json
from tqdm.asyncio import tqdm
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict, OrderedDict
from bs4 import BeautifulSoup, Comment

from typing import List, Optional, Dict, Any

import logging
from logging.handlers import RotatingFileHandler

# --------------------- Logging Configuration ---------------------

# Create a logger for the utilities module
UTIL_LOGGER = logging.getLogger('log')
UTIL_LOGGER.setLevel(logging.DEBUG)  # Set to DEBUG to capture all levels

# Define log format
log_format = logging.Formatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# File handler for DEBUG and higher with rotation
log_file = '../logging/log.log'

# Ensure the log file is wiped each run
if os.path.exists(log_file):
    os.remove(log_file)

file_handler = RotatingFileHandler(
    filename=log_file,
    mode='w',  # Overwrite the log file each run
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=1,
    encoding='utf-8',
    delay=0
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_format)

# Stream handler for ERROR and higher
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.ERROR)
stream_handler.setFormatter(log_format)

# Remove existing handlers and add new ones to ensure log file is overwritten each run
UTIL_LOGGER.handlers = []
UTIL_LOGGER.addHandler(file_handler)
UTIL_LOGGER.addHandler(stream_handler)

# Prevent logs from being propagated to the root logger
UTIL_LOGGER.propagate = False

# --------------------- End of Logging Configuration ---------------------
def HAS_CYCLE(path: str, max_cycle_length: int = 10) -> bool:
    """
    Detects if there is a cycle in the given URL path by identifying
    any repeating subsequences of segments.

    Args:
        path (str): The URL path to analyze.
        max_cycle_length (int): The maximum length of segment sequences to check for cycles.

    Returns:
        bool: True if a cycle is detected, False otherwise.
    """
    # Normalize the path by removing leading and trailing slashes
    normalized_path = path.strip("/")
    segments = normalized_path.split("/") if normalized_path else []

    n = len(segments)
    if n == 0:
        return False

    # Iterate over possible cycle lengths
    for cycle_length in range(1, min(max_cycle_length, n // 2) + 1):
        seen = {}
        for i in range(n - cycle_length + 1):
            window = tuple(segments[i:i + cycle_length])
            if window in seen:
                # Cycle detected
                return True
            seen[window] = True

    return False