import math
import random
import re
from typing import Dict, Literal, Optional, Set, Type

import requests
from bs4 import BeautifulSoup
from crewai.llms.base_llm import BaseLLM
from crewai.tools.base_tool import BaseTool
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    model_validator,
)

_TOOL_RANDOM_CHUNKS_BLOCK_SIZE: int = 1_000
_TOOL_RANDOM_CHUNKS_MIN_MAX_CHARS: int = 3_000
_TOOL_SUMMARY_MODE_INTERNAL_MAX_CHARS: int = 34_000
_TOOL_SUMMARY_MODE_TARGET_LENGTH: int = 6_000
_TOOL_SUMMARY_MIN_VALID_LENGTH: int = 100

DEFAULT_SUMMARY_PROMPT_TEMPLATE: str = (
    "Provide a concise summary of the website text below, capturing the "
    "main points and all the key information. The summary should be up to "
    f"{_TOOL_SUMMARY_MODE_TARGET_LENGTH} characters long. "
    "Text to summarize:\n\n"
)

DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
        "image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.9"
    ),
    "Accept-Language": "*",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class VersatileScrapeWebsiteToolSchema(BaseModel):
    """Input schema for VersatileScrapeWebsiteTool's run method."""

    website_url: str = Field(
        description=("Mandatory URL of the website to scrape for this run."),
    )
    model_config = ConfigDict(extra="ignore")


class VersatileScraperToolOutput(BaseModel):
    """Standardized output for the VersatileScrapeWebsiteTool."""

    scraped_content: Optional[str] = Field(
        default=None,
        description="The scraped or summarized content from the website.",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="An error message if the scraping process failed.",
    )
    source_url: str = Field(
        description="The URL from which the content was scraped or attempted."
    )
    retrieval_mode_used: Literal[
        "full", "head", "random_chunks", "summarize"
    ] = Field(
        description="The retrieval mode used for this scraping operation."
    )
    model_config = ConfigDict(extra="forbid")

    def to_llm_response(self) -> str:
        """Converts the output to a JSON string for the LLM."""
        return self.model_dump_json(exclude_none=True, indent=2)


