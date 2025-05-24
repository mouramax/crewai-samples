# VersatileScrapeWebsiteTool

## Description

The `VersatileScrapeWebsiteTool` is a comprehensive and flexible CrewAI tool for scraping and processing content from websites. It advances beyond basic web scraping by offering diverse retrieval strategies: full text extraction, partial content retrieval (head truncation), intelligent chunking (random chunks), and AI-powered summarization.

**Key Configuration at Initialization**:
The tool's core behavior — such as the `retrieval_mode`, character limits (`max_chars`), and the Language Model (`llm`) for summarization — is configured when an instance of the tool is created. These settings cannot be changed at runtime by the agent.

**Runtime Operation**:
When the tool's `run` method is executed by an agent, it **requires a `website_url`** to be provided. The tool then fetches, processes, and returns the content from this URL according to its initialized configuration.

**Dynamic Tool Description for LLMs**:
A crucial feature is that the tool's `description` (used by LLMs to understand its capabilities) **dynamically updates** based on how it was configured at initialization. For example, if initialized with `retrieval_mode="summarize"`, its description will reflect that it summarizes content.

**Standardized Output**:
The `run` method returns a **JSON string** representing a standardized output model (`VersatileScraperToolOutput`). This JSON string includes the scraped content or an error message, the source URL, and the retrieval mode used. This structured output is designed for clear communication back to the LLM.

This tool is essential for agents that need to gather information from the web, such as:
-   Extracting textual data from articles, blogs, or documentation.
-   Feeding website information to AI models for analysis, summarization, or question-answering.
-   Handling large web pages by sampling content or summarizing it.

It uses the `requests` library for fetching web pages and `BeautifulSoup` for HTML parsing and text extraction.

## Key Features

-   **Multiple Retrieval Modes (Set at Initialization)**:
    -   `full`: Extracts and returns all cleaned text content from the specified website URL.
    -   `head`: Returns the first `N` characters (specified by `max_chars` during initialization) of the cleaned website text.
    -   `random_chunks`: Extracts a strategic selection of text blocks (first, last, and random middle blocks) from the website content, useful for getting an overview of large pages within a character limit (`max_chars` set during initialization).
    -   `summarize`: Uses a Language Model (LLM provided during initialization) to generate a summary of the website's text content. It internally uses a content selection method (similar to `random_chunks`) to prepare text for summarization.
-   **Pydantic-Based Configuration**: All core settings are defined as Pydantic fields at initialization.
-   **Dynamic LLM Description**: The tool's description, which is visible to the LLM, automatically adapts to reflect its specific configuration (e.g., retrieval mode, default URL).
-   **Standardized JSON Output**: The `run` method returns a JSON string detailing the outcome, including `scraped_content`, `error_message`, `source_url`, and `retrieval_mode_used`.
-   **Customizable HTTP Headers and Cookies**: Allows setting custom HTTP headers and a dictionary of cookies for requests during initialization.
-   **Robust Text Extraction**: Uses BeautifulSoup to parse HTML and extract meaningful text, with basic cleaning to remove excessive whitespace.
-   **Intelligent Truncation**: For modes like `head` and `random_chunks`, if the website's total text content is smaller than the effective `max_chars`, the full content is returned.
-   **Clear Error Reporting**: Initialization errors raise Python exceptions. Runtime errors (e.g., network issues, summarization failures) are reported within the JSON output's `error_message` field.

## Standardized Output Structure

The `run` method returns a JSON string. When parsed, this string represents an object with the following potential fields (fields with `null` values are excluded from the JSON string):

```json
{
  "scraped_content": "The actual text content extracted or summarized...",
  "error_message": "A message describing an error if one occurred...",
  "source_url": "https://example.com/index.html",
  "retrieval_mode_used": "full" // or "head", "random_chunks", "summarize"
}
```
An agent or user can parse this JSON string to access the scraped data or error details.

## Example Usage

**Full Content Extraction:**

```python
from versatile_scrape_website_tool import VersatileScrapeWebsiteTool

# Default retrieval_mode is "full"
scrape_website_tool = VersatileScrapeWebsiteTool()

print("--- Tool Description ---")
print(scrape_website_tool.description, end="\n\n")

result = scrape_website_tool.run(
    website_url="https://example.com/index.html"
)

print("\n--- Tool `run()` Result ---")
print(result)
```

**Partial Extraction (Head Truncation Mode):**

