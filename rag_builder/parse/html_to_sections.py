from bs4 import BeautifulSoup, Tag, Comment
from typing import List, Optional
from uuid import UUID
from rag_builder.chunk.schema import SectionNode
from rag_builder.clean.normalize import normalize_text
import re


class ContentNode:
    """Intermediate tree structure for building hierarchical sections."""

    def __init__(self, node_type: str, level: int = 0, text: str = "", element_id: str = ""):
        self.type = node_type  # "heading", "content", "container"
        self.level = level  # 0 for container/content, 1-6 for headings
        self.text = text
        self.element_id = element_id
        self.children: List['ContentNode'] = []
        self.parent: Optional['ContentNode'] = None

    def add_child(self, child: 'ContentNode'):
        """Add a child node and set its parent."""
        child.parent = self
        self.children.append(child)


def get_heading_level(tag_name: str) -> int:
    """Extracts heading level from tag name (e.g., h1 -> 1)."""
    match = re.match(r'h(\d)', tag_name.lower())
    if match:
        return int(match.group(1))
    return 0  # Not a heading


def _strip_non_content(soup: BeautifulSoup) -> None:
    """Remove script/style/iframes/ads/nav/footer/header to keep core content."""
    # Remove non-content tags
    for tag in soup(['script', 'style', 'noscript', 'iframe', 'svg', 'canvas',
                     'form', 'button', 'input', 'select', 'option']):
        tag.decompose()

    # Remove structural/navigation elements
    for tag in soup.find_all(['header', 'footer', 'nav', 'aside']):
        tag.decompose()

    # Drop comments
    for c in soup.find_all(string=lambda text: isinstance(text, Comment)):
        c.extract()


def _build_content_tree(soup: BeautifulSoup) -> ContentNode:
    """
    Build hierarchical tree of headings and content from HTML.
    Returns root container node with all content organized hierarchically.
    """
    root = ContentNode(node_type="container", level=0)
    heading_stack = [root]  # Stack to track current position in hierarchy

    # Find all relevant content elements
    for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                   'p', 'ul', 'ol', 'pre', 'blockquote', 'div']):
        # Get text content
        text = element.get_text(separator=" ", strip=True)
        if not text:
            continue

        # Get element ID for source locator
        element_id = element.get('id', '')

        if element.name.startswith('h') and len(element.name) == 2:
            # This is a heading
            level = get_heading_level(element.name)
            if level > 0:
                # Pop stack until we find appropriate parent level
                while len(heading_stack) > 1 and heading_stack[-1].level >= level:
                    heading_stack.pop()

                # Create heading node
                heading_node = ContentNode(
                    node_type="heading",
                    level=level,
                    text=text,
                    element_id=element_id
                )
                heading_stack[-1].add_child(heading_node)
                heading_stack.append(heading_node)

        elif element.name in ['p', 'ul', 'ol', 'pre', 'blockquote']:
            # Content element - add to current heading
            content_node = ContentNode(
                node_type="content",
                level=0,
                text=text,
                element_id=element_id
            )
            heading_stack[-1].add_child(content_node)

        elif element.name == 'div':
            # Only include divs that don't look like navigation/layout
            # Skip divs with navigation-related classes/ids
            skip_patterns = ['nav', 'menu', 'sidebar', 'footer', 'header',
                             'ad', 'banner', 'social', 'share']
            elem_class = ' '.join(element.get('class', [])).lower()
            elem_id = element.get('id', '').lower()

            should_skip = any(pattern in elem_class or pattern in elem_id
                             for pattern in skip_patterns)

            if not should_skip and text:
                content_node = ContentNode(
                    node_type="content",
                    level=0,
                    text=text,
                    element_id=element_id
                )
                heading_stack[-1].add_child(content_node)

    return root


