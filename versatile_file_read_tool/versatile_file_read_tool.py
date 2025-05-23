import math
import random
from typing import Any, List, Literal, Optional, Set, Type

from crewai.llms.base_llm import BaseLLM
from crewai.tools.base_tool import BaseTool
from pydantic import BaseModel, ConfigDict, Field


class VersatileFileReadToolSchema(BaseModel):
    """Input for VersatileFileReadTool."""

    file_path: Optional[str] = Field(
        default=None,
        description=("Mandatory full path to the file to read."),
    )
    model_config = ConfigDict(arbitrary_types_allowed=True)


class VersatileFileReadTool(BaseTool):
    name: str = "File Reading Tool"
    description: str = (
        "Reads file content with various strategies like full read, head "
        "truncation, random chunks, or summarization."
    )
    args_schema: Type[BaseModel] = VersatileFileReadToolSchema

    default_file_path: Optional[str] = None
    default_retrieval_mode: Literal[
        "full", "head", "random_chunks", "summarize"
    ] = "full"
    default_start_line: int = 1
    default_line_count: Optional[int] = None
    default_max_chars: Optional[int] = None
    default_llm: Optional[BaseLLM] = None

    _RANDOM_CHUNKS_BLOCK_SIZE: int = 1000
    _RANDOM_CHUNKS_MIN_MAX_CHARS: int = 3000
    _SUMMARY_MODE_INTERNAL_MAX_CHARS: int = 34000
    _SUMMARY_MODE_TARGET_LENGTH: int = 6000
    _SUMMARY_PROMPT_TEMPLATE: str = (
        "Provide a concise summary of the following text, capturing the "
        "main points and key information. The summary should be up to "
        "{target_chars} characters long.\n\nText:\n{context}\n\nSummary:"
    )
    _SUMMARY_MIN_VALID_LENGTH: int = 100

    def __init__(
        self,
        file_path: Optional[str] = None,
        retrieval_mode: Optional[
            Literal["full", "head", "random_chunks", "summarize"]
        ] = None,
        start_line: Optional[int] = None,
        line_count: Optional[int] = None,
        max_chars: Optional[int] = None,
        llm: Optional[BaseLLM] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        if name is not None:
            self.name = name
        if description is not None:
            self.description = description

        # Store initialization parameters as defaults
        if file_path is not None:
            self.default_file_path = file_path
        if retrieval_mode is not None:
            self.default_retrieval_mode = retrieval_mode
        if start_line is not None:
            # Ensure start_line is at least 1
            self.default_start_line = max(start_line, 1)

        # line_count can be None or positive int
        self.default_line_count = line_count
        if self.default_line_count is not None:
            self.default_line_count = max(self.default_line_count, 1)

        if max_chars is not None:
            self.default_max_chars = max_chars
        if llm is not None:
            self.default_llm = llm

        base_desc = self.description

        desc_details_list = []
        if self.default_file_path:
            desc_details_list.append(
                f"Default file: '{self.default_file_path}'."
            )

        desc_details_list.append(
            f"Configured retrieval mode: '{self.default_retrieval_mode}'."
        )

        if self.default_retrieval_mode == "full":
            line_desc = f"Starts reading at line {self.default_start_line}."
            if self.default_line_count is not None:
                line_desc += f" Reads up to {self.default_line_count} lines."
            else:
                line_desc += " Reads until the end of the file."
            desc_details_list.append(line_desc)

        if (
            self.default_retrieval_mode in ["head", "random_chunks"]
            and self.default_max_chars is not None
        ):
            desc_details_list.append(
                f"Configured 'max_chars': {self.default_max_chars}."
            )
        elif self.default_retrieval_mode in ["head", "random_chunks"]:
            desc_details_list.append(
                f"Warning: Mode '{self.default_retrieval_mode}' selected but "
                "'max_chars' was not set during initialization."
            )

        if self.default_retrieval_mode == "summarize":
            if self.default_llm:
                desc_details_list.append(
                    "Configured for summarization with a provided LLM."
                )
            else:
                desc_details_list.append(
                    "Warning: Mode 'summarize' selected but 'llm' was not "
                    "provided during initialization."
                )

        desc_suffix = ""
        if desc_details_list:
            desc_suffix = " " + " ".join(desc_details_list)

        # Set the final description including details
        self.description = f"{base_desc}{desc_suffix}"

    def _run(
        self,
        file_path: Optional[str] = None,
    ) -> str:
        eff_fp = file_path if file_path is not None else self.default_file_path
        if eff_fp is None:
            raise ValueError(
                "File path is required."
            )

        # Use the parameters set during initialization
        eff_mode = self.default_retrieval_mode
        eff_sl = self.default_start_line
        eff_lc = self.default_line_count
        eff_mc = self.default_max_chars
        current_llm = self.default_llm

        # Validate parameters based on the initialized mode
        if eff_mode == "head" and eff_mc is None:
            raise ValueError(
                "'max_chars' must be set during initialization for 'head' mode."
            )
        if eff_mode == "random_chunks":
            if eff_mc is None:
                raise ValueError(
                    "'max_chars' must be set during initialization for "
                    "'random_chunks' mode."
                )
            # Ensure minimum max_chars for random_chunks internally
            eff_mc = max(eff_mc, self._RANDOM_CHUNKS_MIN_MAX_CHARS)
        if eff_mode == "summarize" and not isinstance(current_llm, BaseLLM):
            raise ValueError(
                "A valid LLM instance must be provided during initialization "
                "for 'summarize' mode."
            )

        try:
            # Read full content only if needed (for head, random_chunks, summarize)
            full_content: Optional[str] = None
            if eff_mode != "full":
                with open(eff_fp, "r", encoding="utf-8", errors="ignore") as f:
                    full_content = f.read()

                # If content is smaller than limit, return full content directly
                if (
                    eff_mode in ["head", "random_chunks"]
                    and eff_mc
                    is not None  # eff_mc is guaranteed non-None here
                ):
                    if len(full_content) <= eff_mc:
                        return full_content

            if eff_mode == "full":
                # Pass initialized line parameters
                return self._retrieve_full_content(eff_fp, eff_sl, eff_lc)

            # Ensure full_content was loaded for non-'full' modes
            if full_content is None:
                # This should ideally not happen if logic above is correct
                raise RuntimeError(
                    "Internal error: file content not loaded for processing "
                    f"in mode '{eff_mode}'."
                )

            if eff_mode == "head":
                # eff_mc is guaranteed non-None here due to prior validation
                return self._retrieve_head_content(full_content, eff_mc)  # type: ignore
            elif eff_mode == "random_chunks":
                # eff_mc is guaranteed non-None and adjusted here
                return self._retrieve_random_chunks_content(full_content, eff_mc)  # type: ignore
            elif eff_mode == "summarize":
                # current_llm is guaranteed valid BaseLLM here
                return self._retrieve_summarized_content(
                    full_content,
                    current_llm,  # type: ignore
                )
            else:
                raise ValueError(f"Unknown retrieval mode '{eff_mode}'.")
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found at path: {eff_fp}")
        except PermissionError:
            raise PermissionError(f"Permission denied for file: {eff_fp}")
        except (
            ValueError
        ) as ve:  # Catch specific ValueErrors from _retrieve_full_content
            raise ve
        except Exception as e:
            # Catch-all for other unexpected errors
            raise RuntimeError(
                f"An unexpected error occurred while processing file {eff_fp} "
                f"in mode '{eff_mode}': {str(e)}"
            ) from e

    def _retrieve_full_content(
        self, file_path: str, start_line: int, line_count: Optional[int]
    ) -> str:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                # Read all if no line constraints
                if start_line == 1 and line_count is None:
                    return f.read()

                start_idx = max(start_line - 1, 0)
                lines_buffer: List[str] = []
                line_num = 0  # Keep track of actual line number read

                for i, line_text in enumerate(f):
                    line_num = i + 1  # Current line number (1-based)
                    if i >= start_idx:
                        if (
                            line_count is None
                            or len(lines_buffer) < line_count
                        ):
                            lines_buffer.append(line_text)
                        else:
                            break  # Reached line_count limit

                # Check if start_line was beyond the actual number of lines
                if not lines_buffer and start_line > line_num and line_num > 0:
                    raise ValueError(
                        f"Start line {start_line} exceeds the number of "
                        f"lines ({line_num}) in the file."
                    )
                # Handle case where file is empty or start_line is 1 but file empty
                if not lines_buffer and start_line > 0 and line_num == 0:
                    if start_line == 1:
                        return ""  # Empty file is valid for start_line 1
                    else:
                        raise ValueError(
                            "File is empty or start line is invalid."
                        )

                return "".join(lines_buffer)
        except ValueError:  # Re-raise specific ValueError
            raise
        except Exception as e:
            # Wrap other potential IOErrors or unexpected issues
            raise RuntimeError(
                f"Error reading lines from file {file_path}: {str(e)}"
            ) from e

    def _retrieve_head_content(self, full_content: str, max_chars: int) -> str:
        return full_content[:max_chars]

    def _retrieve_random_chunks_content(
        self, full_content: str, max_chars: int
    ) -> str:
        if not full_content:
            return ""

        block_size = self._RANDOM_CHUNKS_BLOCK_SIZE
        num_blocks_to_select = math.floor(max_chars / block_size)

        all_blocks = [
            full_content[i : i + block_size]
            for i in range(0, len(full_content), block_size)
        ]
        if not all_blocks:
            return ""

        # Total content fits within adjusted max_chars after chunking
        if len(all_blocks) <= num_blocks_to_select:
            return "".join(
                all_blocks
            )

        selected_indices: Set[int] = set()
        selected_indices.add(0)  # Always include the first block

        # Include the last block if we need more than one block and there is more than one
        if num_blocks_to_select > 1 and len(all_blocks) > 1:
            selected_indices.add(len(all_blocks) - 1)

        needed_middle_blocks = num_blocks_to_select - len(selected_indices)

        # Potential middle block indices (excluding first and last)
        middle_block_indices = [i for i in range(1, len(all_blocks) - 1)]

        if needed_middle_blocks > 0 and middle_block_indices:
            random.shuffle(middle_block_indices)
            # Select the required number of middle blocks, or fewer if not enough available
            for i in range(
                min(needed_middle_blocks, len(middle_block_indices))
            ):
                selected_indices.add(middle_block_indices[i])

        # Build the result string by joining selected blocks with "..."
        result_parts: List[str] = []
        # Ensure blocks are added in their original order
        for block_idx in sorted(list(selected_indices)):
            result_parts.append(all_blocks[block_idx])

        final_separator = "..."
        result = final_separator.join(result_parts)
        if (
            len(all_blocks) > len(selected_indices)
            and len(selected_indices) > 0
        ):
            result += final_separator  # Add trailing "..." if truncated

        return result

    def _retrieve_summarized_content(
        self, full_content: str, llm: BaseLLM
    ) -> str:
        context_max_chars = (
            self.default_max_chars
            if self.default_max_chars is not None
            else self._SUMMARY_MODE_INTERNAL_MAX_CHARS
        )
        # Ensure it meets the minimum for random_chunks if using default_max_chars
        if self.default_max_chars is not None:
            context_max_chars = max(
                context_max_chars, self._RANDOM_CHUNKS_MIN_MAX_CHARS
            )

        context_for_summary = self._retrieve_random_chunks_content(
            full_content, context_max_chars
        )
        if not context_for_summary.strip():
            raise ValueError("No content extracted from file to summarize.")

        prompt = self._SUMMARY_PROMPT_TEMPLATE.format(
            context=context_for_summary,
            target_chars=self._SUMMARY_MODE_TARGET_LENGTH,
        )

        last_exception: Optional[Exception] = None
        for attempt in range(3):
            try:
                raw_summary = llm.call(prompt)
                if isinstance(raw_summary, str):
                    summary = raw_summary.strip()
                    # Ensure summary does not exceed target length
                    if len(summary) >= self._SUMMARY_MIN_VALID_LENGTH:
                        return summary[:self._SUMMARY_MODE_TARGET_LENGTH]
            except Exception as e:
                last_exception = e
                if attempt == 2:  # Last attempt failed
                    raise RuntimeError(
                        "LLM call failed after 3 attempts to generate summary."
                    ) from last_exception

        # If loop finishes without returning (e.g., summary always too short)
        raise ValueError(
            "LLM failed to generate a valid summary meeting criteria "
            f"(e.g., minimum length {self._SUMMARY_MIN_VALID_LENGTH}) "
            "after 3 attempts."
        )