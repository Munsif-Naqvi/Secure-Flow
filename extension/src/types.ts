// The parts of the engine's JSON output the extension uses.
// Full format: docs/04-findings.schema.json.

export interface Finding {
	finding_match_key: string;
	problem_type: string;
	severity: string;
	finding_status: string;
	url_path: string;
	file_path: string;
	line_number: number;
	explanation: string;
}

export interface Route {
	url_path: string;
	http_methods: string[];
	file_path: string;
	line_number: number;
	protections_found: string[];
}

export interface ScanResult {
	schema_version: string;
	scan: { files_scanned: number };
	routes: Route[];
	findings: Finding[];
	summary: { suspects_found: number; problems_confirmed: number };
}
