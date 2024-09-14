from ._config import *

import os
import re
import numpy as np
import asyncio  # Add asyncio
import aiohttp
import pandas as pd
import sqlite3, json
from tqdm import tqdm
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict, OrderedDict
from bs4 import BeautifulSoup, Comment

import logging
from logging.handlers import RotatingFileHandler

# --------------------- Logging Configuration ---------------------

# Create a logger for the utilities module
util_logger = logging.getLogger('log')
util_logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture all levels

# Define log format
log_format = logging.Formatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


# File handler for DEBUG and higher with rotation
file_handler = RotatingFileHandler(
    filename='../logging/log.log',
    mode='w',
    maxBytes=5*1024*1024,  # 5 MB
    backupCount=3,
    encoding='utf-8',
    delay=0
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_format)

# Stream handler for DEBUG and higher (optional)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.WARNING)
stream_handler.setFormatter(log_format)

# Avoid adding multiple handlers if they already exist
if not util_logger.handlers:
    util_logger.addHandler(file_handler)
    util_logger.addHandler(stream_handler)

# Prevent logs from being propagated to the root logger
util_logger.propagate = False

# --------------------- End of Logging Configuration ---------------------
