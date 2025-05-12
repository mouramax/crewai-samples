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
        description=("Full path to the file to read."),
    )
    retrieval_mode: Optional[
        Literal["full", "head", "random_chunks", "summarize"]
    ] = Field(
        default=None,
        description=("Strategy for retrieving file content."),
    )
    start_line: Optional[int] = Field(
        default=None,
        description=(
            "Line number to start reading from (1-indexed). Primarily "
            "used in 'full' mode."
        ),
    )
    line_count: Optional[int] = Field(
        default=None,
        description=(
            "Number of lines to read. Primarily used in 'full' mode."
        ),
    )
    max_chars: Optional[int] = Field(
        default=None,
        description=(
            "Maximum characters for 'head' or 'random_chunks' modes."
        ),
    )
    llm: Optional[BaseTool] = Field(
        default=None,
        description=(
            "LLM instance for 'summarize' mode. Must be provided if "
            "'summarize' mode is active."
        ),
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

        if file_path is not None:
            self.default_file_path = file_path
        if retrieval_mode is not None:
            self.default_retrieval_mode = retrieval_mode
        if start_line is not None:
            self.default_start_line = start_line

        self.default_line_count = line_count

        if max_chars is not None:
            self.default_max_chars = max_chars
        if llm is not None:
            self.default_llm = llm

        desc_details_list = []
        if self.default_file_path:
            desc_details_list.append(
                f"Default file: '{self.default_file_path}'."
            )

        desc_details_list.append(
            f"Default mode: '{self.default_retrieval_mode}'."
        )

        if (
            self.default_retrieval_mode in ["head", "random_chunks"]
            and self.default_max_chars is not None
        ):
            desc_details_list.append(
                f"Default 'max_chars': {self.default_max_chars}."
            )

        if self.default_retrieval_mode == "summarize":
            if self.default_llm:
                desc_details_list.append(
                    "Configured for summarization with a default LLM."
                )
            else:
                desc_details_list.append(
                    "For 'summarize' mode, an LLM must be provided at "
                    "runtime if no default is set."
                )

        desc_suffix = ""
        if desc_details_list:
            desc_suffix = " " + " ".join(desc_details_list)

        self.description = f"{self.description}{desc_suffix}"

    def _run(
        self,
        file_path: Optional[str] = None,
        retrieval_mode: Optional[
            Literal["full", "head", "random_chunks", "summarize"]
        ] = None,
        start_line: Optional[int] = None,
        line_count: Optional[int] = None,
        max_chars: Optional[int] = None,
        llm: Optional[BaseLLM] = None,
    ) -> str:
        eff_fp = file_path if file_path is not None else self.default_file_path
        if eff_fp is None:
            raise ValueError("File path is required.")

        eff_mode = (
            retrieval_mode
            if retrieval_mode is not None
            else self.default_retrieval_mode
        )
        eff_sl = (
            start_line if start_line is not None else self.default_start_line
        )
        eff_lc = (
            line_count if line_count is not None else self.default_line_count
        )
        eff_mc = max_chars if max_chars is not None else self.default_max_chars

        current_llm = llm
        if not isinstance(current_llm, BaseLLM) and self.default_llm:
            current_llm = self.default_llm

        if eff_mode == "head" and eff_mc is None:
            raise ValueError("'max_chars' is required for 'head' mode.")
        if eff_mode == "random_chunks":
            if eff_mc is None:
                raise ValueError(
                    "'max_chars' is required for 'random_chunks' mode."
                )
            eff_mc = max(eff_mc, self._RANDOM_CHUNKS_MIN_MAX_CHARS)
        if eff_mode == "summarize" and not isinstance(current_llm, BaseLLM):
            raise ValueError(
                "A valid LLM instance is required for 'summarize' mode."
            )

        try:
            full_content: Optional[str] = None
            if eff_mode != "full":
                with open(eff_fp, "r", encoding="utf-8", errors="ignore") as f:
                    full_content = f.read()

                if (
                    eff_mode in ["head", "random_chunks"]
                    and eff_mc is not None
                ):
                    if len(full_content) <= eff_mc:
                        return full_content

            if eff_mode == "full":
                return self._retrieve_full_content(eff_fp, eff_sl, eff_lc)

            if full_content is None:
                raise RuntimeError(
                    "Internal error: file content not loaded for processing."
                )

            if eff_mode == "head":
                return self._retrieve_head_content(full_content, eff_mc)  # type: ignore
            elif eff_mode == "random_chunks":
                return self._retrieve_random_chunks_content(full_content, eff_mc)  # type: ignore
            elif eff_mode == "summarize":
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
        except Exception as e:
            # Catch-all for other unexpected errors during file ops
            raise RuntimeError(
                f"Error during file operation for {eff_fp}: {str(e)}"
            ) from e

    def _retrieve_full_content(
        self, file_path: str, start_line: int, line_count: Optional[int]
    ) -> str:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                if start_line == 1 and line_count is None:
                    return f.read()

                start_idx = max(start_line - 1, 0)
                lines_buffer: List[str] = []
                for i, line_text in enumerate(f):
                    if i >= start_idx:
                        if (
                            line_count is None
                            or len(lines_buffer) < line_count
                        ):
                            lines_buffer.append(line_text)
                        else:
                            break

                if not lines_buffer and start_idx > 0:
                    raise ValueError(
                        f"Start line {start_line} exceeds the number of "
                        f"lines in the file."
                    )
                return "".join(lines_buffer)
        except ValueError:  # Re-raise ValueError specifically
            raise
        except Exception as e:
            raise RuntimeError(
                f"Error in _retrieve_full_content for {file_path}: {str(e)}"
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

        if len(all_blocks) <= num_blocks_to_select:
            return "...".join(all_blocks) + (
                "..." if len(all_blocks) > 0 else ""
            )

        selected_indices: Set[int] = set()
        selected_indices.add(0)

        if num_blocks_to_select > 1 and len(all_blocks) > 1:
            selected_indices.add(len(all_blocks) - 1)

        needed_middle_blocks = num_blocks_to_select - len(selected_indices)

        middle_block_indices = [i for i in range(1, len(all_blocks) - 1)]

        if needed_middle_blocks > 0 and middle_block_indices:
            random.shuffle(middle_block_indices)
            for i in range(
                min(needed_middle_blocks, len(middle_block_indices))
            ):
                selected_indices.add(middle_block_indices[i])

        result_parts: List[str] = []
        for block_idx in sorted(list(selected_indices)):
            result_parts.append(all_blocks[block_idx])

        return "...".join(result_parts) + (
            "..."
            if len(result_parts) > 1 and len(all_blocks) > num_blocks_to_select
            else ""
        )

    def _retrieve_summarized_content(
        self, full_content: str, llm: BaseLLM
    ) -> str:
        context_for_summary = self._retrieve_random_chunks_content(
            full_content, self._SUMMARY_MODE_INTERNAL_MAX_CHARS
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
                    if len(summary) >= self._SUMMARY_MIN_VALID_LENGTH:
                        return summary[: self._SUMMARY_MODE_TARGET_LENGTH]
            except Exception as e:
                last_exception = e
                if attempt == 2:
                    raise RuntimeError(
                        "LLM call failed after 3 attempts."
                    ) from last_exception

        # If loop finishes without returning or raising from LLM error
        raise ValueError(
            "LLM failed to generate a valid summary after 3 attempts "
            "(e.g., summary too short or non-string response)."
        )
