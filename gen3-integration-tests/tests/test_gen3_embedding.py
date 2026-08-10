"""
Gen3 Embedding SERVICE
"""

import ast

import numpy as np
import pandas as pd
import pytest
from services.embedding import Embedding
from utils import TEST_DATA_PATH_OBJECT, logger


@pytest.mark.skipif(
    "gen3-embeddings" not in pytest.deployed_services,
    reason="gen3-embeddings service is not running on this environment",
)
@pytest.mark.gen3_embedding
class TestGen3Embedding:
    @classmethod
    def setup_class(cls):
        cls.gen3_embedding = Embedding()

        cls.gen3_embedding.generate_embedding_data(
            collection_name="hist", number_of_records=100, embedding_size=1536
        )

        cls.collection_data = {
            "hist": {
                "collection_name": "hist",
                "description": "Testing creation of a collection",
                "dimensions": 1536,
            },
        }

        cls.updated_collection_data = {
            "hist": {
                "description": "Testing updation of a collection",
            },
        }

    def test_creation_collection_and_embedding(self):
        """
        Scenario: Create a collection and embeddings
        Steps:
            1. Create a collection named hist using main_account
            2. Update the description for the collection hist
            3. Verify the collection hist is updated
            4. Create embeddings in collection hist using main_account
            5. Verify the embeddings are created
            6. Add a new embedding to collection hist
            7. Delete the embeddings using main_account
            8. Delete the collection using main_account
        """
        try:
            collection_name = "hist"
            # Create the collection
            response = self.gen3_embedding.create_collection(
                data=self.collection_data[collection_name]
            )
            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Update the collection
            response = self.gen3_embedding.update_collection(
                collection_name="hist",
                data=self.updated_collection_data[collection_name],
            )
            # Get the collection
            response = self.gen3_embedding.get_collection(
                collection_name=collection_name
            )
            assert (
                response["description"]
                == self.updated_collection_data[collection_name]["description"]
            ), f"Updation failed, got response: {response}"
            # Create Embedding
            hist_file = TEST_DATA_PATH_OBJECT / "embedding" / f"{collection_name}.tsv"
            df = pd.read_csv(hist_file, sep="\t", keep_default_na=False)
            row = df.iloc[0]
            embedding_data = {
                "embeddings": [
                    {
                        "embedding": ast.literal_eval(row["embedding"]),
                        "metadata": row.drop("embedding").to_dict(),
                    }
                ]
            }
            response = self.gen3_embedding.create_embedding(
                collection_name="hist", data=embedding_data
            )

            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Update Embedding
            updated_embedding_data = {
                "metadata": row.drop("embedding").to_dict(),
            }
            updated_embedding_data["metadata"]["model"] = "hist_updated"
            response = self.gen3_embedding.update_embedding(
                collection_name="hist",
                data=updated_embedding_data,
                embedding_id=response.json()["embeddings"][0]["embedding_id"],
            )
            logger.info(response.json())
            response_metadata = response.json()["info"]["metadata"]
            expected_metadata = updated_embedding_data["metadata"]
            assert (
                response_metadata["model"] == expected_metadata["model"]
            ), f"Expected the embedding to be updated, but got {response.json()}"
            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Get the embeddings
            response = self.gen3_embedding.get_embedding(collection_name="hist")
            assert (
                len(response["embeddings"]) == 1
            ), f"Expected 1 embeddings but got {len(response["embeddings"])}"
            # Delete the embeddings
            for embedding in response["embeddings"]:
                embedding_id = embedding["embedding_id"]
                response = self.gen3_embedding.delete_embedding(
                    collection_name="hist", embedding_id=embedding_id
                )
                assert (
                    response.status_code == 204
                ), f"Expected status to be 204 but got {response.status_code}"
        except Exception as e:
            raise Exception(f"Got exception: {e}")
        finally:
            # Delete the collection
            response = self.gen3_embedding.delete_collection(collection_name="hist")
            assert (
                response.status_code == 204
            ), f"Expected status to be 204 but got {response.status_code}"

    def test_failed_creation_collection(self):
        """
        Scenario: Failed to create collection as user doesn't have permission
        Steps:
            1. Create a collection named hist using user0_account
            2. Verify collection creation fails as user0_account doesn't have permission
        """
        # Create the collection
        response = self.gen3_embedding.create_collection(
            data=self.collection_data["hist"], user="user0_account"
        )
        assert (
            response.status_code == 403
        ), f"Expected status to be 403 but got {response.status_code}"

    def test_crud_operations_non_admin_privileged_user(self):
        """
        Scenario: A non-admin privileged user can perform only read operation
        Steps:
            1. Create a collection named hist using indexing_account
            2. Verify indexing_account can't create the collection
            3. Create a collection named hist using main_account
            4. Verify indexing_account can't update the collection
            5. Verify indexing_account can read the collection
            6. Verify indexing_account can't delete the collection
            7. Create embeddings in collection hist using indexing_account
            8. Verify indexing_account can't create the embedding
            9. Create embeddings in collection hist using main_account
            10. Verify indexing_account can't update the embedding
            11. Verify indexing_account can read the embedding
            12. Verify indexing_account can't delete the embedding
        """
        try:
            collection_name = "hist"
            # Create the collection with user without admin privileges
            response = self.gen3_embedding.create_collection(
                data=self.collection_data["hist"], user="indexing_account"
            )
            assert (
                response.status_code == 403
            ), f"Expected status to be 403 but got {response.status_code}"
            # Create the collection with user having admin privileges
            response = self.gen3_embedding.create_collection(
                data=self.collection_data["hist"]
            )
            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Update the collection with user without admin privileges
            response = self.gen3_embedding.update_collection(
                collection_name="hist",
                data=self.updated_collection_data["hist"],
                user="indexing_account",
            )
            assert (
                response.status_code == 403
            ), f"Expected status to be 403 but got {response.status_code}"
            # Get the collection with user without admin privileges
            response = self.gen3_embedding.get_collection(
                collection_name="hist", user="indexing_account"
            )
            assert (
                response["description"] == self.collection_data["hist"]["description"]
            ), f"Updation failed, got response: {response}"
            # Delete the collection with user without admin privileges
            response = self.gen3_embedding.delete_collection(
                collection_name="hist", user="indexing_account"
            )
            assert (
                response.status_code == 403
            ), f"Expected status to be 403 but got {response.status_code}"
            # Create Embedding with user without admin privileges
            hist_file = TEST_DATA_PATH_OBJECT / "embedding" / f"{collection_name}.tsv"
            df = pd.read_csv(hist_file, sep="\t", keep_default_na=False)
            row = df.iloc[0]
            embedding_data = {
                "embeddings": [
                    {
                        "embedding": ast.literal_eval(row["embedding"]),
                        "metadata": row.drop("embedding").to_dict(),
                    }
                ]
            }
            response = self.gen3_embedding.create_embedding(
                collection_name="hist", data=embedding_data, user="indexing_account"
            )
            assert (
                response.status_code == 403
            ), f"Expected status to be 403 but got {response.status_code}"
            # Create Embedding with user having admin privileges
            response = self.gen3_embedding.create_embedding(
                collection_name="hist", data=embedding_data
            )
            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Update Embedding with user without admin privileges
            updated_embedding_data = {
                "metadata": row.drop("embedding").to_dict(),
            }
            updated_embedding_data["metadata"]["model"] = "hist_updated"
            response = self.gen3_embedding.update_embedding(
                collection_name="hist",
                data=updated_embedding_data,
                embedding_id=response.json()["embeddings"][0]["embedding_id"],
                user="indexing_account",
            )
            assert (
                response.status_code == 403
            ), f"Expected status to be 403 but got {response.status_code}"
            # Get the embeddings
            response = self.gen3_embedding.get_embedding(
                collection_name="hist", user="indexing_account"
            )
            assert (
                len(response["embeddings"]) == 1
            ), f"Expected 1 embeddings but got {len(response["embeddings"])}"
            # Delete the embeddings without admin privileges
            for embedding in response["embeddings"]:
                embedding_id = embedding["embedding_id"]
                response = self.gen3_embedding.delete_embedding(
                    collection_name="hist",
                    embedding_id=embedding_id,
                    user="indexing_account",
                )
                logger.info(response)
                assert (
                    response.status_code == 403
                ), f"Expected status to be 403 but got {response.status_code}"
        except Exception as e:
            raise Exception(f"Got exception: {e}")
        finally:
            # Delete the collection
            response = self.gen3_embedding.delete_collection(collection_name="hist")
            assert (
                response.status_code == 204
            ), f"Expected status to be 204 but got {response.status_code}"
