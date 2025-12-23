import faiss
import numpy as np
import os
import json
from typing import List, Dict, Tuple, Optional
from uuid import UUID

class FaissIndex:
    def __init__(self, embedding_dimension: int, index_type: str = "FlatL2"):
        """
        Initializes a FAISS index.
        Args:
            embedding_dimension: The dimension of the embedding vectors.
            index_type: Type of FAISS index to use (e.g., "FlatL2", "IndexFlatIP", "IVFFlat").
        """
        self.embedding_dimension = embedding_dimension
        self.index_type = index_type
        self.index: Optional[faiss.Index] = None
        self.uuid_to_faiss_id: Dict[UUID, int] = {} # Maps chunk_id (UUID) to FAISS internal ID
        self.faiss_id_to_uuid: List[UUID] = []     # Maps FAISS internal ID to chunk_id (UUID)

        self._init_index()

    def _init_index(self):
        if self.index_type == "FlatL2":
            self.index = faiss.IndexFlatL2(self.embedding_dimension)
        elif self.index_type == "FlatIP":
            self.index = faiss.IndexFlatIP(self.embedding_dimension)
        # Add other index types as needed, e.g., IVFFlat
        # For IVFFlat, you'd need to train the index:
        # nlist = 100  # number of clusters
        # quantizer = faiss.IndexFlatL2(self.embedding_dimension)
        # self.index = faiss.IndexIVFFlat(quantizer, self.embedding_dimension, nlist, faiss.METRIC_L2)
        # self.index.train(some_representative_vectors)
        else:
            raise ValueError(f"Unsupported FAISS index type: {self.index_type}")

    def add_vectors(self, chunk_uuids: List[UUID], vectors: List[List[float]]):
        """
        Adds vectors to the FAISS index, mapping chunk_id to FAISS internal ID.
        Args:
            chunk_uuids: List of UUIDs corresponding to each vector.
            vectors: List of embedding vectors to add.
        """
        if not vectors:
            return

        vectors_np = np.array(vectors).astype('float32')
        if vectors_np.shape[1] != self.embedding_dimension:
            raise ValueError(f"Vector dimension mismatch. Expected {self.embedding_dimension}, got {vectors_np.shape[1]}")

        # Ensure index is trained if it's an IVFFlat index
        # if isinstance(self.index, faiss.IndexIVFFlat) and not self.index.is_trained:
        #     self.index.train(vectors_np) # Train with the first batch or a representative set

        self.index.add(vectors_np)

        # Update mappings
        for i, uuid in enumerate(chunk_uuids):
            faiss_id = self.index.ntotal - len(chunk_uuids) + i # Get the internal ID assigned by FAISS
            self.uuid_to_faiss_id[uuid] = faiss_id
            self.faiss_id_to_uuid.append(uuid) # This assumes IDs are added sequentially and never deleted
            
        print(f"Added {len(vectors)} vectors to FAISS index. Total vectors: {self.index.ntotal}")

    def search(self, query_vector: List[float], k: int = 5) -> List[Tuple[float, UUID]]:
        """
        Searches the FAISS index for the k nearest neighbors.
        Args:
            query_vector: The embedding vector of the query.
            k: The number of nearest neighbors to retrieve.
        Returns:
            A list of tuples (distance, chunk_uuid) of the k nearest neighbors.
        """
        if self.index.ntotal == 0:
            return []

        query_np = np.array([query_vector]).astype('float32')
        distances, faiss_ids = self.index.search(query_np, k)

        results: List[Tuple[float, UUID]] = []
        for i in range(len(faiss_ids[0])):
            faiss_id = faiss_ids[0][i]
            if faiss_id != -1: # -1 indicates no result found
                distance = distances[0][i]
                chunk_uuid = self.faiss_id_to_uuid[faiss_id]
                results.append((distance, chunk_uuid))
        return results

    def save(self, output_dir: str, index_prefix: str):
        """
        Saves the FAISS index and its metadata mappings to disk.
        Args:
            output_dir: Directory to save the files.
            index_prefix: Prefix for the index and mapping files (e.g., "my_embeddings").
        """
        os.makedirs(output_dir, exist_ok=True)
        faiss_path = os.path.join(output_dir, f"{index_prefix}.faiss")
        mapping_path = os.path.join(output_dir, f"{index_prefix}_mapping.json")

        faiss.write_index(self.index, faiss_path)
        with open(mapping_path, 'w', encoding='utf-8') as f:
            # Convert UUIDs to strings for JSON serialization
            serializable_uuid_to_faiss_id = {str(k): v for k, v in self.uuid_to_faiss_id.items()}
            serializable_faiss_id_to_uuid = [str(u) for u in self.faiss_id_to_uuid]
            json.dump({"uuid_to_faiss_id": serializable_uuid_to_faiss_id,
                       "faiss_id_to_uuid": serializable_faiss_id_to_uuid}, f, indent=4)
        print(f"FAISS index saved to {faiss_path}")
        print(f"Mapping saved to {mapping_path}")

    @classmethod
    def load(cls, output_dir: str, index_prefix: str) -> 'FaissIndex':
        """
        Loads a FAISS index and its metadata mappings from disk.
        Args:
            output_dir: Directory where the files are saved.
            index_prefix: Prefix for the index and mapping files.
        Returns:
            An initialized FaissIndex object.
        """
        faiss_path = os.path.join(output_dir, f"{index_prefix}.faiss")
        mapping_path = os.path.join(output_dir, f"{index_prefix}_mapping.json")

        if not os.path.exists(faiss_path):
            raise FileNotFoundError(f"FAISS index file not found at {faiss_path}")
        if not os.path.exists(mapping_path):
            raise FileNotFoundError(f"Mapping file not found at {mapping_path}")

        loaded_index = faiss.read_index(faiss_path)
        
        with open(mapping_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            loaded_uuid_to_faiss_id = {UUID(k): v for k, v in data["uuid_to_faiss_id"].items()}
            loaded_faiss_id_to_uuid = [UUID(u) for u in data["faiss_id_to_uuid"]]

        # Re-initialize the class and then set the loaded attributes
        instance = cls(embedding_dimension=loaded_index.d, index_type="FlatL2") # Index type is not saved in FAISS, assume FlatL2
        instance.index = loaded_index
        instance.uuid_to_faiss_id = loaded_uuid_to_faiss_id
        instance.faiss_id_to_uuid = loaded_faiss_id_to_uuid
        
        print(f"FAISS index loaded from {faiss_path}")
        print(f"Mapping loaded from {mapping_path}")
        return instance

if __name__ == '__main__':
    # Test FAISS Index creation, adding, saving, loading, and searching
    test_dim = 128
    test_output_dir = "test_faiss_output"
    test_prefix = "test_embeddings"
    os.makedirs(test_output_dir, exist_ok=True)

    # 1. Create and add vectors
    faiss_idx = FaissIndex(embedding_dimension=test_dim)
    
    # Generate some dummy data
    test_uuids = [UUID('a1b2c3d4-e5f6-7890-0000-000000000001'), UUID('a1b2c3d4-e5f6-7890-0000-000000000002')]
    test_vectors = [np.random.rand(test_dim).tolist(), np.random.rand(test_dim).tolist()]
    faiss_idx.add_vectors(test_uuids, test_vectors)

    # Add more
    test_uuids2 = [UUID('a1b2c3d4-e5f6-7890-0000-000000000003')]
    test_vectors2 = [np.random.rand(test_dim).tolist()]
    faiss_idx.add_vectors(test_uuids2, test_vectors2)

    # 2. Save
    faiss_idx.save(test_output_dir, test_prefix)

    # 3. Load
    loaded_faiss_idx = FaissIndex.load(test_output_dir, test_prefix)
    print(f"Loaded index has {loaded_faiss_idx.index.ntotal} vectors.")

    # 4. Search
    query_vec = test_vectors[0] # Use the first added vector as a query
    search_results = loaded_faiss_idx.search(query_vec, k=2)
    print(f"\nSearch results for query (top 2): {search_results}")
    
    # Verify the top result is the query itself (distance should be very small or 0)
    assert search_results[0][1] == test_uuids[0]
    print("Search successful, top result is correct.")

    # Clean up test files
    os.remove(os.path.join(test_output_dir, f"{test_prefix}.faiss"))
    os.remove(os.path.join(test_output_dir, f"{test_prefix}_mapping.json"))
    os.rmdir(test_output_dir)