class VersatileScrapeWebsiteTool(BaseTool):
    """
    A versatile tool to scrape website content using various strategies.
    The tool's behavior (like retrieval mode) is configured
    during its initialization. A URL must be provided at runtime.
    """

    name: str = "Versatile Website Scraper"
    description: str = (  # This will be dynamically updated
        "Scrapes website content. Specific behavior depends on "
        "initialization. A URL must be provided by the agent at runtime."
    )
    args_schema: Type[BaseModel] = VersatileScrapeWebsiteToolSchema

    retrieval_mode: Literal["full", "head", "random_chunks", "summarize"] = (
        Field(default="full", description="Strategy for retrieving content.")
    )
    max_chars: Optional[int] = Field(
        default=None,
        description=(
            "Max characters for 'head' or 'random_chunks' modes. "
            "Also influences input limit for 'summarize' mode context."
        ),
    )
    llm: Optional[BaseLLM] = Field(
        default=None, description="crewai.LLM instance for 'summarize' mode."
    )
    cookies_config: Optional[Dict[str, str]] = Field(
        default=None, description="Cookies dictionary for HTTP requests."
    )
    request_headers: Dict[str, str] = Field(
        default_factory=lambda: DEFAULT_HEADERS.copy(),
        description="HTTP headers for scraping requests.",
    )
    summary_prompt_template: str = Field(
        default=DEFAULT_SUMMARY_PROMPT_TEMPLATE,
        description=(
            "Prompt template for 'summarize' mode. The text to be "
            "summarized will be appended to this prompt."
        ),
    )

    _resolved_cookies: Optional[Dict[str, str]] = PrivateAttr(default=None)
    _eff_max_chars_for_retrieval: Optional[int] = PrivateAttr(default=None)

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def _init_tool_and_dynamic_description(
        self,
    ) -> "VersatileScrapeWebsiteTool":
        """
        Validates configuration, resolves internal settings, and
        dynamically builds the tool's description for the LLM.
        """
        if self.cookies_config:
            self._resolved_cookies = self.cookies_config

        if self.retrieval_mode == "summarize":
            if not self.llm:
                raise ValueError(
                    "LLM instance ('llm') is required for 'summarize' mode."
                )
            context_limit = (
                self.max_chars
                if self.max_chars is not None
                else _TOOL_SUMMARY_MODE_INTERNAL_MAX_CHARS
            )
            self._eff_max_chars_for_retrieval = max(
                context_limit, _TOOL_RANDOM_CHUNKS_MIN_MAX_CHARS
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
                self.max_chars, _TOOL_RANDOM_CHUNKS_MIN_MAX_CHARS
            )

        base_desc = (
            f"Scrapes content from a website using the "
            f"'{self.retrieval_mode}' strategy. A specific URL must always "
            "be provided by the agent when running this tool."
        )
        details = []
        if (
            self.retrieval_mode in ["head", "random_chunks"]
            and self._eff_max_chars_for_retrieval is not None
        ):
            details.append(
                f"It's configured to process up to "
                f"{self._eff_max_chars_for_retrieval} characters from the "
                "runtime-provided URL."
            )
        elif (
            self.retrieval_mode == "summarize"
            and self._eff_max_chars_for_retrieval is not None
        ):
            details.append(
                f"It will process up to {self._eff_max_chars_for_retrieval} "
                f"characters of website content (from runtime URL) before "
                f"summarizing. The final summary aims for approx. "
                f"{_TOOL_SUMMARY_MODE_TARGET_LENGTH} characters."
            )

        if self.retrieval_mode == "summarize":
            if self.summary_prompt_template == DEFAULT_SUMMARY_PROMPT_TEMPLATE:
                details.append("Uses a default summarization prompt.")
            else:
                details.append("Uses a custom summarization prompt.")

        self.description = base_desc
        if details:
            self.description += " " + " ".join(details)
        
        # Rebuild the final description
        self._generate_description()

        return self

    def _run(
        self,
        website_url: str,
    ) -> str:
        """
        Executes the scraping process based on initialized configuration
        and the mandatory runtime website_url.
        Returns a JSON string of VersatileScraperToolOutput.
        """
        if not website_url.strip():  # Check for empty or whitespace-only URL
            output = VersatileScraperToolOutput(
                error_message="A non-empty website URL must be provided.",
                source_url=website_url or "Invalid (empty URL provided)",
                retrieval_mode_used=self.retrieval_mode,
            )
            return output.to_llm_response()

        try:
            page = requests.get(
                website_url,
                timeout=15,
                headers=self.request_headers,
                cookies=self._resolved_cookies or {},
            )
            page.raise_for_status()
            page.encoding = page.apparent_encoding
            parsed = BeautifulSoup(page.text, "html.parser")

            text_content = parsed.get_text(" ")
            text_content = re.sub(r"[ \t]+", " ", text_content)
            text_content = re.sub(r"\s*\n\s*", "\n", text_content).strip()

            if not text_content:
                output = VersatileScraperToolOutput(
                    scraped_content="No text content found on the website "
                    "after cleaning.",
                    source_url=website_url,
                    retrieval_mode_used=self.retrieval_mode,
                )
                return output.to_llm_response()

            content_to_return: str
            if self.retrieval_mode == "full":
                content_to_return = text_content
            elif self.retrieval_mode == "head":
                content_to_return = self._retrieve_head_content(
                    text_content, self._eff_max_chars_for_retrieval  # type: ignore
                )
            elif self.retrieval_mode == "random_chunks":
                content_to_return = self._retrieve_random_chunks_content(
                    text_content, self._eff_max_chars_for_retrieval  # type: ignore
                )
            elif self.retrieval_mode == "summarize":
                content_to_return = self._retrieve_summarized_content(
                    text_content,
                    self.llm,  # type: ignore
                    self._eff_max_chars_for_retrieval,  # type: ignore
                )
            else:  # Should be unreachable due to Pydantic validation
                raise AssertionError(
                    f"Invalid retrieval mode: {self.retrieval_mode}"
                )

            output = VersatileScraperToolOutput(
                scraped_content=content_to_return,
                source_url=website_url,
                retrieval_mode_used=self.retrieval_mode,
            )
            return output.to_llm_response()
        except requests.exceptions.RequestException as e:
            output = VersatileScraperToolOutput(
                error_message=f"HTTP error scraping {website_url}: {e}",
                source_url=website_url,
                retrieval_mode_used=self.retrieval_mode,
            )
        except ValueError as e:  # For issues like failed summary
            output = VersatileScraperToolOutput(
                error_message=f"Processing error for {website_url}: {e}",
                source_url=website_url,
                retrieval_mode_used=self.retrieval_mode,
            )
        except Exception as e:  # Catch-all for unexpected errors
            output = VersatileScraperToolOutput(
                error_message=f"Unexpected error processing {website_url}: {e}",
                source_url=website_url,
                retrieval_mode_used=self.retrieval_mode,
            )
        return output.to_llm_response()

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
            return full_content  # Already within limit

        block_size = _TOOL_RANDOM_CHUNKS_BLOCK_SIZE
        num_blocks_select = math.floor(eff_max_chars / block_size)
        if num_blocks_select == 0 and eff_max_chars > 0:
            num_blocks_select = 1  # Ensure at least one block selected

        all_blocks = [
            full_content[i : i + block_size]
            for i in range(0, len(full_content), block_size)
        ]
        if not all_blocks:
            return ""

        if len(all_blocks) <= num_blocks_select:
            # Not enough blocks to warrant complex selection, join and truncate
            return ("...".join(all_blocks))[:eff_max_chars]

        selected_indices: Set[int] = set()
        if num_blocks_select > 0:
            selected_indices.add(0)  # First block
        if num_blocks_select > 1 and len(all_blocks) > 1:
            # Add last block if distinct from first
            if (len(all_blocks) - 1) != 0:
                selected_indices.add(len(all_blocks) - 1)

        needed_middle = num_blocks_select - len(selected_indices)
        # Potential middle blocks
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
        full_content: str,
        llm: BaseLLM,
        context_chars_limit: int
    ) -> str:
        context = self._retrieve_random_chunks_content(
            full_content, context_chars_limit
        )
        if not context.strip():
            raise ValueError("No content extracted from website to summarize.")

        prompt = self.summary_prompt_template + "\n" + context
        raw_summary = ""
        last_exc: Optional[Exception] = None

        for _ in range(3):  # Up to 3 attempts
            try:
                llm_response = llm.call(prompt)

                if isinstance(llm_response, str):
                    summary = llm_response.strip()

                    if len(summary) >= _TOOL_SUMMARY_MIN_VALID_LENGTH:
                        return summary[:_TOOL_SUMMARY_MODE_TARGET_LENGTH]
                    else:
                        raw_summary = summary  # Store if too short
                else:  # Non-string response
                    raw_summary = str(llm_response)
            except Exception as e:
                last_exc = e

        # All attempts failed
        error_msg = (
            "LLM failed to generate a valid summary after 3 attempts. "
            f"Last raw output (truncated): '{raw_summary[:200]}...'"
        )
        if last_exc:
            error_msg += (
                f" Last exception: {type(last_exc).__name__} - {str(last_exc)}"
            )
        raise ValueError(error_msg)
