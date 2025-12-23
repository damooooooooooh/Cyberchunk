import re
import string
import pickle
from collections import Counter
from typing import List, Dict, Tuple, Optional
import numpy as np # For random texts in testing

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer

from rag_builder.chunk.schema import ChunkRecord

# Download NLTK resources if not already present (no need for try-except for DownloadError here)
nltk.download('stopwords', quiet=True, raise_on_error=False)
nltk.download('wordnet', quiet=True, raise_on_error=False)
# 'averaged_perceptron_tagger' is not strictly needed for lemmatization in this basic setup
# nltk.download('averaged_perceptron_tagger', quiet=True, raise_on_error=False)

stop_words = set(stopwords.words('english'))
lemmatizer = WordNetLemmatizer()

def preprocess_text_for_keywords(text: str) -> str:
    """
    Cleans and preprocesses text for keyword extraction:
    - Lowercase
    - Remove punctuation
    - Remove numbers
    - Remove stopwords
    - Lemmatize
    """
    text = text.lower()
    text = re.sub(f"[{re.escape(string.punctuation)}]", "", text) # Remove punctuation
    text = re.sub(r'\d+', '', text) # Remove numbers
    
    tokens = text.split()
    tokens = [lemmatizer.lemmatize(word) for word in tokens if word not in stop_words and word.isalpha()]
    
    return " ".join(tokens)

class KeywordExtractor:
    def __init__(self, top_n: int = 5):
        self.version = "1.0" # Version for the class structure
        self.vectorizer = TfidfVectorizer()
        self.top_n = top_n
        self.feature_names: Optional[List[str]] = None

    def train(self, texts: List[str]):
        """Trains the TF-IDF vectorizer on a corpus of preprocessed texts."""
        preprocessed_texts = [preprocess_text_for_keywords(text) for text in texts]
        self.vectorizer.fit(preprocessed_texts)
        self.feature_names = self.vectorizer.get_feature_names_out()
        print(f"KeywordExtractor trained on {len(texts)} documents.")

    def extract_keywords(self, text: str) -> List[str]:
        """Extracts top N TF-IDF keywords from a single preprocessed text."""
        if self.feature_names is None:
            print("Warning: KeywordExtractor not trained. Returning empty list.")
            return []
        
        preprocessed_text = preprocess_text_for_keywords(text)
        if not preprocessed_text:
            return []

        vector = self.vectorizer.transform([preprocessed_text])
        
        # If the transformed vector has no non-zero elements, there are no keywords.
        if vector.nnz == 0:
            return []

        # Convert to dense array for easier manipulation
        dense_vector = vector.toarray().flatten()

        # Get top N keywords
        top_indices = dense_vector.argsort()[-self.top_n:][::-1]
        
        keywords = [self.feature_names[i] for i in top_indices if i < len(self.feature_names) and dense_vector[i] > 0]
        return keywords

    def extract_keywords_from_chunks(self, chunks: List[ChunkRecord]) -> List[ChunkRecord]:
        """Extracts keywords for each ChunkRecord and updates its tags."""
        if self.feature_names is None:
            print("Warning: KeywordExtractor not trained. Skipping keyword extraction for chunks.")
            return chunks

        updated_chunks = []
        for chunk in chunks:
            keywords = self.extract_keywords(chunk.text)
            chunk.tags["keywords"] = list(set(chunk.tags.get("keywords", []) + keywords)) # Add new keywords, avoid duplicates
            updated_chunks.append(chunk)
        return updated_chunks

    def save(self, file_path: str):
        """Saves the trained KeywordExtractor to a file."""
        with open(file_path, 'wb') as f:
            pickle.dump(self, f)
        print(f"KeywordExtractor saved to {file_path}")

    @classmethod
    def load(cls, file_path: str) -> 'KeywordExtractor':
        """Loads a trained KeywordExtractor from a file."""
        with open(file_path, 'rb') as f:
            extractor = pickle.load(f)
        
        # Version check
        current_version = "1.0"
        loaded_version = getattr(extractor, 'version', '0.0') # Default to 0.0 if no version attribute
        if loaded_version != current_version:
            raise TypeError(f"Saved model version ({loaded_version}) does not match current class version ({current_version}). Please retrain.")
            
        print(f"KeywordExtractor loaded from {file_path}")
        return extractor

if __name__ == '__main__':
    # Test keyword extractor
    import numpy as np # For random texts in testing
    from uuid import uuid4
    import os # Added for os.makedirs and os.path.join

    print("--- Testing KeywordExtractor ---")
    corpus_texts = [
        "Cybersecurity threats are evolving rapidly, requiring advanced defense mechanisms.",
        "SQL injection remains a common vulnerability in web applications, demanding careful input validation.",
        "Protecting sensitive data is paramount; encryption and access control are key mitigations.",
        "Threat modeling helps identify potential risks before deployment.",
        "A strong security posture involves regular audits and continuous monitoring."
    ]

    dummy_doc_id = uuid4()
    dummy_chunks_for_test = [
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="risk",
            text="SQL injection is a severe web vulnerability. Always validate inputs.",
            source_uri="http://test.com", section_path=["risk"], source_locator="#sql", content_hash_sha256="h1"
        ),
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="mitigation",
            text="Implement strong authentication and authorization to prevent unauthorized access.",
            source_uri="http://test.com", section_path=["mit"], source_locator="#auth", content_hash_sha256="h2"
        )
    ]

    extractor = KeywordExtractor(top_n=3)
    extractor.train(corpus_texts)

    # Test single text extraction
    test_text = "Vulnerability assessment is a process of identifying and classifying security flaws."
    keywords = extractor.extract_keywords(test_text)
    print(f"\nKeywords for '{test_text}': {keywords}")

    # Test chunk extraction
    updated_chunks = extractor.extract_keywords_from_chunks(dummy_chunks_for_test)
    print("\nKeywords extracted for chunks:")
    for chunk in updated_chunks:
        print(f"Chunk ID: {chunk.chunk_id}, Keywords: {chunk.tags['keywords']}")

    # Test save/load
    output_dir = "test_tag_output"
    os.makedirs(output_dir, exist_ok=True)
    extractor.save(os.path.join(output_dir, "keywords.pkl"))
    loaded_extractor = KeywordExtractor.load(os.path.join(output_dir, "keywords.pkl"))
    print(f"Loaded extractor keywords for '{test_text}': {loaded_extractor.extract_keywords(test_text)}")

    # Clean up
    os.remove(os.path.join(output_dir, "keywords.pkl"))
    os.rmdir(output_dir)
