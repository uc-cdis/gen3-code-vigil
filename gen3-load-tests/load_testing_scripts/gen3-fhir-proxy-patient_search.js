/* eslint-disable no-mixed-operators */
/* eslint-disable no-bitwise */
/* eslint-disable one-var */
const {
  check,
  group,
  sleep,
} = require('k6'); // eslint-disable-line import/no-unresolved
const http = require('k6/http'); // eslint-disable-line import/no-unresolved
const { Rate } = require('k6/metrics'); // eslint-disable-line import/no-unresolved

// Environment Variable Fallbacks (Default: 50 VU profile)
const RELEASE_VERSION = __ENV.RELEASE_VERSION || 'local-dev';
const GEN3_HOST = __ENV.GEN3_HOST || 'localhost:8000';
const HOSTNAME_PROTOCOL = __ENV.HOSTNAME_PROTOCOL || 'http';
const BASE_PATH = __ENV.BASE_PATH || '';
const ACCESS_TOKEN = __ENV.ACCESS_TOKEN || 'local-dev-token';
//const DEFAULT_VU = '[{"duration": "10s", "target": 10}, {"duration": "30s", "target": 50}, {"duration": "30s", "target": 50}, {"duration": "10s", "target": 0}]';
const DEFAULT_VU = '[{"duration": "10s", "target": 2}, {"duration": "30s", "target": 10}, {"duration": "30s", "target": 10}, {"duration": "10s", "target": 0}]';
const VIRTUAL_USERS = __ENV.VIRTUAL_USERS || DEFAULT_VU;

const myFailRate = new Rate('failed_requests');
const PAGE_SIZE = __ENV.PAGE_SIZE || '1000';


export const options = {
  tags: {
    test_scenario: 'Gen3 FHIR Proxy - Patient Search',
    release: RELEASE_VERSION,
    test_run_id: (new Date()).toISOString().slice(0, 16),
  },
  stages: parseVirtualUsers(VIRTUAL_USERS),
  thresholds: {
    http_req_duration: ['avg<1000', 'p(95)<3000'],
    failed_requests: ['rate<0.01'],
  },
  noConnectionReuse: false,
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
      if (typeof stage.duration !== 'string' || typeof stage.target !== 'number') {
        throw new Error("Each stage must have a 'duration' (string) and 'target' (number).");
      }
    });

    return stages;
  } catch (error) {
    console.error(`Error parsing VIRTUAL_USERS: ${error.message}`);
    return [];
  }
}

export default function () {
  const url = `${HOSTNAME_PROTOCOL}://${GEN3_HOST}${BASE_PATH}/Patient?_count=${PAGE_SIZE}`;
  const params = {
    headers: {
      Accept: 'application/fhir+json',
      Authorization: `Bearer ${ACCESS_TOKEN}`,
    },
    tags: { name: 'FHIRProxy-Patient-Search' },
  };

  group('FHIR Proxy Patient Search', () => {
    group('http get /Patient', () => {
      const res = http.get(url, params);

      myFailRate.add(res.status !== 200);
      if (res.status !== 200) {
        console.log(`Request failed with status ${res.status}: ${res.body}`);
      }

      check(res, {
        'is status 200': (r) => r.status === 200,
        'is Bundle': (r) => {
          try {
            const body = JSON.parse(r.body);
            return body.resourceType === 'Bundle';
          } catch (e) {
            return false;
          }
        },
      });
    });

    group('wait 0.1s between requests', () => {
      sleep(0.1);
    });
  });
}
