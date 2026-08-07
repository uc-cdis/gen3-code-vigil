const { check, group, sleep } = require('k6'); // eslint-disable-line import/no-unresolved
const http = require('k6/http'); // eslint-disable-line import/no-unresolved

const {
  EMBEDDING_LIST,
  COLLECTION_NAME,
  TOP_K,
  DISTANCE_METRIC,
  ACCESS_TOKEN,
  GEN3_HOST,
  RELEASE_VERSION,
  VIRTUAL_USERS,
} = __ENV; // eslint-disable-line no-undef

const embeddings = JSON.parse(EMBEDDING_LIST);

export const options = {
  tags: {
    test_scenario: 'Embedding Search URL',
    release: RELEASE_VERSION,
    test_run_id: new Date().toISOString().slice(0, 16),
  },
  rps: 90000,
  stages: parseVirtualUsers(VIRTUAL_USERS),
  thresholds: {
    http_req_duration: [
      'avg<3000',
      'p(95)<15000',
    ],
    http_req_failed: [
      'rate<0.1',
    ],
  },
  noConnectionReuse: true,
};

function parseVirtualUsers(virtualUsersStr) {
  try {
    if (!virtualUsersStr) {
      throw new Error('VIRTUAL_USERS is not defined or empty.');
    }

    const stages = JSON.parse(virtualUsersStr);

    if (!Array.isArray(stages)) {
      throw new Error('VIRTUAL_USERS must be a JSON array.');
    }

    stages.forEach((stage) => {
      if (
        typeof stage.duration !== 'string' ||
        typeof stage.target !== 'number'
      ) {
        throw new Error(
          "Each stage must have a 'duration' (string) and 'target' (number)."
        );
      }
    });

    return stages;
  } catch (error) {
    console.error(`Error parsing VIRTUAL_USERS: ${error.message}`);
    return [];
  }
}

export default function () {
  const known_collection_search_url = `https://${GEN3_HOST}/ai/vectorstore/collections/${COLLECTION_NAME}/search`;
  const unknown_collection_search_url = `https://${GEN3_HOST}/ai/vectorstore/search`;

  const url = COLLECTION_NAME? known_collection_search_url : unknown_collection_search_url

  const params = {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${ACCESS_TOKEN}`,
    },
    tags: {
      name: 'Embedding',
    },
  };

  const embedding =
    JSON.parse(embeddings[Math.floor(Math.random() * embeddings.length)]);

  const payload = JSON.stringify({
    input: embedding,
    top_k: TOP_K,
    distance_metric: DISTANCE_METRIC,
  });

  group('Sending Embedding Search Request', () => {
    console.log(`Shooting requests against: ${url}`);

    const res = http.post(url, payload, params);

    if (res.status !== 200) {
      console.log(`Status: ${res.status}`);
      console.log(`Response: ${res.body}`);
    }

    check(res, {
      'status is 200': (r) => r.status === 200,
    });

    sleep(0.3);
  });
}
