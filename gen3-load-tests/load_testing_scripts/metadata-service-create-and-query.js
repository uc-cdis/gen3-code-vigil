const { check, group, sleep } = require('k6'); // eslint-disable-line import/no-unresolved
const http = require('k6/http'); // eslint-disable-line import/no-unresolved
const { Rate } = require('k6/metrics'); // eslint-disable-line import/no-unresolved

const {
  ACCESS_TOKEN,
  BASIC_AUTH,
  MDS_TEST_DATA,
  RELEASE_VERSION,
  GEN3_HOST,
  VIRTUAL_USERS,
} = __ENV; // eslint-disable-line no-undef

const myFailRate = new Rate('failed_requests');

export const options = {
  tags: {
    test_scenario: 'MDS - Create and query',
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

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
  });
}

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
  // console.log(`MDS_TEST_DATA_JSON: ${MDS_TEST_DATA}`);
  // const MDS_TEST_DATA_JSON = JSON.parse(MDS_TEST_DATA.slice(1, -1));
  //const sanitizedTestData = MDS_TEST_DATA.slice(1, -1).replace(/,\s*$/, '');
  const MDS_TEST_DATA_JSON = JSON.parse(MDS_TEST_DATA);
  const MDS_BASIC_AUTH = BASIC_AUTH.slice(1, -1);

  // console.log(`MDS_BASIC_AUTH.lenght: ${MDS_BASIC_AUTH.length}`);
  const mdsEndpoint = MDS_BASIC_AUTH.length > 0 ? 'mds' : 'mds-admin';
  const baseUrl = `https://${GEN3_HOST}/${mdsEndpoint}/metadata`;

  const guid1 = generateUUID();

  const url1 = `${baseUrl}/${guid1}`;

  console.log(`sending requests to: ${baseUrl}`);

  const auth = MDS_BASIC_AUTH.length > 0 ? `Basic ${MDS_BASIC_AUTH}` : `Bearer ${ACCESS_TOKEN}`;

  const params = {
    headers: {
      'Content-Type': 'application/json',
      Authorization: auth,
    },
  };
  const body1 = JSON.stringify(MDS_TEST_DATA_JSON.fictitiousRecord1);

  group('Creating and querying records', () => {
    group('create fictitiousRecord1', () => {
      console.log(`sending POST req to: ${url1}`);
      const res = http.post(url1, body1, params, { tags: { name: 'createRecord1' } });
      // console.log(`Request performed: ${new Date()}`);
      myFailRate.add(res.status !== 201);
      if (res.status !== 201) {
        console.log(`Request response: ${res.status}`);
        console.log(`Request response: ${res.body}`);
      }
      check(res, {
        'is status 201': (r) => r.status === 201,
      });
    });
    group('wait 0.3s between requests', () => {
      sleep(0.3);
    });
    group('query fictitiousRecord1', () => {
      console.log(`sending GET req to: ${baseUrl}?${MDS_TEST_DATA_JSON.filter1}`);
      const res = http.get(`${baseUrl}?${MDS_TEST_DATA_JSON.filter1}`, params, { tags: { name: 'queryRecord1' } });
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
    group('delete fictitiousRecord1', () => {
      console.log(`sending DELETE req to: ${url1}`);
      const res = http.request('DELETE', url1, {}, params, { tags: { name: 'deleteRecord1' } });
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
    group('wait 0.3s between requests', () => {
      sleep(0.3);
    });
  });
}
