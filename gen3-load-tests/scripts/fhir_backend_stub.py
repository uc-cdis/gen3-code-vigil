"""High-throughput mock upstream FHIR server generating 1000 US Core v6.1.0 compliant patients with pagination support."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse


def generate_patients(count=1000):
    """Generate US Core v6.1.0 compliant mock patients in memory."""
    print(f"Generating {count} US Core v6.1.0 compliant mock patients in memory...")
    patient_list = []

    genders = ["male", "female"]
    races = [
        {"code": "2106-3", "display": "White"},
        {"code": "2054-5", "display": "Black or African American"},
        {"code": "2028-9", "display": "Asian"},
        {"code": "1002-5", "display": "American Indian or Alaska Native"},
        {"code": "2076-8", "display": "Native Hawaiian or Other Pacific Islander"},
    ]

    for i in range(1, count + 1):
        gender = genders[i % len(genders)]
        race_info = races[i % len(races)]

        patient = {
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
                        {
                            "url": "text",
                            "valueString": race_info["display"],
                        },
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
                        {
                            "url": "text",
                            "valueString": "Not Hispanic or Latino",
                        },
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
                {
                    "system": "phone",
                    "value": f"555-01{i % 100:02d}",
                    "use": "home",
                },
                {
                    "system": "email",
                    "value": f"user{i}@example.com",
                },
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
        patient_list.append(patient)

    patients_dict = {p["id"]: p for p in patient_list}
    bundle = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(patient_list),
        "entry": [{"resource": p} for p in patient_list],
    }

    print(f"Generated {len(patients_dict)} US Core v6.1.0 patients in memory.")
    return patients_dict, bundle


PATIENTS_DICT, PATIENT_BUNDLE = generate_patients(count=1000)

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

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        # Strip prefix if proxy routes through /fhir-proxy
        if path.startswith("/fhir-proxy"):
            path = path[len("/fhir-proxy") :]

        if path == "/metadata":
            payload = CAPABILITY_STATEMENT

        elif path in ["/Patient", "/Patient/"]:
            # Default to 20 resources per page if _count is omitted
            try:
                count = int(query_params.get("_count", [20])[0])
            except ValueError:
                count = 20

            sliced_entries = PATIENT_BUNDLE["entry"][:count]
            payload = {
                "resourceType": "Bundle",
                "type": "searchset",
                "total": PATIENT_BUNDLE["total"],
                "entry": sliced_entries,
            }

        elif path.startswith("/Patient/"):
            patient_id = path.split("/Patient/")[1]
            payload = PATIENTS_DICT.get(patient_id)
            if not payload:
                self.send_error(404, f"Patient {patient_id} Not Found")
                return

        else:
            self.send_error(404, f"Not Found: {path}")
            return

        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/fhir+json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadedHTTPServer(("0.0.0.0", 8080), StubHandler)
    print("Mock US Core v6.1 FHIR server running on http://0.0.0.0:8080")
    server.serve_forever()
