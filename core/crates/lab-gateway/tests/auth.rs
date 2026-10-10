use lab_gateway::auth::{issue_token, verify_token, PairingStore, Role};

#[test]
fn pairing_code_is_single_use_and_returns_the_right_role() {
    let store = PairingStore::new();
    let code = store.issue(Role::Phone);
    assert_eq!(code.len(), 6);

    let claimed = store.claim(&code);
    assert!(matches!(claimed, Some(Role::Phone)));

    // second claim of the same code must fail — single use
    assert!(store.claim(&code).is_none());
}

#[test]
fn unknown_code_does_not_claim() {
    let store = PairingStore::new();
    assert!(store.claim("ZZZZZZ").is_none());
}

#[test]
fn token_roundtrips_and_rejects_tampering() {
    let secret = b"test-secret-32-bytes-or-whatever";
    let token = issue_token(secret, "device-1", Role::Phone, 24);

    let (device_id, role) = verify_token(secret, &token).expect("valid token");
    assert_eq!(device_id, "device-1");
    assert!(matches!(role, Role::Phone));

    // tamper with the role field
    let tampered = token.replace("phone", "desk");
    assert!(verify_token(secret, &tampered).is_none());

    // wrong secret
    assert!(verify_token(b"different-secret", &token).is_none());
}

#[test]
fn role_permissions_match_spec_5_4_4() {
    assert!(Role::Desk.can("anything"));
    assert!(Role::Phone.can("approve"));
    assert!(Role::Phone.can("kill_job"));
    assert!(!Role::Phone.can("policy_set"));
    assert!(!Role::View.can("approve"));
}
