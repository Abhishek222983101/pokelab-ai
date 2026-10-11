//! Cross-language contract validation (P0.6): the SAME fixture files in
//! contracts/fixtures/ parse successfully as lab_store::Event here, as
//! they already do as pydantic's Event in Python
//! (contracts/tests/test_fixtures.py). One fixture, two languages.

use std::path::Path;

fn fixtures_dir() -> std::path::PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../contracts/fixtures")
}

fn load_fixture(name: &str) -> lab_store::Event {
    let path = fixtures_dir().join(name);
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("reading fixture {path:?}: {e}"));
    serde_json::from_str(&text).unwrap_or_else(|e| panic!("parsing fixture {name}: {e}"))
}

#[test]
fn job_metric_fixture_parses_as_event() {
    let event = load_fixture("job_metric_event.json");
    assert_eq!(event.kind, "job.metric");
    assert_eq!(event.payload["job_id"], "job-1");
}

#[test]
fn job_done_fixture_parses_as_event() {
    let event = load_fixture("job_done_event.json");
    assert_eq!(event.kind, "job.done");
    assert_eq!(event.payload["status"], "ok");
}

#[test]
fn agent_spawned_fixture_parses_as_event() {
    let event = load_fixture("agent_spawned_event.json");
    assert_eq!(event.kind, "agent.spawned");
    assert_eq!(event.payload["capability"], "analyze_3d");
}
