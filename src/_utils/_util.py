from _config import *

import os
import re
import numpy as np
import asyncio  # Add asyncio
import aiohttp
import requests
import pandas as pd
import sqlite3, json
from tqdm.asyncio import tqdm
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl, urljoin, urlsplit
from fake_useragent import UserAgent
from datetime import datetime, timezone
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict, OrderedDict
from bs4 import BeautifulSoup, Comment

from typing import List, Optional, Dict, Any, Tuple

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
def has_cycle(path: str, max_cycle_length: int = 10) -> bool:
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

def normalize_url(url: str) -> str:
    """
    Normalize a URL by removing default ports, sorting query parameters, and 
    removing fragments.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.hostname.lower()
    if parsed.port:
        netloc += f":{parsed.port}"

    path = parsed.path or '/'
    query = urlencode(sorted(parse_qsl(parsed.query)))
    normalized = urlunparse((scheme, netloc, path, '', query, ''))
    return normalized


def get_anonymous_headers():
    headers = {
        "User-Agent": f"{UserAgent().random} (compatible; u-evol-guy@proton.me)",
        "Accept": "*/*",  # Accept everything
        "Accept-Language": "en-US,en;q=0.9",  # Accept language preference
        "Accept-Encoding": "*",  # Support compression
        # "DNT": "1",  # Do not track preference
        # "Connection": "close",  # No keep-alive
    }
    return headers