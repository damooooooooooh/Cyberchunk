import re
from typing import List
from uuid import UUID
from rag_builder.chunk.schema import SectionNode
from rag_builder.clean.normalize import normalize_text


def md_to_sections(markdown_text: str, doc_id: UUID, source_uri: str) -> List[SectionNode]:
    """
    Parses Markdown content into SectionNode objects using a state machine.
    Each section contains a heading and ALL content until the next same-level heading.

    - Headings (#, ##, ###...) set the heading level and update section_path
    - Content (paragraphs, lists, code blocks) is aggregated under the current heading
    - Content before first heading becomes "Preamble" section (level 0)
    - Maintains hierarchical section paths
    """
    lines = markdown_text.splitlines()
    sections = []

    # Stack to track heading hierarchy: [(level, heading_text), ...]
    heading_stack = []

    # Current section being built
    current_heading = None
    current_level = 0
    current_path = []
    current_content = []
    preamble_content = []

    locator_counter = 0

    for line in lines:
        # Check if line is a heading
        heading_match = re.match(r'^\s*(#{1,6})\s+(.*)', line)

        if heading_match:
            # Flush previous section if exists
            if current_heading is not None:
                locator_counter += 1
                _flush_section(sections, current_heading, current_level,
                              current_path, current_content, doc_id, source_uri, locator_counter)
                current_content = []
            elif preamble_content or current_content:
                # Flush preamble
                _flush_preamble(sections, preamble_content + current_content,
                               doc_id, source_uri)
                preamble_content = []
                current_content = []

            # Start new section
            hashes, heading_text = heading_match.groups()
            level = len(hashes)
            heading_text = heading_text.strip()

            # Clean markdown artifacts from heading
            # Remove image syntax: ![alt](url) or ![alt](url){style}
            heading_text = re.sub(r'!\[.*?\]\([^)]*\)(\{[^}]*\})?', '', heading_text)
            # Remove inline links: [text](url) -> text
            heading_text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', heading_text)
            # Remove extra whitespace
            heading_text = ' '.join(heading_text.split())
            # Skip headings that are just punctuation or empty
            if not heading_text or heading_text in ['.', '..', '...']:
                continue

            # Update path based on heading hierarchy
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, heading_text))
            current_path = [h[1] for h in heading_stack]

            current_heading = heading_text
            current_level = level

        else:
            # Accumulate content lines
            if line.strip():  # Skip blank lines
                if current_heading is None:
                    preamble_content.append(line)
                else:
                    current_content.append(line)

    # Flush final section
    if current_heading is not None:
        locator_counter += 1
        _flush_section(sections, current_heading, current_level,
                      current_path, current_content, doc_id, source_uri, locator_counter)
    elif preamble_content or current_content:
        _flush_preamble(sections, preamble_content + current_content,
                       doc_id, source_uri)

    return sections


def _flush_section(sections: List[SectionNode], heading: str, level: int,
                   path: List[str], content: List[str], doc_id: UUID,
                   source_uri: str, locator_num: int):
    """Create and append a section with heading and aggregated content."""
    combined = "\n".join(content)
    sections.append(SectionNode(
        doc_id=doc_id,
        heading_text=heading,
        heading_level=level,
        section_path=list(path),
        source_locator=f"md:heading:{locator_num}",
        raw_text=combined,
        clean_text=normalize_text(combined)
    ))


def _flush_preamble(sections: List[SectionNode], content: List[str],
                    doc_id: UUID, source_uri: str):
    """Create and append a preamble section for content before first heading."""
    if not content:
        return
    combined = "\n".join(content)
    sections.append(SectionNode(
        doc_id=doc_id,
        heading_text="Preamble",
        heading_level=0,
        section_path=["Preamble"],
        source_locator="document_start",
        raw_text=combined,
        clean_text=normalize_text(combined)
    ))


if __name__ == "__main__":
    from uuid import UUID

    sample_md = """# Title

Some intro text before any sections.

## Subheading

Content under subheading.

- Bullet one
- Bullet two

### Nested Heading

Nested content here.

## Another Top Level

More content.
"""
    doc = UUID("00000000-0000-0000-0000-000000000000")
    secs = md_to_sections(sample_md, doc, "file.md")

    print(f"Parsed {len(secs)} sections:\n")
    for i, s in enumerate(secs):
        print(f"--- Section {i+1} ---")
        print(f"Heading: {s.heading_text} (Level {s.heading_level})")
        print(f"Path: {s.section_path}")
        print(f"Content length: {len(s.clean_text)} chars")
        print(f"Content preview: {s.clean_text[:100]}...")
        print()
