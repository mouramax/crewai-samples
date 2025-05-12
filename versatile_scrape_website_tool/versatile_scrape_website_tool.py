import math
import os
import random
import re
from typing import Any, Dict, List, Literal, Optional, Set, Type

import requests
from bs4 import BeautifulSoup
from crewai.llms.base_llm import BaseLLM
from crewai.tools.base_tool import BaseTool
from pydantic import BaseModel, ConfigDict, Field


class VersatileScrapeWebsiteToolSchema(BaseModel):
    """Input for VersatileScrapeWebsiteTool."""

    website_url: Optional[str] = Field(
        default=None,
        description=("Mandatory website canonical URL to scrape."),
    )
    retrieval_mode: Optional[
        Literal["full", "head", "random_chunks", "summarize"]
    ] = Field(
        default=None,
        description=("Strategy for retrieving website content."),
    )
    max_chars: Optional[int] = Field(
        default=None,
        description=(
            "Maximum characters for 'head' or 'random_chunks' modes."
        ),
    )
    llm: Optional[BaseLLM] = Field(
        default=None,
        description=(
            "LLM instance for 'summarize' mode. Must be provided if "
            "'summarize' mode is active."
        ),
    )
    model_config = ConfigDict(arbitrary_types_allowed=True)


class VersatileScrapeWebsiteTool(BaseTool):
    name: str = "Website Scraping Tool"
    description: str = (
        "Scrapes website content with various strategies like full text, head "
        "truncation, random chunks, or summarization."
    )
    args_schema: Type[BaseModel] = VersatileScrapeWebsiteToolSchema

    default_website_url: Optional[str] = None
    default_retrieval_mode: Literal[
        "full", "head", "random_chunks", "summarize"
    ] = "full"
    default_max_chars: Optional[int] = None
    default_llm: Optional[BaseLLM] = None
    cookies: Optional[Dict[str, str]] = None
    headers: Dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
            "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    _RANDOM_CHUNKS_BLOCK_SIZE: int = 1000
    _RANDOM_CHUNKS_MIN_MAX_CHARS: int = 3000
    _SUMMARY_MODE_INTERNAL_MAX_CHARS: int = 34000
    _SUMMARY_MODE_TARGET_LENGTH: int = 6000
    _SUMMARY_PROMPT_TEMPLATE: str = (
        "Provide a concise summary of the following website text, capturing "
        "the main points and key information. The summary should be up to "
        "{target_chars} characters long.\n\nText:\n{context}\n\nSummary:"
    )
    _SUMMARY_MIN_VALID_LENGTH: int = 100

    def __init__(
        self,
        website_url: Optional[str] = None,
        retrieval_mode: Optional[
            Literal["full", "head", "random_chunks", "summarize"]
        ] = None,
        max_chars: Optional[int] = None,
        llm: Optional[BaseLLM] = None,
        cookies: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        if name is not None:
            self.name = name
        if description is not None:
            self.description = description

        if website_url is not None:
            self.default_website_url = website_url
        if retrieval_mode is not None:
            self.default_retrieval_mode = retrieval_mode
        if max_chars is not None:
            self.default_max_chars = max_chars
        if llm is not None:
            self.default_llm = llm

        if headers is not None:
            self.headers = headers

        if cookies is not None:
            if (
                "name" in cookies
                and "value" in cookies
                and isinstance(cookies["name"], str)
                and isinstance(cookies["value"], str)
            ):
                cookie_name = cookies["name"]
                env_var_name = cookies["value"]
                cookie_value = os.getenv(env_var_name)
                if cookie_value:
                    self.cookies = {cookie_name: cookie_value}
                else:
                    # For now, silently ignore if env var not found
                    pass
            elif isinstance(cookies, dict):  # Direct cookies
                self.cookies = cookies

        desc_details_list = []
        if self.default_website_url:
            desc_details_list.append(
                f"Default website: '{self.default_website_url}'."
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
        website_url: Optional[str] = None,
        retrieval_mode: Optional[
            Literal["full", "head", "random_chunks", "summarize"]
        ] = None,
        max_chars: Optional[int] = None,
        llm: Optional[BaseLLM] = None,
    ) -> str:
        eff_url = (
            website_url
            if website_url is not None
            else self.default_website_url
        )
        if eff_url is None:
            raise ValueError("Website canonical URL is required.")

        eff_mode = (
            retrieval_mode
            if retrieval_mode is not None
            else self.default_retrieval_mode
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
            page = requests.get(
                eff_url,
                timeout=15,
                headers=self.headers,
                cookies=self.cookies if self.cookies else {},
            )
            page.raise_for_status()
            page.encoding = page.apparent_encoding  # Better encoding detection
            parsed = BeautifulSoup(page.text, "html.parser")

            text_content = parsed.get_text(" ")
            text_content = re.sub(r"[ \t]+", " ", text_content)
            text_content = re.sub(r"\s+\n\s+", "\n", text_content)
            text_content = text_content.strip()

            if not text_content:  # Empty content after cleaning
                return "No text content found on the website after cleaning."

            if eff_mode == "full":
                return text_content

            # For other modes, check size against max_chars if applicable
            if eff_mode in ["head", "random_chunks"] and eff_mc is not None:
                if len(text_content) <= eff_mc:
                    return text_content  # Return full if under limit

            if eff_mode == "head":
                return self._retrieve_head_content(text_content, eff_mc)  # type: ignore
            elif eff_mode == "random_chunks":
                return self._retrieve_random_chunks_content(text_content, eff_mc)  # type: ignore
            elif eff_mode == "summarize":
                return self._retrieve_summarized_content(
                    text_content,
                    current_llm,  # type: ignore
                )
            else:
                raise ValueError(f"Unknown retrieval mode '{eff_mode}'.")

        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"Error scraping website {eff_url}: {str(e)}"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred while processing {eff_url}: {str(e)}"
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
            raise ValueError("No content extracted from website to summarize.")

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

        raise ValueError(
            "LLM failed to generate a valid summary after 3 attempts "
            "(e.g., summary too short or non-string response)."
        )
