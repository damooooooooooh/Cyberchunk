import pickle
from typing import List, Dict, Optional, Tuple
import re
import string
import numpy as np # Import numpy for array operations

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD # Or LatentDirichletAllocation

from rag_builder.chunk.schema import ChunkRecord

# Download NLTK resources if not already present
nltk.download('stopwords', quiet=True, raise_on_error=False)
nltk.download('wordnet', quiet=True, raise_on_error=False)

stop_words = set(stopwords.words('english'))
lemmatizer = WordNetLemmatizer()

def preprocess_text_for_topics(text: str) -> str:
    """
    Cleans and preprocesses text for topic modeling:
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

class TopicModeler:
    def __init__(self, num_topics: int = 5):
        self.vectorizer = TfidfVectorizer()
        self.model = TruncatedSVD(n_components=num_topics) # Using TruncatedSVD
        # For LDA: self.model = LatentDirichletAllocation(n_components=num_topics, random_state=42)
        self.num_topics = num_topics
        self.feature_names: Optional[List[str]] = None
        self.is_trained: bool = False

    def train(self, texts: List[str]):
        """Trains the TF-IDF vectorizer and topic model on a corpus of preprocessed texts."""
        preprocessed_texts = [preprocess_text_for_topics(text) for text in texts]
        tfidf_matrix = self.vectorizer.fit_transform(preprocessed_texts)
        self.feature_names = self.vectorizer.get_feature_names_out()
        self.model.fit(tfidf_matrix)
        self.is_trained = True
        print(f"TopicModeler trained on {len(texts)} documents with {self.num_topics} topics.")

    def get_top_words_for_topic(self, topic_id: int, n_words: int = 5) -> List[str]:
        """Returns the top N words for a given topic."""
        if self.is_trained is False or self.feature_names is None:
            return []
        
        # For TruncatedSVD, components_ are the topic-word distributions
        # For LDA, components_ are also topic-word distributions
        topic_words = self.model.components_[topic_id].argsort()[-n_words:][::-1]
        return [self.feature_names[i] for i in topic_words]

    def infer_topics(self, text: str) -> List[Tuple[int, float]]:
        """
        Infers topic probabilities for a single preprocessed text.
        Returns a list of (topic_id, probability) tuples.
        """
        if self.is_trained is False:
            print("Warning: TopicModeler not trained. Cannot infer topics.")
            return []
        
        preprocessed_text = preprocess_text_for_topics(text)
        if not preprocessed_text:
            return []

        tfidf_vector = self.vectorizer.transform([preprocessed_text])
        topic_distribution = self.model.transform(tfidf_vector)[0]

        # Normalize to get probabilities if using TruncatedSVD (which gives component loadings)
        # For LDA, transform usually gives probabilities directly
        topic_sum = np.sum(topic_distribution)
        if topic_sum == 0:
            return []
        normalized_distribution = topic_distribution / topic_sum
        
        # Get topics with their scores
        inferred_topics = [(i, prob) for i, prob in enumerate(normalized_distribution) if prob > 0.01] # Threshold
        inferred_topics.sort(key=lambda x: x[1], reverse=True)
        return inferred_topics

    def assign_topics_to_chunks(self, chunks: List[ChunkRecord], threshold: float = 0.1) -> List[ChunkRecord]:
        """Infers topics for each ChunkRecord and updates its tags."""
        if self.is_trained is False:
            print("Warning: TopicModeler not trained. Skipping topic assignment for chunks.")
            return chunks

        updated_chunks = []
        for chunk in chunks:
            inferred_topics = self.infer_topics(chunk.text)
            assigned_topic_names = []
            for topic_id, score in inferred_topics:
                if score >= threshold:
                    top_words = self.get_top_words_for_topic(topic_id, n_words=2)
                    assigned_topic_names.append(f"Topic {topic_id} ({', '.join(top_words)})")
            
            chunk.tags["topics"] = list(set(chunk.tags.get("topics", []) + assigned_topic_names))
            updated_chunks.append(chunk)
        return updated_chunks

    def save(self, vectorizer_path: str, model_path: str):
        """Saves the trained TF-IDF vectorizer and topic model to files."""
        with open(vectorizer_path, 'wb') as f:
            pickle.dump(self.vectorizer, f)
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
        print(f"TopicModeler vectorizer saved to {vectorizer_path}")
        print(f"TopicModeler model saved to {model_path}")

    @classmethod
    def load(cls, vectorizer_path: str, model_path: str, num_topics: int = 5) -> 'TopicModeler':
        """Loads a trained TF-IDF vectorizer and topic model from files."""
        with open(vectorizer_path, 'rb') as f:
            vectorizer = pickle.load(f)
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        
        instance = cls(num_topics=num_topics)
        instance.vectorizer = vectorizer
        instance.model = model
        instance.feature_names = vectorizer.get_feature_names_out()
        instance.is_trained = True
        print(f"TopicModeler loaded from {vectorizer_path} and {model_path}")
        return instance

if __name__ == '__main__':
    # Test topic modeler
    import numpy as np
    from uuid import uuid4
    import os

    print("--- Testing TopicModeler ---")
    corpus_texts = [
        "Cybersecurity threats are evolving rapidly, requiring advanced defense mechanisms and attack prevention.",
        "SQL injection remains a common vulnerability in web applications, demanding careful input validation to mitigate risk.",
        "Protecting sensitive data is paramount; encryption and access control are key mitigations for data breaches.",
        "Threat modeling helps identify potential risks before deployment, focusing on attack vectors and vulnerabilities.",
        "A strong security posture involves regular audits and continuous monitoring for compliance."
    ]

    dummy_doc_id = uuid4()
    dummy_chunks_for_test = [
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="risk",
            text="SQL injection is a severe web vulnerability. Always validate inputs to prevent attacks.",
            source_uri="http://test.com", section_path=["risk"], source_locator="#sql", content_hash_sha256="h1"
        ),
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="mitigation",
            text="Implement strong authentication and authorization to prevent unauthorized access and data breaches.",
            source_uri="http://test.com", section_path=["mit"], source_locator="#auth", content_hash_sha256="h2"
        ),
        ChunkRecord(
            chunk_id=uuid4(), doc_id=dummy_doc_id, chunk_type="general",
            text="Recent attacks by a nation-state actor used sophisticated phishing techniques.",
            source_uri="http://test.com", section_path=["gen"], source_locator="#gen", content_hash_sha256="h3"
        )
    ]

    modeler = TopicModeler(num_topics=2) # Test with 2 topics
    modeler.train(corpus_texts)

    print("\nTop words per topic:")
    for i in range(modeler.num_topics):
        print(f"Topic {i}: {modeler.get_top_words_for_topic(i)}")

    # Test single text inference
    test_text = "New data privacy regulations require advanced encryption methods."
    inferred = modeler.infer_topics(test_text)
    print(f"\nInferred topics for '{test_text}': {inferred}")

    # Test chunk assignment
    updated_chunks = modeler.assign_topics_to_chunks(dummy_chunks_for_test)
    print("\nTopics assigned to chunks:")
    for chunk in updated_chunks:
        print(f"Chunk ID: {chunk.chunk_id}, Topics: {chunk.tags['topics']}")

    # Test save/load
    output_dir = "test_tag_output"
    os.makedirs(output_dir, exist_ok=True)
    modeler.save(os.path.join(output_dir, "vectorizer.pkl"), os.path.join(output_dir, "topic_model.pkl"))
    loaded_modeler = TopicModeler.load(os.path.join(output_dir, "vectorizer.pkl"), os.path.join(output_dir, "topic_model.pkl"))
    print(f"Loaded modeler topics for '{test_text}': {loaded_modeler.infer_topics(test_text)}")

    # Clean up
    os.remove(os.path.join(output_dir, "vectorizer.pkl"))
    os.remove(os.path.join(output_dir, "topic_model.pkl"))
    os.rmdir(output_dir)