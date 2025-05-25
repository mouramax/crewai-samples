import math
import random
from typing import List, Literal, Optional, Set, Type

from crewai.llms.base_llm import BaseLLM
from crewai.tools.base_tool import BaseTool
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    model_validator,
)

_TOOL_FILE_RANDOM_CHUNKS_BLOCK_SIZE: int = 1_000
_TOOL_FILE_RANDOM_CHUNKS_MIN_MAX_CHARS: int = 3_000
_TOOL_FILE_SUMMARY_MODE_INTERNAL_MAX_CHARS: int = 34_000
_TOOL_FILE_SUMMARY_MODE_TARGET_LENGTH: int = 6_000
_TOOL_FILE_SUMMARY_MIN_VALID_LENGTH: int = 100

DEFAULT_FILE_SUMMARY_PROMPT_TEMPLATE: str = (
    "Provide a concise summary of the file content below, capturing the "
    "main points and all key information. The summary should be up to "
    f"{_TOOL_FILE_SUMMARY_MODE_TARGET_LENGTH} characters long.\n\n"
    "File content to summarize:\n\n"
)


class VersatileFileReadToolSchema(BaseModel):
    """Input schema for VersatileFileReadTool's run method."""

    file_path: Optional[str] = Field(
        default=None,
        description="Optional full path to the file to read for this run. "
        "If not provided, the tool's default file path (if configured) "
        "will be used.",
    )
    model_config = ConfigDict(extra="ignore")


class VersatileFileReadToolOutput(BaseModel):
    """Standardized output for the VersatileFileReadTool."""

    read_content: Optional[str] = Field(
        default=None,
        description="The read or summarized content from the file.",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="An error message if the file reading process failed.",
    )
    source_file_path: str = Field(
        description="The file path from which content was read or attempted."
    )
    retrieval_mode_used: Literal[
        "full", "head", "random_chunks", "summarize"
    ] = Field(description="The retrieval mode used for this file operation.")
    model_config = ConfigDict(extra="forbid")

    def to_llm_response(self) -> str:
        """Converts the output to a JSON string for the LLM."""
        return self.model_dump_json(exclude_none=True, indent=2)