def _flatten_tree_to_sections(node: ContentNode, doc_id: UUID, source_uri: str,
                               current_path: List[str] = None,
                               locator_counter: List[int] = None) -> List[SectionNode]:
    """
    Convert tree to flat list of well-formed sections.
    Each section contains a heading and all its direct content (not sub-headings).
    """
    if current_path is None:
        current_path = []
    if locator_counter is None:
        locator_counter = [0]  # Use list to make it mutable across recursion

    sections = []

    if node.type == "heading":
        # Build section from this heading
        new_path = current_path + [node.text]
        locator_counter[0] += 1

        # Collect all direct content (not sub-headings)
        content_parts = []
        sub_headings = []

        for child in node.children:
            if child.type == "content":
                content_parts.append(child.text)
            elif child.type == "heading":
                sub_headings.append(child)

        # Create section with aggregated content
        combined_content = "\n\n".join(content_parts)

        # Build source locator
        if node.element_id:
            source_locator = f"#{node.element_id}"
        else:
            source_locator = f"h{node.level}:{locator_counter[0]}"

        sections.append(SectionNode(
            doc_id=doc_id,
            heading_text=node.text,
            heading_level=node.level,
            section_path=list(new_path),
            source_locator=source_locator,
            raw_text=combined_content,
            clean_text=normalize_text(combined_content)
        ))

        # Recursively process sub-headings
        for sub in sub_headings:
            sections.extend(_flatten_tree_to_sections(sub, doc_id, source_uri, new_path, locator_counter))

    elif node.type == "container":
        # Handle preamble (content before first heading)
        preamble_parts = []
        top_headings = []

        for child in node.children:
            if child.type == "content":
                preamble_parts.append(child.text)
            elif child.type == "heading":
                top_headings.append(child)

        # Create preamble section if content exists
        if preamble_parts:
            sections.append(SectionNode(
                doc_id=doc_id,
                heading_text="Preamble",
                heading_level=0,
                section_path=["Preamble"],
                source_locator="document_start",
                raw_text="\n\n".join(preamble_parts),
                clean_text=normalize_text("\n\n".join(preamble_parts))
            ))

        # Process top-level headings
        for heading in top_headings:
            sections.extend(_flatten_tree_to_sections(heading, doc_id, source_uri, [], locator_counter))

    return sections


def html_to_sections(html_content: str, doc_id: UUID, source_uri: str) -> List[SectionNode]:
    """
    Parses HTML content into a list of SectionNode objects.
    Each section contains a heading and ALL content until the next same-level heading.

    Algorithm:
    1. Strip non-content elements (nav, footer, scripts, etc.)
    2. Build hierarchical tree of headings and content
    3. Flatten tree to sections, aggregating content under each heading
    4. Handle preamble (content before first heading)
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    _strip_non_content(soup)

    # Phase 1: Build tree
    tree_root = _build_content_tree(soup)

    # Phase 2: Flatten to sections
    sections = _flatten_tree_to_sections(tree_root, doc_id, source_uri)

    return sections


if __name__ == '__main__':
    from uuid import UUID

    # Example usage
    sample_html = """
    <html>
    <head><title>Test Document</title></head>
    <body>
        <nav>Skip this navigation</nav>

        <p>This is preamble content before any headings.</p>

        <h1 id="intro">Introduction</h1>
        <p>This is an introductory paragraph about cybersecurity.</p>
        <p>Another paragraph in the introduction.</p>

        <h2 id="risk_types">Types of Risks</h2>
        <p>Here are some common risks:</p>
        <ul>
            <li>SQL Injection</li>
            <li>Cross-Site Scripting</li>
        </ul>

        <h3>Detailed Risk 1</h3>
        <p>More details on SQL Injection.</p>

        <h3>Detailed Risk 2</h3>
        <p>More details on XSS.</p>

        <h2>Mitigations</h2>
        <p>How to prevent these risks.</p>

        <div class="footer">This is the footer and should be ignored.</div>
    </body>
    </html>
    """
    test_doc_id = UUID('a1b2c3d4-e5f6-7890-1234-567890abcdef')
    test_source_uri = "http://example.com/test_doc"

    parsed_sections = html_to_sections(sample_html, test_doc_id, test_source_uri)

    print(f"Parsed {len(parsed_sections)} sections:\n")
    for i, section in enumerate(parsed_sections):
        print(f"--- Section {i+1} ---")
        print(f"Heading: {section.heading_text} (Level {section.heading_level})")
        print(f"Path: {section.section_path}")
        print(f"Locator: {section.source_locator}")
        print(f"Content length: {len(section.clean_text)} chars")
        print(f"Content preview: {section.clean_text[:100]}...")
        print()
