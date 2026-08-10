"""
Gen3 Embedding SERVICE
"""

import ast

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
        cls.updated_collection_data = {}
        for collection_name, dimensions in [("hist", 1536), ("expr", 256)]:
            cls.gen3_embedding.generate_embedding_data(
                collection_name=collection_name,
                number_of_records=100,
                embedding_size=dimensions,
            )

            cls.updated_collection_data[collection_name] = {
                "description": "Testing updation of a collection",
            }

    def test_creation_collection_and_embedding(self):
        """
        Scenario: Create a collection and embeddings
        Steps:
            1. Create a collection named expr using main_account
            2. Update the description for the collection expr
            3. Verify the collection expr is updated
            4. Create embeddings in collection expr using main_account
            5. Verify the embeddings are created
            6. Add a new embedding to collection expr
            7. Delete the embeddings using main_account
            8. Delete the collection using main_account
        """
        try:
            collection_name = "expr"
            dimensions = 256
            # Create the collection
            response = self.gen3_embedding.create_collection(
                collection_name=collection_name,
                dimensions=dimensions,
            )
            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Update the collection
            response = self.gen3_embedding.update_collection(
                collection_name=collection_name,
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
            tsv_file = TEST_DATA_PATH_OBJECT / "embedding" / f"{collection_name}.tsv"
            df = pd.read_csv(tsv_file, sep="\t", keep_default_na=False)
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
                collection_name=collection_name, data=embedding_data
            )

            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Update Embedding
            updated_embedding_data = {
                "metadata": row.drop("embedding").to_dict(),
            }
            updated_embedding_data["metadata"]["model"] = "updated"
            response = self.gen3_embedding.update_embedding(
                collection_name=collection_name,
                data=updated_embedding_data,
                embedding_id=response.json()["embeddings"][0]["embedding_id"],
            )
            response_metadata = response.json()["info"]["metadata"]
            expected_metadata = updated_embedding_data["metadata"]
            assert (
                response_metadata["model"] == expected_metadata["model"]
            ), f"Expected the embedding to be updated, but got {response.json()}"
            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Get the embeddings
            response = self.gen3_embedding.get_embedding(
                collection_name=collection_name
            )
            assert (
                len(response["embeddings"]) == 1
            ), f"Expected 1 embeddings but got {len(response["embeddings"])}"
            # Delete the embeddings
            for embedding in response["embeddings"]:
                embedding_id = embedding["embedding_id"]
                response = self.gen3_embedding.delete_embedding(
                    collection_name=collection_name, embedding_id=embedding_id
                )
                assert (
                    response.status_code == 204
                ), f"Expected status to be 204 but got {response.status_code}"
        except Exception as e:
            raise Exception(f"Got exception: {e}")
        finally:
            # Delete the collection
            response = self.gen3_embedding.delete_collection(
                collection_name=collection_name
            )
            assert (
                response.status_code == 204
            ), f"Expected status to be 204 but got {response.status_code}"

    def test_failed_creation_collection(self):
        """
        Scenario: Failed to create collection as user doesn't have permission
        Steps:
            1. Create a collection named expr using user0_account
            2. Verify collection creation fails as user0_account doesn't have permission
        """
        collection_name = "expr"
        dimensions = 256
        # Create the collection
        response = self.gen3_embedding.create_collection(
            collection_name=collection_name,
            dimensions=dimensions,
            user="user0_account",
        )
        assert (
            response.status_code == 403
        ), f"Expected status to be 403 but got {response.status_code}"

    def test_crud_operations_non_admin_privileged_user(self):
        """
        Scenario: A non-admin privileged user can perform only read operation
        Steps:
            1. Create a collection named expr using indexing_account
            2. Verify indexing_account can't create the collection
            3. Create a collection named expr using main_account
            4. Verify indexing_account can't update the collection
            5. Verify indexing_account can read the collection
            6. Verify indexing_account can't delete the collection
            7. Create embeddings in collection expr using indexing_account
            8. Verify indexing_account can't create the embedding
            9. Create embeddings in collection expr using main_account
            10. Verify indexing_account can't update the embedding
            11. Verify indexing_account can read the embedding
            12. Verify indexing_account can't delete the embedding
        """
        try:
            collection_name = "expr"
            dimensions = 256
            # Create the collection with user without admin privileges
            response = self.gen3_embedding.create_collection(
                collection_name=collection_name,
                dimensions=dimensions,
                user="indexing_account",
            )
            assert (
                response.status_code == 403
            ), f"Expected status to be 403 but got {response.status_code}"
            # Create the collection with user having admin privileges
            response = self.gen3_embedding.create_collection(
                collection_name=collection_name,
                dimensions=dimensions,
            )
            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Update the collection with user without admin privileges
            response = self.gen3_embedding.update_collection(
                collection_name=collection_name,
                data=self.updated_collection_data[collection_name],
                user="indexing_account",
            )
            assert (
                response.status_code == 403
            ), f"Expected status to be 403 but got {response.status_code}"
            # Get the collection with user without admin privileges
            response = self.gen3_embedding.get_collection(
                collection_name=collection_name, user="indexing_account"
            )
            assert (
                response["description"] == "Create collection for dimensions testing"
            ), f"Updation failed, got response: {response}"
            # Delete the collection with user without admin privileges
            response = self.gen3_embedding.delete_collection(
                collection_name=collection_name, user="indexing_account"
            )
            assert (
                response.status_code == 403
            ), f"Expected status to be 403 but got {response.status_code}"
            # Create Embedding with user without admin privileges
            tsv_file = TEST_DATA_PATH_OBJECT / "embedding" / f"{collection_name}.tsv"
            df = pd.read_csv(tsv_file, sep="\t", keep_default_na=False)
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
                collection_name=collection_name,
                data=embedding_data,
                user="indexing_account",
            )
            assert (
                response.status_code == 403
            ), f"Expected status to be 403 but got {response.status_code}"
            # Create Embedding with user having admin privileges
            response = self.gen3_embedding.create_embedding(
                collection_name=collection_name, data=embedding_data
            )
            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Update Embedding with user without admin privileges
            updated_embedding_data = {
                "metadata": row.drop("embedding").to_dict(),
            }
            updated_embedding_data["metadata"]["model"] = "updated"
            response = self.gen3_embedding.update_embedding(
                collection_name=collection_name,
                data=updated_embedding_data,
                embedding_id=response.json()["embeddings"][0]["embedding_id"],
                user="indexing_account",
            )
            assert (
                response.status_code == 403
            ), f"Expected status to be 403 but got {response.status_code}"
            # Get the embeddings
            response = self.gen3_embedding.get_embedding(
                collection_name=collection_name, user="indexing_account"
            )
            assert (
                len(response["embeddings"]) == 1
            ), f"Expected 1 embeddings but got {len(response["embeddings"])}"
            # Delete the embeddings without admin privileges
            for embedding in response["embeddings"]:
                embedding_id = embedding["embedding_id"]
                response = self.gen3_embedding.delete_embedding(
                    collection_name=collection_name,
                    embedding_id=embedding_id,
                    user="indexing_account",
                )
                assert (
                    response.status_code == 403
                ), f"Expected status to be 403 but got {response.status_code}"
        except Exception as e:
            raise Exception(f"Got exception: {e}")
        finally:
            # Delete the collection
            response = self.gen3_embedding.delete_collection(
                collection_name=collection_name
            )
            assert (
                response.status_code == 204
            ), f"Expected status to be 204 but got {response.status_code}"

    def test_bulk_retrieval(self):
        """
        Scenario: Search embedding in a known/unknown collection
        Steps:
            1. Create a collection named hist using main_account
            2. Prepare the embeddings including the indexding records
            3. Submit a number of indexd guids for bulk content retrieval
            4. Verify the same number of embeddings were returned
        """
        collection_name = "hist"
        dimensions = 1536
        number_of_records = 100
        try:
            self.gen3_embedding.prepare_embeddings(
                collection_name=collection_name,
                dimensions=dimensions,
                file_name=f"{collection_name}.tsv",
                number_of_records=number_of_records,
            )
            # Perform bulk retrieval
            output_converted_indexed_file = (
                TEST_DATA_PATH_OBJECT
                / "embedding"
                / f"{collection_name}_output_converted_indexed.tsv"
            )
            df = pd.read_csv(output_converted_indexed_file, sep="\t")
            guids_list = df["guid"].astype(str).tolist()
            response = self.gen3_embedding.embedding_bulk_retrieval(guids_list)
            assert (
                int(response.json()["total_guids"]) == number_of_records
            ), f"Expected {number_of_records} but got {response.json()["total_guids"]}"
        except Exception as e:
            raise Exception(f"Got exception: {e}")
        finally:
            # Delete the collection
            response = self.gen3_embedding.delete_collection(
                collection_name=collection_name
            )
            assert (
                response.status_code == 204
            ), f"Expected status to be 204 but got {response.status_code}"

    def test_search_embedding(self):
        """
        Scenario: Search embedding in a known/unknown collection
        Steps:
            1. Create a collection named hist using main_account
            2. Publish the embeddings
            3. Search the embedding in a known collection
            4. Verify the top_k number of records were returned
            5. Search the embedding in a unknown collection
            6. Verify the top_k number of records were returned
        """
        collection_name = "hist"
        dimensions = 1536
        number_of_records = 100
        try:
            response = self.gen3_embedding.create_collection(
                collection_name=collection_name,
                dimensions=dimensions,
            )
            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            duration_ms, result = self.gen3_embedding.publish_embeddings(
                collection_name=collection_name,
                file_name=f"{collection_name}.tsv",
                number_of_records=number_of_records,
            )
            logger.info(f"Publish embeddings took {duration_ms} ms")
            if result.returncode != 0:
                raise Exception(f"Publish Embeddings failed: {result.stderr}")
            # Search Embeddings in known collection
            response = self.gen3_embedding.search_known_collection(
                collection_name=collection_name,
                embedding=self.gen3_embedding.get_random_embedding(
                    embedding_size=dimensions
                ),
                top_k=5,
                distance_metric="cosine_similarity",
            )
            assert (
                len(response.json()["embeddings"]) == 5
            ), f"Expected 5 embeddings to be returned but got {len(response.json()["embeddings"])}"
            # Search Embeddings in unknown collection
            response = self.gen3_embedding.search_unknown_collection(
                embedding=self.gen3_embedding.get_random_embedding(
                    embedding_size=dimensions
                ),
                top_k=10,
                distance_metric="inner_product",
            )
            assert (
                len(response.json()["embeddings"]) == 10
            ), f"Expected 10 embeddings to be returned but got {len(response.json()["embeddings"])}"
        except Exception as e:
            raise Exception(f"Got exception: {e}")
        finally:
            # Delete the collection
            response = self.gen3_embedding.delete_collection(
                collection_name=collection_name
            )
            assert (
                response.status_code == 204
            ), f"Expected status to be 204 but got {response.status_code}"
