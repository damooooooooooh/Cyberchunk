import re
import html
import unicodedata
from typing import List, Optional


def strip_whitespace(text: str) -> str:
    """Strips leading/trailing whitespace and collapses internal whitespace."""
    # Preserve paragraph breaks lightly by first normalizing newlines
    text = re.sub(r'\r\n?', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)  # cap empty lines
    return re.sub(r'[ \t]+', ' ', text).strip()


def remove_boilerplate(text: str, boilerplate_patterns: Optional[List[str]] = None) -> str:
    """
    Removes common boilerplate text using regex patterns.
    Patterns should be simple strings or regex.
    """
    if boilerplate_patterns is None:
        boilerplate_patterns = [
            r"Copyright \d{4}.*$",
            r"All rights reserved.*$",
            r"[\s*\[\s*edit\s*]\s*]$",
            r"Skip to content",
            r"Table of Contents",
            r"Related Articles",
            r"References",
            r"Footnotes",
            r"Further Reading",
            r"Privacy Policy",
            r"Terms of Service",
            r"Cookie Policy",
            r"Subscribe to our newsletter",
            r"Share this article",
            r"Comments",
            r"Disclaimer:",
            r"Contact Us",
            r"(\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{2,4})",
            r"(\s+-\s+\d+\s+of\s+\d+)",
            r"(\s+page\s+\d+)",
            r"\(\s*\[\s*edit\s*]\s*\)",
        ]

    cleaned_text = text
    for pattern in boilerplate_patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
    return cleaned_text


def remove_control_chars(text: str) -> str:
    """Strip control characters that can confuse tokenizers/LLMs."""
    return ''.join(ch for ch in text if unicodedata.category(ch)[0] != 'C' or ch in ('\n', '\t'))


def normalize_text(text: str, boilerplate_patterns: Optional[List[str]] = None) -> str:
    """
    Combines cleaning and normalization steps for LLM-friendly text:
    - Unicode normalize (NFKC)
    - HTML unescape
    - Remove control chars
    - Drop common boilerplate
    - Collapse whitespace while keeping light paragraph structure
    """
    text = unicodedata.normalize("NFKC", text)
    text = html.unescape(text)
    text = remove_control_chars(text)
    text = remove_boilerplate(text, boilerplate_patterns)
    text = strip_whitespace(text)
    return text


if __name__ == '__main__':
    sample_text = """
    <h1>Introduction</h1>
    <p>   This is a sample text.   </p>
    <p>With multiple    spaces and new lines.</p>
    <footer>
        Copyright 2023. All rights reserved.
        <a href="#">Privacy Policy</a>
    </footer>
    [ [ edit ] ]
    Some other content. Page 1 of 10.
    """

    print("Original:\n", sample_text)

    normalized = normalize_text(sample_text)
    print("\nNormalized:\n", normalized)

    custom_boilerplate = [r"footer.*$", r"sample"]
    normalized_custom = normalize_text(sample_text, custom_boilerplate)
    print("\nNormalized with custom boilerplate:\n", normalized_custom)
