# VersatileScrapeWebsiteTool

## Description

The `VersatileScrapeWebsiteTool` is a comprehensive and flexible solution for scraping and processing content from websites. It advances beyond basic web scraping by offering diverse retrieval strategies: full text extraction from web pages, partial content retrieval based on character limits (head truncation), intelligent chunking for an overview of large pages (random chunks), and AI-powered summarization. **The specific retrieval strategy (`retrieval_mode`), character limits (`max_chars`), and LLM (for summarization) are configured when the tool is initialized and cannot be changed at runtime by an agent.**

This tool is essential for agents that need to gather information from the web, such as:
-   Extracting textual data from articles, blogs, or documentation.
-   Monitoring website content changes.
-   Feeding website information to AI models for analysis, summarization, or question-answering.
-   Handling large web pages by sampling content or summarizing it.

It uses the `requests` library for fetching web pages and `BeautifulSoup` for HTML parsing and text extraction.

## Key Features

-   **Multiple Retrieval Modes (Set at Initialization)**:
    -   `full`: Extracts and returns all cleaned text content from the specified website URL.
    -   `head`: Returns the first `N` characters (specified by `max_chars` during initialization) of the cleaned website text.
    -   `random_chunks`: Extracts a strategic selection of text blocks (first, last, and random middle blocks) from the website content, useful for getting an overview of large pages within a character limit (`max_chars` set during initialization). Each selected block is followed by "..." to indicate potential discontinuity.
    -   `summarize`: Uses a Language Model (LLM) provided during initialization to generate a summary of the website's text content. It internally uses the `random_chunks` method to select a substantial portion of the text for summarization.
-   **Configurable Defaults at Initialization**: Initialize the tool with settings for website URL, retrieval mode, character limits, LLM instance, cookies, and headers. Only the `website_url` can be overridden when the `run` method is called. The tool's description dynamically updates to reflect the configured defaults.
-   **Customizable HTTP Headers and Cookies**: Allows setting custom HTTP headers and cookies for requests during initialization, including support for fetching cookie values from environment variables.
-   **Robust Text Extraction**: Uses BeautifulSoup to parse HTML and extract meaningful text, with basic cleaning to remove excessive whitespace.
-   **Intelligent Truncation**: For modes like `head` and `random_chunks`, if the website's total text content is smaller than the `max_chars` set during initialization, the full content is returned without truncation.
-   **Error Handling**: Raises appropriate Python exceptions for issues like invalid URLs, network errors (e.g., connection errors, bad HTTP status codes), or problems during summarization (e.g., missing LLM).

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

The tool is configured at initialization. Only the `website_url` can be optionally overridden when calling the `run` method.

### Initialization Parameters (`__init__`):
-   `website_url` (Optional[str]): Default URL to scrape if none is provided to `run`.
-   `retrieval_mode` (Optional[Literal["full", "head", "random_chunks", "summarize"]]): Retrieval strategy to use. Defaults to `"full"`. **This cannot be changed after initialization.**
-   `max_chars` (Optional[int]): Maximum characters for `"head"` or `"random_chunks"` modes. Required if using these modes. **This cannot be changed after initialization.**
    -   For `'random_chunks'`, if a value less than 3000 is provided, it will be internally adjusted to 3000.
-   `llm` (Optional[BaseLLM]): An LLM instance (compatible with `crewai.llms.base_llm.BaseLLM`) for `"summarize"` mode. Required if `retrieval_mode` is `"summarize"`. **This cannot be changed after initialization.**
-   `cookies` (Optional[Dict[str, str]]): Cookies for requests. Can be a direct dictionary or configured to load from environment variables (see original README example).
-   `headers` (Optional[Dict[str, str]]): HTTP headers for requests. Overrides the class default headers if provided.
-   `name` (Optional[str]): Custom name for the tool instance.
-   `description` (Optional[str]): Custom base description for the tool instance. Details about configured defaults are appended to this.
-   `**kwargs`: Additional keyword arguments passed to `BaseTool`.

### Runtime `run` Method Parameters (defined in `VersatileScrapeWebsiteToolSchema`):
-   `website_url` (Optional[str]): URL of the website to scrape. If provided, overrides the `website_url` set during initialization (if any). Mandatory if no default `website_url` was set during initialization.
-   **Other parameters like `retrieval_mode`, `max_chars`, `llm` cannot be provided or changed at runtime via the `run` method.** The values set during initialization will always be used.

## Error Handling

The tool raises Python exceptions for various error conditions:
-   `ValueError`: For invalid or missing essential parameters during initialization (e.g., `max_chars` when required by the mode, `llm` for summarize mode) or if `website_url` is missing at both initialization and runtime.
-   `requests.exceptions.RequestException`: For network-related errors during the web request (e.g., connection errors, DNS failures, timeouts). This includes `requests.exceptions.HTTPError` for bad HTTP status codes (4xx or 5xx).
-   `RuntimeError`: For unexpected issues during processing, or if the LLM fails repeatedly during summarization.