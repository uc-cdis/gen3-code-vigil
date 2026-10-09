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

// Environment Variable Fallbacks (Default: 10 VU ramp profile for local runs)
const RELEASE_VERSION = __ENV.RELEASE_VERSION || 'local-dev';
const GEN3_HOST = __ENV.GEN3_HOST || 'localhost:8000';
const HOSTNAME_PROTOCOL = __ENV.HOSTNAME_PROTOCOL || 'http';
const BASE_PATH = __ENV.BASE_PATH || '';
const ACCESS_TOKEN = __ENV.ACCESS_TOKEN || 'local-dev-token';
const DEFAULT_VU = '[{"duration": "10s", "target": 2}, {"duration": "30s", "target": 10}, {"duration": "30s", "target": 10}, {"duration": "10s", "target": 0}]';
const VIRTUAL_USERS = __ENV.VIRTUAL_USERS || DEFAULT_VU;

// Total patients the backend claims — used to randomize page offsets so VUs
// do not all hammer the same cached first page.
const TOTAL_PATIENTS = parseInt(__ENV.TOTAL_PATIENTS || '5000000', 10);
// Default to 1000 to stress-test the proxy's per-entry auth-filtering loop under load.
// Override with PAGE_SIZE=20 to simulate interactive FHIR app traffic instead.
const PAGE_SIZE = parseInt(__ENV.PAGE_SIZE || '1000', 10);

const myFailRate = new Rate('failed_requests');

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

/**
 * Pick a random page offset within the total patient population so concurrent
 * VUs spread across the dataset rather than all reading the first page.
 */
function randomOffset() {
  const totalPages = Math.max(1, Math.floor(TOTAL_PATIENTS / PAGE_SIZE));
  return Math.floor(Math.random() * totalPages) * PAGE_SIZE;
}

export default function () {
  const baseUrl = `${HOSTNAME_PROTOCOL}://${GEN3_HOST}${BASE_PATH}`;
  const params = {
    headers: {
      Accept: 'application/fhir+json',
      Authorization: `Bearer ${ACCESS_TOKEN}`,
    },
  };

  group('FHIR Proxy Patient Search', () => {
    const offset = randomOffset();
    const searchUrl = `${baseUrl}/Patient?_count=${PAGE_SIZE}&_offset=${offset}`;

    let patientId = null;

    group('GET /Patient (randomized page)', () => {
      const res = http.get(searchUrl, { ...params, tags: { name: 'FHIRProxy-Patient-Search' } });

      myFailRate.add(res.status !== 200);
      if (res.status !== 200) {
        console.log(`Patient search failed [offset=${offset}] status=${res.status}: ${res.body}`);
      }

      const ok = check(res, {
        'is status 200': (r) => r.status === 200,
        'is Bundle': (r) => {
          try {
            const body = JSON.parse(r.body);
            return body.resourceType === 'Bundle';
          } catch (e) {
            return false;
          }
        },
        'has entries': (r) => {
          try {
            const body = JSON.parse(r.body);
            return Array.isArray(body.entry) && body.entry.length > 0;
          } catch (e) {
            return false;
          }
        },
      });

      // Capture a patient ID to exercise the read endpoint below
      if (ok) {
        try {
          const body = JSON.parse(res.body);
          if (body.entry && body.entry.length > 0) {
            patientId = body.entry[0].resource.id;
          }
        } catch (e) { /* ignore */ }
      }
    });

    sleep(0.1);

    // Simulate the realistic follow-up: a user drills into a specific patient
    // after finding them in search results.
    if (patientId) {
      group('GET /Patient/{id} (individual read)', () => {
        const readUrl = `${baseUrl}/Patient/${patientId}`;
        const res = http.get(readUrl, { ...params, tags: { name: 'FHIRProxy-Patient-Read' } });

        myFailRate.add(res.status !== 200);
        if (res.status !== 200) {
          console.log(`Patient read failed [id=${patientId}] status=${res.status}: ${res.body}`);
        }

        check(res, {
          'read: is status 200': (r) => r.status === 200,
          'read: is Patient': (r) => {
            try {
              const body = JSON.parse(r.body);
              return body.resourceType === 'Patient';
            } catch (e) {
              return false;
            }
          },
        });
      });

      sleep(0.1);
    }
  });
}
