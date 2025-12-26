"""
Ask pipeline for full RAG flow.

Combines query analysis, retrieval, and LLM generation.
"""

import os
import json
from typing import Optional, List, Dict, Any
from rag_builder.embeddings import get_embedding_provider
from rag_builder.database import get_db_connection, search_chunks


def analyze_query(question: str, llm_provider: str, llm_model: Optional[str] = None) -> dict:
    """
    Use LLM to analyze query and determine optimal retrieval filters.

    Returns:
        dict with keys: intent, chunk_type, asset_types, taxonomy, version, reasoning
    """
    import requests

    analysis_prompt = f"""Analyze this cybersecurity question and determine the optimal filters for retrieving relevant information from a knowledge base.

Question: "{question}"

Available filters:
- chunk_type: "mitigation", "weakness", "risk", "attack_scenario", "example", "related_link", "description", "impact", "reference", "glossary"
- asset_types: List of asset types mentioned in the question (e.g., ["Web Application"], ["API", "REST API"], ["Mobile Application"])
  Common examples: API, REST API, GraphQL, Web Application, Mobile Application, Database, Authentication Service,
  Authorization Service, Session Management, Token Service, File System, Cloud Service, Container, Network Device, etc.
  Extract whatever asset types are relevant - not limited to examples above.
- taxonomy: List of CWE/CAPEC IDs (e.g., ["CWE-79", "CWE-89"])
- version: Specific version like "2025", "2024", etc.

Analyze the question and return ONLY a JSON object with these fields:
{{
  "intent": "seeking_mitigations" | "seeking_vulnerabilities" | "seeking_risks" | "seeking_information" | "seeking_examples" | "seeking_definition",
  "chunk_type": null or one of the chunk types above,
  "asset_types": null or list of asset types,
  "taxonomy": null or list of CWE/CAPEC IDs if mentioned,
  "version": null or version string if mentioned,
  "reasoning": "Brief explanation of why these filters were chosen"
}}

Guidelines:
- "what is", "define", "explain what", "meaning of" → chunk_type="glossary"
- "how do I", "prevent", "mitigate", "fix", "secure" → chunk_type="mitigation"
- "what are", "risks", "vulnerabilities", "weaknesses" → chunk_type="weakness" or "risk"
- "examples of", "show me" → chunk_type="example"
- Extract asset types naturally from the question - use specific technical terms that would appear in documentation
- Match the terminology style used in cybersecurity docs (e.g., "Web Application" not "web app", "REST API" not "API endpoint")
- Only include asset_types if the question clearly references a specific type of system/component
- Only include taxonomy if specific CWE/CAPEC IDs are mentioned
- Only include version if year/version is mentioned

Return ONLY the JSON object, no other text."""

    try:
        if llm_provider == "openai":
            import openai
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = llm_model or "gpt-4o-mini"

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a query analysis assistant. Return only valid JSON."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            result = response.choices[0].message.content.strip()

        elif llm_provider == "ollama":
            model = llm_model or "llama3.2:latest"

            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a query analysis assistant. Return only valid JSON."},
                        {"role": "user", "content": analysis_prompt}
                    ],
                    "stream": False
                }
            )

            if response.status_code != 200:
                return {}

            result = response.json()["message"]["content"].strip()

        # Parse JSON response
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0].strip()
        elif "```" in result:
            result = result.split("```")[1].split("```")[0].strip()

        analysis = json.loads(result)
        return analysis

    except Exception as e:
        print(f"  ⚠ Query analysis failed: {e}")
        return {}


