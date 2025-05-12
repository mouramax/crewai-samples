# VersatileFileReadTool

## Description

The `VersatileFileReadTool` offers a robust and adaptable approach to reading and processing content from various file types. It significantly enhances standard file reading methods by providing multiple retrieval strategies: complete content extraction, partial reads limited by character count (head truncation), intelligent chunking for sampling large files (random chunks), and AI-driven summarization. **The specific retrieval strategy (`retrieval_mode`), character limits (`max_chars`), line ranges (`start_line`, `line_count`), and LLM (for summarization) are configured when the tool is initialized and cannot be changed at runtime by an agent.**

This tool is invaluable for tasks requiring interaction with file data, such as:
-   Processing text files for information extraction.
-   Handling large configuration files or log files by sampling relevant parts.
-   Feeding file content to AI agents in manageable or summarized forms.
-   Importing data for analysis or further processing.

It supports text-based files and reads them using UTF-8 encoding, with error handling for common file access issues.

## Key Features

-   **Multiple Retrieval Modes (Set at Initialization)**:
    -   `full`: Reads the entire file or a specified range of lines (using `start_line` and `line_count` set during initialization).
    -   `head`: Reads the first `N` characters of a file (using `max_chars` set during initialization).
    -   `random_chunks`: Extracts a strategic selection of blocks (first, last, and random middle blocks) from a file, useful for getting a sense of large files within a character limit (`max_chars` set during initialization). Each selected block is followed by "..." to indicate potential discontinuity.
    -   `summarize`: Uses a Language Model (LLM) provided during initialization to generate a summary of the file's content. It internally uses the `random_chunks` method to select a substantial portion of the file for summarization.
-   **Configurable Defaults at Initialization**: The tool is initialized with settings for file path, retrieval mode, character limits, line ranges, and LLM instance. Only the `file_path` can be overridden when the `run` method is called. The tool's description dynamically updates to reflect the configured defaults.
-   **UTF-8 Encoding**: Reads files with UTF-8 encoding and ignores errors.
-   **Intelligent Truncation**: For modes like `head` and `random_chunks`, if the file's total content is smaller than the `max_chars` set during initialization, the full content is returned without truncation.
-   **Error Handling**: Raises appropriate Python exceptions for issues like file not found, permission errors, invalid line numbers, missing required initialization parameters (like `max_chars` or `llm` for specific modes), or problems during summarization.

## Example Usage

**Full Content Extraction (Default/Compatibility Mode):**

```python
from versatile_file_read_tool import VersatileFileReadTool

file_read_tool = VersatileFileReadTool()

content = file_read_tool.run(
    file_path="/path/to/your/file.txt"
)

print(f"Retrieved {len(content)} chars")
```

**Partial Extraction (Head Truncation Mode):**

```python
from versatile_file_read_tool import VersatileFileReadTool

file_read_tool = VersatileFileReadTool(
    retrieval_mode="head",
    max_chars=13002
)

content = file_read_tool.run(
    file_path="/path/to/your/file.txt"
)

print(f"Retrieved {len(content)} chars")
```

**Partial Extraction (Random Chunking Mode):**

```python
from versatile_file_read_tool import VersatileFileReadTool

file_read_tool = VersatileFileReadTool(
    retrieval_mode="random_chunks",
    max_chars=13321
)

content = file_read_tool.run(
    file_path="/path/to/your/file.txt"
)

print(f"Retrieved {len(content)} chars")
```

**AI-Powered Extraction (Summarization Mode):**

```python
from versatile_file_read_tool import VersatileFileReadTool
from crewai import LLM
import os

os.environ["GEMINI_API_KEY"] = "<YOUR_API_KEY>"

gemini_llm = LLM(
    model="gemini/gemini-2.5-flash-preview-04-17",
    temperature=0.3
)

file_read_tool = VersatileFileReadTool(
    retrieval_mode="summarize",
    llm=gemini_llm
)

content = file_read_tool.run(
    file_path="/path/to/your/file.txt"
)

print(f"Retrieved {len(content)} chars")
print(content)
```

## Arguments

The tool is configured at initialization. Only the `file_path` can be optionally overridden when calling the `run` method.

### Initialization Parameters (`__init__`):
-   `file_path` (Optional[str]): Default path to the file if none is provided to `run`.
-   `retrieval_mode` (Optional[Literal["full", "head", "random_chunks", "summarize"]]): Retrieval strategy to use. Defaults to `"full"`. **This cannot be changed after initialization.**
-   `start_line` (Optional[int]): Default starting line for `"full"` mode (1-indexed). Defaults to 1. **This cannot be changed after initialization.**
-   `line_count` (Optional[int]): Default number of lines to read for `"full"` mode. Defaults to `None` (read to end). **This cannot be changed after initialization.**
-   `max_chars` (Optional[int]): Default maximum characters for `"head"` or `"random_chunks"` modes. Required if using these modes. **This cannot be changed after initialization.**
    -   For `'random_chunks'`, if a value less than 3000 is provided, it will be internally adjusted to 3000.
-   `llm` (Optional[BaseLLM]): An LLM instance (compatible with `crewai.llms.base_llm.BaseLLM`) for `"summarize"` mode. Required if `retrieval_mode` is `"summarize"`. **This cannot be changed after initialization.**
-   `name` (Optional[str]): Custom name for the tool instance.
-   `description` (Optional[str]): Custom base description for the tool instance. Details about configured defaults are appended to this.
-   `**kwargs`: Additional keyword arguments passed to `BaseTool`.

### Runtime `run` Method Parameters (defined in `VersatileFileReadToolSchema`):
-   `file_path` (Optional[str]): Path to the file to read. If provided, overrides the `file_path` set during initialization (if any). Mandatory if no default `file_path` was set during initialization.
-   **Other parameters like `retrieval_mode`, `start_line`, `line_count`, `max_chars`, `llm` cannot be provided or changed at runtime via the `run` method.** The values set during initialization will always be used.

## Error Handling

The tool raises Python exceptions for various error conditions:
-   `ValueError`: For invalid or missing essential parameters during initialization (e.g., `max_chars` when required by the mode, `llm` for summarize mode) or if `file_path` is missing at both initialization and runtime. Also raised if `start_line` is invalid for the file size in `full` mode.
-   `FileNotFoundError`: If the specified `file_path` does not exist.
-   `PermissionError`: If the program lacks permissions to read the file at `file_path`.
-   `RuntimeError`: For unexpected issues during file operations or processing, or if the LLM fails repeatedly during summarization.