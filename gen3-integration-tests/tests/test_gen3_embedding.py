"""
Gen3 Embedding SERVICE
"""

import numpy as np
import pytest
from services.embedding import Embedding
from utils import TEST_DATA_PATH_OBJECT, logger


class TestGen3Embedding:
    @classmethod
    def setup_class(cls):
        data = np.load(
            TEST_DATA_PATH_OBJECT / "embedding" / "embeddings.npz", allow_pickle=True
        )
        cls.sentences = data["sentences"]
        cls.embeddings = data["embeddings"]
        cls.gen3_embedding = Embedding()

        cls.collection_data = {
            "public": {
                "collection_name": "public",
                "description": "Testing creation of a collection",
                "dimensions": 384,
            },
        }

        cls.updated_collection_data = {
            "public": {
                "description": "Testing updation of a collection",
            },
        }

    def test_creation_collection_and_embedding(self):
        """
        Scenario: Create a collection and embeddings
        Steps:
            1. Create a collection named public using main_account
            2. Update the description for the collection public
            3. Verify the collection public is updated
            4. Create embeddings in collection public using main_account
            5. Verify the embeddings are created
            6. Add a new embedding to collection public
            7. Delete the embeddings using main_account
            8. Delete the collection using main_account
        """
        try:
            # Create the collection
            response = self.gen3_embedding.create_collection(
                data=self.collection_data["public"]
            )
            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Update the collection
            response = self.gen3_embedding.update_collection(
                collection_name="public", data=self.updated_collection_data["public"]
            )
            # Get the collection
            response = self.gen3_embedding.get_collection(collection_name="public")
            assert (
                response["description"]
                == self.updated_collection_data["public"]["description"]
            ), f"Updation failed, got response: {response}"
            # Create Embedding
            embedding_data = {
                "embeddings": [
                    {
                        "embedding": self.embeddings[0].tolist(),
                        "metadata": {"source": "some_file.md", "chunk_size": "1000"},
                    }
                ]
            }
            response = self.gen3_embedding.create_embedding(
                collection_name="public", data=embedding_data
            )
            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Update Embedding
            updated_embedding_data = {
                "embeddings": [
                    {
                        "embedding": self.embeddings[0].tolist(),
                        "metadata": {
                            "source": "some_file_update.md",
                            "chunk_size": "1000",
                        },
                    }
                ]
            }
            response = self.gen3_embedding.update_embedding(
                collection_name="public", data=updated_embedding_data
            )
            response_metadata = response.json()["embeddings"][0]["info"]["metadata"]
            expected_metadata = updated_embedding_data["embeddings"][0]["metadata"]
            assert (
                response_metadata["source"] == expected_metadata["source"]
            ), f"Expected the embedding to be updated, but got {response.json()}"
            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Get the embeddings
            response = self.gen3_embedding.get_embedding(collection_name="public")
            assert (
                len(response["embeddings"]) == 1
            ), f"Expected 1 embeddings but got {len(response["embeddings"])}"
            # Delete the embeddings
            for embedding in response["embeddings"]:
                embedding_id = embedding["embedding_id"]
                response = self.gen3_embedding.delete_embedding(
                    collection_name="public", embedding_id=embedding_id
                )
                assert (
                    response.status_code == 204
                ), f"Expected status to be 204 but got {response.status_code}"
        except Exception as e:
            raise Exception(f"Got exception: {e}")
        finally:
            # Delete the collection
            response = self.gen3_embedding.delete_collection(collection_name="public")
            assert (
                response.status_code == 204
            ), f"Expected status to be 204 but got {response.status_code}"

    def test_failed_creation_collection(self):
        """
        Scenario: Failed to create collection as user doesn't have permission
        Steps:
            1. Create a collection named public using user0_account
            2. Verify collection creation fails as user0_account doesn't have permission
        """
        # Create the collection
        response = self.gen3_embedding.create_collection(
            data=self.collection_data["public"], user="user0_account"
        )
        assert (
            response.status_code == 401
        ), f"Expected status to be 401 but got {response.status_code}"
