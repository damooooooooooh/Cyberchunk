"""
Synonym expansion for cybersecurity terminology.

Adds synonyms and alternate forms to extracted keywords.
"""

import json
from typing import List, Dict, Any


def expand_keywords_with_synonyms(
    text: str,
    current_keywords: List[str],
    llm_client,
    max_keywords: int = 20
) -> List[str]:
    """
    Use LLM to add synonyms and alternate forms to keywords.

    Args:
        text: Original chunk text (for context)
        current_keywords: Existing keywords
        llm_client: LLM client for API calls
        max_keywords: Maximum number of keywords to return

    Returns:
        Enhanced keywords including original + synonyms + variants
    """
    if not current_keywords:
        return []

    prompt = f"""You are a cybersecurity terminology expert.

Given these extracted keywords, add standard terminology variants and synonyms.

Text context: {text[:500]}...

Current keywords: {json.dumps(current_keywords)}

Add:
- Acronym expansions (e.g., "XSS" → add "Cross-Site Scripting")
- Full forms (e.g., "Cross-Site Scripting" → add "XSS")
- Common synonyms (e.g., "hacker" → add "threat actor", "attacker")
- Related CWE/CAPEC if mentioned in text

Use standard NIST/OWASP terminology when available.

Return ONLY a JSON array with enhanced keywords (max {max_keywords}).

Example:
Input: ["XSS", "hackers"]
Output: ["XSS", "Cross-Site Scripting", "hackers", "threat actor", "attacker"]
"""

    try:
        # Call LLM
        response = llm_client.generate_text(prompt, temperature=0.3, max_tokens=500)

        # Parse JSON response
        enhanced = _parse_json_response(response)

        if not enhanced:
            # Fallback to original keywords
            return current_keywords

        # Validate and limit
        enhanced = [kw for kw in enhanced if kw and isinstance(kw, str)]
        enhanced = enhanced[:max_keywords]

        return enhanced

    except Exception as e:
        print(f"    Warning: Failed to expand synonyms: {e}")
        return current_keywords


def _parse_json_response(response: str) -> List[str]:
    """
    Parse LLM JSON response, handling markdown code blocks.

    Args:
        response: Raw LLM response text

    Returns:
        Parsed list of keywords
    """
    # Handle markdown code blocks
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        response = response.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(response)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "keywords" in result:
            return result["keywords"]
        else:
            return []
    except json.JSONDecodeError:
        return []


def batch_expand_synonyms(
    chunks: List[Dict[str, Any]],
    llm_client,
    batch_size: int = 10
) -> Dict[str, List[str]]:
    """
    Expand synonyms for multiple chunks in batches.

    Args:
        chunks: List of chunk dicts with 'chunk_id', 'text', 'keywords'
        llm_client: LLM client
        batch_size: Number of chunks to process at once

    Returns:
        Dictionary mapping chunk_id to enhanced keywords
    """
    results = {}

    for chunk in chunks:
        chunk_id = chunk['chunk_id']
        text = chunk.get('text', '')
        keywords = chunk.get('keywords', [])

        enhanced = expand_keywords_with_synonyms(text, keywords, llm_client)
        results[chunk_id] = enhanced

    return results
