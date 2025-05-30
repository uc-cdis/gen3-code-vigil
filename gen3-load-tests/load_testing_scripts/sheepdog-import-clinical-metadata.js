/* eslint-disable no-mixed-operators */
/* eslint-disable no-bitwise */
/* eslint-disable one-var */
const {
    check,
    group,
    sleep,
  //  fail
  } = require('k6'); // eslint-disable-line import/no-unresolved
  const http = require('k6/http'); // eslint-disable-line import/no-unresolved
  const { Rate } = require('k6/metrics'); // eslint-disable-line import/no-unresolved

  const {
  //  NUM_OF_RECORDS,
    RELEASE_VERSION,
    GEN3_HOST,
    ACCESS_TOKEN,
    VIRTUAL_USERS,
  } = __ENV; // eslint-disable-line no-undef

  const myFailRate = new Rate('failed_requests');

  export const options = {
    tags: {
      test_scenario: 'Sheepdog - Import clinical metadata',
      release: RELEASE_VERSION,
      test_run_id: (new Date()).toISOString().slice(0, 16),
    },
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
    function uuidv4() {
      return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
      });
    }

    const program = 'DEV';
    const project = 'test';
    const url = `https://${GEN3_HOST}/api/v0/submission/${program}/${project}/`;
    // console.log(`sending req to: ${url}`);
    const params = {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${ACCESS_TOKEN}`,
      },
    };
    const body = {
      eligibility: false,
      index_date: null,
      amputation_type: '6f9b1f1084',
      derived_parent_subject_id: '5c41ec1d49',
      derived_topmed_subject_id: '2fb4aae615',
      participant_id: 'study_9ad93324ff',
      '*studies': {
        submitter_id: 'study_9ad93324ff',
      },
      '*consent_codes': [],
      project_id: `${program}-${project}`,
      '*submitter_id': uuidv4(),
      transplanted_organ: '1671409e2e',
      unit_geographic_site: 'a0761970f8',
      '*type': 'subject',
      cohort_id: 'Postmortem',
      geographic_site: 'c75bf740d9', // pragma: allowlist secret
    };
    const strBody = JSON.stringify(body);
    // console.log(`debugging: ${JSON.stringify(body)}`);

    // console.log(`submitting: subject_9769d601552${__ITER}`); // eslint-disable-line no-undef

    group('Importing and exporting clinical metadata', () => {
      // TODO: Come up with a way to interrupt the load test
      // When we reach a certain number of records
      console.log(`__ITER: ${__ITER}`); // eslint-disable-line no-undef
      // if (__ITER < NUM_OF_RECORDS) { // eslint-disable-line no-undef
      group('http put', () => {
        const res = http.put(url, strBody, params, { tags: { name: 'Sheepdog-data-submission' } });
        // console.log(`Request performed: ${new Date()}`);
        myFailRate.add(res.status !== 200);
        if (res.status !== 200) {
          // console.log(`Request response: ${res.status}`);
          console.log(`Request response: ${res.body}`);
        }
        check(res, {
          'is status 200': (r) => r.status === 200,
        });
      });
      group('wait 0.1s between requests', () => {
        sleep(0.1);
      });
      // } else {
      //   fail(`${__ITER} records created on ${GEN3_HOST}`); // eslint-disable-line no-undef
      // }
    });
  }
