# VersatileFileReadTool

## Description

The `VersatileFileReadTool` provides a robust and adaptable CrewAI tool for reading and processing content from files. It enhances standard file operations by offering diverse retrieval strategies: complete content extraction, partial reads limited by character count (head truncation), intelligent chunking for sampling large files (random chunks), and AI-driven summarization.

**Key Configuration at Initialization**:
The tool's core behavior — such as the `retrieval_mode`, character limits (`max_chars`), line ranges (`start_line`, `line_count` for "full" mode), the Language Model (`llm`) for summarization, and an optional default `file_path` — is configured when an instance of the tool is created. **These settings, once initialized, cannot be changed at runtime by an agent.**

**Runtime Operation**:
When the tool's `run` method is executed by an agent, it can optionally accept a `file_path`.
- If a `file_path` is provided at runtime, it will be used for that specific operation, overriding any default `file_path` set during initialization.
- If no `file_path` is provided at runtime, the tool will use the default `file_path` (if one was configured during initialization).
- If neither a runtime `file_path` nor a initialization one is available, an error will be reported.
The tool then reads, processes, and returns the content from the determined file path according to its initialized configuration.

**Dynamic Tool Description for LLMs**:
A crucial feature is that the tool's `description` (used by LLMs to understand its capabilities) **dynamically updates** based on how it was configured at initialization. For example, if initialized with `retrieval_mode="summarize"` and a default `file_path`, its description will reflect these settings.

**Standardized Output**:
The `run` method returns a **JSON string** representing a standardized output model (`VersatileFileReadToolOutput`). This JSON string includes the read content or an error message, the source file path used, and the retrieval mode applied. This structured output is designed for clear communication back to the LLM.

This tool is invaluable for agents needing to interact with file data, such as:
-   Processing text files for information extraction.
-   Handling large configuration or log files by sampling relevant parts.
-   Feeding file content to AI agents in manageable or summarized forms.
-   Importing data for analysis or further processing.

It primarily supports text-based files and reads them using UTF-8 encoding, with error handling for common file access issues.

## Key Features

-   **Multiple Retrieval Modes (Set at Initialization)**:
    -   `full`: Reads the entire file or a specified range of lines (using `start_line` and `line_count` set during initialization).
    -   `head`: Reads the first `N` characters of a file (using `max_chars` set during initialization).
    -   `random_chunks`: Extracts a strategic selection of blocks (first, last, and random middle blocks) from a file, useful for getting a sense of large files within a character limit (`max_chars` set during initialization).
    -   `summarize`: Uses a Language Model (LLM provided during initialization) to generate a summary of the file's content. It internally uses a content selection method (similar to `random_chunks`) to prepare text for summarization.
-   **Pydantic-Based Configuration**: All core settings are defined as Pydantic fields at initialization.
-   **Optional Default File Path**: A `file_path` can be set at initialization, which can be overridden by a `file_path` provided at runtime.
-   **Dynamic LLM Description**: The tool's description, visible to the LLM, automatically adapts to reflect its specific configuration (e.g., retrieval mode, default file path).
-   **Standardized JSON Output**: The `run` method returns a JSON string detailing the outcome, including `read_content`, `error_message`, `source_file_path`, and `retrieval_mode_used`.
-   **UTF-8 Encoding**: Reads files with UTF-8 encoding and ignores errors by default.
-   **Intelligent Truncation**: For modes like `head` and `random_chunks`, if the file's total content is smaller than the effective `max_chars`, the full content is returned.
-   **Clear Error Reporting**: Initialization errors raise Python exceptions. Runtime errors (e.g., file not found, permission issues, summarization failures) are reported within the JSON output's `error_message` field.

## Standardized Output Structure

The `run` method returns a JSON string. When parsed, this string represents an object with the following potential fields (fields with `null` values are excluded from the JSON string):

```json
{
  "read_content": "The actual text content read or summarized...",
  "error_message": "A message describing an error if one occurred...",
  "source_file_path": "/path/to/your/file.txt",
  "retrieval_mode_used": "full" // or "head", "random_chunks", "summarize"
}
```
An agent or user can parse this JSON string to access the read data or error details.

## Example Usage

**Full Content Extraction (Using Runtime `file_path`):**

```python
from versatile_file_read_tool import VersatileFileReadTool

# Default retrieval_mode is "full"
file_read_tool = VersatileFileReadTool()

print("--- Tool Description ---")
print(file_read_tool.description, end="\n\n")

result = file_read_tool.run(
    file_path="/path/to/your/file.txt"
)

print("\n--- Tool `run()` Result ---")
print(result)
```

**Full Content Extraction (Using `file_path` from Initialization):**

```python
from versatile_file_read_tool import VersatileFileReadTool

file_read_tool = VersatileFileReadTool(
    file_path="/path/to/your/file.txt",
    retrieval_mode="full" # Explicitly full, or rely on default
)

print("--- Tool Description ---")
print(file_read_tool.description, end="\n\n")

# No file_path provided to run(), so initial file_path is used
result = file_read_tool.run()

print("\n--- Tool `run()` Result ---")
print(result)
```

