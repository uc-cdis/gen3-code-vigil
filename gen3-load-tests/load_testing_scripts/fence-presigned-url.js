const { check, group, sleep } = require('k6'); // eslint-disable-line import/no-unresolved
const http = require('k6/http'); // eslint-disable-line import/no-unresolved
const { Rate } = require('k6/metrics'); // eslint-disable-line import/no-unresolved

const {
  GUIDS_LIST,
  RELEASE_VERSION,
  GEN3_HOST,
  ACCESS_TOKEN,
  VIRTUAL_USERS,
} = __ENV; // eslint-disable-line no-undef

// __ENV.GUIDS_LIST should contain either a list of GUIDs from load-test-descriptor.json
// or it should be assembled based on an indexd query (requires `indexd_record_url` to fetch DIDs)
const guids = GUIDS_LIST.split(',');

const myFailRate = new Rate('failed_requests');

export const options = {
  tags: {
    test_scenario: 'Fence - Presigned URL',
    release: RELEASE_VERSION,
    test_run_id: (new Date()).toISOString().slice(0, 16),
  },
  rps: 90000,
  stages: parseVirtualUsers(VIRTUAL_USERS),
  thresholds: {
    http_req_duration: ['avg<3000', 'p(95)<15000'],
    'failed_requests': ['rate<0.1'],
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
  const url = `https://${GEN3_HOST}/user/data/download/${guids[Math.floor(Math.random() * guids.length)]}`;
  const params = {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${ACCESS_TOKEN}`,
    },
  };
  group('Sending PreSigned URL request', () => {
    group('http get', () => {
      console.log(`Shooting requests against: ${url}`);
      const res = http.get(url, params, { tags: { name: 'PreSignedURL' } });
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
  });
}
