const { check, group, sleep } = require('k6'); // eslint-disable-line import/no-unresolved
const http = require('k6/http'); // eslint-disable-line import/no-unresolved
const { Rate } = require('k6/metrics'); // eslint-disable-line import/no-unresolved

// declare mutable ACCESS_TOKEN
let { ACCESS_TOKEN } = __ENV; // eslint-disable-line no-undef

const {
  NUM_OF_JSONS,
  API_KEY,
  RELEASE_VERSION,
  GEN3_HOST,
  VIRTUAL_USERS,
  GUID1,
} = __ENV; // eslint-disable-line no-undef

const myFailRate = new Rate('failed_requests');
const numOfJsons = NUM_OF_JSONS;

// load all JSONs into memory
const jsons = [];
for (let i = 1; i <= numOfJsons; i += 1) {
  const j = open(`../tmp/${i}.json`); // eslint-disable-line no-restricted-globals
  jsons.push(j);
}

export const options = {
  tags: {
    test_scenario: 'MDS - Filter large database',
    release: RELEASE_VERSION,
    test_run_id: (new Date()).toISOString().slice(0, 16),
  },
  stages: parseVirtualUsers(VIRTUAL_USERS),
  thresholds: {
    http_req_duration: ['avg<1000', 'p(95)<2000'],
    'failed_requests': ['rate<0.05'],
  },
  noConnectionReuse: true,
};

function parseVirtualUsers(virtualUsersStr) {
  try {
    if (!virtualUsersStr) {
      throw new Error("VIRTUAL_USERS is not defined or empty.");
    }
    const stages = JSON.parse(virtualUsersStr);

    // Validate that the stages array is well-formed
    if (!Array.isArray(stages)) {
      throw new Error("VIRTUAL_USERS must be a JSON array.");
    }
    stages.forEach((stage) => {
      if (typeof stage.duration !== 'string' || typeof stage.target !== 'number') {
        throw new Error("Each stage must have a 'duration' (string) and 'target' (number).");
      }
    });

    return stages;
  } catch (error) {
    console.error(`Error parsing VIRTUAL_USERS: ${error.message}`);
    // Provide a fallback option, you might want to exit the process instead
    return [];
  }
}

export default function () {
  const apiKey = API_KEY.slice(1, -1);
  const accessToken = ACCESS_TOKEN;

  const jsonIndex = __ITER % numOfJsons; // eslint-disable-line no-undef
  console.log(`jsonIndex: ${jsonIndex}`);

  const baseUrl = `https://${GEN3_HOST}/mds-admin/metadata`;

  // obtain random guid
  const url = `${baseUrl}/${GUID1}`;

  const params = {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
  };

  const jsonData = jsons[jsonIndex];
  // console.log(`data: ${jsonData}`);

  group('Populating the MDS database', () => {
    if (__ITER < numOfJsons) { // eslint-disable-line no-undef
      group('create record in MDS', () => {
        console.log(`sending POST req to: ${url}`);
        const res = http.post(url, jsonData, params, { tags: { name: 'createRecord1' } });

        // If the ACCESS_TOKEN expires, renew it with the apiKey
        if (res.status === 401) {
          console.log('renewing access token!!!');
          console.log(`Request response: ${res.status}`);
          console.log(`Request response: ${res.body}`);

          const tokenRenewalUrl = `https://${GEN3_HOST}/user/credentials/cdis/access_token`;

          const tokenRenewalParams = {
            headers: {
              'Content-Type': 'application/json',
              accept: 'application/json',
            },
          };
          const tokenRenewalData = JSON.stringify({
            api_key: apiKey,
          });
          const renewalRes = http.post(tokenRenewalUrl, tokenRenewalData, tokenRenewalParams, { tags: { name: 'renewingToken1' } });
          ACCESS_TOKEN = JSON.parse(renewalRes.body).access_token;

          console.log(`NEW ACCESS TOKEN!: ${ACCESS_TOKEN}`);
        } else {
          // console.log(`Request performed: ${new Date()}`);
          console.log(`Request response: ${res.status}`);
          myFailRate.add(res.status !== 201);
          if (res.status !== 201) {
            console.log(`Request response: ${res.status}`);
            console.log(`Request response: ${res.body}`);
          }
          check(res, {
            'is status 201': (r) => r.status === 201,
          });
        }
      });
      group('wait 0.3s between requests', () => {
        sleep(0.3);
      });
    } else {
      group('query large database', () => {
        console.log(`sending GET req to: ${baseUrl}?dbgap.consent_code=2`);
        const res = http.get(`${baseUrl}?dbgap.consent_code=2`, params, { tags: { name: 'query large db' } });
        // console.log(`Request performed: ${new Date()}`);
        myFailRate.add(res.status !== 200);
        if (res.status !== 200) {
          console.log(`Request response: ${res.status}`);
          console.log(`Request response: ${res.body}`);
        }
        check(res, {
          'is status 200': (r) => r.status === 200,
        });
      });
      group('wait 0.3s between requests', () => {
        sleep(0.3);
      });
    }
  });
}