**Partial Extraction (Head Truncation Mode):**

```python
from versatile_file_read_tool import VersatileFileReadTool

file_read_tool = VersatileFileReadTool(
    retrieval_mode="head",
    max_chars=500  # Max characters to read from the start
)

print("--- Tool Description ---")
print(file_read_tool.description, end="\n\n")

result = file_read_tool.run(
    file_path="/path/to/your/large_file.log"
)

print("\n--- Tool `run()` Result ---")
print(result)
```

**Partial Extraction (Random Chunking Mode):**

```python
from versatile_file_read_tool import VersatileFileReadTool

file_read_tool = VersatileFileReadTool(
    retrieval_mode="random_chunks",
    max_chars=3250 # Target total characters from chunks
)

print("--- Tool Description ---")
print(file_read_tool.description, end="\n\n")

result = file_read_tool.run(
    file_path="/path/to/your/very_large_document.txt"
)

print("\n--- Tool `run()` Result ---")
print(result)
```

**AI-Powered Extraction (Summarization Mode):**

```python
from versatile_file_read_tool import VersatileFileReadTool
from crewai import LLM
import os

os.environ["GEMINI_API_KEY"] = "<YOUR_API_KEY>"

# This LLM doesn't need to be the same one that your Agent uses. It can
# and should be a less robust LLM for summarization.
gemini_llm = LLM(
    model="gemini/gemini-2.5-flash-preview-04-17",
    temperature=0.1
)

file_read_tool = VersatileFileReadTool(
    retrieval_mode="summarize",
    llm=gemini_llm
)

print("--- Tool Description ---")
print(gemini_llm.description, end="\n\n")

result = file_read_tool_summarize.run(
    file_path="/path/to/your/article_to_summarize.md"
)

print("\n--- Tool `run()` Result ---")
print(result)
```

## Configuration and Runtime Arguments

The tool's behavior is primarily set by Pydantic fields during its initialization.

### Configuration Fields (at Initialization):
These are fields of the `VersatileFileReadTool` class.
-   `file_path` (Optional[str]): Default full path to the file. If set, this path will be used by `run()` if no `file_path` is provided at runtime.
-   `retrieval_mode` (Literal["full", "head", "random_chunks", "summarize"]): Retrieval strategy. Defaults to `"full"`. **Cannot be changed after initialization.**
-   `start_line` (int): Line number to start reading from (1-indexed) for `"full"` mode. Defaults to `1`. **Cannot be changed after initialization.**
-   `line_count` (Optional[int]): Number of lines to read for `"full"` mode. `None` means read to end. Defaults to `None`. **Cannot be changed after initialization.**
-   `max_chars` (Optional[int]): Maximum characters for `"head"` or `"random_chunks"` modes. Required if using these modes. Also influences context size for `"summarize"` mode. Must be >= 1 if set. **Cannot be changed after initialization.**
    -   For `'random_chunks'` and context for `'summarize'`, if a value less than a configured minimum (e.g., 3000) is provided, it will be internally adjusted.
-   `llm` (Optional[BaseLLM]): An LLM instance (compatible with `crewai.llms.base_llm.BaseLLM`) for `"summarize"` mode. Required if `retrieval_mode` is `"summarize"`. **Cannot be changed after initialization.**
-   `summary_prompt_template` (str): Prompt template for `"summarize"` mode. The file content to be summarized will be appended to this prompt. Defaults to a predefined template. **Cannot be changed after initialization.**

Standard `BaseTool` fields like `name` and `description` can also be set; the tool's main `description` for the LLM is dynamically generated based on the above configurations and prepended to any custom base description.

### Runtime `run` Method Parameters (defined in `VersatileFileReadToolSchema`):
-   `file_path` (Optional[str]): Path to the file to read for the current operation.
    - If provided, this path overrides the default `file_path` (set during initialization).
    - If not provided, the `file_path` from initialization is used.
    - It is mandatory to have an effective `file_path`, either from this runtime argument or from the initialization.
-   **Other parameters like `retrieval_mode`, `start_line`, `line_count`, `max_chars`, `llm` cannot be provided or changed at runtime via the `run` method.** The values set during Pydantic initialization will always be used.

## Error Handling

-   **Initialization Errors**: If essential parameters are missing or invalid during tool instantiation (e.g., `max_chars` not set for `"head"` mode, or `llm` missing for `"summarize"` mode), Pydantic will raise a `ValueError`.
-   **Runtime Errors**: These are reported within the `error_message` field of the returned JSON string:
    -   If no `file_path` is available (i.e., not provided to `run()` and no `file_path` was set at initialization).
    -   If the determined `file_path` does not exist (`FileNotFoundError` internally).
    -   If the program lacks permissions to read the file (`PermissionError` internally).
    -   If `start_line` is invalid for the file size in `"full"` mode (`ValueError` internally).
    -   If an LLM fails to generate a summary after multiple attempts in `"summarize"` mode (`ValueError` internally).
    -   Other unexpected errors during file operations (`RuntimeError` internally).