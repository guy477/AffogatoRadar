# Affogato Radar

Affogato Radar is an intelligent web scraping and crawling tool designed to locate establishments (such as cafes and restaurants) that serve affogato based on user-specified criteria. By leveraging advanced web crawling techniques, natural language processing with embeddings, and robust caching mechanisms, Affogato Radar provides a comprehensive and automated way to discover and analyze relevant establishments in your desired area.

## Table of Contents

- [Features](#features)
- [Why Affogato Radar is Cool](#why-affogato-radar-is-cool)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
  - [Web Scraping](#web-scraping)
  - [Web Crawling](#web-crawling)
  - [Embedding Matching](#embedding-matching)
  - [Caching and Storage](#caching-and-storage)
  - [Logging and Monitoring](#logging-and-monitoring)
- [Learning Experience](#learning-experience)
- [Potential Repurposing](#potential-repurposing)
- [Contributing](#contributing)
- [Comments](#Comments)

## Features

- **Intelligent Web Crawling:** Efficiently navigates and extracts data from multiple websites, handling various content types including HTML and PDF.
- **Advanced Web Scraping:** Parses and interprets web content to extract relevant information about establishments and their offerings.
- **Embeddings and Similarity Matching:** Utilizes OpenAI's language models to generate embeddings, enabling sophisticated similarity comparisons between scraped data and target attributes.
- **Robust Caching Mechanism:** Implements a local storage solution to cache fetched data, reducing redundant network requests and improving performance.
- **Comprehensive Logging:** Detailed logging at various levels (INFO, DEBUG, ERROR) to monitor the scraping and crawling processes.
- **Asynchronous Processing:** Leverages Python's `asyncio` for concurrent execution, enhancing the efficiency of web operations.

## Why Affogato Radar is Cool

Affogato Radar stands out by integrating several cutting-edge technologies to automate the discovery and analysis of establishments serving affogato. Unlike manual Google searches, this tool:

- **Deep Analysis:** Goes beyond simple search results by crawling through establishment websites to extract detailed menu information.
- **Smart Matching:** Uses embeddings to understand and match the attributes of menu items, ensuring accurate and relevant results.
- **Efficiency:** Caches data to minimize redundant scraping, saving time and resources.
- **Scalability:** Designed to handle large-scale data collection with concurrency controls, making it suitable for extensive searches.

## Installation

Affogato Radar leverages Anaconda for environment management to ensure a seamless setup. Follow the steps below to get started:

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/guy477/AffogatoRadar.git
   cd AffogatoRadar
   ```

2. **Create a Conda Environment:**

   Initialize a new Conda environment named `affogato` with Python 3.11:

   ```bash
   conda create -n affogato python=3.11
   ```

3. **Activate the Environment:**

   ```bash
   conda activate affogato
   ```

4. **Install Dependencies:**

   Install the necessary packages using Conda and Pip:

   - **Using Conda:**

     Install packages available through Conda's default channels or Conda-Forge:

     ```bash
     conda install numpy aiohttp requests pandas tqdm scikit-learn beautifulsoup4 -c conda-forge
     ```

   - **Using Pip:**

     Install the remaining packages via Pip:

     ```bash
     pip install rich tiktoken openai pymysql geopy pdfplumber playwright
     ```

5. **Install Playwright Browsers:**

   Playwright requires browser binaries to function correctly. Install the Chromium browser using Playwright:

   ```bash
   playwright install chromium
   ```

6. **Set Up Environment Variables:**

   Create a `.env` file in the root directory and add your API keys:

   ```env
   OPENAI_API_KEY="your_openai_api_key"
   GOOGLE_API_KEY="your_google_api_key"
   ```

   **Note:** Replace `"your_openai_api_key"` and `"your_google_api_key"` with your actual API keys.

## Configuration

Customize your scraping parameters in the `src/_config.py` file:

```python
# src/_config.py

SELECTED_ADDRESS = "Houston, Texas"
SEARCH_REQUEST = "affogato"
ESTABLISHMENT_TYPES = ["cafe", "restaurant"]
LOOKUP_RADIUS = 10000  # in meters
MAX_CONCURRENCY = 4
WEBPAGE_TIMEOUT = 10000  # in milliseconds
SIMILARITY_THRESHOLD = 0.6

TARGET_ATTRIBUTES = {  # Attributes of the dish of interest.
    "name": ["affogato"],  # Full, common name(s) of the menu item.
    "ingredient_1": ["espresso", "coffee", "cold brew"],  # Primary ingredients.
    "ingredient_2": ["ice cream", "vanilla ice cream", "gelato"],  # Secondary ingredients.
    # "ingredient_3": [],  # Tertiary ingredients and on..
}
```

Adjust the parameters as needed to tailor the scraping process to your requirements.

## Usage

Run the main script to start the crawling and scraping process:

```bash
python src/main.py
```

Upon completion, the results will be saved to `../results.csv`, containing detailed information about establishments and their menu offerings related to affogato.

## Project Structure

### Web Scraping

Handles fetching and parsing web content from establishments' websites.

- **File:** `src/web/webscraper.py`
- **Key Components:**
  - `WebScraper` class: Manages content fetching, caching, and parsing.
  - `ContentParser`: Parses HTML and PDF content to extract relevant information.

### Web Crawling

Efficiently navigates through web pages to discover relevant subpages.

- **File:** `src/web/webcrawler.py`
- **Key Components:**
  - `WebCrawler` class: Manages the crawling process using BFS, handles URL normalization, and cycle detection.

### Embedding Matching

Utilizes OpenAI's embeddings to match scraped data with target attributes.

- **File:** `src/_utils/_llm.py`
- **Key Components:**
  - `LLM` class: Interfaces with OpenAI's API to generate embeddings and handle chat completions.
  - `ItemMatcher` class: Calculates similarity scores between scraped items and target attributes using cosine similarity.

### Caching and Storage

Implements a robust caching mechanism to store and retrieve data efficiently.

- **Files:**
  - `src/_utils/_localstorage.py`
  - `src/_utils/_cust_db_manager.py`
  - `src/backend/cachemanager.py`
- **Key Components:**
  - `LocalStorage`: Manages local database interactions using `CustomDBManager`.
  - `CacheManager`: Handles different storage instances and provides methods to get/set cached data.

### Logging and Monitoring

Provides comprehensive logging to monitor the application's operations and debug issues.

- **File:** `src/_utils/_util.py`
- **Key Components:**
  - Logging configuration: Sets up logging levels, handlers, and formats.
  - Utility functions: Includes functions like `normalize_url` and `has_cycle` for URL processing.

## Learning Experience

Affogato Radar serves as an excellent educational project, encompassing various aspects of software development:

- **Web Technologies:** Gain hands-on experience with web crawling and scraping techniques.
- **Asynchronous Programming:** Learn to implement concurrent operations using `asyncio`.
- **Natural Language Processing:** Understand how to use language model embeddings for data matching.
- **Database Management:** Explore caching strategies and database interactions with MySQL.
- **Software Design Principles:** Apply concepts like single responsibility, cohesion, and naming conventions to create a maintainable codebase.
- **Error Handling and Logging:** Develop robust error handling mechanisms and effective logging practices.

## Potential Repurposing

Several components of Affogato Radar can be repurposed for other projects:

- **WebCrawler:** Can be adapted to crawl and scrape data for different keywords or industries.
- **CacheManager:** Useful for any project requiring efficient data caching and retrieval.
- **ItemMatcher:** Can be extended to match and analyze items based on different attributes using embeddings.
- **LLM Handler:** Easily configurable for various NLP tasks beyond embedding generation.

## Contributing

Contributions are welcome! Please follow these steps:

1. **Fork the Repository**
2. **Create a New Branch**

   ```bash
   git checkout -b feature/YourFeature
   ```

3. **Commit Your Changes**

   ```bash
   git commit -m "Add your message here"
   ```

4. **Push to the Branch**

   ```bash
   git push origin feature/YourFeature
   ```

5. **Open a Pull Request**

## Comments

This entire readme was generated using a single prompt in Cursor (IDE) using OpenAI's o1-mini model and it LGTM. The future is here, folks.

---

*Happy Crawling! ☕🍨*
