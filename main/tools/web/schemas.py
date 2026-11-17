from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class WebArgs(BaseModel):
    action: Literal["search", "fetch"]
    query: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=2048)
    limit: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def validate_action_input(self):
        if self.action == "search" and not (self.query and self.query.strip()):
            raise ValueError("query is required for web search")
        if self.action == "fetch" and not (self.url and self.url.strip()):
            raise ValueError("url is required to fetch a webpage")
        return self


class BrowserArgs(BaseModel):
    action: Literal["navigate", "snapshot", "click", "type", "screenshot", "execute"]
    url: str | None = Field(default=None, max_length=2048)
    selector: str | None = Field(default=None, max_length=1000)
    text: str | None = Field(default=None, max_length=20_000)
    script: str | None = Field(default=None, max_length=20_000)

    @model_validator(mode="after")
    def validate_action_input(self):
        if self.action == "navigate" and not (self.url and self.url.strip()):
            raise ValueError("url is required for browser navigation")
        if self.action in {"click", "type"} and not (self.selector and self.selector.strip()):
            raise ValueError(f"selector is required for browser {self.action}")
        if self.action == "type" and self.text is None:
            raise ValueError("text is required for browser type")
        if self.action == "execute" and not (self.script and self.script.strip()):
            raise ValueError("script is required for browser execute")
        return self
