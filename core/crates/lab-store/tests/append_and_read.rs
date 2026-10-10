use lab_store::{NewEvent, Store};
use serde_json::json;
use tempfile::tempdir;

fn new_event(kind: &str, project: Option<&str>, causation: Option<i64>) -> NewEvent {
    NewEvent {
        kind: kind.to_string(),
        v: 1,
        project: project.map(str::to_string),
        actor: "test".to_string(),
        corr: None,
        causation,
        payload: json!({"ok": true}),
        display: None,
    }
}

#[test]
fn append_assigns_increasing_seq() {
    let dir = tempdir().unwrap();
    let store = Store::open(dir.path().join("lab.db")).unwrap();

    let e1 = store.append(new_event("agent.spawned", Some("p1"), None)).unwrap();
    let e2 = store.append(new_event("agent.evolved", Some("p1"), Some(e1.seq))).unwrap();

    assert_eq!(e1.seq, 1);
    assert_eq!(e2.seq, 2);
    assert_eq!(e2.causation, Some(1));
    assert!(!e1.ts.is_empty());
}

#[test]
fn since_filters_by_project_and_seq() {
    let dir = tempdir().unwrap();
    let store = Store::open(dir.path().join("lab.db")).unwrap();

    store.append(new_event("x", Some("p1"), None)).unwrap();
    let in_p2 = store.append(new_event("x", Some("p2"), None)).unwrap();
    store.append(new_event("x", Some("p1"), None)).unwrap();

    let all = store.since(0, None).unwrap();
    assert_eq!(all.len(), 3);

    let p2_only = store.since(0, Some("p2")).unwrap();
    assert_eq!(p2_only.len(), 1);
    assert_eq!(p2_only[0].seq, in_p2.seq);

    let after_first = store.since(1, None).unwrap();
    assert_eq!(after_first.len(), 2);
}

#[test]
fn latest_seq_tracks_appends() {
    let dir = tempdir().unwrap();
    let store = Store::open(dir.path().join("lab.db")).unwrap();
    assert_eq!(store.latest_seq().unwrap(), 0);
    store.append(new_event("x", None, None)).unwrap();
    assert_eq!(store.latest_seq().unwrap(), 1);
}

#[test]
fn snapshot_roundtrip() {
    let dir = tempdir().unwrap();
    let store = Store::open(dir.path().join("lab.db")).unwrap();
    store.append(new_event("x", None, None)).unwrap();
    store.save_snapshot("state", 1, &json!({"n": 42})).unwrap();
    let (seq, payload) = store.load_snapshot("state").unwrap().unwrap();
    assert_eq!(seq, 1);
    assert_eq!(payload["n"], 42);
}

#[test]
fn reopening_existing_db_does_not_lose_events() {
    let dir = tempdir().unwrap();
    let path = dir.path().join("lab.db");
    {
        let store = Store::open(&path).unwrap();
        store.append(new_event("x", None, None)).unwrap();
    }
    let store2 = Store::open(&path).unwrap();
    assert_eq!(store2.latest_seq().unwrap(), 1);
    let events = store2.since(0, None).unwrap();
    assert_eq!(events.len(), 1);
}
