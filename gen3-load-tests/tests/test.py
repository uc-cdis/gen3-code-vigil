# """
# This just aggregates all the GUIDs from all our indexed files into a single file.

# This output file simulates (or rather, skips) the process of finding data of interest and getting the GUIDs.
# """
# import glob
# import pandas as pd

# file_pattern = "./test_data/embedding/expr_output_converted_indexed.tsv"
# output_file = "./test_data/embedding/test_aggregated_guids.tsv"

# all_files = glob.glob(file_pattern)

# df_list = []
# for file in all_files:
#     # usecols ensures we don't waste memory. only load guids
#     df = pd.read_csv(file, sep="\t", usecols=["guid"])
#     df_list.append(df)

# combined_df = pd.concat(df_list, ignore_index=True)
# combined_df.to_csv(output_file, sep="\t", index=False)

# print(f"Done! Aggregated {len(all_files)} files into: {output_file}")

import time

from gen3.auth import Gen3Auth
from gen3.file import Gen3File

start = time.perf_counter()

# auth = Gen3Auth(refresh_file="FULL_PATH_TO/creds.json")
auth = Gen3Auth(refresh_file="/Users/krishnaa/.gen3/krishna_main_account.json")
gen3_file = Gen3File(auth.endpoint, auth_provider=auth)

embeddings_contents = gen3_file.get_bulk_content(
    input_file="./test_data/embedding/test_aggregated_guids.tsv"
)

end = time.perf_counter()
print(f"Total runtime: {end - start:.3f} seconds")

print(f"Got all {len(embeddings_contents)} GUIDs")

import pandas as pd

rows = []
for i, (guid, emb) in enumerate(embeddings_contents.items()):
    if i >= 100:  # sample first 100 to keep it light
        break
    rows.append(
        {
            "guid": emb.guid,
            "embedding_id": emb.embedding_id,
            "embedding_len": emb.embedding.shape[0],
            "dtype": str(emb.embedding.dtype),
            "authz": emb.authz,
            "collection_id": emb.collection_id,
            **emb.metadata,
        }
    )

df_sample = pd.DataFrame(rows)
df_sample.head()
print(df_sample)
