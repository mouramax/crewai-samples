# VersatileFileReadTool

## Description

The `VersatileFileReadTool` is a powerful and flexible tool, offering flexible and powerful ways to read and process content from files. It expands upon basic file reading by introducing multiple retrieval strategies, including full content extraction, partial reads based on character limits (head truncation), intelligent chunking for large files (random chunks), and AI-powered summarization.

This tool is invaluable for tasks requiring interaction with file data, such as:
-   Processing text files for information extraction.
-   Handling large configuration files or log files by sampling relevant parts.
-   Feeding file content to AI agents in manageable or summarized forms.
-   Importing data for analysis or further processing.

It supports text-based files and reads them using UTF-8 encoding, with error handling for common file access issues.

## Key Features

-   **Multiple Retrieval Modes**:
    -   `full`: Reads the entire file or a specified range of lines (using `start_line` and `line_count`).
    -   `head`: Reads the first `N` characters of a file (using `max_chars`).
    -   `random_chunks`: Extracts a strategic selection of blocks (first, last, and random middle blocks) from a file, useful for getting a sense of large files within a character limit (`max_chars`). Each selected block is followed by "..." to indicate potential discontinuity.
    -   `summarize`: Uses a provided Language Model (LLM) to generate a summary of the file's content. It internally uses the `random_chunks` method to select a substantial portion of the file for summarization.
-   **Configurable Defaults**: The tool can be initialized with default settings for file path, retrieval mode, character limits, and LLM instance, which can be overridden at runtime.
-   **UTF-8 Encoding**: Enforces reading files with UTF-8 encoding and includes an option to ignore encoding errors.
-   **Intelligent Truncation**: For modes like `head` and `random_chunks`, if the file's total content is smaller than the specified `max_chars`, the full content is returned without truncation.
-   **Error Handling**: Provides clear error messages for issues like file not found, permission errors, or problems during summarization.

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
    file_path="dracula_by_bram_stoker.txt"
)

print(f"Retrieved {len(content)} chars")
print(content)
```

## Arguments

The tool can be configured at initialization and its behavior further refined by arguments passed to the `run` method. Runtime arguments override initialization defaults.

### Initialization Parameters:
-   `file_path` (Optional[str]): Default path to the file.
-   `retrieval_mode` (Optional[Literal["full", "head", "random_chunks", "summarize"]]): Default retrieval strategy. Defaults to `"full"`.
-   `start_line` (Optional[int]): Default starting line for `"full"` mode (1-indexed). Defaults to 1.
-   `line_count` (Optional[int]): Default number of lines to read for `"full"` mode. Defaults to `None` (read to end).
-   `max_chars` (Optional[int]): Default maximum characters for `"head"` or `"random_chunks"` modes.
-   `llm` (Optional[BaseLLM]): Default LLM instance for `"summarize"` mode.
-   `name` (Optional[str]): Custom name for the tool instance.
-   `description` (Optional[str]): Custom description for the tool instance.

### Runtime `run` Method Parameters (defined in `VersatileFileReadToolSchema`):
-   `file_path` (Optional[str]): Path to the file. If provided, overrides the initialized `default_file_path`. Mandatory if no default is set.
-   `retrieval_mode` (Optional[Literal["full", "head", "random_chunks", "summarize"]]): The retrieval strategy to use for this specific run. Overrides `default_retrieval_mode`.
-   `start_line` (Optional[int]): Line number to start reading from (1-indexed). Primarily used in `'full'` mode.
-   `line_count` (Optional[int]): Number of lines to read. Primarily used in `'full'` mode. If `None`, reads from `start_line` to the end of the file.
-   `max_chars` (Optional[int]): Maximum characters for `'head'` or `'random_chunks'` modes.
    -   For `'random_chunks'`, if a value less than 3000 is provided, it will be internally adjusted to 3000.
-   `llm` (Optional[BaseLLM]): An LLM instance for `'summarize'` mode. Required if `retrieval_mode` is `'summarize'` and no `default_llm` was set at initialization.

## Error Handling

The tool returns descriptive error messages as strings if:
-   The specified file is not found.
-   There are permission issues accessing the file.
-   Required parameters for a chosen mode are missing (e.g., `max_chars` for `head` mode, `llm` for `summarize` mode).
-   The LLM fails to generate a valid summary after multiple attempts in `summarize` mode.
-   `start_line` is out of bounds in `full` mode.