```python
from versatile_scrape_website_tool import VersatileScrapeWebsiteTool

scrape_website_tool = VersatileScrapeWebsiteTool(
    retrieval_mode="head",
    max_chars=1000
)

print("--- Tool Description ---")
print(scrape_website_tool.description, end="\n\n")

result = scrape_website_tool.run(
    website_url="https://example.com/index.html"
)

print("\n--- Tool `run()` Result ---")
print(result)
```

**Partial Extraction (Random Chunking Mode):**

```python
from versatile_scrape_website_tool import VersatileScrapeWebsiteTool

scrape_website_tool = VersatileScrapeWebsiteTool(
    retrieval_mode="random_chunks",
    max_chars=3500
)

print("--- Tool Description ---")
print(scrape_website_tool.description, end="\n\n")

result = scrape_website_tool.run(
    website_url="https://example.com/index.html"
)

print("\n--- Tool `run()` Result ---")
print(result)
```

**AI-Powered Extraction (Summarization Mode):**

```python
from versatile_scrape_website_tool import VersatileScrapeWebsiteTool
from crewai import LLM
import os

os.environ["GEMINI_API_KEY"] = "<YOUR_API_KEY>"

# This LLM doesn't need to be the same one that your Agent uses. It can
# and should be a less robust LLM for summarization.
gemini_llm = LLM(
    model="gemini/gemini-2.5-flash-preview-04-17",
    temperature=0.1
)

scrape_website_tool = VersatileScrapeWebsiteTool(
    retrieval_mode="summarize", llm=gemini_llm
)

print("--- Tool Description ---")
print(scrape_website_tool.description, end="\n\n")

result = scrape_website_tool.run(
    website_url="https://example.com/index.html"
)

print("\n--- Tool `run()` Result ---")
print(result)
```

## Configuration and Runtime Arguments

The tool's behavior is primarily set by Pydantic fields during its initialization.

### Configuration Fields (at Initialization):
These are fields of the `VersatileScrapeWebsiteTool` class.
-   `retrieval_mode` (Literal["full", "head", "random_chunks", "summarize"]): Retrieval strategy. Defaults to `"full"`. **Cannot be changed after initialization.**
-   `max_chars` (Optional[int]): Maximum characters for `"head"` or `"random_chunks"` modes. Required if using these modes. Also influences context size for `"summarize"` mode. **Cannot be changed after initialization.**
    -   For `'random_chunks'`, if a value less than a configured minimum (e.g., 3000) is provided, it will be internally adjusted.
-   `llm` (Optional[BaseLLM]): An LLM instance (compatible with `crewai.llms.base_llm.BaseLLM`) for `"summarize"` mode. Required if `retrieval_mode` is `"summarize"`. **Cannot be changed after initialization.**
-   `cookies_config` (Optional[Dict[str, str]]): A dictionary of cookies for HTTP requests.
-   `request_headers` (Dict[str, str]): HTTP headers for requests. Defaults to a standard set of browser-like headers.
-   `summary_prompt_template` (str): Prompt template for `"summarize"` mode. The text to be summarized will be appended to this prompt. Defaults to a predefined template.

Standard `BaseTool` fields like `name` and `description` can also be set, but the tool's main `description` for the LLM is dynamically generated based on the above configurations.

### Runtime `run` Method Parameters (defined in `VersatileScrapeWebsiteToolSchema`):
-   `website_url` (str): **Mandatory** URL of the website to scrape for the current operation. This is the URL that will actually be fetched.
-   **Other parameters like `retrieval_mode`, `max_chars`, `llm` cannot be provided or changed at runtime via the `run` method.** The values set during Pydantic initialization will always be used.

## Error Handling

-   **Initialization Errors**: If essential parameters are missing or invalid during tool instantiation (e.g., `max_chars` not set for `"head"` mode, or `llm` missing for `"summarize"` mode), Pydantic will raise a `ValueError`.
-   **Runtime Errors**:
    -   If the `website_url` provided to `run` is empty or invalid, the returned JSON string will contain an `error_message`.
    -   Network-related errors during web requests (e.g., connection errors, DNS failures, timeouts, bad HTTP status codes from `requests.exceptions.RequestException`) are caught, and the returned JSON string will contain an `error_message` detailing the issue.
    -   Processing errors, such as an LLM failing to generate a summary after multiple attempts in `"summarize"` mode, will also be reported via the `error_message` in the JSON output.