def execute_rag(
    question: str,
    config: dict,
    llm_provider: str = "openai",
    llm_model: Optional[str] = None,
    embed_provider: str = "ollama",
    embed_model: Optional[str] = None,
    limit: int = 10,
    chunk_type: Optional[str] = None,
    asset_types: Optional[List[str]] = None,
    taxonomy: Optional[List[str]] = None,
    version: Optional[str] = None,
    include_inactive: bool = False,
    show_context: bool = False
) -> Dict[str, Any]:
    """
    Execute full RAG flow with LLM answer generation.

    Returns:
        dict with:
            - answer: str
            - context: List[dict]
            - filters_used: dict
    """
    # Step 1: Analyze query
    query_analysis = analyze_query(question, llm_provider, llm_model)

    # Merge auto-detected filters with manual overrides
    final_chunk_type = chunk_type or query_analysis.get('chunk_type')
    final_asset_types = asset_types or query_analysis.get('asset_types')
    final_taxonomy = taxonomy or query_analysis.get('taxonomy')
    final_version = version or query_analysis.get('version')

    # Step 2: Retrieve context
    provider = get_embedding_provider(provider=embed_provider, model=embed_model)
    query_embeddings = provider.embed_batch([question])
    query_embedding = query_embeddings[0]

    conn = get_db_connection(config)
    results = search_chunks(
        conn,
        query_embedding=query_embedding,
        limit=limit,
        chunk_type=final_chunk_type,
        asset_types=final_asset_types,
        taxonomy=final_taxonomy,
        version=final_version,
        only_active=not include_inactive
    )
    conn.close()

    if not results:
        return {
            'answer': "No relevant information found in the knowledge base.",
            'context': [],
            'filters_used': {}
        }

    # Step 3: Build prompt with context
    context_parts = []
    for i, chunk in enumerate(results, 1):
        context_part = f"[Chunk {i}]\n"
        context_part += f"Title: {chunk['title'] or 'N/A'}\n"
        context_part += f"ID: {chunk['canonical_id'] or 'N/A'}\n"
        context_part += f"Type: {chunk['chunk_type']}\n"
        context_part += f"Source: {chunk['source_uri']}\n"

        if chunk.get('tags') and chunk['tags'].get('stride'):
            stride_tags = chunk['tags']['stride']
            if stride_tags:
                context_part += f"STRIDE: {', '.join(stride_tags)}\n"

        context_part += f"Content:\n{chunk['text']}\n"
        context_parts.append(context_part)

    context_text = "\n---\n\n".join(context_parts)

    system_prompt = """You are a helpful cybersecurity expert. Answer the user's question using ONLY the reference material provided below.

CRITICAL INSTRUCTIONS:
- You MUST answer ONLY using information from the reference material below - DO NOT use general knowledge or training data
- If the reference material doesn't contain the answer, politely decline: "I don't have information about that in my current knowledge base. I specialize in [mention what topics you see in the reference material, e.g., 'OWASP security guidelines', 'web application security']. Is there something related I can help with?"
- Be authoritative and direct - speak as the expert, not as someone reporting on reference material
- DO NOT say "based on the reference material", "according to the sources", "the documentation shows" - just state the facts
- DO NOT mention "chunks", "context", "embeddings", "knowledge base", or "reference material" in your answer
- Cite sources naturally using document IDs and titles (e.g., "OWASP Top 10 2025 (A01:2025) identifies...")
- Synthesize information across multiple sources when relevant
- Organize by STRIDE categories or risk levels when applicable
- Be direct and actionable - focus on practical guidance
- Be helpful and encouraging - end with actionable takeaways, impact statements, or offers of further assistance
- Sound conversational and supportive, not robotic - you're helping someone improve their security posture

Reference Material:

{context}

---

USER QUESTION: {question}

Answer authoritatively and helpfully using ONLY the reference material above."""

    prompt = system_prompt.format(context=context_text, question=question)

    # Step 4: Generate answer
    answer = _generate_answer(prompt, llm_provider, llm_model)

    return {
        'answer': answer,
        'context': results if show_context else [],
        'chunk_count': len(results),  # Always include count even if context is hidden
        'filters_used': {
            'chunk_type': final_chunk_type,
            'asset_types': final_asset_types,
            'taxonomy': final_taxonomy,
            'version': final_version
        },
        'query_analysis': query_analysis
    }


def _generate_answer(prompt: str, llm_provider: str, llm_model: Optional[str]) -> str:
    """Generate LLM answer from prompt."""
    import requests

    try:
        if llm_provider == "openai":
            import openai
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = llm_model or "gpt-4o-mini"

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful cybersecurity expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            return response.choices[0].message.content

        elif llm_provider == "ollama":
            model = llm_model or "llama3.2:latest"

            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful cybersecurity expert."},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False
                }
            )

            if response.status_code != 200:
                return f"Error: Ollama API returned {response.status_code}"

            return response.json()["message"]["content"]

    except Exception as e:
        return f"Error generating answer: {e}"
