# VersatileScrapeWebsiteTool

## Description

The `VersatileScrapeWebsiteTool` is a powerful and flexible tool, designed for scraping and processing content from websites. It expands upon basic web scraping by introducing multiple retrieval strategies, including full content extraction, partial reads based on character limits (head truncation), intelligent chunking for large files (random chunks), and AI-powered summarization.

This tool is essential for agents that need to gather information from the web, such as:
-   Extracting textual data from articles, blogs, or documentation.
-   Monitoring website content changes.
-   Feeding website information to AI models for analysis, summarization, or question-answering.
-   Handling large web pages by sampling content or summarizing it.

It uses the `requests` library for fetching web pages and `BeautifulSoup` for HTML parsing and text extraction.

## Key Features

-   **Multiple Retrieval Modes**:
    -   `full`: Extracts and returns all cleaned text content from the specified website URL.
    -   `head`: Returns the first `N` characters (specified by `max_chars`) of the cleaned website text.
    -   `random_chunks`: Extracts a strategic selection of text blocks (first, last, and random middle blocks) from the website content, useful for getting an overview of large pages within a character limit (`max_chars`). Each selected block is followed by "..." to indicate potential discontinuity.
    -   `summarize`: Uses a provided Language Model (LLM) to generate a summary of the website's text content. It internally uses the `random_chunks` method to select a substantial portion of the text for summarization.
-   **Configurable Defaults**: Initialize the tool with default settings for website URL, retrieval mode, character limits, LLM instance, cookies, and headers. These can be overridden at runtime. The tool's description dynamically updates to reflect these defaults.
-   **Customizable HTTP Headers and Cookies**: Allows setting custom HTTP headers and cookies for requests, including support for fetching cookie values from environment variables.
-   **Robust Text Extraction**: Uses BeautifulSoup to parse HTML and extract meaningful text, with basic cleaning to remove excessive whitespace.
-   **Intelligent Truncation**: For modes like `head` and `random_chunks`, if the website's total text content is smaller than the specified `max_chars`, the full content is returned without truncation.
-   **Error Handling**: Raises appropriate Python exceptions for issues like invalid URLs, network errors (e.g., connection errors, bad HTTP status codes), or problems during summarization.

## Example Usage

**Full Content Extraction (Default/Compatibility Mode):**

```python
from versatile_scrape_website_tool import VersatileScrapeWebsiteTool

scrape_website_tool = VersatileScrapeWebsiteTool()

content = scrape_website_tool.run(
    website_url="https://example.com/index.html"
)

print(f"Retrieved {len(content)} chars")
```

**Partial Extraction (Head Truncation Mode):**

```python
from versatile_scrape_website_tool import VersatileScrapeWebsiteTool

scrape_website_tool = VersatileScrapeWebsiteTool(
    retrieval_mode="head",
    max_chars=13002
)

content = scrape_website_tool.run(
    website_url="https://example.com/index.html"
)

print(f"Retrieved {len(content)} chars")
```

**Partial Extraction (Random Chunking Mode):**

```python
from versatile_scrape_website_tool import VersatileScrapeWebsiteTool

scrape_website_tool = VersatileScrapeWebsiteTool(
    retrieval_mode="random_chunks",
    max_chars=13321
)

content = scrape_website_tool.run(
    website_url="https://example.com/index.html"
)

print(f"Retrieved {len(content)} chars")
```

**AI-Powered Extraction (Summarization Mode):**

```python
from versatile_scrape_website_tool import VersatileScrapeWebsiteTool
from crewai import LLM
import os

os.environ["GEMINI_API_KEY"] = "<YOUR_API_KEY>"

gemini_llm = LLM(
    model="gemini/gemini-2.5-flash-preview-04-17",
    temperature=0.3
)

scrape_website_tool = VersatileScrapeWebsiteTool(
    retrieval_mode="summarize",
    llm=gemini_llm
)

content = scrape_website_tool.run(
    website_url="https://example.com/index.html"
)

print(f"Retrieved {len(content)} chars")
print(content)
```

## Arguments

The tool can be configured at initialization and its behavior further refined by arguments passed to the `run` method. Runtime arguments override initialization defaults.

### Initialization Parameters (`__init__`):
-   `website_url` (Optional[str]): Default URL to scrape.
-   `retrieval_mode` (Optional[Literal["full", "head", "random_chunks", "summarize"]]): Default retrieval strategy. Defaults to `"full"`.
-   `max_chars` (Optional[int]): Default maximum characters for `"head"` or `"random_chunks"` modes.
-   `llm` (Optional[BaseLLM]): Default LLM instance for `"summarize"` mode.
-   `cookies` (Optional[Dict[str, str]]): Default cookies for requests. Can be a direct dictionary of cookie names to values, or a dictionary like `{"name": "cookie_name", "value": "ENV_VAR_CONTAINING_VALUE"}` to load a cookie value from an environment variable.
-   `headers` (Optional[Dict[str, str]]): Default HTTP headers for requests. Overrides the class default headers if provided.
-   `name` (Optional[str]): Custom name for the tool instance.
-   `description` (Optional[str]): Custom base description for the tool instance. Details about defaults are appended to this.
-   `**kwargs`: Additional keyword arguments passed to `BaseTool`.

### Runtime `run` Method Parameters (defined in `VersatileScrapeWebsiteToolSchema`):
-   `website_url` (Optional[str]): URL of the website to scrape. If provided, overrides the initialized `default_website_url`. Mandatory if no default is set.
-   `retrieval_mode` (Optional[Literal["full", "head", "random_chunks", "summarize"]]): The retrieval strategy to use for this specific run. Overrides `default_retrieval_mode`.
-   `max_chars` (Optional[int]): Maximum characters for `'head'` or `'random_chunks'` modes.
    -   For `'random_chunks'`, if a value less than 3000 is provided, it will be internally adjusted to 3000.
-   `llm` (Optional[BaseLLM]): An LLM instance for `'summarize'` mode. Required if `retrieval_mode` is `'summarize'` and no `default_llm` was set at initialization or provided at runtime.

## Error Handling

The tool raises Python exceptions for various error conditions:
-   `ValueError`: For invalid or missing essential parameters (e.g., `website_url`, `max_chars` when required, `llm` for summarize mode).
-   `requests.exceptions.RequestException`: For network-related errors during the web request (e.g., connection errors, DNS failures, timeouts). This includes `requests.exceptions.HTTPError` for bad HTTP status codes (4xx or 5xx).
-   `RuntimeError`: For unexpected issues during processing, or if the LLM fails repeatedly during summarization.