class VersatileFileReadTool(BaseTool):
    """
    A versatile tool to read file content using various strategies.
    The tool's behavior (like retrieval mode and default file path) is
    configured during its initialization. A file path can also be
    provided at runtime.
    """

    name: str = "Versatile File Reader"
    description: str = (  # This will be dynamically updated
        "Reads file content. Specific behavior depends on "
        "initialization. A file path can be provided by the agent at runtime "
        "to override any default."
    )
    args_schema: Type[BaseModel] = VersatileFileReadToolSchema

    file_path: Optional[str] = Field(
        default=None,
        description=(
            "Default full path to the file to read if not "
            "provided at runtime."
        ),
    )
    retrieval_mode: Literal["full", "head", "random_chunks", "summarize"] = (
        Field(default="full", description="Strategy for retrieving content.")
    )
    start_line: int = Field(
        default=1,
        ge=1,
        description=(
            "Line number to start reading from (1-indexed). "
            "Applicable for 'full' mode."
        ),
    )
    line_count: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "Number of lines to read. Applicable for 'full' mode. "
            "None means read to end of file."
        ),
    )
    max_chars: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "Max characters for 'head' or 'random_chunks' modes. "
            "Also influences input limit for 'summarize' mode context."
        ),
    )
    llm: Optional[BaseLLM] = Field(
        default=None, description="crewai.LLM instance for 'summarize' mode."
    )
    summary_prompt_template: str = Field(
        default=DEFAULT_FILE_SUMMARY_PROMPT_TEMPLATE,
        description=(
            "Prompt template for 'summarize' mode. The file content to be "
            "summarized will be appended to this prompt."
        ),
    )

    _eff_max_chars_for_retrieval: Optional[int] = PrivateAttr(default=None)

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def _init_tool_and_dynamic_description(
        self,
    ) -> "VersatileFileReadTool":
        """
        Validates configuration, resolves internal settings, and
        dynamically builds the tool's description for the LLM.
        """
        if self.retrieval_mode == "summarize":
            if not self.llm:
                raise ValueError(
                    "LLM instance ('llm') is required for 'summarize' mode."
                )
            context_limit = (
                self.max_chars
                if self.max_chars is not None
                else _TOOL_FILE_SUMMARY_MODE_INTERNAL_MAX_CHARS
            )
            self._eff_max_chars_for_retrieval = max(
                context_limit, _TOOL_FILE_RANDOM_CHUNKS_MIN_MAX_CHARS
            )
        elif self.retrieval_mode == "head":
            if self.max_chars is None:
                raise ValueError("'max_chars' is required for 'head' mode.")
            self._eff_max_chars_for_retrieval = self.max_chars
        elif self.retrieval_mode == "random_chunks":
            if self.max_chars is None:
                raise ValueError(
                    "'max_chars' is required for 'random_chunks' mode."
                )
            self._eff_max_chars_for_retrieval = max(
                self.max_chars, _TOOL_FILE_RANDOM_CHUNKS_MIN_MAX_CHARS
            )

        base_desc_intro = (
            f"Reads content from a file using the '{self.retrieval_mode}' "
            "strategy."
        )
        details = []

        if self.file_path:
            details.append(
                f"Default file path configured: '{self.file_path}'. "
                "A different path can be provided at runtime."
            )
        else:
            details.append(
                "No default file path configured; a file path must be "
                "provided at runtime."
            )

        if self.retrieval_mode == "full":
            line_desc = "For 'full' mode: starts reading at line "
            line_desc += f"{self.start_line}."
            if self.line_count is not None:
                line_desc += f" Reads up to {self.line_count} lines."
            else:
                line_desc += " Reads until the end of the file."
            details.append(line_desc)

        if (
            self.retrieval_mode in ["head", "random_chunks"]
            and self._eff_max_chars_for_retrieval is not None
        ):
            details.append(
                f"It's configured to process up to "
                f"{self._eff_max_chars_for_retrieval} characters."
            )
        elif (
            self.retrieval_mode == "summarize"
            and self._eff_max_chars_for_retrieval is not None
        ):
            details.append(
                f"For 'summarize' mode: it will process up to "
                f"{self._eff_max_chars_for_retrieval} characters of file "
                f"content before summarizing. The final summary aims for "
                f"approx. {_TOOL_FILE_SUMMARY_MODE_TARGET_LENGTH} characters."
            )

        if self.retrieval_mode == "summarize":
            if (
                self.summary_prompt_template
                == DEFAULT_FILE_SUMMARY_PROMPT_TEMPLATE
            ):
                details.append("Uses a default summarization prompt.")
            else:
                details.append("Uses a custom summarization prompt.")

        self.description = base_desc_intro
        if details:
            self.description += " " + " ".join(details)
        
        # Rebuild the final description
        self._generate_description()
        
        return self

    def _run(
        self,
        file_path: Optional[str] = None,
    ) -> str:
        """
        Executes the file reading process. Uses runtime file_path if
        provided, otherwise falls back to file_path (if set).
        Returns a JSON string of VersatileFileReadToolOutput.
        """
        eff_fp_candidate = (
            file_path if file_path is not None else self.file_path
        )

        if eff_fp_candidate is None or not eff_fp_candidate.strip():
            output = VersatileFileReadToolOutput(
                error_message="A file path must be provided either during tool "
                "initialization (as file_path) or at runtime.",
                source_file_path=eff_fp_candidate or "No file path provided",
                retrieval_mode_used=self.retrieval_mode,
            )
            return output.to_llm_response()

        # Ensure eff_fp is a non-empty string after this check
        eff_fp = eff_fp_candidate.strip()

        try:
            content_to_return: str
            full_content_for_processing: Optional[str] = None

            if self.retrieval_mode != "full":
                # Handle encoding mismatches gracefully by replacing invalid characters
                with open(eff_fp, "r", encoding="utf-8", errors="replace") as f:
                    full_content_for_processing = f.read()

                if (
                    self.retrieval_mode in ["head", "random_chunks"]
                    and self._eff_max_chars_for_retrieval is not None
                    and len(full_content_for_processing)
                    <= self._eff_max_chars_for_retrieval
                ):
                    output = VersatileFileReadToolOutput(
                        read_content=full_content_for_processing,
                        source_file_path=eff_fp,
                        retrieval_mode_used=self.retrieval_mode,
                    )
                    return output.to_llm_response()

            if self.retrieval_mode == "full":
                content_to_return = self._retrieve_full_content(
                    eff_fp, self.start_line, self.line_count
                )
            elif self.retrieval_mode == "head":
                if full_content_for_processing is None:
                    raise AssertionError(
                        "Internal: content not loaded for head."
                    )
                content_to_return = self._retrieve_head_content(
                    full_content_for_processing,
                    self._eff_max_chars_for_retrieval,  # type: ignore
                )
            elif self.retrieval_mode == "random_chunks":
                if full_content_for_processing is None:
                    raise AssertionError(
                        "Internal: content not loaded for chunks."
                    )
                content_to_return = self._retrieve_random_chunks_content(
                    full_content_for_processing,
                    self._eff_max_chars_for_retrieval,  # type: ignore
                )
            elif self.retrieval_mode == "summarize":
                if full_content_for_processing is None:
                    raise AssertionError(
                        "Internal: content not loaded for summary."
                    )
                content_to_return = self._retrieve_summarized_content(
                    full_content_for_processing,
                )
            else:
                raise AssertionError(
                    f"Invalid retrieval mode: {self.retrieval_mode}"
                )

            output = VersatileFileReadToolOutput(
                read_content=content_to_return,
                source_file_path=eff_fp,
                retrieval_mode_used=self.retrieval_mode,
            )
            return output.to_llm_response()
        except FileNotFoundError:
            output = VersatileFileReadToolOutput(
                error_message=f"File not found at path: {eff_fp}",
                source_file_path=eff_fp,
                retrieval_mode_used=self.retrieval_mode,
            )
        except PermissionError:
            output = VersatileFileReadToolOutput(
                error_message=f"Permission denied for file: {eff_fp}",
                source_file_path=eff_fp,
                retrieval_mode_used=self.retrieval_mode,
            )
        except ValueError as ve:
            output = VersatileFileReadToolOutput(
                error_message=f"Processing error for {eff_fp}: {ve}",
                source_file_path=eff_fp,
                retrieval_mode_used=self.retrieval_mode,
            )
        except Exception as e:
            output = VersatileFileReadToolOutput(
                error_message=f"Unexpected error processing {eff_fp}: {e}",
                source_file_path=eff_fp,
                retrieval_mode_used=self.retrieval_mode,
            )
        return output.to_llm_response()

    def _retrieve_full_content(
        self,
        file_path: str,
        start_line: int,
        line_count: Optional[int]
    ) -> str:
        try:
            # Handle encoding mismatches gracefully by replacing invalid characters
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                if start_line == 1 and line_count is None:
                    return f.read()

                start_idx = start_line - 1
                lines_buffer: List[str] = []
                current_line_num = 0

                for i, line_text in enumerate(f):
                    current_line_num = i + 1
                    if i >= start_idx:
                        if (
                            line_count is None
                            or len(lines_buffer) < line_count
                        ):
                            lines_buffer.append(line_text)
                        else:
                            break

                if (
                    not lines_buffer
                    and start_line > current_line_num
                    and current_line_num > 0
                ):
                    raise ValueError(
                        f"Start line {start_line} exceeds the number of "
                        f"lines ({current_line_num}) in the file."
                    )
                if (
                    not lines_buffer
                    and start_line > 0
                    and current_line_num == 0
                ):
                    if start_line == 1:
                        return ""
                    else:
                        raise ValueError(
                            "File is empty and start line is greater than 1."
                        )
                return "".join(lines_buffer)
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Error reading lines from file {file_path}: {str(e)}"
            ) from e

    def _retrieve_head_content(
        self,
        full_content: str,
        max_chars: int
    ) -> str:
        if len(full_content) <= max_chars:
            return full_content
        return full_content[:max_chars]

    def _retrieve_random_chunks_content(
        self,
        full_content: str,
        eff_max_chars: int
    ) -> str:
        if not full_content:
            return ""
        if len(full_content) <= eff_max_chars:
            return full_content

        block_size = _TOOL_FILE_RANDOM_CHUNKS_BLOCK_SIZE
        num_blocks_select = math.floor(eff_max_chars / block_size)
        if num_blocks_select == 0 and eff_max_chars > 0:
            num_blocks_select = 1

        all_blocks = [
            full_content[i : i + block_size]
            for i in range(0, len(full_content), block_size)
        ]
        if not all_blocks:
            return ""

        if len(all_blocks) <= num_blocks_select:
            return ("...".join(all_blocks))[:eff_max_chars]

        selected_indices: Set[int] = set()
        if num_blocks_select > 0:
            selected_indices.add(0)
        if num_blocks_select > 1 and len(all_blocks) > 1:
            if (len(all_blocks) - 1) != 0:
                selected_indices.add(len(all_blocks) - 1)

        needed_middle = num_blocks_select - len(selected_indices)
        middle_indices = [i for i in range(1, len(all_blocks) - 1)]

        if needed_middle > 0 and middle_indices:
            random.shuffle(middle_indices)
            for i in range(min(needed_middle, len(middle_indices))):
                selected_indices.add(middle_indices[i])

        result_parts = [all_blocks[i] for i in sorted(list(selected_indices))]

        final_str = "...".join(result_parts)
        # Add ellipsis if content was indeed truncated by selection
        if len(all_blocks) > num_blocks_select and num_blocks_select > 0:
            final_str += "..."

        return final_str[:eff_max_chars]

    def _retrieve_summarized_content(
        self,
        full_content: str
    ) -> str:
        llm = self.llm
        context_chars_limit = self._eff_max_chars_for_retrieval

        if llm is None or context_chars_limit is None:
            raise AssertionError("LLM or context limit not set for summarize.")

        context_for_summary = self._retrieve_random_chunks_content(
            full_content, context_chars_limit
        )
        if not context_for_summary.strip():
            raise ValueError("No content extracted from file to summarize.")

        prompt = self.summary_prompt_template + context_for_summary

        raw_summary = ""
        last_exception: Optional[Exception] = None
        for attempt in range(3):  # Up to 3 attempts
            try:
                llm_response = llm.call(prompt)

                if isinstance(llm_response, str):
                    summary = llm_response.strip()

                    if len(summary) >= _TOOL_FILE_SUMMARY_MIN_VALID_LENGTH:
                        return summary[:_TOOL_FILE_SUMMARY_MODE_TARGET_LENGTH]
                    else:
                        raw_summary = summary
                else:  # Non-string response
                    raw_summary = str(llm_response)
            except Exception as e:
                last_exception = e

        # All attempts failed
        error_msg_parts = [
            "LLM failed to generate a valid summary after 3 attempts."
        ]
        if raw_summary:
            error_msg_parts.append(
                f"Last raw output (may be truncated): '{raw_summary[:200]}...'"
            )
        if last_exception:
            error_msg_parts.append(
                f"Last exception: {type(last_exception).__name__} - "
                f"{str(last_exception)}"
            )
        raise ValueError(" ".join(error_msg_parts))