const { check, group, sleep } = require('k6'); // eslint-disable-line import/no-unresolved
const http = require('k6/http'); // eslint-disable-line import/no-unresolved
const { Counter, Rate } = require('k6/metrics'); // eslint-disable-line import/no-unresolved

const {
  ACCESS_TOKEN,
  BATCH_SIZES,
  BULK_ACCESS_ID,
  BULK_TEST_DURATION,
  BULK_TEST_SCENARIO_GAP_SECONDS,
  BULK_TEST_VUS,
  GEN3_HOST,
  GUIDS_LIST,
  RELEASE_VERSION,
} = __ENV; // eslint-disable-line no-undef

const guids = GUIDS_LIST.split(',').filter((guid) => guid);
const batchSizes = parseBatchSizes(BATCH_SIZES || '1,5,10,25,50,100');
const scenarioDuration = BULK_TEST_DURATION || '60s';
const scenarioGapSeconds = parseInt(BULK_TEST_SCENARIO_GAP_SECONDS || '5', 10);
const vus = parseInt(BULK_TEST_VUS || '20', 10);
const accessId = BULK_ACCESS_ID || 's3';

const failedRequests = new Rate('failed_requests');
const partialBulkResponses = new Rate('partial_bulk_responses');
const requestedObjects = new Counter('bulk_objects_requested');
const resolvedObjects = new Counter('bulk_objects_resolved');
const unresolvedObjects = new Counter('bulk_objects_unresolved');

export const options = {
  tags: {
    test_scenario: 'Fence - Bulk Presigned URL',
    release: RELEASE_VERSION,
    test_run_id: (new Date()).toISOString().slice(0, 16),
  },
  rps: 90000,
  scenarios: buildScenarios(batchSizes, scenarioDuration, scenarioGapSeconds, vus),
  thresholds: {
    http_req_duration: ['avg<5000', 'p(95)<30000'],
    failed_requests: ['rate<0.1'],
    partial_bulk_responses: ['rate<0.1'],
  },
  noConnectionReuse: true,
};

function parseBatchSizes(rawBatchSizes) {
  return rawBatchSizes
    .split(',')
    .map((size) => parseInt(size.trim(), 10))
    .filter((size) => !Number.isNaN(size) && size > 0);
}

function durationToSeconds(duration) {
  if (!duration) {
    return 60;
  }

  const value = parseInt(duration.slice(0, -1), 10);
  const unit = duration.slice(-1);
  if (Number.isNaN(value)) {
    return 60;
  }
  if (unit === 'm') {
    return value * 60;
  }
  if (unit === 'h') {
    return value * 60 * 60;
  }
  return value;
}

function buildScenarios(sizes, duration, gapSeconds, scenarioVus) {
  const scenarios = {};
  const durationSeconds = durationToSeconds(duration);

  sizes.forEach((batchSize, index) => {
    scenarios[`batch_${batchSize}`] = {
      executor: 'constant-vus',
      vus: scenarioVus,
      duration,
      startTime: `${index * (durationSeconds + gapSeconds)}s`,
      gracefulStop: '30s',
      env: {
        BATCH_SIZE: `${batchSize}`,
      },
      tags: {
        batch_size: `${batchSize}`,
      },
    };
  });

  return scenarios;
}

function bulkAccessPayload(batchSize) {
  const startIndex = Math.floor(Math.random() * guids.length);
  const entries = [];

  for (let offset = 0; offset < batchSize; offset += 1) {
    const guid = guids[(startIndex + offset) % guids.length];
    entries.push({
      bulk_object_id: guid,
      bulk_access_ids: [accessId],
    });
  }

  return entries;
}

function parseResponseBody(response) {
  try {
    return response.json();
  } catch (error) {
    console.log(`Could not parse bulk presigned URL response JSON: ${error.message}`);
    return {};
  }
}

export default function () {
  const batchSize = parseInt(__ENV.BATCH_SIZE || '1', 10); // eslint-disable-line no-undef
  const url = `https://${GEN3_HOST}/ga4gh/drs/v1/objects/access`;
  const bulkObjectAccessIds = bulkAccessPayload(batchSize);
  const payload = JSON.stringify({ bulk_object_access_ids: bulkObjectAccessIds });
  const params = {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${ACCESS_TOKEN}`,
    },
    tags: {
      name: 'BulkPreSignedURL',
      batch_size: `${batchSize}`,
    },
  };

  group('Sending bulk PreSigned URL request', () => {
    const res = http.post(url, payload, params);
    const body = parseResponseBody(res);
    const summary = body.summary || {};
    const requested = summary.requested || batchSize;
    const resolved = summary.resolved || 0;
    const unresolved = summary.unresolved || Math.max(requested - resolved, 0);

    requestedObjects.add(requested, { batch_size: `${batchSize}` });
    resolvedObjects.add(resolved, { batch_size: `${batchSize}` });
    unresolvedObjects.add(unresolved, { batch_size: `${batchSize}` });
    failedRequests.add(res.status !== 200, { batch_size: `${batchSize}` });
    partialBulkResponses.add(resolved < requested, { batch_size: `${batchSize}` });

    if (res.status !== 200 || resolved < requested) {
      console.log(`Bulk presigned URL response status=${res.status} batch_size=${batchSize} requested=${requested} resolved=${resolved} unresolved=${unresolved}`);
      console.log(`Request response: ${res.body}`);
    }

    check(res, {
      'is status 200': (r) => r.status === 200,
      'resolved requested objects': () => resolved === requested,
    });

    sleep(0.3);
  });
}
