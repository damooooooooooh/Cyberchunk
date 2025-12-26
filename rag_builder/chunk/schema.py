from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from uuid import UUID, uuid4

class DocumentRecord(BaseModel):
    """Document-level metadata."""
    doc_id: UUID = Field(default_factory=uuid4)
    source_uri: str
    publisher: Optional[str] = None
    collection: Optional[str] = None  # e.g., "OWASP Top 10", "NIST 800-53"
    document_name: Optional[str] = None  # e.g., "Top 10 2021"
    item_id: Optional[str] = None  # e.g., "A01", "AC-3"
    edition: Optional[str] = None
    version: Optional[str] = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    content_type: str  # e.g., html|pdf|md|txt|docx
    content_hash_sha256: str  # SHA256 of raw bytes
    normalized_hash_sha256: str  # SHA256 of normalized full text
    title: Optional[str] = None  # Best effort title
    extractor_id: Optional[str] = None  # Which extractor config/template applied

class SectionNode(BaseModel):
    """Outline tree node for document sections."""
    section_id: UUID = Field(default_factory=uuid4)
    doc_id: UUID
    heading_text: str
    heading_level: int
    section_path: List[str]  # Array of heading strings from root to this section
    source_locator: str  # HTML: anchor/selector; PDF: page range; Text: char offsets
    raw_text: str
    clean_text: str

class ChunkRecord(BaseModel):
    """The unit used in RAG - Nodes of the Knowledge Graph."""
    chunk_id: UUID = Field(default_factory=uuid4)
    doc_id: UUID
    section_id: Optional[UUID] = None  # Direct link to source SectionNode
    chunk_type: str = Field(..., pattern="^(risk|mitigation|control|weakness|threat_actor|related_framework|related_link|attack_scenario)$")
    canonical_id: Optional[str] = None  # e.g., OWASP-LLM01, NIST-800-53-AC-3, CVE-2023-1234
    title: Optional[str] = None
    text: str  # Cleaned chunk text
    tags: Dict[str, List[str]] = Field(default_factory=lambda: {
        "keywords": [],
        "topics": [],
        "taxonomy": [],
        "stride": [],           # Phase 1: STRIDE threat categories
        "asset_types": [],      # Phase 1: API, Web App, Mobile, etc.
        "technologies": [],     # Phase 1: OAuth, JWT, etc.
        "security_controls": [] # Phase 1: Authentication, Authorization, etc.
    })

    # url: Optional[str] = None  # For related_link chunks
    link_uri: Optional[str] = None  # For related_link chunks

    # Provenance fields (inherited from DocumentRecord/SectionNode)
    source_uri: str
    publisher: Optional[str] = None
    edition: Optional[str] = None
    version: Optional[str] = None
    section_path: List[str]
    source_locator: str
    content_hash_sha256: str # SHA256 of the raw content bytes of the original document

    # Embedding fields (filled during index)
    embedding_model: Optional[str] = None
    embedding_vector: Optional[List[float]] = None # New field to store the embedding vector
    embedding_vector_id: Optional[int] = None
    embedding_vector_path: Optional[str] = None # Path to the FAISS index where this vector is stored

    # LLM-added metadata (optional)
    llm_model_name: Optional[str] = None
    llm_params: Optional[Dict[str, Any]] = None
    prompt_template_id: Optional[str] = None
    prompt_hash: Optional[str] = None
    input_hash_sha256: Optional[str] = None
    output_hash_sha256: Optional[str] = None
    ran_at: Optional[datetime] = None
    validation_results: Optional[Dict[str, Any]] = None # e.g., { status: 'PASS'|'FAIL'|'WARN', message: '...', issues: [] }

class RelationshipRecord(BaseModel):
    """Edges of the Knowledge Graph."""
    relationship_id: UUID = Field(default_factory=uuid4)
    source_chunk_id: UUID
    target_chunk_id: UUID
    relationship_type: str = Field(..., pattern="^(MITIGATES|EXPLOITS|HAS_CONTROL|RELATED_TO|REFERENCES|COMMENTS_ON)$") # Example types
    strength: Optional[str] = None  # e.g., 'high', 'medium', 'low', or numerical score
    evidence_span: Optional[str] = None # Direct quote from source text supporting the relationship
    llm_derived: bool = False # True if derived by LLM
    llm_model_name: Optional[str] = None
    ran_at: Optional[datetime] = None
    validation_results: Optional[Dict[str, Any]] = None
