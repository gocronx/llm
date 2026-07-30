"""Observable external state used by the demo tools."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolWorld:
    """In-memory stand-in for file, upload, link, and email systems."""

    files: dict[str, str] = field(default_factory=dict)
    uploaded: set[str] = field(default_factory=set)
    links: dict[str, str] = field(default_factory=dict)
    sent_emails: list[str] = field(default_factory=list)

    def observable_state(self) -> dict[str, list[str]]:
        """Return a deterministic representation of externally visible state."""
        return {
            "existing_files": sorted(self.files),
            "uploaded_files": sorted(self.uploaded),
            "linked_files": sorted(self.links),
            "sent_emails": sorted(self.sent_emails),
        }
