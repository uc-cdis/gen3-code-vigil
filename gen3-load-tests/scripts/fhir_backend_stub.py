"""High-throughput mock upstream FHIR server with lazy patient generation and pagination.

Patients are generated on-demand per request using arithmetic — no memory is allocated
at startup. TOTAL_PATIENTS can be set to any value (e.g. 5_000_000) without cost.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse

TOTAL_PATIENTS = int(os.getenv("TOTAL_PATIENTS", "5000000"))
MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", "1000"))

_GENDERS = ["male", "female"]
_RACES = [
    {"code": "2106-3", "display": "White"},
    {"code": "2054-5", "display": "Black or African American"},
    {"code": "2028-9", "display": "Asian"},
    {"code": "1002-5", "display": "American Indian or Alaska Native"},
    {"code": "2076-8", "display": "Native Hawaiian or Other Pacific Islander"},
]


def _generate_patient(i: int) -> dict:
    """Generate US Core v6.1.0 compliant patient i deterministically (1-indexed)."""
    gender = _GENDERS[i % len(_GENDERS)]
    race_info = _RACES[i % len(_RACES)]
    return {
        "resourceType": "Patient",
        "id": f"patient-{i}",
        "meta": {
            "profile": [
                "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
            ],
            "security": [{"code": "/fhir/Patient"}],
        },
        "extension": [
            {
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                "extension": [
                    {
                        "url": "ombCategory",
                        "valueCoding": {
                            "system": "urn:oid:2.16.840.1.113883.6.238",
                            "code": race_info["code"],
                            "display": race_info["display"],
                        },
                    },
                    {"url": "text", "valueString": race_info["display"]},
                ],
            },
            {
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity",
                "extension": [
                    {
                        "url": "ombCategory",
                        "valueCoding": {
                            "system": "urn:oid:2.16.840.1.113883.6.238",
                            "code": "2186-5",
                            "display": "Not Hispanic or Latino",
                        },
                    },
                    {"url": "text", "valueString": "Not Hispanic or Latino"},
                ],
            },
        ],
        "identifier": [
            {
                "use": "usual",
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": "MR",
                            "display": "Medical Record Number",
                        }
                    ]
                },
                "system": "http://hospital.smarthealthit.org",
                "value": f"MRN-{10000 + i}",
            }
        ],
        "active": True,
        "name": [
            {
                "use": "official",
                "family": f"Doe{i}",
                "given": [f"TestUser{i}"],
            }
        ],
        "telecom": [
            {"system": "phone", "value": f"555-{i % 10000:04d}", "use": "home"},
            {"system": "email", "value": f"user{i}@example.com"},
        ],
        "gender": gender,
        "birthDate": f"{1950 + (i % 50):04d}-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
        "address": [
            {
                "use": "home",
                "line": [f"{i} Main Street"],
                "city": "Chicago",
                "state": "IL",
                "postalCode": "60601",
                "country": "US",
            }
        ],
        "communication": [
            {
                "language": {
                    "coding": [
                        {
                            "system": "urn:ietf:bcp:47",
                            "code": "en",
                            "display": "English",
                        }
                    ]
                }
            }
        ],
    }


CAPABILITY_STATEMENT = {
    "resourceType": "CapabilityStatement",
    "status": "active",
    "date": "2026-01-01",
    "kind": "instance",
    "fhirVersion": "4.0.1",
    "format": ["application/fhir+json"],
    "rest": [
        {
            "mode": "server",
            "interaction": [{"code": "capabilities"}],
            "resource": [
                {
                    "type": "Patient",
                    "profile": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient",
                    "interaction": [{"code": "read"}, {"code": "search-type"}],
                    "searchParam": [
                        {"name": "_count", "type": "number"},
                        {"name": "_offset", "type": "number"},
                    ],
                }
            ],
        }
    ],
}


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class StubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def _send_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/fhir+json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        if path.startswith("/fhir-proxy"):
            path = path[len("/fhir-proxy") :]

        if path == "/metadata":
            self._send_json(CAPABILITY_STATEMENT)

        elif path in ["/Patient", "/Patient/"]:
            try:
                count = min(int(query_params.get("_count", [20])[0]), MAX_PAGE_SIZE)
            except ValueError:
                count = 20
            try:
                offset = max(int(query_params.get("_offset", [0])[0]), 0)
            except ValueError:
                offset = 0

            # Clamp to available range
            start = min(offset, TOTAL_PATIENTS)
            actual_count = min(count, TOTAL_PATIENTS - start)

            entries = [
                {"resource": _generate_patient(start + j + 1)}
                for j in range(actual_count)
            ]
            self._send_json(
                {
                    "resourceType": "Bundle",
                    "type": "searchset",
                    "total": TOTAL_PATIENTS,
                    "entry": entries,
                }
            )

        elif path.startswith("/Patient/"):
            patient_id = path.split("/Patient/")[1].rstrip("/")
            try:
                index = int(patient_id.removeprefix("patient-"))
            except ValueError:
                self.send_error(404, f"Patient {patient_id} Not Found")
                return
            if index < 1 or index > TOTAL_PATIENTS:
                self.send_error(404, f"Patient {patient_id} Not Found")
                return
            self._send_json(_generate_patient(index))

        else:
            self.send_error(404, f"Not Found: {path}")


if __name__ == "__main__":
    print(
        f"Stub configured for {TOTAL_PATIENTS:,} patients (lazy generation, max page {MAX_PAGE_SIZE})"
    )
    server = ThreadedHTTPServer(("0.0.0.0", 8080), StubHandler)
    print("Mock US Core v6.1 FHIR server running on http://0.0.0.0:8080")
    server.serve_forever()
